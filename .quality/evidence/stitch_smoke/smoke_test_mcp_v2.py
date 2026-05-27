"""Smoke test #3 (refined): full design-system chain via MCP JSON-RPC.

This iteration fixes parsing bugs in v1 and runs the full 7-step canonical
flow against Stitch MCP. Inputs use the EXACT enum values and field shapes
that the server returned in tools/list.

Key insights from smoke v1:
- get_project requires "name" (full path like "projects/{id}"), NOT just "projectId"
- create_design_system_from_design_md requires the screenInstance after upload
- The MCP returns content[0].text as a JSON string that needs json.loads

Outputs:
  smoke_mcp_v2_report.json
  smoke_mcp_v2_report.md
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
REPORT_JSON = EVIDENCE_DIR / "smoke_mcp_v2_report.json"
REPORT_MD = EVIDENCE_DIR / "smoke_mcp_v2_report.md"

DESIGN_MD_CONTENT = """---
name: SmokeTest M3 Tokens
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

# SmokeTest MCP DS v2

Material 3 design system for the SpecBox Stitch native chain smoke test (v2).
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def api_key() -> str:
    k = os.environ.get("STITCH_API_KEY")
    if not k:
        print("ERROR: STITCH_API_KEY not set", file=sys.stderr)
        sys.exit(2)
    return k


def mcp_call(method: str, params: dict[str, Any] | None = None, timeout: int = 180) -> tuple[int, dict]:
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


def call_tool(name: str, args: dict[str, Any] | None = None, timeout: int = 180) -> tuple[int, dict, dict]:
    """Returns (http_code, raw_rpc_response, parsed_tool_result)."""
    code, rpc = mcp_call("tools/call", {"name": name, "arguments": args or {}}, timeout=timeout)
    parsed: dict = {}
    if isinstance(rpc, dict):
        if "error" in rpc:
            parsed = {"_tool_error": rpc["error"]}
        else:
            result = rpc.get("result", {})
            content = result.get("content", [])
            is_error = result.get("isError", False)
            if content and isinstance(content, list) and len(content) >= 1:
                text = content[0].get("text", "")
                try:
                    parsed = json.loads(text)
                    if is_error:
                        parsed["_isError"] = True
                except (json.JSONDecodeError, TypeError):
                    parsed = {"_text": text[:1500], "_isError": is_error}
            else:
                parsed = {"_empty_content": True, "_isError": is_error}
    return code, rpc, parsed


class Step:
    def __init__(self, name: str):
        self.name = name
        self.started_at = now_iso()
        self.duration_ms: int | None = None
        self.status = "pending"
        self.http_code: int | None = None
        self.parsed: Any = None
        self.error: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "http_code": self.http_code,
            "parsed": self.parsed,
            "error": self.error,
        }


def run(steps: list, name: str, fn, *args, **kwargs) -> Any:
    s = Step(name)
    t0 = time.perf_counter()
    try:
        result = fn(s, *args, **kwargs)
        s.duration_ms = int((time.perf_counter() - t0) * 1000)
        if s.status == "pending":
            s.status = "ok"
        steps.append(s.to_dict())
        return result
    except Exception as exc:  # noqa: BLE001
        s.duration_ms = int((time.perf_counter() - t0) * 1000)
        s.status = "error"
        s.error = f"{type(exc).__name__}: {exc!s}"
        steps.append(s.to_dict())
        return None


