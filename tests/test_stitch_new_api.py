"""US-85 · UC-8501 — global design systems, the design system when generating, shared projects."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from fastmcp import FastMCP

import server.stitch_client as stitch_client_module
import server.tools.stitch as stitch_v1
import server.tools.stitch_v2 as stitch_v2
from server.stitch_client import STITCH_MCP_URL, StitchClient, StitchClientError

THEME = {"colorMode": "LIGHT", "headlineFont": "INTER", "bodyFont": "INTER", "roundness": "ROUND_FOUR", "customColor": "#16130F"}


def _text(payload) -> httpx.Response:
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": json.dumps(payload)}]}})


def _calls(route) -> list[dict]:
    return [json.loads(c.request.content)["params"] for c in route.calls]


@pytest.fixture
def v1(tmp_path: Path, monkeypatch):
    real = StitchClient(api_key="test-api-key-12345678")

    async def _client(*_a, **_k):
        return real

    monkeypatch.setattr(stitch_v1, "get_stitch_client", _client)
    mcp = FastMCP("test-new-api")
    state = tmp_path / "state"
    state.mkdir()
    stitch_v1.register_stitch_tools(mcp, state)
    return mcp


async def _call(mcp: FastMCP, name: str, **kwargs) -> dict:
    tool = await mcp._get_tool(name)
    return await tool.fn(AsyncMock(), project="p", **kwargs)


class TestDesignSystemWhenGenerating:
    """AC-01."""

    @respx.mock
    async def test_v1_sends_the_project_design_system(self, v1):
        route = respx.post(STITCH_MCP_URL).mock(
            side_effect=[_text({"designSystems": [{"name": "assets/9", "designSystem": {"displayName": "Tinta"}}]}), _text({})]
        )
        res = await _call(v1, "stitch_generate_screen", stitch_project_id="123", prompt="A list")
        first, second = _calls(route)
        assert first == {"name": "list_design_systems", "arguments": {"projectId": "123"}}
        assert second["arguments"]["designSystem"] == "assets/9"
        assert res["design_system_used"] == "assets/9"

    @respx.mock
    async def test_v1_explicit_design_system_wins(self, v1):
        route = respx.post(STITCH_MCP_URL).mock(return_value=_text({}))
        await _call(v1, "stitch_generate_screen", stitch_project_id="123", prompt="A list", design_system="7")
        calls = _calls(route)
        assert [c["name"] for c in calls] == ["generate_screen_from_text"]
        assert calls[0]["arguments"]["designSystem"] == "assets/7"

    @respx.mock
    async def test_v1_without_design_system_sends_none(self, v1):
        route = respx.post(STITCH_MCP_URL).mock(side_effect=[_text({}), _text({})])
        res = await _call(v1, "stitch_generate_screen", stitch_project_id="123", prompt="A list")
        assert "designSystem" not in _calls(route)[1]["arguments"] and res["design_system_used"] is None

    async def test_v2_sends_the_design_system_it_detects(self, tmp_path, monkeypatch):
        seen: list = []

        class _Fake:
            async def list_design_systems(self, project_id):
                return {"designSystems": [{"name": "assets/9"}]}

            async def generate_screen_from_text(self, project_id, prompt, *, device_type=None, model_id=None, design_system=None):
                seen.append(design_system)
                return {"outputComponents": []}

        async def _client(*_a, **_k):
            return _Fake()

        monkeypatch.setattr(stitch_v2, "_v2_get_client", _client)
        mcp = FastMCP("test-v2-ds")
        state = tmp_path / "state"
        state.mkdir()
        stitch_v2.register_stitch_v2_tools(mcp, state)
        res = await _call(mcp, "stitch_generate_screen_v2", stitch_project_id="123", prompt="A list #0EA5E9 buttons")
        assert seen == ["assets/9"]
        assert res["prompt_mode"] == "design_system_applied" and res["design_system_used"] == "assets/9"


class TestGlobalDesignSystems:
    """AC-02."""

    @respx.mock
    async def test_create_without_project(self, v1):
        route = respx.post(STITCH_MCP_URL).mock(return_value=_text({"name": "assets/1"}))
        res = await _call(v1, "stitch_create_design_system", display_name="Tinta", theme=THEME)
        assert res["status"] == "ok"
        assert _calls(route)[0]["arguments"] == {"designSystem": {"displayName": "Tinta", "theme": THEME}}

    @respx.mock
    async def test_list_without_project(self, v1):
        route = respx.post(STITCH_MCP_URL).mock(return_value=_text({"designSystems": []}))
        await _call(v1, "stitch_list_design_systems")
        assert _calls(route)[0] == {"name": "list_design_systems", "arguments": {}}


class TestSharedProjects:
    """AC-03."""

    @respx.mock
    async def test_view_shared(self, v1):
        route = respx.post(STITCH_MCP_URL).mock(return_value=_text({"projects": []}))
        await _call(v1, "stitch_list_projects", view="shared")
        assert _calls(route)[0]["arguments"] == {"filter": "view=shared"}

    async def test_unknown_view_is_rejected(self):
        client = StitchClient(api_key="test-api-key-12345678")
        with pytest.raises(StitchClientError, match="owned"):
            await client.list_projects("everything")
        await client.close()


class TestDeleteProjectIsNotExposed:
    """AC-04."""

    async def test_no_wrapper_and_no_tool(self, v1):
        assert not hasattr(StitchClient, "delete_project")
        assert not any("delete_project" in t.name for t in await v1.list_tools())

    def test_the_client_says_why(self):
        doc = inspect.getdoc(stitch_client_module)
        assert "delete_project" in doc and "irreversible" in doc
