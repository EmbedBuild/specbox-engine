"""US-84 · UC-8406 — a screen's HTML and screenshot come from the URLs of get_screen.

Stitch has no ``fetch_screen_code`` nor ``fetch_screen_image`` tool (rpc
-32602 «Tools Call name is not found»); ``get_screen`` returns
``htmlCode.downloadUrl`` and ``screenshot.downloadUrl``.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from fastmcp import FastMCP

import server.tools.stitch as stitch_v1
from server.stitch_client import STITCH_MCP_URL, StitchClient, StitchClientError

HTML_URL = "https://contribution.usercontent.google.com/download?c=abc"
PNG_URL = "https://lh3.googleusercontent.com/aida/xyz"
PNG = b"\x89PNG\r\n\x1a\nfake"
SCREEN = {
    "name": "projects/123/screens/abc",
    "title": "Cita confirmada",
    "htmlCode": {"downloadUrl": HTML_URL, "mimeType": "text/html"},
    "screenshot": {"downloadUrl": PNG_URL},
}


def _rpc(payload) -> httpx.Response:
    return httpx.Response(
        200, json={"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": json.dumps(payload)}]}}
    )


@pytest.fixture
def client():
    return StitchClient(api_key="test-api-key-12345678")


class TestClient:
    @respx.mock
    async def test_code_comes_from_the_html_url(self, client):
        """AC-01."""
        api = respx.post(STITCH_MCP_URL).mock(return_value=_rpc(SCREEN))
        dl = respx.get(HTML_URL).mock(return_value=httpx.Response(200, text="<!DOCTYPE html><html></html>"))
        res = await client.fetch_screen_code("123", "abc")
        assert res["html"].startswith("<!DOCTYPE html>")
        assert res["screen"] == "projects/123/screens/abc" and res["downloadUrl"] == HTML_URL
        assert [json.loads(c.request.content)["params"]["name"] for c in api.calls] == ["get_screen"]
        assert "x-goog-api-key" not in dl.calls[0].request.headers
        await client.close()

    @respx.mock
    async def test_image_comes_from_the_screenshot_url(self, client):
        """AC-02."""
        respx.post(STITCH_MCP_URL).mock(return_value=_rpc(SCREEN))
        dl = respx.get(PNG_URL).mock(return_value=httpx.Response(200, content=PNG, headers={"content-type": "image/png"}))
        res = await client.fetch_screen_image("123", "abc")
        assert base64.b64decode(res["image_base64"]) == PNG
        assert res["mime_type"] == "image/png"
        assert "x-goog-api-key" not in dl.calls[0].request.headers
        await client.close()

    @respx.mock
    async def test_screen_without_html(self, client):
        respx.post(STITCH_MCP_URL).mock(return_value=_rpc({"name": "projects/123/screens/abc", "screenshot": {}}))
        with pytest.raises(StitchClientError, match="no htmlCode.downloadUrl"):
            await client.fetch_screen_code("123", "abc")
        await client.close()

    @respx.mock
    async def test_failed_download_is_an_error(self, client):
        respx.post(STITCH_MCP_URL).mock(return_value=_rpc(SCREEN))
        respx.get(HTML_URL).mock(return_value=httpx.Response(403, text="expired"))
        with pytest.raises(StitchClientError, match="Download failed 403"):
            await client.fetch_screen_code("123", "abc")
        await client.close()


@pytest.fixture
def tools(tmp_path: Path, monkeypatch):
    real = StitchClient(api_key="test-api-key-12345678")

    async def _client(*_a, **_k):
        return real

    monkeypatch.setattr(stitch_v1, "get_stitch_client", _client)
    mcp = FastMCP("test-fetch")
    state = tmp_path / "state"
    state.mkdir()
    stitch_v1.register_stitch_tools(mcp, state)
    return mcp


class TestTools:
    @respx.mock
    async def test_fetch_screen_code_tool(self, tools):
        respx.post(STITCH_MCP_URL).mock(return_value=_rpc(SCREEN))
        respx.get(HTML_URL).mock(return_value=httpx.Response(200, text="<html>hola</html>"))
        tool = await tools._get_tool("stitch_fetch_screen_code")
        res = await tool.fn(AsyncMock(), project="p", stitch_project_id="123", screen_id="abc")
        assert res["status"] == "ok" and res["result"]["html"] == "<html>hola</html>"
        assert res["design_role"] == "candidate"