def main() -> int:
    api_key()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    steps: list[dict] = []
    overall: dict[str, Any] = {"started_at": now_iso(), "endpoint": MCP_URL}

    # Step 1: create project
    def _create_project(s: Step):
        title = f"SmokeMCPv2-{int(time.time())}"
        code, _, parsed = call_tool("create_project", {"title": title})
        s.http_code = code
        s.parsed = parsed
        if parsed.get("_isError") or parsed.get("_tool_error") or parsed.get("_empty_content"):
            s.status = "fail"
            return None
        project_name = parsed.get("name") or (parsed.get("project", {}) or {}).get("name")
        project_id = project_name.split("/")[-1] if project_name and "/" in project_name else None
        return {"project_name": project_name, "project_id": project_id, "title": title}

    proj = run(steps, "create_project", _create_project)
    if not proj or not proj.get("project_id"):
        _finalize(steps, overall, fail_reason="cannot_get_project_id")
        return 10
    project_id = proj["project_id"]
    project_name = proj["project_name"]

    # Step 2: upload_design_md (MCP tool, small payload <5KB)
    def _upload(s: Step):
        b64 = base64.b64encode(DESIGN_MD_CONTENT.encode("utf-8")).decode("ascii")
        code, _, parsed = call_tool("upload_design_md", {
            "projectId": project_id,
            "designMdBase64": b64,
        }, timeout=180)
        s.http_code = code
        s.parsed = parsed
        if parsed.get("_isError") or parsed.get("_tool_error"):
            s.status = "fail"
        return parsed

    upload_result = run(steps, "upload_design_md", _upload)

    # Step 3: get_project — try with "name" (full path), not "projectId"
    def _get_project_by_name(s: Step):
        code, _, parsed = call_tool("get_project", {"name": project_name})
        s.http_code = code
        s.parsed = parsed
        if parsed.get("_isError") or parsed.get("_tool_error"):
            s.status = "fail"
        return parsed

    project_body = run(steps, "get_project_by_name", _get_project_by_name)

    # Find a DOCUMENT screen instance to anchor DS creation.
    # Prefer the most recently uploaded markdown screen.
    screen_instance = None
    if isinstance(project_body, dict):
        instances = project_body.get("screenInstances") or (project_body.get("project", {}) or {}).get("screenInstances") or []
        for inst in reversed(instances):  # most recent last
            if isinstance(inst, dict) and inst.get("sourceScreen"):
                screen_instance = {
                    "id": inst.get("id"),
                    "sourceScreen": inst.get("sourceScreen"),
                }
                break

    overall["screen_instance_found"] = screen_instance is not None
    overall["screen_instance"] = screen_instance

    # Step 4: list_design_systems (pre)
    def _list_ds_pre(s: Step):
        code, _, parsed = call_tool("list_design_systems", {"projectId": project_id})
        s.http_code = code
        s.parsed = parsed
        if parsed.get("_isError") or parsed.get("_tool_error"):
            s.status = "fail"
        return parsed

    run(steps, "list_design_systems_pre", _list_ds_pre)

    # Step 5: create_design_system_from_design_md
    if screen_instance:
        def _create_ds(s: Step):
            code, _, parsed = call_tool("create_design_system_from_design_md", {
                "projectId": project_id,
                "selectedScreenInstance": screen_instance,
                "deviceType": "DESKTOP",
            }, timeout=180)
            s.http_code = code
            s.parsed = parsed
            if parsed.get("_isError") or parsed.get("_tool_error"):
                s.status = "fail"
            return parsed

        ds_result = run(steps, "create_design_system_from_design_md", _create_ds)
    else:
        overall.setdefault("notes", []).append("step create_design_system_from_design_md skipped: no screen instance")
        ds_result = None

    # Step 6: list_design_systems (post)
    def _list_ds_post(s: Step):
        code, _, parsed = call_tool("list_design_systems", {"projectId": project_id})
        s.http_code = code
        s.parsed = parsed
        if parsed.get("_isError") or parsed.get("_tool_error"):
            s.status = "fail"
        return parsed

    list_post = run(steps, "list_design_systems_post", _list_ds_post)

    # Try to extract assetId from list_post
    asset_id = None
    if isinstance(list_post, dict):
        ds_list = list_post.get("designSystems", [])
        if ds_list and isinstance(ds_list, list):
            first = ds_list[0]
            if isinstance(first, dict):
                name = first.get("name", "")
                if name.startswith("assets/"):
                    asset_id = name.split("/")[-1]
                else:
                    asset_id = first.get("id") or first.get("assetId")
    overall["asset_id"] = asset_id

    # Step 7: update_design_system (smoke a token change)
    if asset_id:
        def _update_ds(s: Step):
            code, _, parsed = call_tool("update_design_system", {
                "name": f"assets/{asset_id}",
                "projectId": project_id,
                "designSystem": {
                    "displayName": "SmokeTest Update",
                    "theme": {
                        "colorMode": "LIGHT",
                        "headlineFont": "INTER",
                        "bodyFont": "INTER",
                        "roundness": "ROUND_EIGHT",
                        "customColor": "#0EA5E9",
                    },
                },
            }, timeout=120)
            s.http_code = code
            s.parsed = parsed
            if parsed.get("_isError") or parsed.get("_tool_error"):
                s.status = "fail"
            return parsed

        run(steps, "update_design_system", _update_ds)

        # Step 8: apply_design_system to the DS instance itself (smoke)
        if screen_instance:
            def _apply_ds(s: Step):
                code, _, parsed = call_tool("apply_design_system", {
                    "projectId": project_id,
                    "assetId": asset_id,
                    "selectedScreenInstances": [screen_instance],
                }, timeout=180)
                s.http_code = code
                s.parsed = parsed
                if parsed.get("_isError") or parsed.get("_tool_error"):
                    s.status = "fail"
                return parsed

            run(steps, "apply_design_system", _apply_ds)
    else:
        overall.setdefault("notes", []).append("update_design_system & apply_design_system skipped: no assetId resolved")

    _finalize(steps, overall)
    return 0


