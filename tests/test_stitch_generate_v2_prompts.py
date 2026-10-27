"""Tests for v6.5.0 F6 — contract-aware prompt resolution in
``stitch_generate_screen_v2``.

The helpers ``_strip_theme_directives`` and ``_resolve_prompt_for_contract``
are pure / async-but-mockable, so we test them directly without standing
up the FastMCP harness.
"""

from __future__ import annotations

import pytest

from server.tools.stitch_v2 import (
    _resolve_prompt_for_contract,
    _strip_theme_directives,
)


class TestStripThemeDirectives:
    def test_strips_hex_color_line(self):
        cleaned, stripped = _strip_theme_directives(
            "Layout: two columns\nUse #0EA5E9 primary"
        )
        assert "Layout: two columns" in cleaned
        assert "Use #0EA5E9" not in cleaned
        assert len(stripped) == 1

    def test_strips_font_family_line(self):
        cleaned, stripped = _strip_theme_directives(
            "Hero with welcome headline\nfont-family: Inter, sans-serif"
        )
        assert "Hero with welcome headline" in cleaned
        assert "font-family" not in cleaned

    def test_strips_font_name_line(self):
        cleaned, _ = _strip_theme_directives(
            "Body text\nUse Playfair Display headings"
        )
        assert "Playfair Display" not in cleaned

    def test_strips_roundness_line(self):
        cleaned, _ = _strip_theme_directives(
            "Cards with stats\nborder-radius: 8px round corners"
        )
        assert "border-radius" not in cleaned

    def test_preserves_pure_layout_prompt(self):
        prompt = "Two-column layout with hero on left and stats on right."
        cleaned, stripped = _strip_theme_directives(prompt)
        assert cleaned == prompt
        assert stripped == []

    def test_handles_empty_prompt(self):
        cleaned, stripped = _strip_theme_directives("")
        assert cleaned == ""
        assert stripped == []


class _FakeClient:
    """Minimal stand-in for StitchClient used in F6 prompt resolution."""

    def __init__(self, *, design_systems=None, raise_on_list=False):
        self._design_systems = design_systems
        self._raise = raise_on_list
        self.list_called = False

    async def list_design_systems(self, project_id):
        self.list_called = True
        if self._raise:
            raise RuntimeError("boom")
        if self._design_systems is None:
            return {}
        return {"designSystems": self._design_systems}


@pytest.mark.asyncio
class TestResolvePromptForContract:
    async def test_inline_prefix_with_design_md_prepends(self):
        client = _FakeClient(design_systems=[])  # not consulted
        prompt = "Login screen with email and password"
        effective, mode, info = await _resolve_prompt_for_contract(
            client,
            "p1",
            prompt,
            contract="inline_prefix_v1",
            design_md_content="DESIGN_MD_CONTENT_HERE",
        )
        assert mode == "inline_prefix"
        assert "DESIGN_MD_CONTENT_HERE" in effective
        assert prompt in effective
        # Legacy contract must not consult list_design_systems.
        assert not client.list_called
        assert info == {}

    async def test_inline_prefix_without_design_md_passes_prompt_as_is(self):
        client = _FakeClient()
        effective, mode, info = await _resolve_prompt_for_contract(
            client,
            "p1",
            "Just the prompt",
            contract="inline_prefix_v1",
            design_md_content=None,
        )
        assert mode == "inline_prefix"
        assert effective == "Just the prompt"

    async def test_native_v2_with_ds_applied_strips_theme_lines(self):
        ds = [{"name": "assets/abc"}]
        client = _FakeClient(design_systems=ds)
        effective, mode, info = await _resolve_prompt_for_contract(
            client,
            "p1",
            "Layout: hero centred\nfont-family: Inter\nUse #0EA5E9 primary",
            contract="native_v2",
            design_md_content=None,
        )
        assert mode == "design_system_applied"
        assert info["count"] == 1
        assert info["first_asset"] == "assets/abc"
        # Theme lines stripped.
        assert "font-family" not in effective
        assert "#0EA5E9" not in effective
        # Layout instructions preserved.
        assert "Layout: hero centred" in effective

    async def test_native_v2_without_ds_falls_back_to_prefix_when_provided(self):
        client = _FakeClient()  # no DS
        effective, mode, info = await _resolve_prompt_for_contract(
            client,
            "p1",
            "screen prompt",
            contract="native_v2",
            design_md_content="DESIGN_MD",
        )
        assert mode == "design_system_missing"
        assert "DESIGN_MD" in effective
        assert "PROVISIONAL" in effective

    async def test_native_v2_without_ds_or_design_md_passes_through(self):
        client = _FakeClient()
        effective, mode, _ = await _resolve_prompt_for_contract(
            client,
            "p1",
            "raw prompt",
            contract="native_v2",
            design_md_content=None,
        )
        assert mode == "design_system_missing"
        assert effective == "raw prompt"

    async def test_native_v2_list_failure_treated_as_no_ds(self):
        client = _FakeClient(raise_on_list=True)
        effective, mode, _ = await _resolve_prompt_for_contract(
            client,
            "p1",
            "prompt",
            contract="native_v2",
            design_md_content=None,
        )
        # An exception during list_design_systems must not break generation.
        assert mode == "design_system_missing"
        assert effective == "prompt"


# ── UC-11302: native_v2 says what it removes, and can keep it ─────────


PROMPT = "Lista de solicitudes con su fecha\nBotón principal en #0EA5E9\nTarjetas con avatar"


async def _generate(tmp_path, monkeypatch, *, design_systems, **kwargs):
    from unittest.mock import AsyncMock

    from fastmcp import FastMCP

    from server.tools import stitch_v2

    sent: list[str] = []

    class _Fake(_FakeClient):
        async def generate_screen_from_text(self, project_id, prompt, *, device_type=None, model_id=None, design_system=None):
            sent.append(prompt)
            return {"outputComponents": []}

    async def _client(*_a, **_k):
        return _Fake(design_systems=design_systems)

    monkeypatch.setattr(stitch_v2, "_v2_get_client", _client)
    mcp = FastMCP("test-uc11302")
    (tmp_path / "state").mkdir()
    stitch_v2.register_stitch_v2_tools(mcp, tmp_path / "state")
    tool = await mcp._get_tool("stitch_generate_screen_v2")
    res = await tool.fn(AsyncMock(), project="p", stitch_project_id="123", prompt=PROMPT, **kwargs)
    return res, sent[0]


@pytest.mark.asyncio
class TestThemeDirectivesAreVisible:
    async def test_with_a_design_system_the_removed_lines_come_back_with_a_notice(self, tmp_path, monkeypatch):
        res, sent = await _generate(tmp_path, monkeypatch, design_systems=[{"name": "assets/9"}])
        assert "#0EA5E9" not in sent
        assert res["design_system_info"]["stripped_lines"] == ["Botón principal en #0EA5E9"]
        assert "keep_theme_directives" in res["prompt_notice"]

    async def test_keep_theme_directives_sends_the_hex_lines(self, tmp_path, monkeypatch):
        res, sent = await _generate(tmp_path, monkeypatch, design_systems=[{"name": "assets/9"}], keep_theme_directives=True)
        assert sent == PROMPT
        assert res["design_system_info"]["stripped_lines"] == []
        assert "prompt_notice" not in res

    async def test_without_a_design_system_every_line_is_sent(self, tmp_path, monkeypatch):
        res, sent = await _generate(tmp_path, monkeypatch, design_systems=None)
        assert sent.splitlines() == PROMPT.splitlines()
        assert res["prompt_mode"] == "design_system_missing"
        assert "prompt_notice" not in res
