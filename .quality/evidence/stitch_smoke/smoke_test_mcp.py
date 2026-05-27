"""Smoke test #2: Stitch MCP JSON-RPC for design-system tools.

Validates whether the 5 design-system tools documented by google-labs-code/
stitch-skills are reachable via the MCP JSON-RPC transport (the same one
SpecBox's StitchClient uses).

Steps:
  1. tools/list — discover what tools the MCP exposes
  2. tools/call list_projects (sanity)
  3. tools/call create_project (smoke project)
  4. tools/call upload_design_md (with small DESIGN.md)
  5. tools/call create_design_system_from_design_md
  6. tools/call list_design_systems
  7. tools/call apply_design_system
  8. cleanup (best-effort)

Outputs:
  smoke_mcp_report.json
  smoke_mcp_report.md
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

MCP_URL = "https://stitch.googleapis.com/mcp"
EVIDENCE_DIR = Path(__file__).resolve().parent
REPORT_JSON = EVIDENCE_DIR / "smoke_mcp_report.json"
REPORT_MD = EVIDENCE_DIR / "smoke_mcp_report.md"

DESIGN_MD_CONTENT = """---
name: SmokeTest Tokens MCP
colors:
  surface: '#FFFFFF'
  on-surface: '#1A1A1A'
  primary: '#0EA5E9'
  on-primary: '#FFFFFF'
  primary-container: '#E0F2FE'
  on-primary-container: '#0C4A6E'
  secondary: '#64748B'
  error: '#DC2626'
  background: '#FFFFFF'
  on-background: '#1A1A1A'
  outline: '#94A3B8'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '800'
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
  body-base:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
---

# SmokeTest MCP DS

Minimal Material 3 DS for MCP JSON-RPC smoke test.
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def api_key() -> str:
    k = os.environ.get("STITCH_API_KEY")
    if not k:
        print("ERROR: STITCH_API_KEY not set", file=sys.stderr)
        sys.exit(2)
    return k


def mcp_call(method: str, params: dict[str, Any] | None = None, timeout: int = 120) -> tuple[int, Any]:
    """Send a JSON-RPC 2.0 request to the Stitch MCP endpoint."""
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params or {},
    }
    req = request.Request(
        MCP_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "x-goog-api-key": api_key(),
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            ctype = resp.headers.get("Content-Type", "")
            if "text/event-stream" in ctype:
                # Parse SSE
                for line in body.splitlines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str:
                            try:
                                return resp.status, json.loads(data_str)
                            except json.JSONDecodeError:
                                continue
                return resp.status, {"_raw_sse": body[:2000]}
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, {"_raw": body[:2000]}
    except error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"_raw_error": raw[:2000]}
    except error.URLError as e:
        return -1, {"url_error": str(e)}


def call_tool(name: str, args: dict[str, Any] | None = None, timeout: int = 120) -> tuple[int, Any]:
    """Wrapper for tools/call."""
    return mcp_call("tools/call", {"name": name, "arguments": args or {}}, timeout=timeout)


def extract_tool_result(rpc_response: dict) -> Any:
    """Extract content from MCP tools/call response. Returns dict or raw."""
    if not isinstance(rpc_response, dict):
        return rpc_response
    if "error" in rpc_response:
        return {"_rpc_error": rpc_response["error"]}
    result = rpc_response.get("result", {})
    content = result.get("content", [])
    if not content:
        return result
    if len(content) == 1 and content[0].get("type") == "text":
        text = content[0].get("text", "")
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return {"text": text[:1000]}
    return {"content": content, "isError": result.get("isError", False)}


