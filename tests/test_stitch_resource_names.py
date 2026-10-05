"""US-84 · UC-8402 — projects and screens are asked for by their resource name.

The API asks ``get_project`` for ``name=projects/{id}`` and ``get_screen`` for
``name=projects/{p}/screens/{s}``; the engine sent ``projectId``/``screenId``
and Stitch rejected every call. An id that already carries the prefix must
not end up with it twice.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from fastmcp import FastMCP

import server.tools.stitch as stitch_v1
from server.stitch_client import STITCH_MCP_URL, StitchClient, project_resource, screen_resource


@pytest.mark.parametrize("project_id", ["123", "projects/123", "/projects/123/", " 123 "])
def test_project_resource(project_id):
    assert project_resource(project_id) == "projects/123"


@pytest.mark.parametrize(
    ("project_id", "screen_id"),
    [
        ("123", "abc"),
        ("projects/123", "abc"),
        ("123", "screens/abc"),
        ("123", "projects/123/screens/abc"),
        ("projects/123", "projects/123/screens/abc"),
    ],
)
def test_screen_resource(project_id, screen_id):
    assert screen_resource(project_id, screen_id) == "projects/123/screens/abc"


@pytest.fixture
def stitch_tools(tmp_path: Path, monkeypatch):
    real = StitchClient(api_key="test-api-key-12345678")

    async def _client(*_args, **_kwargs):
        return real

    monkeypatch.setattr(stitch_v1, "get_stitch_client", _client)
    mcp = FastMCP("test-stitch-names")
    state = tmp_path / "state"
    state.mkdir()
    stitch_v1.register_stitch_tools(mcp, state)
    return mcp


async def _sent_name(mcp: FastMCP, tool_name: str, **kwargs) -> str:
    with respx.mock:
        route = respx.post(STITCH_MCP_URL).mock(
            return_value=httpx.Response(
                200, json={"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": "{}"}]}}
            )
        )
        tool = await mcp._get_tool(tool_name)
        res = await tool.fn(AsyncMock(), project="p", **kwargs)
        assert res["status"] == "ok", res
        arguments = json.loads(route.calls[0].request.content)["params"]["arguments"]
    assert list(arguments) == ["name"]
    return arguments["name"]


class TestToolsSendTheSameName:
    """AC-03 — with or without the prefix, the tools send the same name."""

    @pytest.mark.parametrize("stitch_project_id", ["123", "projects/123"])
    async def test_get_project(self, stitch_tools, stitch_project_id):
        name = await _sent_name(stitch_tools, "stitch_get_project", stitch_project_id=stitch_project_id)
        assert name == "projects/123"

    @pytest.mark.parametrize(
        ("stitch_project_id", "screen_id"),
        [("123", "abc"), ("projects/123", "abc"), ("123", "projects/123/screens/abc")],
    )
    async def test_get_screen(self, stitch_tools, stitch_project_id, screen_id):
        name = await _sent_name(
            stitch_tools, "stitch_get_screen", stitch_project_id=stitch_project_id, screen_id=screen_id
        )
        assert name == "projects/123/screens/abc"
