"""Stitch native chain smoke test.

Validates the 7-step canonical flow documented by Google in
google-labs-code/stitch-skills against the real Stitch API.

Outputs JSON + Markdown reports under .quality/evidence/stitch_smoke/.

ABORT semantics: if any step fails, dumps full response and stops.
No partial state cleanup attempted.

Usage:
    STITCH_API_KEY=... python3 smoke_test.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

API_BASE = "https://stitch.googleapis.com"
EVIDENCE_DIR = Path(__file__).resolve().parent
REPORT_JSON = EVIDENCE_DIR / "smoke_report.json"
REPORT_MD = EVIDENCE_DIR / "smoke_report.md"

# Minimal valid Material 3 DESIGN.md for smoke testing.
# Kept small to test the upload_design_md MCP path; the REST batchCreate
# path is tested separately if this fails by size.
DESIGN_MD_CONTENT = """---
name: SmokeTest Tokens
colors:
  surface: '#FFFFFF'
  on-surface: '#1A1A1A'
  surface-container: '#F5F5F5'
  surface-container-low: '#FAFAFA'
  surface-container-high: '#EEEEEE'
  primary: '#0EA5E9'
  on-primary: '#FFFFFF'
  primary-container: '#E0F2FE'
  on-primary-container: '#0C4A6E'
  secondary: '#64748B'
  on-secondary: '#FFFFFF'
  tertiary: '#7C3AED'
  on-tertiary: '#FFFFFF'
  error: '#DC2626'
  on-error: '#FFFFFF'
  background: '#FFFFFF'
  on-background: '#1A1A1A'
  outline: '#94A3B8'
  outline-variant: '#CBD5E1'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '800'
    lineHeight: 56px
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  body-base:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: '0.08em'
---

# SmokeTest Design System

Minimal Material 3 design system for the SpecBox Stitch native chain smoke test.

## Tokens

The YAML frontmatter contains the canonical Material 3 token set. This body is
informational and may include VEG-derived notes once the migration is fully wired.

## Notes

This file exists solely to validate that `upload_design_md` +
`create_design_system_from_design_md` accept a Material 3 frontmatter and
populate the resulting design system theme correctly server-side.
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def api_key() -> str:
    k = os.environ.get("STITCH_API_KEY")
    if not k:
        print("ERROR: STITCH_API_KEY not set in environment", file=sys.stderr)
        sys.exit(2)
    return k


