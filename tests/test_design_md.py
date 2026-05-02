"""Tests for the design_md module (v5.31.0 Phase 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from server.design_md.archetypes import ARCHETYPES, ArchetypeId, default_archetype
from server.design_md.generator import GeneratorInputs, generate_design_md
from server.design_md.io import compute_signature, load, save
from server.design_md.schema import (
    Colors,
    ComponentSpec,
    Components,
    DesignMd,
    FontFamily,
    FontSize,
    FontWeight,
    FrontMatter,
    LineHeight,
    Rounded,
    Spacing,
    Typography,
)
from server.design_md.writer import serialize


# ── Schema validation ───────────────────────────────────────────────────


class TestColorsValidation:
    def test_accepts_six_digit_hex(self):
        c = Colors(primary="#FF00AA", background="#FFFFFF", text_primary="#000000")
        assert c.primary == "#FF00AA"

    def test_accepts_eight_digit_hex_alpha(self):
        c = Colors(primary="#FF00AA80", background="#FFFFFF", text_primary="#000000")
        assert c.primary == "#FF00AA80"

    def test_accepts_token_reference(self):
        c = Colors(
            primary="{colors.brand.main}",
            background="#FFFFFF",
            text_primary="#000000",
        )
        assert c.primary == "{colors.brand.main}"

    def test_rejects_named_color(self):
        with pytest.raises(ValueError, match="hex"):
            Colors(primary="coral", background="#FFFFFF", text_primary="#000000")

    def test_rejects_short_hex(self):
        with pytest.raises(ValueError, match="hex"):
            Colors(primary="#FFF", background="#FFFFFF", text_primary="#000000")


class TestComponents:
    def test_extra_components_allowed(self):
        comp = Components(
            button_primary=ComponentSpec(backgroundColor="#000000"),
            toast=ComponentSpec(backgroundColor="#222222"),  # extra key
        )
        assert "toast" in comp.model_dump()


# ── Archetypes ──────────────────────────────────────────────────────────


class TestArchetypes:
    def test_all_six_archetypes_present(self):
        assert set(ARCHETYPES.keys()) == set(ArchetypeId)

    def test_default_is_startup(self):
        assert default_archetype() == ArchetypeId.STARTUP

    @pytest.mark.parametrize("ar", list(ArchetypeId))
    def test_archetype_palette_is_valid(self, ar):
        # Round-trip through Pydantic to confirm hex codes pass validation.
        Colors(**ARCHETYPES[ar].palette)

    @pytest.mark.parametrize("ar", list(ArchetypeId))
    def test_archetype_components_are_well_formed(self, ar):
        Components(**ARCHETYPES[ar].components)

    @pytest.mark.parametrize("ar", list(ArchetypeId))
    def test_archetype_has_dos_and_donts(self, ar):
        a = ARCHETYPES[ar]
        assert len(a.dos) >= 2
        assert len(a.donts) >= 2


# ── Generator ──────────────────────────────────────────────────────────


class TestGenerator:
    def test_generates_with_no_inputs(self, tmp_path: Path):
        inp = GeneratorInputs(project_root=tmp_path, project_name="demo")
        doc = generate_design_md(inp)
        assert doc.front_matter.name == "demo"
        # Defaults to startup archetype.
        assert doc.front_matter.colors.primary == ARCHETYPES[ArchetypeId.STARTUP].palette["primary"]

    def test_archetype_override_wins(self, tmp_path: Path):
        inp = GeneratorInputs(
            project_root=tmp_path,
            project_name="demo",
            archetype_override=ArchetypeId.GEN_Z,
        )
        doc = generate_design_md(inp)
        assert (
            doc.front_matter.colors.primary
            == ARCHETYPES[ArchetypeId.GEN_Z].palette["primary"]
        )

    def test_extracts_palette_from_brand_kit(self, tmp_path: Path):
        bk = tmp_path / "brand_kit.md"
        bk.write_text(
            "# Brand kit\n"
            "- primary: #112233\n"
            "- background: #FFFFFF\n"
            "- text_primary: #000000\n"
            "- success: #00AA55\n",
            encoding="utf-8",
        )
        inp = GeneratorInputs(
            project_root=tmp_path,
            project_name="demo",
            brand_kit_path=bk,
        )
        doc = generate_design_md(inp)
        assert doc.front_matter.colors.primary == "#112233"
        assert doc.front_matter.colors.success == "#00AA55"

    def test_falls_back_to_archetype_when_brand_kit_incomplete(self, tmp_path: Path):
        # Missing required keys -> fall back entirely to archetype.
        bk = tmp_path / "brand_kit.md"
        bk.write_text("- primary: #112233\n", encoding="utf-8")
        inp = GeneratorInputs(
            project_root=tmp_path,
            project_name="demo",
            brand_kit_path=bk,
        )
        doc = generate_design_md(inp)
        assert (
            doc.front_matter.colors.primary
            == ARCHETYPES[ArchetypeId.STARTUP].palette["primary"]
        )

    def test_detects_archetype_from_veg(self, tmp_path: Path):
        veg = tmp_path / "veg.md"
        veg.write_text("# VEG\n\nArquetipo: gov\n", encoding="utf-8")
        inp = GeneratorInputs(
            project_root=tmp_path,
            project_name="demo",
            veg_path=veg,
        )
        doc = generate_design_md(inp)
        assert (
            doc.front_matter.colors.primary
            == ARCHETYPES[ArchetypeId.GOV].palette["primary"]
        )

    def test_overview_uses_app_prd_vision(self, tmp_path: Path):
        prd = tmp_path / "app_prd.md"
        prd.write_text(
            "# App PRD\n\n## Vision\n\nUna app para mascotas felices.\n\n## Audiencia\n",
            encoding="utf-8",
        )
        inp = GeneratorInputs(
            project_root=tmp_path,
            project_name="demo",
            app_prd_path=prd,
        )
        doc = generate_design_md(inp)
        assert "mascotas felices" in doc.overview


# ── Writer / round-trip ─────────────────────────────────────────────────


class TestWriterRoundTrip:
    def test_serialize_starts_with_frontmatter(self, tmp_path: Path):
        inp = GeneratorInputs(project_root=tmp_path, project_name="demo")
        doc = generate_design_md(inp)
        out = serialize(doc)
        assert out.startswith("---\n")
        assert "\n---\n" in out
        assert "## Overview" in out
        assert "## Colors" in out

    def test_round_trip_preserves_palette(self, tmp_path: Path):
        inp = GeneratorInputs(
            project_root=tmp_path,
            project_name="demo",
            archetype_override=ArchetypeId.CREATIVE,
        )
        doc = generate_design_md(inp)
        path = tmp_path / "DESIGN.md"
        save(doc, path)
        loaded = load(path)
        assert loaded.front_matter.colors.primary == doc.front_matter.colors.primary
        assert loaded.front_matter.name == "demo"

    def test_round_trip_preserves_sections(self, tmp_path: Path):
        inp = GeneratorInputs(project_root=tmp_path, project_name="demo")
        doc = generate_design_md(inp)
        path = tmp_path / "DESIGN.md"
        save(doc, path)
        loaded = load(path)
        for attr in ("overview", "colors_md", "typography_md", "dos_and_donts"):
            assert getattr(loaded, attr).strip() != ""

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        inp = GeneratorInputs(project_root=tmp_path, project_name="demo")
        doc = generate_design_md(inp)
        nested = tmp_path / "doc" / "design" / "DESIGN.md"
        save(doc, nested)
        assert nested.exists()


# ── Signature (drift detection) ────────────────────────────────────────


class TestSignature:
    def test_signature_is_stable_across_generated_at(self, tmp_path: Path):
        inp = GeneratorInputs(project_root=tmp_path, project_name="demo")
        a = generate_design_md(inp)
        b = generate_design_md(inp)
        # generated_at differs by milliseconds typically; signature must not.
        assert compute_signature(a) == compute_signature(b)

    def test_signature_changes_when_palette_changes(self, tmp_path: Path):
        a = generate_design_md(
            GeneratorInputs(
                project_root=tmp_path,
                project_name="demo",
                archetype_override=ArchetypeId.STARTUP,
            )
        )
        b = generate_design_md(
            GeneratorInputs(
                project_root=tmp_path,
                project_name="demo",
                archetype_override=ArchetypeId.CREATIVE,
            )
        )
        assert compute_signature(a) != compute_signature(b)
