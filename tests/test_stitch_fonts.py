"""US-84 · UC-8407 — fonts and corner sizes match the ones the API has today."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from server.design_md import material3_view
from server.stitch_client import STITCH_MCP_URL, StitchClient
from server.stitch_enums import (
    DEPRECATED_FONTS,
    DEPRECATED_ROUNDNESS,
    Roundness,
    StitchFont,
    current_theme,
)
from server.stitch_schema import load_schema

THEME = {
    "colorMode": "LIGHT",
    "headlineFont": "SOURCE_SERIF_FOUR",
    "bodyFont": "SOURCE_SANS_THREE",
    "labelFont": "INTER",
    "roundness": "ROUND_EIGHT",
    "customColor": "#16130F",
}


def test_new_fonts_are_in_the_enum():
    """AC-01."""
    assert {"SOURCE_SERIF_4", "SOURCE_SANS_3", "METROPHOBIC"} <= {f.value for f in StitchFont}


def test_deprecations_are_the_ones_the_api_declares():
    """AC-02 — pinned against «Deprecated» / «Unused» in the saved schema."""
    schema = load_schema()
    tool = next(t for t in schema["tools"] if t["name"] == "create_design_system")
    props = tool["inputSchema"]["$defs"]["DesignTheme"]["properties"]
    fonts = dict(zip(props["headlineFont"]["enum"], props["headlineFont"]["x-google-enum-descriptions"]))
    assert {f for f, d in fonts.items() if "Deprecated" in d} == set(DEPRECATED_FONTS)
    rounds = dict(zip(props["roundness"]["enum"], props["roundness"]["x-google-enum-descriptions"]))
    assert {r for r, d in rounds.items() if "Unused" in d} == set(DEPRECATED_ROUNDNESS)


def test_the_mapper_never_produces_a_deprecated_value():
    """AC-02 — the DESIGN.md → Material 3 view."""
    produced_fonts = {f.value for f in material3_view._FAMILY_TO_FONT.values()}
    assert not produced_fonts & set(DEPRECATED_FONTS)
    produced_rounds = {r.value for r in material3_view._ROUNDED_TO_ENUM.values()}
    assert not produced_rounds & DEPRECATED_ROUNDNESS
    assert material3_view._ROUNDED_TO_ENUM["2px"] == Roundness.ROUND_FOUR
    assert material3_view._FAMILY_TO_FONT["source sans 3"] == StitchFont.SOURCE_SANS_3


def test_visual_setup_does_not_offer_them():
    """AC-02 — the font tables of /visual-setup."""
    from pathlib import Path

    skill = (Path(__file__).resolve().parents[1] / ".claude/skills/visual-setup/SKILL.md").read_text()
    for value in (*DEPRECATED_FONTS, *DEPRECATED_ROUNDNESS):
        assert f"| {value} " not in skill and f"| {value} |" not in skill, value


def test_current_theme_renames_the_deprecated_fonts():
    out = current_theme(THEME)
    assert out["headlineFont"] == "SOURCE_SERIF_4" and out["bodyFont"] == "SOURCE_SANS_3"
    assert out["labelFont"] == "INTER" and THEME["headlineFont"] == "SOURCE_SERIF_FOUR"


@respx.mock
async def test_theme_is_sent_with_the_new_names():
    """AC-03."""
    route = respx.post(STITCH_MCP_URL).mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": "{}"}]}})
    )
    client = StitchClient(api_key="test-api-key-12345678")
    await client.create_design_system("123", "Tinta", THEME)
    theme = json.loads(route.calls[0].request.content)["params"]["arguments"]["designSystem"]["theme"]
    assert theme["headlineFont"] == "SOURCE_SERIF_4" and theme["bodyFont"] == "SOURCE_SANS_3"
    await client.close()


@pytest.mark.parametrize("font", ["METROPOLIS"])
def test_metropolis_has_no_replacement_and_is_left_as_is(font):
    assert current_theme({**THEME, "headlineFont": font})["headlineFont"] == font
