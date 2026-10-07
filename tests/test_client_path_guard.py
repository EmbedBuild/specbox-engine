"""A remote server never touches a path the client names (US-86 · UC-8604).

Remotely, every tool in ``CLIENT_PATH_TOOLS`` answers before resolving its
path: the filesystem calls a tool could use (``Path.write_text``/``mkdir``/
``read_text``/``open``/``exists``, ``open``) are instrumented to fail during
the call, so a single disk access breaks the test. The backend-switch
transaction writes only the registry remotely and returns the client's two
files as ``client_writes``.
"""

from __future__ import annotations

import builtins
import inspect
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
from server.app_docs.migrate_freeform import register_freeform_migration_tools
from server.app_docs.migration_v529 import register_v529_migration_tools
from server.app_docs.queue import register_queue_tools
from server.app_docs.sync import register_sync_tools as register_app_sync_tools
from server.coordination.client_paths import (
    APP_DOCS_CONTENT_REQUIRED,
    CLIENT_PATH_TOOLS,
    REMOTE_PATH_REJECTED,
    ClientPathGuardMiddleware,
)
from server.migration.transactional_switch import apply_mirror_transactional, apply_switch_transactional
from server.tools.claude_design import register_claude_design_tools
from server.tools.milestone_management import register_milestone_management_tools
from server.tools.stitch_v2 import register_stitch_v2_tools
from server.tools.sync import register_sync_tools

ENGINE = Path(__file__).resolve().parent.parent

#: Registered tools with a path-like parameter that the guard does not reject,
#: each with the reason it is safe.
APPROVED: dict[str, str] = {
    "generate_design_md_tool": "own guard: DESIGN_MD_CONTENT_REQUIRED remotely (UC-4901)",
    "set_auth_token": "FreeForm root_path rejected remotely (UC-3801)",
    "get_visual_gap_report": "system_tokens_path only labels the content sent",
    "onboard_project": "freeform_root_absolute is stored in the registry, never opened",
    "report_e2e_results": "report_path is stored as text, never opened",
    "run_quality_audit": "project_path is never used: the tool raises (deprecated)",
    "switch_backend": "remotely writes the registry only and returns client_writes",
    "switch_project_backend": "remotely writes the registry only and returns client_writes",
    "enable_mirror": "remotely writes the registry only and returns client_writes",
    "disable_mirror": "remotely writes the registry only and returns client_writes",
}

def _payload(result) -> dict:
    """The envelope as the client reads it.

    Unwrapped for tools whose output schema wraps under ``result``; from the
    text block for tools that return a list (sent as an error result).
    """
    text = result.content[0].text if result.content else ""
    assert "Output validation error" not in text
    out = result.structured_content
    if out is None:
        return json.loads(text)
    if set(out) == {"result"} and isinstance(out["result"], dict):
        return out["result"]
    return out


PATH_LIKE = re.compile(r"(path|root|_dir$|folder)", re.I)
NOT_A_PATH = re.compile(r"(content|present|inventory|files_modified|has_)", re.I)


# ── Inventory ────────────────────────────────────────────────────────


async def test_every_tool_with_a_client_path_is_guarded_or_approved():
    from server.server import mcp

    found: dict[str, list[str]] = {}
    for tool in await mcp.list_tools():
        params = [
            p
            for p in inspect.signature(tool.fn).parameters
            if PATH_LIKE.search(p) and not NOT_A_PATH.search(p)
        ]
        if params:
            found[tool.name] = params

    unguarded = sorted(set(found) - set(CLIENT_PATH_TOOLS) - set(APPROVED))
    assert unguarded == [], f"tools with a client path and no remote guard: {unguarded}"
    for name, rule in CLIENT_PATH_TOOLS.items():
        assert name in found, f"{name} is guarded but not registered with a path parameter"
        assert set(rule.path_params) <= set(found[name]), name


# ── Remote rejection without touching the disk (AC-01, AC-04) ────────