def _finalize(steps: list[dict], overall: dict, fail_reason: str | None = None) -> None:
    overall["finished_at"] = now_iso()
    overall["steps"] = steps
    statuses = [s.get("status") for s in steps]
    if fail_reason:
        overall["verdict"] = f"fail:{fail_reason}"
    elif statuses and all(st == "ok" for st in statuses):
        overall["verdict"] = "pass"
    elif any(st == "fail" or st == "error" for st in statuses):
        overall["verdict"] = "partial_or_fail"
    else:
        overall["verdict"] = "unknown"

    REPORT_JSON.write_text(json.dumps(overall, indent=2, default=str), encoding="utf-8")

    md = [
        f"# Stitch MCP JSON-RPC Smoke Test v2 — {overall['started_at']}",
        "",
        f"**Endpoint**: `{MCP_URL}`",
        f"**Verdict**: `{overall['verdict']}`",
        f"**Screen instance found**: {overall.get('screen_instance_found')}",
        f"**Asset ID resolved**: `{overall.get('asset_id')}`",
        "",
        "## Steps",
        "",
        "| # | Step | Status | HTTP | Duration | Notes |",
        "|---|------|--------|------|----------|-------|",
    ]
    for i, s in enumerate(steps, start=1):
        parsed = s.get("parsed") or {}
        keys = list(parsed.keys())[:6] if isinstance(parsed, dict) else "?"
        err = s.get("error") or (parsed.get("_tool_error", {}).get("message") if isinstance(parsed, dict) else "")
        notes = err or f"keys={keys}"
        md.append(f"| {i} | `{s['name']}` | {s['status']} | {s['http_code']} | {s['duration_ms']}ms | {notes} |")
    md.append("")
    if overall.get("notes"):
        md.append("## Notes")
        for n in overall["notes"]:
            md.append(f"- {n}")
        md.append("")
    md.append("## Parsed responses (truncated)")
    for s in steps:
        md.append(f"### {s['name']}")
        md.append("```json")
        md.append(json.dumps(s.get("parsed"), indent=2, default=str)[:2500])
        md.append("```")
        md.append("")
    REPORT_MD.write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
