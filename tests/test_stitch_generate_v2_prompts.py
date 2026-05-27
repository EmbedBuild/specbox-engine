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
