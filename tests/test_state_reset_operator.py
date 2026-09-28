"""UC-3804 — Las operaciones de borrado de estado exigen identidad de operador.

Hasta ahora ``reset_all_state`` / ``reset_project`` solo pedían la palabra
``confirm='yes'``: cualquier sesión del MCP remoto podía borrar el estado de
cualquier proyecto (o de todos).

AC-01: reiniciar el estado global o el de un proyecto solo es posible con
       identidad de operador; cualquier otra identidad, o ninguna, recibe un
       error de autorización y no se borra nada.
AC-02: cada reinicio queda en el registro de accesos con la identidad que lo
       ejecutó y el proyecto afectado.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from server.coordination import access_log as al
from server.coordination.identity import UnauthenticatedError
from server.coordination.scope import CallerScope
from server.tools.state import STATE_RESET_ALL, STATE_RESET_EVENT

REPO_ROOT = Path(__file__).resolve().parent.parent
OPS = CallerScope("ops", "Ops", frozenset())
ALICE = CallerScope("alice", "Alice", frozenset({"acme/api"}))


def _seed(state_path: Path) -> None:
    (state_path / "registry.json").write_text(
        json.dumps({"projects": {"acme-api": {"stack": "python", "registered_by": "alice"}, "other": {"stack": "go"}}}),
        encoding="utf-8",
    )
    for name in ("acme-api", "other"):
        d = state_path / "projects" / name
        d.mkdir(parents=True)
        (d / "meta.json").write_text('{"stack": "x"}', encoding="utf-8")
        (d / "sessions.jsonl").write_text('{"timestamp": "t"}\n', encoding="utf-8")
    (state_path / "tool_access_log.spool.jsonl").write_text('{"tool": "x"}\n', encoding="utf-8")


def _snapshot(state_path: Path) -> dict[str, str]:
    return {str(p.relative_to(state_path)): p.read_text() for p in sorted(state_path.rglob("*")) if p.is_file()}


async def _tools(state_path: Path) -> dict[str, Any]:
    from server.tools.state import register_state_tools

    mcp = FastMCP(name="t-state-reset")
    register_state_tools(mcp, engine_path=REPO_ROOT, state_path=state_path)
    return {name: (await mcp.get_tool(name)).fn for name in ("reset_all_state", "reset_project")}


@pytest.fixture
def store():
    s = al.MemoryStore()
    al.configure_store(s)
    yield s
    al.configure_store(None)


# ── AC-01 ──────────────────────────────────────────────────────────────


async def test_ac01_without_identity_nothing_is_deleted(tmp_path, store):
    _seed(tmp_path)
    before = _snapshot(tmp_path)
    tools = await _tools(tmp_path)
    with patch("server.tools.state.resolve_caller_scope", new=AsyncMock(side_effect=UnauthenticatedError())):
        r_all = await tools["reset_all_state"](confirm="yes", ctx=None)
        r_one = await tools["reset_project"](project="acme-api", confirm="yes", ctx=None)
    assert r_all["code"] == "UNAUTHENTICATED" and r_one["code"] == "UNAUTHENTICATED"
    assert _snapshot(tmp_path) == before
    assert store.records == []


async def test_ac01_a_developer_who_is_not_the_operator_is_refused(tmp_path, store, monkeypatch):
    monkeypatch.delenv(al.OPERATOR_IDS_ENV, raising=False)
    _seed(tmp_path)
    before = _snapshot(tmp_path)
    tools = await _tools(tmp_path)
    # Alice is a legitimate developer and even owns acme-api — still not the operator.
    with patch("server.tools.state.resolve_caller_scope", new=AsyncMock(return_value=ALICE)), patch(
        "server.tools.state.is_operator", new=AsyncMock(return_value=False)
    ):
        r_all = await tools["reset_all_state"](confirm="yes", ctx=None)
        r_one = await tools["reset_project"](project="acme-api", confirm="yes", ctx=None)
    assert r_all["code"] == "FORBIDDEN" and r_all["status"] == "forbidden"
    assert r_one["code"] == "FORBIDDEN"
    assert _snapshot(tmp_path) == before
    assert store.records == []


async def test_ac01_operator_still_needs_the_confirmation_word(tmp_path, store, monkeypatch):
    monkeypatch.setenv(al.OPERATOR_IDS_ENV, "ops")
    _seed(tmp_path)
    before = _snapshot(tmp_path)
    tools = await _tools(tmp_path)
    with patch("server.tools.state.resolve_caller_scope", new=AsyncMock(return_value=OPS)):
        r_all = await tools["reset_all_state"](confirm="no", ctx=None)
        r_one = await tools["reset_project"](project="acme-api", confirm="", ctx=None)
        ghost = await tools["reset_project"](project="ghost", confirm="yes", ctx=None)
    assert "Safety guard" in r_all["error"] and "Safety guard" in r_one["error"]
    assert "not found" in ghost["error"]
    assert _snapshot(tmp_path) == before
    assert store.records == []


# ── AC-01 + AC-02: the operator resets, and it is on the record ────────


async def test_ac02_project_reset_by_operator_is_logged_with_identity_and_project(tmp_path, store, monkeypatch):
    monkeypatch.setenv(al.OPERATOR_IDS_ENV, "ops")
    _seed(tmp_path)
    tools = await _tools(tmp_path)
    with patch("server.tools.state.resolve_caller_scope", new=AsyncMock(return_value=OPS)):
        result = await tools["reset_project"](project="acme-api", confirm="yes", ctx=None)
    assert result["status"] == "ok" and result["project"] == "acme-api" and result["operator"] == "ops"
    assert result["files_deleted"] == 2
    assert not (tmp_path / "projects" / "acme-api").exists()
    assert (tmp_path / "projects" / "other" / "meta.json").exists()
    registry = json.loads((tmp_path / "registry.json").read_text())
    assert "acme-api" not in registry["projects"] and "other" in registry["projects"]
    # AC-02: one execution event, with who and what.
    events = [r for r in store.records if r.tool == STATE_RESET_EVENT]
    assert len(events) == 1
    assert events[0].developer_id == "ops" and events[0].identity_kind == "developer"
    assert events[0].project_id == "acme-api" and events[0].outcome == "ok"


async def test_ac02_full_reset_by_operator_is_logged_and_spares_the_access_log_spool(tmp_path, store, monkeypatch):
    monkeypatch.setenv(al.OPERATOR_IDS_ENV, "ops")
    _seed(tmp_path)
    tools = await _tools(tmp_path)
    with patch("server.tools.state.resolve_caller_scope", new=AsyncMock(return_value=OPS)):
        result = await tools["reset_all_state"](confirm="yes", ctx=None)
    assert result["action"] == "full_reset" and result["deleted_projects"] == ["acme-api", "other"]
    assert result["operator"] == "ops"
    assert not (tmp_path / "registry.json").exists()
    assert (tmp_path / "projects").is_dir() and not any((tmp_path / "projects").iterdir())
    # The access-log spool is not "state": a pending trail survives the reset.
    assert (tmp_path / "tool_access_log.spool.jsonl").exists()
    events = [r for r in store.records if r.tool == STATE_RESET_EVENT]
    assert len(events) == 1 and events[0].developer_id == "ops" and events[0].project_id == STATE_RESET_ALL


async def test_ac02_a_failing_audit_store_does_not_hide_the_reset_result(tmp_path, monkeypatch):
    monkeypatch.setenv(al.OPERATOR_IDS_ENV, "ops")

    class Exploding:
        async def write(self, record):
            raise OSError("db down")

        async def query(self, **_):
            return []

    al.configure_store(Exploding())
    try:
        _seed(tmp_path)
        tools = await _tools(tmp_path)
        with patch("server.tools.state.resolve_caller_scope", new=AsyncMock(return_value=OPS)):
            result = await tools["reset_project"](project="other", confirm="yes", ctx=None)
        assert result["status"] == "ok"
        assert not (tmp_path / "projects" / "other").exists()
    finally:
        al.configure_store(None)


async def test_schema_exposes_dev_token_and_hides_ctx():
    from server.tools.state import register_state_tools

    mcp = FastMCP(name="t-state-schema")
    register_state_tools(mcp, engine_path=REPO_ROOT, state_path=Path("/nonexistent"))
    for name in ("reset_all_state", "reset_project"):
        props = list((await mcp.get_tool(name)).parameters.get("properties", {}).keys())
        assert "dev_token" in props and "ctx" not in props and "confirm" in props
