"""Content mode gives the same answer as a local server, without the disk (US-86 · UC-8604 AC-02).

For each tool the same project is used twice:

* **path mode** — a local server (``stdio``) works on a real directory;
* **content mode** — a remote server (``http``) receives the same files as
  ``files_content`` while every filesystem call outside the engine's own code
  is a tripwire.

The answers must match (paths, timestamps and generated ids normalised) and
applying ``files_changed`` / ``files_deleted`` / ``files_appended`` to the
sent files must give exactly what path mode left on disk.
"""

from __future__ import annotations

import builtins
import json
import pathlib
import re
from pathlib import Path

import pytest
from fastmcp import Client, FastMCP

from server.app_docs.autopilot import register_autopilot_tools
from server.app_docs.canonical import register_canonical_tools
from server.app_docs.discovery import register_discovery_tools
from server.app_docs.drift_detector import register_drift_tools
from server.app_docs.migration_v529 import register_v529_migration_tools
from server.app_docs.queue import register_queue_tools
from server.app_docs.sync import register_sync_tools as register_app_sync_tools
from server.app_docs.workspace import MemoryWorkspace, WorkspacePathError
from server.coordination.client_paths import ClientPathGuardMiddleware
from server.tools.claude_design import register_claude_design_tools
from server.tools.stitch_v2 import register_stitch_v2_tools
from server.tools.sync import register_sync_tools
from tests.test_app_docs_sync import _seed_app_prd, _seed_app_spec

ENGINE = Path(__file__).resolve().parent.parent
KEY = "tokens_confirmation"

PRD = """# PRD demo

## UC-001: Demo

Algo.
"""

DESIGN_MD = """---
name: Demo
colors:
  primary: "#1A73E8"
---

## Overview

Demo.
"""


def _repo(root: Path) -> dict[str, str]:
    """A project with canonical docs, settings, a PRD and a design-system."""
    (root / "doc" / "app").mkdir(parents=True)
    _seed_app_prd(root / "doc" / "app" / "app_prd.md")
    _seed_app_spec(root / "doc" / "app" / "app_spec.md")
    files = {
        ".claude/settings.local.json": json.dumps(
            {
                "specbox": {
                    "backend_type": "freeform",
                    "autopilot": {"level": "equilibrado", "queue_enabled": True},
                },
                "veg": {"providers": ["claude_design"]},
            }
        ),
        "doc/prds/demo_prd.md": PRD,
        "package.json": '{"name": "ds"}',
        "dist/index.html": "<html></html>",
        "doc/design/DESIGN.md": DESIGN_MD,
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return _read_tree(root)


def _read_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+00:00|Z)?")
DQ = re.compile(r"dq-[0-9a-zA-Z_-]+")


def _norm(value, root: Path):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    for prefix in (str(root.resolve()), str(root)):
        text = text.replace(prefix + "/", "").replace(prefix, ".")
    text = DQ.sub("<dq>", TS.sub("<ts>", text))
    return json.loads(text)


def _server(state: Path) -> FastMCP:
    mcp = FastMCP("content-mode-test")
    mcp.add_middleware(ClientPathGuardMiddleware())
    for register in (
        register_app_sync_tools,
        register_canonical_tools,
        register_queue_tools,
        register_autopilot_tools,
        register_drift_tools,
        register_discovery_tools,
        register_v529_migration_tools,
        register_sync_tools,
    ):
        register(mcp, ENGINE)
    register_claude_design_tools(mcp, state)
    register_stitch_v2_tools(mcp, state)
    return mcp


@pytest.fixture
def tripwire(monkeypatch):
    """Fail on any filesystem call outside the engine's own tree while armed."""

    armed = {"on": False}
    touched: list[str] = []

    def trip(name, original):
        def wrapper(self_or_path, *a, **k):
            target = str(self_or_path)
            if armed["on"] and not target.startswith(str(ENGINE)):
                touched.append(f"{name}({target})")
                raise AssertionError(f"disk access in content mode: {name}({target})")
            return original(self_or_path, *a, **k)

        return wrapper

    for name in ("write_text", "read_text", "mkdir", "open", "exists", "is_file", "is_dir", "touch", "glob", "iterdir"):
        monkeypatch.setattr(pathlib.Path, name, trip(f"Path.{name}", getattr(pathlib.Path, name)))
    monkeypatch.setattr(builtins, "open", trip("open", builtins.open))
    return armed, touched


async def _call(server: FastMCP, tool: str, args: dict) -> dict:
    async with Client(server) as client:
        result = await client.call_tool(tool, args, raise_on_error=False)
    out = result.structured_content
    if out is None:
        return json.loads(result.content[0].text)
    if set(out) == {"result"}:
        return out["result"]
    return out


def _apply(files: dict[str, str], out: dict) -> dict[str, str]:
    after = dict(files)
    after.update(out.get("files_changed", {}))
    for rel in out.get("files_deleted", []):
        after.pop(rel, None)
    for rel, text in out.get("files_appended", {}).items():
        after[rel] = after.get(rel, "") + text
    return after


REPORT = ("files_changed", "files_deleted", "files_appended", "files_requested")

