"""A project's state is read and written only by who can see it (US-86 · UC-8603).

A real FastMCP server with in-memory clients. "Remote" is the server's
transport (``MCP_TRANSPORT=http``); the caller's identity comes from
``resolve_caller_scope``, replaced here by a fake so the tests need no
identity database. Minimum cases of threat model §8.7: no identity, another
developer, an invalid name — plus stdio, which must behave as before.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastmcp import Client, FastMCP

from server.coordination import project_state_scope as pss
from server.coordination.identity import UnauthenticatedError
from server.coordination.project_state_scope import (
    PROJECT_NAME_TOOLS,
    STATE_PROJECT_TOOLS,
    InvalidProjectNameError,
    ProjectStateScopeMiddleware,
    check_project_name,
    project_state_dir,
)
from server.coordination.scope import CallerScope
from server.stitch_client import StitchClient
from server.tools.audit import register_audit_tools
from server.tools.claude_design import register_claude_design_tools
from server.tools.state import register_state_tools
from server.tools.stitch import register_stitch_tools

ME = CallerScope(developer_id="dev-a", display_name="A", project_ids=frozenset())


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    for name in ("mine", "theirs"):
        (state / "projects" / name).mkdir(parents=True)
    (state / "registry.json").write_text(
        json.dumps(
            {
                "projects": {
                    "mine": {"stack": "react", "registered_by": "dev-a"},
                    "theirs": {"stack": "flutter", "registered_by": "dev-b"},
                }
            }
        ),
        encoding="utf-8",
    )
    return state


@pytest.fixture
def server(state_path: Path, tmp_path: Path) -> FastMCP:
    mcp = FastMCP("project-state-scope-test")
    mcp.add_middleware(ProjectStateScopeMiddleware(state_path))
    register_state_tools(mcp, tmp_path, state_path)
    register_audit_tools(mcp, tmp_path, state_path)
    register_stitch_tools(mcp, state_path)
    register_claude_design_tools(mcp, state_path)
    return mcp


@pytest.fixture
def remote(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "http")


@pytest.fixture
def as_dev_a(monkeypatch):
    async def fake(ctx, *, token=""):
        return ME

    monkeypatch.setattr(pss, "resolve_caller_scope", fake)


@pytest.fixture
def anonymous(monkeypatch):
    async def fake(ctx, *, token=""):
        raise UnauthenticatedError("no identity")

    monkeypatch.setattr(pss, "resolve_caller_scope", fake)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


async def _call(server: FastMCP, tool: str, args: dict) -> dict:
    async with Client(server) as client:
        result = await client.call_tool(tool, args, raise_on_error=False)
    return result.structured_content or {}


def _report_session(project: str) -> tuple[str, dict]:
    return "report_session", {"project": project, "timestamp": "2026-10-07T10:00:00Z", "files_modified": 3}


# ── Names (AC-01) ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    ["moto.fan", "Gemelo Digital", "2. Workflow Ventas VA360", "EmbedBuild/specbox-manager", "a"],
)
def test_names_in_use_are_valid(name, tmp_path):
    assert check_project_name(name) == name
    assert project_state_dir(tmp_path, name) == tmp_path / "projects" / name


@pytest.mark.parametrize(
    "name",
    ["", " ", " mine", "mine ", "/etc", "../escape", "a/../b", "a/b/c", "a\\b", ".", "..", "a/", "/", "a/ ", None, 7],
)
def test_names_that_leave_projects_are_rejected(name, tmp_path):
    with pytest.raises(InvalidProjectNameError):
        project_state_dir(tmp_path, name)


@pytest.mark.parametrize("transport", ["stdio", "http"])
async def test_an_invalid_name_is_answered_before_the_tool_runs(server, state_path, tmp_path, monkeypatch, transport, as_dev_a):
    monkeypatch.setenv("MCP_TRANSPORT", transport)
    before = _snapshot(tmp_path)
    for tool, args in (
        _report_session("../../escape"),
        ("register_project", {"project": "../escape"}),
        ("get_project_timeline", {"project": "a/b/c"}),
    ):
        out = await _call(server, tool, args)
        assert out["code"] == "INVALID_PROJECT_NAME", tool
    assert _snapshot(tmp_path) == before
    assert not (tmp_path / "escape").exists()


# ── Telemetry writes (AC-02) ─────────────────────────────────────────


async def test_remote_report_without_identity_writes_nothing(server, state_path, remote, anonymous):
    before = _snapshot(state_path)
    tool, args = _report_session("mine")
    out = await _call(server, tool, args)
    assert out["code"] == "UNAUTHENTICATED"
    assert _snapshot(state_path) == before


async def test_remote_report_on_another_developers_project_writes_nothing(server, state_path, remote, as_dev_a):
    before = _snapshot(state_path)
    out = await _call(
        server,
        "report_feedback",
        {
            "project": "theirs",
            "feature": "f",
            "timestamp": "2026-10-07T10:00:00Z",
            "feedback_id": "FB-001",
            "severity": "critical",
            "status": "open",
            "ac_ids": ["AC-01"],
            "description": "x",
            "expected": "y",
            "actual": "z",
            "invalidates_acceptance": True,
            "reporter": "dev-a",
        },
    )
    assert out["code"] == "PROJECT_NOT_VISIBLE"
    assert out["available"] == ["mine"]
    assert _snapshot(state_path) == before


async def test_remote_report_on_an_unregistered_project_neither_writes_nor_registers(server, state_path, remote, as_dev_a):
    before = _snapshot(state_path)
    tool, args = _report_session("brand-new")
    out = await _call(server, tool, args)
    assert out["code"] == "PROJECT_NOT_VISIBLE"
    assert _snapshot(state_path) == before
    assert not (state_path / "projects" / "brand-new").exists()


async def test_remote_report_on_my_project_is_recorded(server, state_path, remote, as_dev_a):
    tool, args = _report_session("mine")
    out = await _call(server, tool, args)
    assert out["status"] == "ok"
    assert (state_path / "projects" / "mine" / "sessions.jsonl").exists()


# ── Activity reads (AC-03) ───────────────────────────────────────────


@pytest.mark.parametrize("tool", ["get_project_activity", "get_project_timeline"])
@pytest.mark.parametrize("project", ["theirs", "does-not-exist"])
async def test_remote_reads_answer_only_for_my_projects(server, remote, as_dev_a, tool, project):
    out = await _call(server, tool, {"project": project})
    assert out["code"] == "PROJECT_NOT_VISIBLE"
    assert out["available"] == ["mine"]


async def test_remote_read_of_my_project_works(server, remote, as_dev_a):
    out = await _call(server, "get_project_timeline", {"project": "mine"})
    assert "code" not in out


# ── Audit evidence and usage logs (AC-04) ────────────────────────────


async def test_remote_audit_evidence_is_not_read_nor_written_for_another_project(server, state_path, remote, as_dev_a):
    before = _snapshot(state_path)
    attached = await _call(server, "attach_audit_evidence", {"project": "theirs", "report": {}})
    last = await _call(server, "get_last_audit", {"project": "theirs"})
    assert attached["code"] == last["code"] == "PROJECT_NOT_VISIBLE"
    assert _snapshot(state_path) == before


async def test_remote_design_usage_logs_write_nothing(server, state_path, remote, monkeypatch):
    async def fake_list_projects(self, view=None):
        return {"projects": []}

    monkeypatch.setattr(StitchClient, "list_projects", fake_list_projects)
    before = _snapshot(state_path)
    async with Client(server) as client:
        await client.call_tool("stitch_set_api_key", {"project": "theirs", "api_key": "k" * 20})
        out = await client.call_tool("stitch_list_projects", {"project": "theirs"}, raise_on_error=False)
        await client.call_tool("claude_design_list_projects", {"project": "theirs"}, raise_on_error=False)
    assert out.structured_content["status"] == "ok"
    assert _snapshot(state_path) == before


async def test_local_design_usage_log_never_leaves_projects(server, tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")

    async def fake_list_projects(self, view=None):
        return {"projects": []}

    monkeypatch.setattr(StitchClient, "list_projects", fake_list_projects)
    async with Client(server) as client:
        await client.call_tool("stitch_set_api_key", {"project": "../../escape", "api_key": "k" * 20})
        await client.call_tool("stitch_list_projects", {"project": "../../escape"}, raise_on_error=False)
    assert not (tmp_path / "escape").exists()


# ── stdio stays as it was (AC-05) ────────────────────────────────────


async def test_stdio_reports_need_no_identity_and_auto_register(server, state_path, monkeypatch, anonymous):
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    tool, args = _report_session("local-project")
    out = await _call(server, tool, args)
    assert out["status"] == "ok"
    assert (state_path / "projects" / "local-project" / "sessions.jsonl").exists()
    registry = json.loads((state_path / "registry.json").read_text(encoding="utf-8"))
    assert "local-project" in registry["projects"]


def test_every_guarded_tool_is_registered(server):
    import asyncio

    names = {t.name for t in asyncio.run(server.list_tools())}
    expected = {t for t in STATE_PROJECT_TOOLS if t != "upload_design_md_to_stitch"}
    expected |= {"register_project", "update_project_meta", "reset_project"}
    assert expected <= names
    assert STATE_PROJECT_TOOLS <= PROJECT_NAME_TOOLS
