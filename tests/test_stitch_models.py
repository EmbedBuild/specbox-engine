"""US-84 · UC-8405 — the default models are the ones Stitch accepts today.

Since 2026-10 the API only takes GEMINI_3_8_FLASH and GEMINI_3_5_FLASH_LITE;
GEMINI_3_PRO, the engine default, answers «invalid argument».
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from fastmcp import FastMCP

import server.tools.stitch as stitch_v1
import server.tools.stitch_v2 as stitch_v2
from server.stitch_client import STITCH_MCP_URL, StitchClient
from server.stitch_enums import (
    DEFAULT_MODEL,
    FALLBACK_MODEL,
    LEGACY_MODELS,
    ModelId,
    UnknownModelError,
    resolve_model,
)
from server.stitch_orchestration.batching import build_site_batched
from server.stitch_orchestration.fallback import generate_screen_with_fallback
from server.stitch_schema import input_schema, load_schema


class TestEnum:
    def test_defaults(self):
        assert DEFAULT_MODEL == "GEMINI_3_8_FLASH"
        assert FALLBACK_MODEL == "GEMINI_3_5_FLASH_LITE"

    def test_enum_is_what_stitch_accepts(self):
        """AC-02 — pinned against the saved schema of every tool that takes a model."""
        schema = load_schema()
        for tool in ("generate_screen_from_text", "edit_screens", "generate_variants"):
            server = set(input_schema(tool, schema)["properties"]["modelId"]["enum"]) - {"MODEL_ID_UNSPECIFIED"}
            assert {m.value for m in ModelId} == server, tool

    def test_legacy_ids_are_not_accepted_any_more(self):
        accepted = {m.value for m in ModelId}
        assert not accepted & set(LEGACY_MODELS)


class TestResolveModel:
    @pytest.mark.parametrize("raw", ["", None, "  "])
    def test_empty_is_the_default(self, raw):
        assert resolve_model(raw) == (DEFAULT_MODEL, None)

    @pytest.mark.parametrize("raw", ["GEMINI_3_8_FLASH", "gemini_3_5_flash_lite"])
    def test_accepted_passes(self, raw):
        assert resolve_model(raw) == (raw.upper(), None)

    @pytest.mark.parametrize(
        ("legacy", "new"),
        [("GEMINI_3_PRO", "GEMINI_3_8_FLASH"), ("GEMINI_3_1_PRO", "GEMINI_3_8_FLASH"), ("GEMINI_3_FLASH", "GEMINI_3_5_FLASH_LITE")],
    )
    def test_legacy_is_translated_and_said(self, legacy, new):
        model, notice = resolve_model(legacy)
        assert model == new
        assert legacy in notice and new in notice and "stitch.modelId" in notice

    def test_unknown_is_rejected_naming_the_accepted(self):
        with pytest.raises(UnknownModelError, match="GEMINI_3_8_FLASH, GEMINI_3_5_FLASH_LITE"):
            resolve_model("GPT_5")


def _ok() -> httpx.Response:
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": "{}"}]}})


@pytest.fixture
def v1_tools(tmp_path: Path, monkeypatch):
    real = StitchClient(api_key="test-api-key-12345678")

    async def _client(*_a, **_k):
        return real

    monkeypatch.setattr(stitch_v1, "get_stitch_client", _client)
    mcp = FastMCP("test-models")
    state = tmp_path / "state"
    state.mkdir()
    stitch_v1.register_stitch_tools(mcp, state)
    return mcp


async def _call(mcp: FastMCP, name: str, **kwargs) -> dict:
    tool = await mcp._get_tool(name)
    return await tool.fn(AsyncMock(), **kwargs)


class TestToolsUseTheNewModels:
    @respx.mock
    async def test_generate_screen_defaults_to_flash(self, v1_tools):
        route = respx.post(STITCH_MCP_URL).mock(return_value=_ok())
        res = await _call(v1_tools, "stitch_generate_screen", project="p", stitch_project_id="1", prompt="A list")
        assert json.loads(route.calls[0].request.content)["params"]["arguments"]["modelId"] == DEFAULT_MODEL
        assert res["model_used"] == DEFAULT_MODEL and "model_notice" not in res

    @respx.mock
    async def test_legacy_model_in_settings_keeps_generating(self, v1_tools):
        """AC-03 — a project still configured with GEMINI_3_PRO generates with the new model."""
        route = respx.post(STITCH_MCP_URL).mock(return_value=_ok())
        res = await _call(
            v1_tools, "stitch_generate_screen", project="p", stitch_project_id="1", prompt="A list", model_id="GEMINI_3_PRO"
        )
        assert res["status"] == "ok"
        assert json.loads(route.calls[0].request.content)["params"]["arguments"]["modelId"] == "GEMINI_3_8_FLASH"
        assert "GEMINI_3_PRO" in res["model_notice"]

    @respx.mock
    async def test_unknown_model_never_reaches_stitch(self, v1_tools):
        """AC-02 — rejected before calling Stitch."""
        route = respx.post(STITCH_MCP_URL).mock(return_value=_ok())
        res = await _call(
            v1_tools, "stitch_generate_screen", project="p", stitch_project_id="1", prompt="A list", model_id="GPT_5"
        )
        assert "Unknown Stitch model" in res["error"] and "status" not in res
        assert not route.called

    @respx.mock
    async def test_edit_screen_defaults_to_flash(self, v1_tools):
        route = respx.post(STITCH_MCP_URL).mock(return_value=_ok())
        res = await _call(v1_tools, "stitch_edit_screen", project="p", stitch_project_id="1", screen_id="s", prompt="Blue")
        assert json.loads(route.calls[0].request.content)["params"]["arguments"]["modelId"] == DEFAULT_MODEL
        assert res["model_used"] == DEFAULT_MODEL


class _FakeStitch:
    def __init__(self):
        self.models: list[str] = []

    async def list_design_systems(self, project_id):
        return []

    async def generate_screen_from_text(self, project_id, prompt, *, device_type=None, model_id=None):
        self.models.append(model_id)
        return {"screen": {"id": "s1"}}


@pytest.fixture
def v2_tools(tmp_path: Path, monkeypatch):
    fake = _FakeStitch()

    async def _client(*_a, **_k):
        return fake

    monkeypatch.setattr(stitch_v2, "_v2_get_client", _client)
    mcp = FastMCP("test-models-v2")
    state = tmp_path / "state"
    state.mkdir()
    stitch_v2.register_stitch_v2_tools(mcp, state)
    return mcp, fake


class TestGenerateScreenV2:
    async def test_default_model(self, v2_tools):
        mcp, fake = v2_tools
        res = await _call(mcp, "stitch_generate_screen_v2", project="p", stitch_project_id="1", prompt="A list")
        assert res["status"] == "ok" and res["model_used"] == DEFAULT_MODEL
        assert fake.models == [DEFAULT_MODEL]

    async def test_legacy_model_is_translated(self, v2_tools):
        mcp, fake = v2_tools
        res = await _call(
            mcp, "stitch_generate_screen_v2", project="p", stitch_project_id="1", prompt="A list", model_id="GEMINI_3_1_PRO"
        )
        assert fake.models == ["GEMINI_3_8_FLASH"] and "GEMINI_3_1_PRO" in res["model_notice"]

    async def test_unknown_model_is_rejected(self, v2_tools):
        mcp, fake = v2_tools
        res = await _call(mcp, "stitch_generate_screen_v2", project="p", stitch_project_id="1", prompt="A list", model_id="X")
        assert "Unknown Stitch model" in res["error"] and fake.models == []


class _FailsFirst:
    def __init__(self):
        self.models: list[str] = []

    async def generate_screen(self, project_id, prompt, *, device_type="DESKTOP", model_id=DEFAULT_MODEL):
        self.models.append(model_id)
        if len(self.models) == 1:
            raise RuntimeError("Request contains an invalid argument.")
        return {"screen": {"id": "s2"}}

    async def edit_screens(self, *a, **k):  # pragma: no cover — no baseline in these tests
        raise AssertionError

    async def generate_variants(self, *a, **k):  # pragma: no cover
        raise AssertionError


class TestFallbackModel:
    """AC-01 — GEMINI_3_5_FLASH_LITE is the model of the fallback chain."""

    async def test_ladder_uses_the_fallback_model_and_says_so(self):
        ops = _FailsFirst()
        res = await generate_screen_with_fallback(ops, "1", "A list")
        assert ops.models == [DEFAULT_MODEL, FALLBACK_MODEL]
        assert res.model_used == FALLBACK_MODEL
        assert res.degraded is True and res.degraded_reason == "fallback_model"

    def test_defaults_in_signatures(self):
        sig = inspect.signature(generate_screen_with_fallback).parameters
        assert sig["model_id"].default == DEFAULT_MODEL
        assert sig["fallback_model_id"].default == FALLBACK_MODEL
        assert inspect.signature(build_site_batched).parameters["model_id"].default == DEFAULT_MODEL
        assert inspect.signature(StitchClient.generate_screen_from_text).parameters["model_id"].default == DEFAULT_MODEL