CASES = [
    ("verify_app_docs", {}),
    ("record_app_docs_signature", {}),
    ("apply_app_docs_sync", {"event_type": "set_auth_token", "payload": {"backend_type": "native", "native_project_id": "Owner/demo"}}),
    ("record_canonical_confirmation", {"decision_key": KEY, "value": "si"}),
    ("list_canonical_decisions", {}),
    ("get_canonical_decision", {"decision_key": KEY}),
    ("revoke_canonical_decision", {"decision_key": KEY}),
    ("enqueue_decision_tool", {"decision_key": KEY, "feature": "demo", "default_applied": "si"}),
    ("list_decisions_queue", {}),
    ("evaluate_autopilot_decision", {"decision_key": KEY, "feature": "demo"}),
    ("detect_app_docs_drift", {}),
    ("app_docs_drift_for_heartbeat", {}),
    ("detect_project_backend", {}),
    ("detect_v529_migration_case", {}),
    ("run_v529_migration", {"apply": True}),
    ("get_implementation_status", {"item_id": "UC-001"}),
    ("write_implementation_status", {"uc_id": "UC-001", "branch": "feature/demo", "phase_deltas": ["### Fase 1\n- hecho"]}),
    ("claude_design_status", {"project": "demo"}),
]


def _path_param(tool: str) -> str:
    return "project_root" if tool.startswith("claude_design") else "project_path"


@pytest.mark.parametrize(("tool", "args"), CASES, ids=[c[0] for c in CASES])
async def test_content_mode_matches_path_mode(tool, args, tmp_path, monkeypatch, tripwire):
    repo = tmp_path / "repo"
    files = _repo(repo)
    server = _server(tmp_path / "state")

    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    disk = await _call(server, tool, {**args, _path_param(tool): str(repo)})
    after_disk = _read_tree(repo)

    monkeypatch.setenv("MCP_TRANSPORT", "http")
    armed, touched = tripwire
    armed["on"] = True
    try:
        # A path outside the engine that does not exist: any real access trips.
        mem = await _call(server, tool, {**args, _path_param(tool): str(tmp_path / "never"), "files_content": files})
    finally:
        armed["on"] = False

    assert touched == []
    report = mem if isinstance(mem, dict) else {}  # a tool that returns a list only reads
    body = {k: v for k, v in mem.items() if k not in REPORT} if isinstance(mem, dict) else mem
    assert "code" not in report or report.get("code") == disk.get("code"), mem
    assert _norm(body, repo) == _norm(disk, repo)
    assert _norm(_apply(files, report), repo) == _norm(after_disk, repo)


async def test_enqueue_then_resolve_chains_in_content_mode(tmp_path, monkeypatch, tripwire):
    files = _repo(tmp_path / "repo")
    server = _server(tmp_path / "state")
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    armed, touched = tripwire
    armed["on"] = True
    try:
        queued = await _call(server, "enqueue_decision_tool", {"decision_key": KEY, "feature": "demo", "default_applied": "si", "files_content": files})
        files = _apply(files, queued)
        engine_id = queued["entry"]["engine_id"]
        resolved = await _call(server, "resolve_queue_entry", {"engine_id": engine_id, "resolution": "confirmado", "files_content": files})
        listed = await _call(server, "list_decisions_queue", {"files_content": _apply(files, resolved)})
    finally:
        armed["on"] = False
    assert touched == []
    assert resolved.get("ok") is True, resolved
    assert [e["engine_id"] for e in listed["resueltas"]] == [engine_id]


async def test_missing_files_are_requested(tmp_path, monkeypatch):
    server = _server(tmp_path / "state")
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    out = await _call(server, "verify_app_docs", {"files_content": {}})
    assert "doc/app/app_prd.md" in out["files_requested"]
    assert out["files_changed"] == {}


async def test_validate_stitch_prompt_reads_the_palette_from_content(tmp_path, monkeypatch, tripwire):
    repo = tmp_path / "repo"
    _repo(repo)
    server = _server(tmp_path / "state")
    prompt = "A login screen with a primary button."
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    disk = await _call(server, "validate_stitch_prompt", {"project": "demo", "prompt": prompt, "project_root": str(repo)})
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    armed, touched = tripwire
    armed["on"] = True
    try:
        mem = await _call(server, "validate_stitch_prompt", {"project": "demo", "prompt": prompt, "design_md_content": DESIGN_MD})
    finally:
        armed["on"] = False
    assert touched == []
    assert mem == disk


def test_sync_multirepo_settings_parse_from_content():
    from server.tools.milestone_management import _parse_multirepo_settings

    text = json.dumps({"multirepo": {"satellites": {"engine": {"uc_prefix": "ENG"}}}})
    assert _parse_multirepo_settings(text) == {"satellites": {"engine": {"uc_prefix": "ENG"}}}
    assert _parse_multirepo_settings("{not json") == {}


@pytest.mark.parametrize("bad", ["/etc/passwd", "../x", "a/../../b", "a\\b", "", "C:/x"])
async def test_files_content_never_names_a_server_path(bad, tmp_path, monkeypatch):
    with pytest.raises(WorkspacePathError):
        MemoryWorkspace({bad: "x"})
    server = _server(tmp_path / "state")
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    out = await _call(server, "verify_app_docs", {"files_content": {bad: "x"}})
    assert out["code"] == "INVALID_FILES_CONTENT"


def test_a_virtual_path_cannot_reach_the_real_filesystem():
    vp = MemoryWorkspace({"a.txt": "x"}).root / "a.txt"
    with pytest.raises(TypeError):
        open(vp)  # noqa: SIM115 — no __fspath__: fails instead of touching the disk
    with pytest.raises(WorkspacePathError):
        vp.parent / "../../etc/passwd"