@pytest.fixture
def server(tmp_path: Path) -> FastMCP:
    mcp = FastMCP("client-path-guard-test")
    mcp.add_middleware(ClientPathGuardMiddleware())
    for register in (
        register_app_sync_tools,
        register_canonical_tools,
        register_queue_tools,
        register_autopilot_tools,
        register_drift_tools,
        register_discovery_tools,
        register_freeform_migration_tools,
        register_v529_migration_tools,
        register_sync_tools,
    ):
        register(mcp, ENGINE)
    register_claude_design_tools(mcp, tmp_path / "state")
    register_stitch_v2_tools(mcp, tmp_path / "state")
    register_milestone_management_tools(mcp)
    return mcp


def _args(tool: str, where: str) -> dict:
    """Minimal valid arguments, with ``where`` in every path parameter."""
    base = {
        "apply_app_docs_sync": {"event_type": "complete_uc"},
        "record_canonical_confirmation": {"decision_key": "k", "value": "v"},
        "revoke_canonical_decision": {"decision_key": "k"},
        "get_canonical_decision": {"decision_key": "k"},
        "enqueue_decision_tool": {"decision_key": "k", "feature": "f", "default_applied": "x"},
        "resolve_queue_entry": {"engine_id": "Q-1", "resolution": "confirm"},
        "evaluate_autopilot_decision": {"decision_key": "k"},
        "migrate_to_freeform_tool": {"project": "p"},
        "get_implementation_status": {"item_id": "UC-1"},
        "write_implementation_status": {"uc_id": "UC-1", "branch": "b", "phase_deltas": ["d"]},
        "claude_design_status": {"project": "p"},
        "claude_design_create_project": {"project": "p", "name": "n"},
        "claude_design_sync_design_system": {"project": "p"},
        "upload_design_md_to_stitch": {"project": "p", "stitch_project_id": "1"},
        "validate_stitch_prompt": {"project": "p", "prompt": "a screen"},
        "sync_multirepo_state": {},
    }.get(tool, {})
    rule = CLIENT_PATH_TOOLS[tool]
    return {**base, rule.path_params[0]: where}


@pytest.fixture
def no_disk(monkeypatch):
    """Arm a tripwire on every filesystem call a tool could make."""

    touched: list[str] = []
    armed = {"on": False}

    def trip(name, original):
        def wrapper(*a, **k):
            if armed["on"]:
                touched.append(f"{name}{a[:2]!r}")
                raise AssertionError(f"disk access during a remote call: {name}")
            return original(*a, **k)

        return wrapper

    for name in ("write_text", "read_text", "mkdir", "open", "exists", "is_file", "is_dir", "touch"):
        monkeypatch.setattr(pathlib.Path, name, trip(f"Path.{name}", getattr(pathlib.Path, name)))
    monkeypatch.setattr(builtins, "open", trip("open", builtins.open))
    return armed, touched


@pytest.mark.parametrize("tool", sorted(CLIENT_PATH_TOOLS))
async def test_remote_call_with_a_client_path_is_rejected_without_touching_disk(
    server, tool, tmp_path, monkeypatch, no_disk
):
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    armed, touched = no_disk
    async with Client(server) as client:
        armed["on"] = True
        try:
            result = await client.call_tool(tool, _args(tool, str(tmp_path / "client-repo")), raise_on_error=False)
        finally:
            armed["on"] = False
    out = _payload(result)
    assert touched == []
    assert out["code"] in (APP_DOCS_CONTENT_REQUIRED, REMOTE_PATH_REJECTED)
    assert out["code"] == CLIENT_PATH_TOOLS[tool].code
    assert str(tmp_path) not in json.dumps(out)


