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

import pytest
from fastmcp import Client, FastMCP

from server.stitch_client import StitchClient
from server.tools.stitch import register_stitch_tools
from server.tools.stitch_v2 import register_stitch_v2_tools

PROJECT = "test-project"
KEY = "stitch-key-of-session-a-1234"


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
