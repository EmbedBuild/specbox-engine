"""US-84 · UC-8401 — a Stitch failure reaches the caller as an error, not as ok.

Stitch answers a rejected call with HTTP 200, ``isError: true`` and a single
text. The client used to return ``{"text": ...}`` and every tool wrapped it in
``status: ok``, so six tools failed in silence.
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
from server.stitch_client import STITCH_MCP_URL, StitchClient, StitchClientError

INVALID = "Request contains an invalid argument."


def _rpc(result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": "x", "result": result}


def _stitch_rejects() -> httpx.Response:
    """The real answer of the API to a call with a wrong argument (2026-10-05)."""
    return httpx.Response(
        200,
        json=_rpc({"content": [{"type": "text", "text": INVALID}], "isError": True}),
    )


@pytest.fixture
def client():
    return StitchClient(api_key="test-api-key-12345678")


class TestClientRaises:
    @respx.mock
    async def test_is_error_raises_with_the_stitch_text(self, client):
        respx.post(STITCH_MCP_URL).mock(return_value=_stitch_rejects())
        with pytest.raises(StitchClientError) as err:
            await client.list_projects()
        assert str(err.value) == INVALID
        assert err.value.data["isError"] is True
        await client.close()

    @respx.mock
    async def test_is_error_over_sse_raises(self, client):
        body = "data: " + json.dumps(
            _rpc({"content": [{"type": "text", "text": INVALID}], "isError": True})
        ) + "\n\n"
        respx.post(STITCH_MCP_URL).mock(
            return_value=httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
        )
        with pytest.raises(StitchClientError, match="invalid argument"):
            await client.list_projects()
        await client.close()

    @respx.mock
    async def test_is_error_without_text_still_raises(self, client):
        respx.post(STITCH_MCP_URL).mock(
            return_value=httpx.Response(200, json=_rpc({"content": [], "isError": True}))
        )
        with pytest.raises(StitchClientError, match="without a message"):
            await client.list_projects()
        await client.close()


class TestCorrectAnswersUnchanged:
    """AC-03 — a correct single text comes back exactly as before."""

    @respx.mock
    async def test_json_text_is_parsed(self, client):
        respx.post(STITCH_MCP_URL).mock(
            return_value=httpx.Response(200, json=_rpc({"content": [{"type": "text", "text": '{"projects": []}'}]}))
        )
        assert await client.list_projects() == {"projects": []}
        await client.close()

    @respx.mock
    async def test_plain_text_is_wrapped(self, client):
        respx.post(STITCH_MCP_URL).mock(
            return_value=httpx.Response(200, json=_rpc({"content": [{"type": "text", "text": "hola"}], "isError": False}))
        )
        assert await client.list_projects() == {"text": "hola"}
        await client.close()

    @respx.mock
    async def test_several_items_keep_their_shape(self, client):
        content = [{"type": "text", "text": "a"}, {"type": "image", "data": "b64"}]
        respx.post(STITCH_MCP_URL).mock(return_value=httpx.Response(200, json=_rpc({"content": content})))
        assert await client.list_projects() == {"content": content, "isError": False}
        await client.close()


@pytest.fixture
def stitch_tools(tmp_path: Path, monkeypatch):
    real = StitchClient(api_key="test-api-key-12345678")

    async def _client(*_args, **_kwargs):
        return real

    monkeypatch.setattr(stitch_v1, "get_stitch_client", _client)
    mcp = FastMCP("test-stitch-is-error")
    state = tmp_path / "state"
    state.mkdir()
    stitch_v1.register_stitch_tools(mcp, state)
    return mcp


async def _call(mcp: FastMCP, name: str, **kwargs) -> dict:
    tool = await mcp._get_tool(name)
    return await tool.fn(AsyncMock(), **kwargs)


class TestToolAnswersError:
    """AC-01 / AC-02 — the engine tool answers with ``error`` and never ``status: ok``."""

    @pytest.mark.parametrize(
        ("tool", "kwargs"),
        [
            ("stitch_list_projects", {}),
            ("stitch_get_project", {"stitch_project_id": "123"}),
            ("stitch_list_design_systems", {"stitch_project_id": "123"}),
        ],
    )
    @respx.mock
    async def test_tool_returns_error(self, stitch_tools, tool, kwargs):
        respx.post(STITCH_MCP_URL).mock(return_value=_stitch_rejects())
        res = await _call(stitch_tools, tool, project="p", **kwargs)
        assert res["error"] == INVALID
        assert "status" not in res