@pytest.mark.parametrize(
    "tool", sorted(t for t, r in CLIENT_PATH_TOOLS.items() if r.code == APP_DOCS_CONTENT_REQUIRED and t not in (
        "get_implementation_status", "write_implementation_status"))
)
async def test_remote_default_dot_is_never_resolved(server, tool, monkeypatch, no_disk):
    """``project_path="."`` (the default) would be the engine's /app remotely."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    args = _args(tool, ".")
    args.pop("project_path")
    armed, touched = no_disk
    async with Client(server) as client:
        armed["on"] = True
        try:
            result = await client.call_tool(tool, args, raise_on_error=False)
        finally:
            armed["on"] = False
    assert touched == []
    assert _payload(result)["code"] == APP_DOCS_CONTENT_REQUIRED


async def test_remote_optional_path_only_rejects_when_given(server, monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    async with Client(server) as client:
        without = await client.call_tool(
            "validate_stitch_prompt", {"project": "p", "prompt": "a login screen"}, raise_on_error=False
        )
        with_root = await client.call_tool(
            "validate_stitch_prompt", {"project": "p", "prompt": "a login screen", "project_root": "/x"},
            raise_on_error=False,
        )
    assert (without.structured_content or {}).get("code") is None
    assert with_root.structured_content["code"] == REMOTE_PATH_REJECTED


async def test_stdio_keeps_reading_the_path(server, tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    async with Client(server) as client:
        result = await client.call_tool("verify_app_docs", {"project_path": str(tmp_path)}, raise_on_error=False)
    out = result.structured_content or {}
    assert "code" not in out
    assert "in_sync" in out


# ── Backend switch and mirror write the registry only (remote) ───────


@pytest.fixture
def client_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "client-repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / "doc" / "app").mkdir(parents=True)
    (repo / ".claude" / "settings.local.json").write_text('{"specbox": {"backend_type": "freeform"}}', encoding="utf-8")
    (repo / "doc" / "app" / "app_spec.md").write_text("# spec\n", encoding="utf-8")
    return repo


@pytest.fixture
def state(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    state.mkdir()
    (state / "projects.json").write_text(
        json.dumps({"projects": {"demo": {"spec_backend": "freeform", "board_id": "ff"}}}), encoding="utf-8"
    )
    return state


def _snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_remote_switch_writes_registry_only_and_returns_client_writes(state, client_repo, monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    before = _snapshot(client_repo)

    out = apply_switch_transactional("demo", "native", "Owner/demo", str(client_repo), str(state))

    assert out["updated"] == ["registry"]
    assert _snapshot(client_repo) == before
    registry = json.loads((state / "projects.json").read_text(encoding="utf-8"))
    assert registry["projects"]["demo"]["spec_backend"] == "native"
    writes = out["client_writes"]
    assert writes["settings"] == {"path": ".claude/settings.local.json", "set": {"specbox.backend_type": "native"}}
    assert writes["app_spec"]["zone_id"] == "tracking_backend"
    assert "**Native project id:** Owner/demo" in writes["app_spec"]["body"]


def test_remote_mirror_writes_registry_only_and_returns_client_writes(state, client_repo, monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    before = _snapshot(client_repo)

    enabled = apply_mirror_transactional(
        "demo", "Owner/demo", str(client_repo), str(state), primary_backend="trello", primary_board_id="b1"
    )
    disabled = apply_mirror_transactional("demo", None, str(client_repo), str(state))

    assert enabled["updated"] == disabled["updated"] == ["registry"]
    assert _snapshot(client_repo) == before
    assert enabled["client_writes"]["settings"]["set"] == {
        "specbox.mirror": {"backend": "native", "project_id": "Owner/demo"}
    }
    assert "**Mirror (native):** Owner/demo" in enabled["client_writes"]["app_spec"]["body"]
    assert disabled["client_writes"]["settings"]["unset"] == ["specbox.mirror"]


def test_stdio_switch_still_writes_the_three_places(state, client_repo, monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    out = apply_switch_transactional("demo", "native", "Owner/demo", str(client_repo), str(state))
    assert out["updated"] == ["registry", "app_spec", "settings"]
    assert "client_writes" not in out
    settings = json.loads((client_repo / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    assert settings["specbox"]["backend_type"] == "native"
