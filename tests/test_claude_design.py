"""Tests for the Claude Design MCP tools (US-29 · UC-2902).

Covers AC-01 (5 tools registered), AC-02 (ordering enforced / no write without
plan), AC-03 (no token/api_key in signatures), AC-04 (projectId anchored),
AC-06 (session-identity guarantee, multi-account).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from fastmcp import FastMCP

from server.tools.claude_design import (
    REASON_NO_LOGIN,
    anchor_project_id,
    assert_session_identity,
    build_sync_plan,
    register_claude_design_tools,
    resolve_writability,
    validate_plan_ordering,
)

EXPECTED_TOOLS = {
    "claude_design_list_projects",
    "claude_design_get_project",
    "claude_design_create_project",
    "claude_design_sync_design_system",
    "claude_design_status",
}


async def _registered_tools(mcp: FastMCP) -> list:
    return await mcp.list_tools()


async def _registered_tool_names(mcp: FastMCP) -> set[str]:
    return {t.name for t in await _registered_tools(mcp)}


# --------------------------------------------------------------------------
# AC-01 — the 5 tools are registered
# --------------------------------------------------------------------------

async def test_five_tools_registered(tmp_path: Path) -> None:
    mcp = FastMCP("test")
    register_claude_design_tools(mcp, tmp_path)
    names = await _registered_tool_names(mcp)
    assert EXPECTED_TOOLS.issubset(names)


async def test_no_delete_project_tool(tmp_path: Path) -> None:
    # AC-05: there is intentionally no delete tool.
    mcp = FastMCP("test")
    register_claude_design_tools(mcp, tmp_path)
    names = await _registered_tool_names(mcp)
    assert "claude_design_delete_project" not in names


# --------------------------------------------------------------------------
# AC-03 — no tool signature accepts a token / api_key
# --------------------------------------------------------------------------

async def test_no_tool_accepts_token_or_api_key(tmp_path: Path) -> None:
    mcp = FastMCP("test")
    register_claude_design_tools(mcp, tmp_path)
    tools = await _registered_tools(mcp)
    forbidden = {"token", "api_key", "apikey", "api_token", "secret"}
    for tool in tools:
        if not tool.name.startswith("claude_design_"):
            continue
        fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
        if fn is None:
            continue
        params = set(inspect.signature(fn).parameters)
        assert not (params & forbidden), f"{tool.name} accepts a credential param"


# --------------------------------------------------------------------------
# AC-02 — ordering: never write before finalize_plan
# --------------------------------------------------------------------------

def test_build_sync_plan_orders_read_finalize_write() -> None:
    plan = build_sync_plan(
        project_id="uuid-1", site_path="/repo", writes=["components/**"]
    )
    methods = [s["method"] for s in sorted(plan["ordered_steps"], key=lambda s: s["order"])]
    assert methods[0] in {"list_files", "list_projects", "get_file", "get_project"}
    assert "finalize_plan" in methods
    assert methods.index("finalize_plan") < methods.index("write_files")


def test_build_sync_plan_rejects_write_without_project() -> None:
    with pytest.raises(ValueError):
        build_sync_plan(project_id=None, site_path="/repo", writes=["x"])


def test_validate_plan_ordering_rejects_write_before_finalize() -> None:
    bad = [
        {"order": 1, "method": "write_files"},
        {"order": 2, "method": "finalize_plan"},
    ]
    with pytest.raises(ValueError):
        validate_plan_ordering(bad)


def test_validate_plan_ordering_accepts_correct_order() -> None:
    good = [
        {"order": 1, "method": "list_files"},
        {"order": 2, "method": "finalize_plan"},
        {"order": 3, "method": "write_files"},
    ]
    validate_plan_ordering(good)  # must not raise


# --------------------------------------------------------------------------
# AC-04 — create_project anchors the projectId in veg.claude_design
# --------------------------------------------------------------------------

def test_anchor_project_id_persists_in_settings(tmp_path: Path) -> None:
    cd = anchor_project_id(tmp_path, "uuid-new")
    assert cd["projectId"] == "uuid-new"
    data = json.loads((tmp_path / ".claude" / "settings.local.json").read_text())
    assert data["veg"]["claude_design"]["projectId"] == "uuid-new"


def test_anchor_project_id_merges_without_clobbering(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.local.json").write_text(
        json.dumps({"stitch": {"projectId": "stitch_keep"}, "veg": {"providers": ["claude_design"]}})
    )
    anchor_project_id(tmp_path, "uuid-2")
    data = json.loads((claude / "settings.local.json").read_text())
    # existing keys preserved
    assert data["stitch"]["projectId"] == "stitch_keep"
    assert data["veg"]["providers"] == ["claude_design"]
    assert data["veg"]["claude_design"]["projectId"] == "uuid-2"


def test_anchor_does_not_persist_any_secret(tmp_path: Path) -> None:
    anchor_project_id(tmp_path, "uuid-3")
    raw = (tmp_path / ".claude" / "settings.local.json").read_text().lower()
    for forbidden in ("token", "api_key", "secret", "password", "_b64"):
        assert forbidden not in raw


# --------------------------------------------------------------------------
# AC-06 — session identity / writability guarantee (multi-account)
# --------------------------------------------------------------------------

def test_no_login_yields_pending() -> None:
    out = assert_session_identity(None)
    assert out["ok"] is False
    assert out["reason"] == REASON_NO_LOGIN


def test_login_present_ok_even_when_empty_list() -> None:
    # An empty (but non-None) list means the read succeeded → login active.
    assert assert_session_identity([])["ok"] is True


def test_writable_when_anchored_project_in_session() -> None:
    session = [{"projectId": "uuid-1", "owner": "me@x.com"}]
    out = resolve_writability("uuid-1", session)
    assert out["writable"] is True


def test_writable_foreign_owner_proceeds_with_warning_flag() -> None:
    # JR-CD.4 multi-account: another account created it but the active session
    # is writable → proceed (foreign_owner surfaced).
    session = [{"projectId": "uuid-1", "owner": "teammate@x.com"}]
    out = resolve_writability("uuid-1", session)
    assert out["writable"] is True
    assert out["foreign_owner"] == "teammate@x.com"


def test_not_writable_when_project_absent_from_session() -> None:
    session = [{"projectId": "other", "owner": "x"}]
    out = resolve_writability("uuid-1", session)
    assert out["writable"] is False
    assert "not writable" in out["reason"]


def test_no_login_not_writable() -> None:
    out = resolve_writability("uuid-1", None)
    assert out["writable"] is False
    assert out["reason"] == REASON_NO_LOGIN
