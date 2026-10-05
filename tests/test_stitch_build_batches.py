"""US-84 · UC-8504 — the batched build tool says when a screen failed.

stitch_build_site_batched_v2 used to call a build_site the adapter never had:
every batch failed and the tool still answered status ok.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from fastmcp import FastMCP

import server.tools.stitch_v2 as stitch_v2
from server.stitch_client import STITCH_MCP_URL, StitchClient


def _generated(screen_id: str) -> httpx.Response:
    payload = {"outputComponents": [{"design": {"screens": [{"name": f"projects/123/screens/{screen_id}"}]}}]}
    return httpx.Response(
        200, json={"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": json.dumps(payload)}]}}
    )


def _rejected() -> httpx.Response:
    return httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": "x", "result": {"isError": True, "content": [{"type": "text", "text": "Request contains an invalid argument."}]}},
    )


@pytest.fixture
def tool(tmp_path: Path, monkeypatch):
    real = StitchClient(api_key="test-api-key-12345678")

    async def _client(*_a, **_k):
        return real

    monkeypatch.setattr(stitch_v2, "_v2_get_client", _client)
    mcp = FastMCP("test-build-batches")
    state = tmp_path / "state"
    state.mkdir()
    stitch_v2.register_stitch_v2_tools(mcp, state)
    return mcp


async def _build(mcp: FastMCP, screens: list[dict]) -> dict:
    t = await mcp._get_tool("stitch_build_site_batched_v2")
    return await t.fn(AsyncMock(), project="p", stitch_project_id="123", screens=screens)


@respx.mock
async def test_all_screens_generated_is_ok(tool):
    route = respx.post(STITCH_MCP_URL).mock(side_effect=[_generated("a"), _generated("b")])
    res = await _build(tool, [{"name": "home", "prompt": "Home"}, {"name": "list", "prompt": "List"}])
    assert res["status"] == "ok" and res["generated_screen_ids"] == ["a", "b"]
    sent = [json.loads(c.request.content)["params"] for c in route.calls]
    assert [s["name"] for s in sent] == ["generate_screen_from_text", "generate_screen_from_text"]
    assert [s["arguments"]["prompt"] for s in sent] == ["Home", "List"]


@respx.mock
async def test_a_failed_screen_is_not_ok(tool):
    respx.post(STITCH_MCP_URL).mock(side_effect=[_rejected(), _generated("b")])
    res = await _build(tool, [{"name": "home", "prompt": "Home"}, {"name": "list", "prompt": "List"}])
    assert res["status"] == "error"
    assert res["error"] == "home: Request contains an invalid argument."
    assert res["failed_screens"][0]["name"] == "home" and res["generated_screen_ids"] == ["b"]
