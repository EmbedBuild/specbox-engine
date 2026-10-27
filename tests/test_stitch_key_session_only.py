"""The Stitch API key lives only in the MCP session (UC-8601).

Before UC-8601, ``stitch_set_api_key`` wrote the key (base64) into
``state/projects/<project>/meta.json`` and every Stitch tool fell back to that
file when the session had no key, so any session that named a project could
use its owner's key. These tests run a real FastMCP server with in-memory
clients: each client is its own MCP session.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import pytest
from fastmcp import Client, FastMCP

from server.stitch_client import StitchClient
from server.tools.stitch import register_stitch_tools
from server.tools.stitch_v2 import register_stitch_v2_tools

PROJECT = "test-project"
KEY = "stitch-key-of-session-a-1234"


@pytest.fixture(autouse=True)
def _no_key_in_the_environment(monkeypatch):
    """A developer's own STITCH_API_KEY must not change what these tests see."""

    monkeypatch.delenv("STITCH_API_KEY", raising=False)
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    (state / "projects" / PROJECT).mkdir(parents=True)
    return state


@pytest.fixture
def server(state_path: Path) -> FastMCP:
    mcp = FastMCP("stitch-key-test")
    register_stitch_tools(mcp, state_path)
    register_stitch_v2_tools(mcp, state_path)
    return mcp


@pytest.fixture
def stitch_calls(monkeypatch) -> list[str]:
    """Record which key reached Stitch instead of calling the real API."""

    calls: list[str] = []

    async def fake_list_projects(self, view=None):
        calls.append(self.api_key)
        return {"projects": []}

    monkeypatch.setattr(StitchClient, "list_projects", fake_list_projects)
    return calls


def _snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _store_key_on_disk(state_path: Path, key: str) -> None:
    """The shape 6.21.0 and earlier left in production meta.json files."""

    (state_path / "projects" / PROJECT / "meta.json").write_text(
        json.dumps(
            {
                "stitch_configured": True,
                "stitch_key_hint": f"...{key[-4:]}",
                "stitch_key_b64": base64.b64encode(key.encode()).decode(),
            }
        ),
        encoding="utf-8",
    )


async def _call(client: Client, tool: str, args: dict) -> dict:
    result = await client.call_tool(tool, args, raise_on_error=False)
    return result.structured_content or {}


async def test_set_api_key_writes_nothing_on_the_server(server, state_path):
    before = _snapshot(state_path)
    async with Client(server) as client:
        out = await _call(client, "stitch_set_api_key", {"project": PROJECT, "api_key": KEY})
    assert out["status"] == "ok"
    assert out["key_hint"] == f"...{KEY[-4:]}"
    assert _snapshot(state_path) == before


async def test_a_key_left_on_disk_is_never_used(server, state_path, stitch_calls):
    _store_key_on_disk(state_path, "owner-key-left-on-disk-9999")
    async with Client(server) as client:
        v1 = await _call(client, "stitch_list_projects", {"project": PROJECT})
        v2 = await _call(
            client,
            "stitch_generate_screen_v2",
            {"project": PROJECT, "stitch_project_id": "123", "prompt": "Pantalla de prueba"},
        )
    assert "not configured" in v1["error"]
    assert "not configured" in json.dumps(v2)
    assert stitch_calls == []


async def test_another_session_cannot_use_the_key_of_this_one(server, state_path, stitch_calls):
    async with Client(server) as session_a, Client(server) as session_b:
        await _call(session_a, "stitch_set_api_key", {"project": PROJECT, "api_key": KEY})

        mine = await _call(session_a, "stitch_list_projects", {"project": PROJECT})
        theirs = await _call(session_b, "stitch_list_projects", {"project": PROJECT})

    assert mine["status"] == "ok"
    assert "not configured" in theirs["error"]
    assert stitch_calls == [KEY]
    assert not (state_path / "projects" / PROJECT / "meta.json").exists()


# ── UC-11301: the key travels in a header, not through the conversation ──

HEADER_KEY = "stitch-key-from-the-helper-5678"
MCP_HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
    "mcp-protocol-version": "2025-06-18",
}


