"""Tests for the Stitch enums extracted from the live MCP server.

These enums are the source of truth for any code building DesignTheme
payloads. The tests pin the exact values the server accepts so that a
silent drift between local enums and `mcp_tools_schema.json` is caught
in CI rather than at runtime against Stitch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.stitch_enums import (
    ColorMode,
    ColorVariant,
    CreativeRange,
    DeviceType,
    Roundness,
    ScreenType,
    StitchFont,
    VariantAspect,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / ".quality"
    / "evidence"
    / "stitch_smoke"
    / "mcp_tools_schema.json"
)


def _design_theme_props() -> dict:
    """Pull the DesignTheme JSON Schema embedded in any tool's outputSchema."""
    schema = json.loads(SCHEMA_PATH.read_text())
    for tool in schema["tools"]:
        defs = tool.get("outputSchema", {}).get("$defs") or tool.get("outputSchema", {}).get("definitions") or {}
        if "DesignTheme" in defs:
            return defs["DesignTheme"]["properties"]
    raise AssertionError("DesignTheme not found in any tool's outputSchema")


def test_color_mode_matches_server_enum() -> None:
    props = _design_theme_props()
    server_enum = set(props["colorMode"]["enum"])
    local_enum = {m.value for m in ColorMode}
    assert local_enum == server_enum, (
        f"ColorMode drift: local={local_enum} server={server_enum}"
    )


def test_color_variant_matches_server_enum() -> None:
    props = _design_theme_props()
    server_enum = set(props["colorVariant"]["enum"])
    local_enum = {v.value for v in ColorVariant}
    assert local_enum == server_enum, (
        f"ColorVariant drift: local={local_enum} server={server_enum}"
    )


def test_roundness_matches_server_enum() -> None:
    props = _design_theme_props()
    server_enum = set(props["roundness"]["enum"])
    local_enum = {r.value for r in Roundness}
    assert local_enum == server_enum, (
        f"Roundness drift: local={local_enum} server={server_enum}"
    )


def test_stitch_font_matches_server_enum() -> None:
    props = _design_theme_props()
    # Three font fields use the same enum — test against headlineFont.
    server_enum = set(props["headlineFont"]["enum"])
    local_enum = {f.value for f in StitchFont}
    assert local_enum == server_enum, (
        "StitchFont drift between local enum and MCP server schema. "
        f"missing_locally={server_enum - local_enum} "
        f"extra_locally={local_enum - server_enum}"
    )


def test_font_count_pinned() -> None:
    # Sanity check that the enum hasn't accidentally lost values during edits.
    # Captured from MCP tools/list on 2026-05-26: 65 values including the
    # UNSPECIFIED sentinel.
    assert len(list(StitchFont)) == 65


def test_device_type_excludes_agnostic() -> None:
    # Public docs list AGNOSTIC but the live MCP does not — verified via
    # smoke v2. Including it locally would let bad calls through.
    values = {d.value for d in DeviceType}
    assert "AGNOSTIC" not in values
    assert values == {"DESKTOP", "MOBILE", "TABLET"}


@pytest.mark.parametrize(
    "enum_cls,expected",
    [
        (CreativeRange, {"REFINE", "EXPLORE", "REIMAGINE"}),
        (
            VariantAspect,
            {"LAYOUT", "COLOR_SCHEME", "IMAGES", "TEXT_FONT", "TEXT_CONTENT"},
        ),
        (ScreenType, {"DOCUMENT", "IMAGE"}),
    ],
)
def test_misc_enums_pinned(enum_cls, expected) -> None:
    assert {e.value for e in enum_cls} == expected
