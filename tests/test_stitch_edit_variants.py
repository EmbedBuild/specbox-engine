"""US-84 · UC-8404 — edit and variants with the shape the API asks for today.

``edit_screens`` and ``generate_variants`` sent ``screenId``; the API asks for
the list ``selectedScreenIds``. Variants also sent ``variantCount``,
``creativeRange`` and ``aspects`` loose instead of inside ``variantOptions``,
and left ``prompt`` optional when it is required.
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
from server.stitch_client import STITCH_MCP_URL, StitchClient, StitchClientError, screen_ids_for
from server.stitch_enums import DEFAULT_MODEL, FALLBACK_MODEL
from server.stitch_orchestration.fallback import FallbackStrategy, generate_screen_with_fallback
from server.tools.stitch_v2 import _StitchOpsAdapter


def _ok(payload=None) -> httpx.Response:
    return httpx.Response(
        200, json={"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": json.dumps(payload or {})}]}}
    )


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("abc", ["abc"]),
        ("abc, def", ["abc", "def"]),
        (["abc", "screens/def"], ["abc", "def"]),
        ("projects/1/screens/abc", ["abc"]),
    ],
)
def test_screen_ids_for(given, expected):
    assert screen_ids_for(given) == expected


def test_screen_ids_cannot_be_empty():
    with pytest.raises(StitchClientError, match="at least one"):
        screen_ids_for(" , ")


@pytest.fixture
def tools(tmp_path: Path, monkeypatch):
    real = StitchClient(api_key="test-api-key-12345678")

    async def _client(*_a, **_k):
        return real

    monkeypatch.setattr(stitch_v1, "get_stitch_client", _client)
    mcp = FastMCP("test-edit-variants")
    state = tmp_path / "state"
    state.mkdir()
    stitch_v1.register_stitch_tools(mcp, state)
    return mcp


async def _call(mcp: FastMCP, name: str, **kwargs) -> dict:
    tool = await mcp._get_tool(name)
    return await tool.fn(AsyncMock(), project="p", stitch_project_id="123", **kwargs)


def _sent(route) -> dict:
    return json.loads(route.calls[0].request.content)["params"]["arguments"]


class TestEdit:
    """AC-01."""

    @respx.mock
    async def test_one_screen(self, tools):
        route = respx.post(STITCH_MCP_URL).mock(return_value=_ok())
        res = await _call(tools, "stitch_edit_screen", screen_id="abc", prompt="Blue button")
        assert res["status"] == "ok"
        assert _sent(route) == {
            "projectId": "123", "selectedScreenIds": ["abc"], "prompt": "Blue button", "modelId": DEFAULT_MODEL,
        }

    @respx.mock
    async def test_several_screens(self, tools):
        route = respx.post(STITCH_MCP_URL).mock(return_value=_ok())
        await _call(tools, "stitch_edit_screen", screen_id="abc,def", prompt="Same header")
        assert _sent(route)["selectedScreenIds"] == ["abc", "def"]


class TestVariants:
    @respx.mock
    async def test_payload(self, tools):
        """AC-02."""
        route = respx.post(STITCH_MCP_URL).mock(return_value=_ok())
        res = await _call(
            tools, "stitch_generate_variants", screen_id="abc", prompt="Warmer", variant_count=1,
            creative_range="REFINE", aspects="layout, color_scheme", device_type="MOBILE",
            model_id="GEMINI_3_5_FLASH_LITE",
        )
        assert res["status"] == "ok" and res["model_used"] == "GEMINI_3_5_FLASH_LITE"
        assert _sent(route) == {
            "projectId": "123",
            "selectedScreenIds": ["abc"],
            "prompt": "Warmer",
            "variantOptions": {"variantCount": 1, "creativeRange": "REFINE", "aspects": ["LAYOUT", "COLOR_SCHEME"]},
            "deviceType": "MOBILE",
            "modelId": "GEMINI_3_5_FLASH_LITE",
        }

    @respx.mock
    async def test_without_prompt_never_reaches_stitch(self, tools):
        """AC-03."""
        route = respx.post(STITCH_MCP_URL).mock(return_value=_ok())
        res = await _call(tools, "stitch_generate_variants", screen_id="abc")
        assert "needs a prompt" in res["error"] and "status" not in res
        assert not route.called

    @respx.mock
    async def test_count_out_of_range(self, tools):
        route = respx.post(STITCH_MCP_URL).mock(return_value=_ok())
        res = await _call(tools, "stitch_generate_variants", screen_id="abc", prompt="x", variant_count=9)
        assert "between 1 and 5" in res["error"] and not route.called


class _Recorder:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def generate_screen(self, project_id, prompt, *, device_type="DESKTOP", model_id=None):
        self.calls.append(("generate_screen", {"model_id": model_id}))
        raise RuntimeError("Request contains an invalid argument.")

    async def edit_screens(self, project_id, screen_id, prompt, *, device_type=None, model_id=None):
        self.calls.append(("edit_screens", {"screen_id": screen_id, "model_id": model_id}))
        raise RuntimeError("Request contains an invalid argument.")

    async def generate_variants(self, project_id, screen_id, **kwargs):
        self.calls.append(("generate_variants", {"screen_id": screen_id, **kwargs}))
        return {"screens": [{"id": "v"}]}


class TestAdapterAndFallback:
    """AC-04."""

    @respx.mock
    async def test_adapter_sends_the_new_shapes(self):
        route = respx.post(STITCH_MCP_URL).mock(side_effect=[_ok(), _ok()])
        client = StitchClient(api_key="test-api-key-12345678")
        ops = _StitchOpsAdapter(client)
        await ops.edit_screens("123", "abc", "Blue", model_id=DEFAULT_MODEL)
        await ops.generate_variants("123", "abc", prompt="Warmer", model_id=FALLBACK_MODEL)
        edit, variants = (json.loads(c.request.content)["params"]["arguments"] for c in route.calls)
        assert edit["selectedScreenIds"] == ["abc"]
        assert variants["selectedScreenIds"] == ["abc"]
        assert variants["variantOptions"] == {"variantCount": 1, "creativeRange": "REFINE"}
        assert variants["modelId"] == FALLBACK_MODEL
        await client.close()

    async def test_ladder_varies_the_baseline_with_the_fallback_model(self):
        ops = _Recorder()
        res = await generate_screen_with_fallback(
            ops, "123", "A list", baseline_screen_id="base",
            fallback_strategy=[FallbackStrategy.EDIT_BASELINE, FallbackStrategy.VARIANTS_REFINE],
        )
        assert [name for name, _ in ops.calls] == ["generate_screen", "edit_screens", "generate_variants"]
        variants = ops.calls[-1][1]
        assert variants["screen_id"] == "base" and variants["prompt"] == "A list"
        assert variants["model_id"] == FALLBACK_MODEL
        assert res.final_strategy == "variants_refine" and res.model_used == FALLBACK_MODEL