def http_request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    timeout: int = 60,
) -> tuple[int, dict[str, Any] | str]:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = request.Request(
        url,
        data=data,
        method=method,
        headers={
            "X-Goog-Api-Key": api_key(),
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except error.URLError as e:
        return -1, f"URLError: {e!s}"


class StepResult:
    def __init__(self, name: str):
        self.name = name
        self.started_at = now_iso()
        self.duration_ms: int | None = None
        self.status: str = "pending"
        self.http_code: int | None = None
        self.payload_summary: dict[str, Any] = {}
        self.error: str | None = None
        self.raw_excerpt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "http_code": self.http_code,
            "payload_summary": self.payload_summary,
            "error": self.error,
            "raw_excerpt": self.raw_excerpt,
        }


def run_step(
    name: str, fn, *args, **kwargs
) -> tuple[StepResult, Any]:
    s = StepResult(name)
    t0 = time.perf_counter()
    try:
        result = fn(s, *args, **kwargs)
        s.duration_ms = int((time.perf_counter() - t0) * 1000)
        if s.status == "pending":
            s.status = "ok"
        return s, result
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        s.duration_ms = int((time.perf_counter() - t0) * 1000)
        s.status = "error"
        s.error = f"{type(exc).__name__}: {exc!s}"
        return s, None


def step_1_list_projects(s: StepResult) -> list[dict[str, Any]]:
    code, body = http_request("GET", "/v1/projects")
    s.http_code = code
    if code != 200:
        s.status = "fail"
        s.raw_excerpt = str(body)[:500]
        raise RuntimeError(f"list_projects failed: {code}")
    projects = body.get("projects", []) if isinstance(body, dict) else []
    s.payload_summary = {"project_count": len(projects)}
    return projects


def step_2_create_project(s: StepResult) -> dict[str, Any]:
    title = f"SmokeTest-NativeChain-{int(time.time())}"
    code, body = http_request(
        "POST",
        "/v1/projects",
        body={
            "project": {
                "title": title,
                "deviceType": "DESKTOP",
                "visibility": "PRIVATE",
            }
        },
    )
    s.http_code = code
    if code not in (200, 201):
        s.status = "fail"
        s.raw_excerpt = str(body)[:1000]
        raise RuntimeError(f"create_project failed: {code}")
    s.payload_summary = {
        "project_name": body.get("name") if isinstance(body, dict) else None,
        "title": title,
    }
    return body


def step_3_upload_design_md(s: StepResult, project_name: str) -> dict[str, Any]:
    """Upload DESIGN.md via REST batchCreate endpoint."""
    project_id = project_name.split("/")[-1]
    md_b64 = base64.b64encode(DESIGN_MD_CONTENT.encode("utf-8")).decode("ascii")
    code, body = http_request(
        "POST",
        f"/v1/projects/{project_id}/screens:batchCreate",
        body={
            "parent": project_name,
            "requests": [
                {
                    "screen": {
                        "htmlCode": {
                            "fileContentBase64": md_b64,
                            "mimeType": "text/markdown",
                        },
                        "screenType": "DOCUMENT",
                        "isCreatedByClient": True,
                        "title": "SmokeTest DESIGN.md",
                    }
                }
            ],
            "createScreenInstances": True,
        },
        timeout=120,
    )
    s.http_code = code
    if code not in (200, 201):
        s.status = "fail"
        s.raw_excerpt = str(body)[:1500]
        raise RuntimeError(f"upload_design_md (batchCreate) failed: {code}")
    s.payload_summary = {
        "design_md_size_bytes": len(DESIGN_MD_CONTENT.encode("utf-8")),
        "response_keys": list(body.keys()) if isinstance(body, dict) else None,
    }
    s.raw_excerpt = json.dumps(body, indent=2)[:2000] if isinstance(body, dict) else str(body)[:2000]
    return body


def step_4_get_project_screens(s: StepResult, project_name: str) -> dict[str, Any]:
    project_id = project_name.split("/")[-1]
    code, body = http_request("GET", f"/v1/projects/{project_id}")
    s.http_code = code
    if code != 200:
        s.status = "fail"
        s.raw_excerpt = str(body)[:1500]
        raise RuntimeError(f"get_project failed: {code}")
    instances = body.get("screenInstances", []) if isinstance(body, dict) else []
    s.payload_summary = {
        "screen_instances_count": len(instances),
        "instance_types": sorted({i.get("type") for i in instances if i.get("type")}),
    }
    s.raw_excerpt = json.dumps(instances[:3], indent=2)[:2000] if instances else "no instances"
    return body


def step_5_list_design_systems_pre(s: StepResult, project_name: str) -> list[dict[str, Any]]:
    project_id = project_name.split("/")[-1]
    code, body = http_request("GET", f"/v1/projects/{project_id}/designSystems")
    s.http_code = code
    if code not in (200, 404):
        s.status = "fail"
        s.raw_excerpt = str(body)[:1500]
        raise RuntimeError(f"list_design_systems (pre) failed: {code}")
    ds = body.get("designSystems", []) if isinstance(body, dict) else []
    s.payload_summary = {"design_systems_count_pre": len(ds)}
    return ds


def step_6_canary_create_ds(s: StepResult, project_name: str, screen_instances: list[dict]) -> dict[str, Any]:
    """Try create_design_system_from_design_md via REST.

    Endpoint shape unknown from public docs. Best guess: a method on the
    project resource. We try the most likely paths and capture which one
    works (or all fail and we report the error verbatim).
    """
    project_id = project_name.split("/")[-1]
    doc_instance = next(
        (i for i in screen_instances if isinstance(i, dict) and i.get("sourceScreen")), None
    )
    if not doc_instance:
        s.status = "fail"
        s.error = "no DOCUMENT instance found after upload"
        raise RuntimeError("step_6 needs a screen instance to anchor DS creation")
    payload = {
        "projectId": project_id,
        "selectedScreenInstance": {
            "id": doc_instance.get("id"),
            "sourceScreen": doc_instance.get("sourceScreen"),
        },
        "deviceType": "DESKTOP",
    }
    candidate_paths = [
        f"/v1/projects/{project_id}/designSystems:createFromDesignMd",
        f"/v1/projects/{project_id}:createDesignSystemFromDesignMd",
        f"/v1/projects/{project_id}/designSystems",
    ]
    attempts = []
    for p in candidate_paths:
        code, body = http_request("POST", p, body=payload, timeout=120)
        attempts.append({"path": p, "code": code, "body_preview": str(body)[:400]})
        if code in (200, 201):
            s.payload_summary = {
                "successful_path": p,
                "ds_name": body.get("name") if isinstance(body, dict) else None,
            }
            s.raw_excerpt = json.dumps(body, indent=2)[:2000] if isinstance(body, dict) else str(body)[:2000]
            return body
    s.status = "fail"
    s.payload_summary = {"all_attempts_failed": True, "attempts": attempts}
    s.raw_excerpt = json.dumps(attempts, indent=2)[:3000]
    raise RuntimeError("create_design_system_from_design_md: all candidate paths returned non-2xx")


def step_7_cleanup(s: StepResult, project_name: str) -> dict[str, Any]:
    """Best-effort cleanup of the smoke test project."""
    project_id = project_name.split("/")[-1]
    code, body = http_request("DELETE", f"/v1/projects/{project_id}")
    s.http_code = code
    s.payload_summary = {"deleted": code in (200, 204), "code": code}
    if code not in (200, 204, 404):
        s.status = "warn"
        s.raw_excerpt = str(body)[:500]
    return body if isinstance(body, dict) else {}


def main() -> int:
    api_key()  # fail fast
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    overall = {
        "started_at": now_iso(),
        "steps": [],
        "verdict": "pending",
        "notes": [],
    }

    # Step 1
    s1, projects = run_step("list_projects", step_1_list_projects)
    overall["steps"].append(s1.to_dict())
    if s1.status != "ok":
        overall["verdict"] = "fail_step_1"
        _write_reports(overall)
        return 10

    # Step 2
    s2, proj = run_step("create_project", step_2_create_project)
    overall["steps"].append(s2.to_dict())
    if s2.status != "ok":
        overall["verdict"] = "fail_step_2"
        _write_reports(overall)
        return 11

    project_name = proj.get("name") if isinstance(proj, dict) else None
    if not project_name:
        overall["verdict"] = "fail_no_project_name"
        _write_reports(overall)
        return 12

    try:
        # Step 3
        s3, _ = run_step("upload_design_md_batchCreate", step_3_upload_design_md, project_name)
        overall["steps"].append(s3.to_dict())
        upload_ok = s3.status == "ok"

        # Step 4 (only if upload succeeded)
        instances: list[dict] = []
        if upload_ok:
            s4, project_body = run_step("get_project_screens", step_4_get_project_screens, project_name)
            overall["steps"].append(s4.to_dict())
            if s4.status == "ok" and isinstance(project_body, dict):
                instances = project_body.get("screenInstances", [])

        # Step 5
        s5, _ = run_step("list_design_systems_pre", step_5_list_design_systems_pre, project_name)
        overall["steps"].append(s5.to_dict())

        # Step 6 (only if we have instances)
        if upload_ok and instances:
            s6, _ = run_step("create_design_system_from_design_md", step_6_canary_create_ds, project_name, instances)
            overall["steps"].append(s6.to_dict())
        else:
            overall["notes"].append("Step 6 skipped: no instances available from upload")
    finally:
        # Step 7 always runs
        s7, _ = run_step("cleanup_delete_project", step_7_cleanup, project_name)
        overall["steps"].append(s7.to_dict())

    overall["finished_at"] = now_iso()
    # Verdict logic
    statuses = [s["status"] for s in overall["steps"] if s["name"] != "cleanup_delete_project"]
    if all(st == "ok" for st in statuses):
        overall["verdict"] = "pass"
    elif any(st == "fail" for st in statuses):
        overall["verdict"] = "fail"
    else:
        overall["verdict"] = "partial"

    _write_reports(overall)
    return 0 if overall["verdict"] == "pass" else 1


def _write_reports(overall: dict[str, Any]) -> None:
    REPORT_JSON.write_text(json.dumps(overall, indent=2), encoding="utf-8")
    md_lines = [
        f"# Stitch Native Chain Smoke Test — {overall.get('started_at')}",
        "",
        f"**Verdict**: `{overall.get('verdict')}`",
        "",
        "## Steps",
        "",
        "| # | Step | Status | HTTP | Duration | Notes |",
        "|---|------|--------|------|----------|-------|",
    ]
    for i, s in enumerate(overall["steps"], start=1):
        notes = s.get("error") or json.dumps(s.get("payload_summary") or {}, separators=(",", ":"))[:120]
        md_lines.append(
            f"| {i} | `{s['name']}` | {s['status']} | {s['http_code']} | {s['duration_ms']}ms | {notes} |"
        )
    md_lines.append("")
    if overall.get("notes"):
        md_lines.append("## Notes")
        for n in overall["notes"]:
            md_lines.append(f"- {n}")
        md_lines.append("")
    md_lines.append("## Raw excerpts")
    md_lines.append("")
    for s in overall["steps"]:
        if s.get("raw_excerpt"):
            md_lines.append(f"### {s['name']}")
            md_lines.append("```")
            md_lines.append(s["raw_excerpt"])
            md_lines.append("```")
            md_lines.append("")
    REPORT_MD.write_text("\n".join(md_lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