async def _http_call(server: FastMCP, tool: str, args: dict, headers: dict[str, str]) -> dict:
    """Call a tool over real Streamable HTTP, as Claude Code does with the hosted MCP."""

    app = server.http_app(json_response=True)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://mcp.test")
    base = {**MCP_HEADERS, **headers}
    async with app.router.lifespan_context(app), client:
        init = await client.post(
            "/mcp",
            headers=base,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "prueba", "version": "1.0"},
                },
            },
        )
        assert init.status_code == 200, init.text
        session = {**base, "mcp-session-id": init.headers["mcp-session-id"]}
        await client.post("/mcp", headers=session, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        resp = await client.post(
            "/mcp",
            headers=session,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool, "arguments": args}},
        )
    assert resp.status_code == 200, resp.text
    return resp.json()["result"]


async def test_uc11301_ac02_the_header_key_reaches_stitch_without_set_api_key(server, state_path, stitch_calls, monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "http")  # the hosted MCP: no usage log on its disk either
    before = _snapshot(state_path)
    result = await _http_call(
        server, "stitch_list_projects", {"project": PROJECT}, {"x-stitch-api-key": HEADER_KEY}
    )
    assert result["structuredContent"]["status"] == "ok"
    assert stitch_calls == [HEADER_KEY]
    # AC-01: the key is in no answer the conversation sees, and nothing is written on the server.
    assert HEADER_KEY not in json.dumps(result)
    assert _snapshot(state_path) == before


async def test_uc11301_without_header_or_session_the_error_names_the_new_path(server, stitch_calls):
    result = await _http_call(server, "stitch_list_projects", {"project": PROJECT}, {})
    error = result["structuredContent"]["error"]
    assert "not configured" in error
    assert "stitch.apiKey" in error and "settings.local.json" in error
    assert "stitch_set_api_key" not in error
    assert stitch_calls == []


class _Request:
    def __init__(self, headers: dict[str, str]):
        self.headers = headers


class _Ctx:
    """Just what get_stitch_client reads: session state and the HTTP request."""

    def __init__(self, session_key: str | None = None, headers: dict[str, str] | None = None):
        self._state = {f"stitch_config_{PROJECT}": {"api_key": session_key}} if session_key else {}
        self.request_context = type("RC", (), {"request": _Request(headers) if headers is not None else None})()

    async def get_state(self, key):
        return self._state.get(key)


async def test_uc11301_the_session_key_still_wins_over_the_header():
    from server.auth_gateway import get_stitch_client

    client = await get_stitch_client(_Ctx(session_key=KEY, headers={"x-stitch-api-key": HEADER_KEY}), PROJECT)
    assert client.api_key == KEY
    client = await get_stitch_client(_Ctx(headers={"x-stitch-api-key": f"  {HEADER_KEY}  "}), PROJECT)
    assert client.api_key == HEADER_KEY


async def test_uc11301_the_environment_key_only_counts_on_a_local_server(monkeypatch):
    from server.auth_gateway import get_stitch_client

    monkeypatch.setenv("STITCH_API_KEY", "key-of-the-local-developer-0000")
    client = await get_stitch_client(_Ctx(headers={}), PROJECT)
    assert client.api_key == "key-of-the-local-developer-0000"

    # The hosted server's own environment is never anyone's key.
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    with pytest.raises(RuntimeError, match="not configured"):
        await get_stitch_client(_Ctx(headers={}), PROJECT)
    client = await get_stitch_client(_Ctx(headers={"x-stitch-api-key": HEADER_KEY}), PROJECT)
    assert client.api_key == HEADER_KEY


async def test_uc11301_ac03_set_api_key_answers_with_the_deprecation_notice(server):
    async with Client(server) as client:
        out = await _call(client, "stitch_set_api_key", {"project": PROJECT, "api_key": KEY})
        tools = {tool.name: tool for tool in await client.list_tools()}
    assert out["status"] == "ok"
    notice = out["deprecation"]
    assert "deprecated" in notice and "stitch.apiKey" in notice and "X-Stitch-Api-Key" in notice
    assert tools["stitch_set_api_key"].description.startswith("DEPRECATED")