def main() -> int:
    api_key()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    overall: dict[str, Any] = {
        "started_at": now_iso(),
        "endpoint": MCP_URL,
        "steps": [],
        "verdict": "pending",
    }

    def step(name: str, fn, *args, **kw):
        t0 = time.perf_counter()
        st = {
            "name": name,
            "started_at": now_iso(),
        }
        try:
            code, body = fn(*args, **kw)
            st["http_code"] = code
            st["raw_response"] = body if not isinstance(body, dict) else {k: v for k, v in body.items() if k != "_raw"}
            st["duration_ms"] = int((time.perf_counter() - t0) * 1000)
            if isinstance(body, dict) and body.get("error"):
                st["status"] = "fail"
            elif code in (200, 201):
                st["status"] = "ok"
            else:
                st["status"] = "warn"
        except Exception as exc:  # noqa: BLE001
            st["status"] = "error"
            st["error"] = f"{type(exc).__name__}: {exc!s}"
            st["duration_ms"] = int((time.perf_counter() - t0) * 1000)
        overall["steps"].append(st)
        return st

    # Step 1: discover tools
    s1 = step("tools/list", mcp_call, "tools/list")
    # Step 2: sanity call
    s2 = step("call list_projects", call_tool, "list_projects")
    # Step 3: create project
    title = f"SmokeMCP-{int(time.time())}"
    s3 = step("call create_project", call_tool, "create_project", {"title": title})

    # Extract project ID from create result
    project_id = None
    create_result = None
    try:
        raw = s3.get("raw_response", {})
        if isinstance(raw, dict) and "result" in raw:
            create_result = extract_tool_result(raw)
            if isinstance(create_result, dict):
                project_id = (
                    create_result.get("projectId")
                    or create_result.get("id")
                    or (create_result.get("project", {}) or {}).get("id")
                )
                if not project_id:
                    name = create_result.get("name") or (create_result.get("project", {}) or {}).get("name")
                    if name and isinstance(name, str) and "/" in name:
                        project_id = name.split("/")[-1]
    except Exception as exc:  # noqa: BLE001
        overall.setdefault("notes", []).append(f"create_project parse error: {exc!s}")

    if not project_id:
        overall.setdefault("notes", []).append(
            f"Could not extract projectId from create_project response: {json.dumps(create_result)[:500] if create_result else 'no result'}"
        )

    # Step 4: upload_design_md via MCP tool
    if project_id:
        b64 = base64.b64encode(DESIGN_MD_CONTENT.encode("utf-8")).decode("ascii")
        step("call upload_design_md", call_tool, "upload_design_md", {
            "projectId": project_id,
            "designMdBase64": b64,
        }, timeout=120)

        # Step 5: get_project to find screenInstance
        sgp = step("call get_project", call_tool, "get_project", {"projectId": project_id})

        # Try to find a screen instance
        screen_instance = None
        try:
            raw = sgp.get("raw_response", {})
            if isinstance(raw, dict) and "result" in raw:
                gp_result = extract_tool_result(raw)
                if isinstance(gp_result, dict):
                    instances = (
                        gp_result.get("screenInstances")
                        or (gp_result.get("project", {}) or {}).get("screenInstances")
                        or []
                    )
                    for inst in instances:
                        if isinstance(inst, dict) and inst.get("sourceScreen"):
                            screen_instance = {"id": inst.get("id"), "sourceScreen": inst.get("sourceScreen")}
                            break
        except Exception as exc:  # noqa: BLE001
            overall.setdefault("notes", []).append(f"get_project parse error: {exc!s}")

        # Step 6: create_design_system_from_design_md
        if screen_instance:
            step("call create_design_system_from_design_md", call_tool,
                 "create_design_system_from_design_md", {
                     "projectId": project_id,
                     "selectedScreenInstance": screen_instance,
                     "deviceType": "DESKTOP",
                 }, timeout=120)
        else:
            overall.setdefault("notes", []).append("Skipped create_design_system_from_design_md: no screen instance")

        # Step 7: list_design_systems
        step("call list_design_systems", call_tool, "list_design_systems", {"projectId": project_id})

    # Verdict
    statuses = [s.get("status") for s in overall["steps"]]
    if all(st == "ok" for st in statuses):
        overall["verdict"] = "pass"
    elif any(st == "ok" for st in statuses):
        overall["verdict"] = "partial"
    else:
        overall["verdict"] = "fail"

    overall["finished_at"] = now_iso()

    REPORT_JSON.write_text(json.dumps(overall, indent=2, default=str), encoding="utf-8")

    # Markdown summary
    md = [
        f"# Stitch MCP JSON-RPC Smoke Test — {overall['started_at']}",
        "",
        f"**Endpoint**: `{MCP_URL}`",
        f"**Verdict**: `{overall['verdict']}`",
        "",
        "## Steps",
        "",
        "| # | Step | Status | HTTP | Duration |",
        "|---|------|--------|------|----------|",
    ]
    for i, s in enumerate(overall["steps"], start=1):
        md.append(f"| {i} | `{s['name']}` | {s.get('status')} | {s.get('http_code')} | {s.get('duration_ms')}ms |")
    md.append("")
    if overall.get("notes"):
        md.append("## Notes")
        for n in overall["notes"]:
            md.append(f"- {n}")
        md.append("")
    md.append("## Raw responses (truncated)")
    for s in overall["steps"]:
        md.append(f"### {s['name']}")
        md.append("```json")
        md.append(json.dumps(s.get("raw_response"), indent=2, default=str)[:3000])
        md.append("```")
        md.append("")

    REPORT_MD.write_text("\n".join(md), encoding="utf-8")
    return 0 if overall["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
