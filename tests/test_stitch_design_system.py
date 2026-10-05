"""US-84 · UC-8403 — creating a design system sends designSystem with its whole theme.

The API asks ``create_design_system`` for ``designSystem: {displayName, theme}``
with colorMode, headlineFont, bodyFont, roundness and customColor; the engine
sent ``{projectId, displayName}``. ``update_design_system`` built the theme
but left out ``displayName``, which the API also requires.
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
from server.stitch_client import (
    REQUIRED_THEME_FIELDS,
    STITCH_MCP_URL,
    StitchClient,
    StitchClientError,
    design_system_payload,
)

THEME = {
    "colorMode": "LIGHT",
    "headlineFont": "IBM_PLEX_SANS",
    "bodyFont": "IBM_PLEX_SANS",
    "roundness": "ROUND_FOUR",
    "customColor": "#16130F",
}


def _text(payload) -> httpx.Response:
    return httpx.Response(
        200, json={"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": json.dumps(payload)}]}}
    )


class TestPayload:
    def test_full_payload(self):
        assert design_system_payload(" Tinta ", THEME) == {"displayName": "Tinta", "theme": THEME}

    @pytest.mark.parametrize("field", REQUIRED_THEME_FIELDS)
    def test_missing_field_is_named(self, field):
        theme = {k: v for k, v in THEME.items() if k != field}
        with pytest.raises(StitchClientError, match=field):
            design_system_payload("Tinta", theme)

    def test_name_is_required(self):
        with pytest.raises(StitchClientError, match="displayName"):
            design_system_payload("", THEME)

    def test_legacy_font_is_rejected(self):
        with pytest.raises(StitchClientError, match="legacy"):
            design_system_payload("Tinta", {**THEME, "font": "INTER"})


@pytest.fixture
def tools(tmp_path: Path, monkeypatch):
    real = StitchClient(api_key="test-api-key-12345678")

    async def _client(*_a, **_k):
        return real

    monkeypatch.setattr(stitch_v1, "get_stitch_client", _client)
    mcp = FastMCP("test-design-system")
    state = tmp_path / "state"
    state.mkdir()
    stitch_v1.register_stitch_tools(mcp, state)
    return mcp


async def _call(mcp: FastMCP, name: str, **kwargs) -> dict:
    tool = await mcp._get_tool(name)
    return await tool.fn(AsyncMock(), project="p", **kwargs)


class TestCreate:
    @respx.mock
    async def test_sends_design_system_with_its_theme(self, tools):
        """AC-01."""
        route = respx.post(STITCH_MCP_URL).mock(return_value=_text({"name": "assets/9"}))
        res = await _call(tools, "stitch_create_design_system", stitch_project_id="123", display_name="Tinta", theme=THEME)
        assert res["status"] == "ok"
        args = json.loads(route.calls[0].request.content)["params"]["arguments"]
        assert args == {"designSystem": {"displayName": "Tinta", "theme": THEME}, "projectId": "123"}

    @respx.mock
    @pytest.mark.parametrize("field", REQUIRED_THEME_FIELDS)
    async def test_missing_field_is_named_before_calling_stitch(self, tools, field):
        """AC-02."""
        route = respx.post(STITCH_MCP_URL).mock(return_value=_text({}))
        theme = {k: v for k, v in THEME.items() if k != field}
        res = await _call(tools, "stitch_create_design_system", stitch_project_id="123", display_name="Tinta", theme=theme)
        assert field in res["error"] and "status" not in res
        assert not route.called

    @respx.mock
    async def test_without_theme(self, tools):
        route = respx.post(STITCH_MCP_URL).mock(return_value=_text({}))
        res = await _call(tools, "stitch_create_design_system", stitch_project_id="123", display_name="Tinta")
        assert "colorMode" in res["error"] and not route.called


class TestUpdateAlwaysSendsTheName:
    """AC-03."""

    @respx.mock
    async def test_reuses_the_current_name(self, tools):
        listed = {"designSystems": [
            {"name": "assets/7", "designSystem": {"displayName": "Otro"}},
            {"name": "assets/9", "designSystem": {"displayName": "Tinta"}},
        ]}
        route = respx.post(STITCH_MCP_URL).mock(side_effect=[_text(listed), _text({"name": "assets/9"})])
        res = await _call(tools, "stitch_update_design_system", stitch_project_id="123", asset_name="assets/9", theme=THEME)
        assert res["status"] == "ok", res
        first, second = (json.loads(c.request.content)["params"] for c in route.calls)
        assert first == {"name": "list_design_systems", "arguments": {"projectId": "123"}}
        assert second["name"] == "update_design_system"
        assert second["arguments"]["designSystem"] == {"displayName": "Tinta", "theme": THEME}

    @respx.mock
    async def test_given_name_is_sent_without_looking_it_up(self, tools):
        route = respx.post(STITCH_MCP_URL).mock(return_value=_text({"name": "assets/9"}))
        await _call(
            tools, "stitch_update_design_system", stitch_project_id="123", asset_name="assets/9", theme=THEME,
            display_name="Tinta 2.2",
        )
        assert len(route.calls) == 1
        args = json.loads(route.calls[0].request.content)["params"]["arguments"]
        assert args["designSystem"]["displayName"] == "Tinta 2.2"

    @respx.mock
    async def test_unknown_asset_asks_for_the_name(self, tools):
        respx.post(STITCH_MCP_URL).mock(return_value=_text({"designSystems": []}))
        res = await _call(tools, "stitch_update_design_system", stitch_project_id="123", asset_name="assets/9", theme=THEME)
        assert "pass display_name" in res["error"]

    @respx.mock
    async def test_incomplete_theme_never_reaches_stitch(self, tools):
        route = respx.post(STITCH_MCP_URL).mock(return_value=_text({}))
        res = await _call(
            tools, "stitch_update_design_system", stitch_project_id="123", asset_name="assets/9",
            theme={"colorMode": "LIGHT"}, display_name="Tinta",
        )
        assert "headlineFont" in res["error"] and not route.called
