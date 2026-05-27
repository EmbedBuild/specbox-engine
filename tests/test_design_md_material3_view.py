"""Tests for the v6.5.0 Material 3 frontmatter view (F5).

The Material 3 projection of a DesignMd is what Stitch's
``create_design_system_from_design_md`` actually parses server-side.
These tests pin the output shape so any drift is caught locally before
hitting the real API.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.design_md.archetypes import ArchetypeId
from server.design_md.generator import GeneratorInputs, generate_design_md
from server.design_md.material3_view import (
    Material3FrontMatter,
    _derive_m3_colors,
    _derive_m3_typography,
    _font_from_family,
    _on_color_for,
    _roundness_from_rounded,
    build_material3_frontmatter,
    render_veg_notes_section,
)
from server.design_md.writer import serialize
from server.stitch_enums import ColorMode, ColorVariant, Roundness, StitchFont


@pytest.fixture
def default_doc(tmp_path: Path):
    inputs = GeneratorInputs(project_root=tmp_path, project_name="TestApp")
    return generate_design_md(inputs)


class TestFontResolution:
    def test_known_family_maps_to_enum(self):
        assert _font_from_family("Inter, sans-serif", fallback=StitchFont.GEIST) == StitchFont.INTER
        assert _font_from_family("DM Sans", fallback=StitchFont.GEIST) == StitchFont.DM_SANS
        assert _font_from_family("Playfair Display", fallback=StitchFont.GEIST) == StitchFont.PLAYFAIR_DISPLAY

    def test_unknown_family_falls_back(self):
        assert _font_from_family("Comic Sans MS", fallback=StitchFont.INTER) == StitchFont.INTER

    def test_none_or_empty_falls_back(self):
        assert _font_from_family(None, fallback=StitchFont.INTER) == StitchFont.INTER
        assert _font_from_family("", fallback=StitchFont.INTER) == StitchFont.INTER


class TestRoundnessResolution:
    @pytest.mark.parametrize(
        "css,expected",
        [
            ("2px", Roundness.ROUND_TWO),
            ("4px", Roundness.ROUND_FOUR),
            ("8px", Roundness.ROUND_EIGHT),
            ("12px", Roundness.ROUND_TWELVE),
            ("9999px", Roundness.ROUND_FULL),
        ],
    )
    def test_known_values(self, css, expected):
        assert _roundness_from_rounded(css, fallback=Roundness.ROUND_EIGHT) == expected

    def test_unknown_falls_back(self):
        assert _roundness_from_rounded("17px", fallback=Roundness.ROUND_EIGHT) == Roundness.ROUND_EIGHT


class TestOnColorLuminance:
    def test_dark_text_on_light_background(self):
        # Light yellow → dark text.
        assert _on_color_for("#FDE68A") == "#1A1A1A"

    def test_light_text_on_dark_background(self):
        # Deep blue → light text.
        assert _on_color_for("#1E3A8A") == "#FFFFFF"

    def test_malformed_hex_returns_white_default(self):
        assert _on_color_for("not-hex") == "#FFFFFF"


class TestDeriveColors:
    def test_emits_m3_anchors(self, default_doc):
        m3 = build_material3_frontmatter(default_doc, ArchetypeId.STARTUP)
        assert m3.colors["surface"] == "#FFFFFF"  # LIGHT mode anchor
        assert m3.colors["on-surface"] == "#1A1A1A"
        assert m3.colors["primary"] == m3.theme.custom_color
        assert "on-primary" in m3.colors

    def test_dark_mode_flips_anchors(self):
        # Force a DARK theme via Gen-Z archetype.
        # Build a minimal doc through the public API.
        from server.design_md.generator import GeneratorInputs as GI

        doc = generate_design_md(GI(project_root=Path("/tmp"), project_name="t"))
        # Override via build_material3_frontmatter with the gen-z archetype.
        m3 = build_material3_frontmatter(doc, ArchetypeId.GEN_Z)
        assert m3.theme.color_mode == ColorMode.DARK
        assert m3.colors["surface"] != "#FFFFFF"


class TestDeriveTypography:
    def test_emits_canonical_categories(self, default_doc):
        m3 = build_material3_frontmatter(default_doc, ArchetypeId.STARTUP)
        for key in ("display-lg", "headline-md", "body-base", "label-caps"):
            assert key in m3.typography
            assert m3.typography[key]["fontFamily"] in {f.value for f in StitchFont}


class TestBuildFrontmatter:
    def test_archetype_id_maps_to_veg(self, default_doc):
        m3 = build_material3_frontmatter(default_doc, ArchetypeId.CORPORATE)
        # Corporate archetype maps to NEUTRAL color variant in the mapper.
        assert m3.theme.color_variant == ColorVariant.NEUTRAL

    def test_gov_archetype_maps_to_gobierno_veg(self, default_doc):
        m3 = build_material3_frontmatter(default_doc, ArchetypeId.GOV)
        # GOV → gobierno → MONOCHROME.
        assert m3.theme.color_variant == ColorVariant.MONOCHROME

    def test_to_dict_serialises_theme_payload(self, default_doc):
        m3 = build_material3_frontmatter(default_doc, ArchetypeId.STARTUP)
        d = m3.to_dict()
        assert d["name"] == default_doc.front_matter.name
        # theme must be ready for stitch_update_design_system.
        theme = d["theme"]
        assert theme["colorMode"] in {"LIGHT", "DARK"}
        assert theme["headlineFont"] in {f.value for f in StitchFont}
        assert theme["customColor"].startswith("#")


class TestVegNotesSection:
    def test_renders_bulleted_markdown(self):
        out = render_veg_notes_section(["Note A", "Note B"])
        assert "- Note A" in out
        assert "- Note B" in out

    def test_empty_returns_empty(self):
        assert render_veg_notes_section([]) == ""


class TestSerializeWithMaterial3:
    def test_native_v2_yaml_contains_theme_block(self, default_doc):
        m3 = build_material3_frontmatter(default_doc, ArchetypeId.STARTUP)
        output = serialize(default_doc, material3=m3)
        assert "theme:" in output
        assert "colorMode:" in output
        assert "VEG Notes" in output

    def test_default_yaml_omits_theme_block(self, default_doc):
        output = serialize(default_doc)
        assert "theme:" not in output
        assert "colorMode:" not in output
