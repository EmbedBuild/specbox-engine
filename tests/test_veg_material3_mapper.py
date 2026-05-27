"""Tests for the VEG → Material 3 deterministic mapper."""

from __future__ import annotations

import pytest

from server.stitch_enums import (
    ColorMode,
    ColorVariant,
    Roundness,
    StitchFont,
)
from server.veg.material3_mapper import (
    BrandKit,
    JTBDOverrides,
    Material3Theme,
    map_veg_to_material3,
    material3_to_veg_hints,
)

ALL_ARCHETYPES = ["corporate", "startup", "creative", "consumer", "gen_z", "gobierno"]


@pytest.mark.parametrize("archetype", ALL_ARCHETYPES)
def test_each_archetype_produces_valid_theme(archetype: str) -> None:
    theme = map_veg_to_material3(archetype)
    assert isinstance(theme, Material3Theme)
    payload = theme.to_dict()
    # All required Material 3 fields present.
    for field in (
        "colorMode",
        "colorVariant",
        "roundness",
        "headlineFont",
        "bodyFont",
        "labelFont",
        "customColor",
    ):
        assert field in payload, f"{archetype} missing {field}"
    # All values are server-validated enums (not free strings).
    assert payload["colorMode"] in {m.value for m in ColorMode}
    assert payload["colorVariant"] in {v.value for v in ColorVariant}
    assert payload["roundness"] in {r.value for r in Roundness}
    assert payload["headlineFont"] in {f.value for f in StitchFont}


def test_unknown_archetype_raises() -> None:
    with pytest.raises(ValueError, match="Unknown VEG archetype"):
        map_veg_to_material3("not_a_real_archetype")


def test_brand_kit_overrides_archetype_defaults() -> None:
    base = map_veg_to_material3("startup")
    overridden = map_veg_to_material3(
        "startup",
        brand_kit=BrandKit(
            primary_color="#FF0000",
            headline_font=StitchFont.GEIST,
        ),
    )
    assert overridden.to_dict()["customColor"] == "#FF0000"
    assert overridden.to_dict()["headlineFont"] == "GEIST"
    # overridePrimary is emitted when the brand-kit sets it.
    assert overridden.to_dict()["overridePrimaryColor"] == "#FF0000"
    # Untouched defaults are preserved.
    assert overridden.color_variant == base.color_variant


def test_jtbd_overrides_apply_within_whitelist() -> None:
    overridden = map_veg_to_material3(
        "corporate",
        jtbd_overrides=JTBDOverrides(
            color_mode=ColorMode.DARK,
            roundness=Roundness.ROUND_EIGHT,
        ),
    )
    payload = overridden.to_dict()
    assert payload["colorMode"] == "DARK"
    assert payload["roundness"] == "ROUND_EIGHT"
    # color_variant was NOT overridden, defaults to corporate's NEUTRAL.
    assert payload["colorVariant"] == "NEUTRAL"


def test_brand_kit_wins_over_jtbd_overrides() -> None:
    # Resolution order: archetype < jtbd < brand_kit.
    overridden = map_veg_to_material3(
        "startup",
        brand_kit=BrandKit(headline_font=StitchFont.METROPOLIS),
        jtbd_overrides=JTBDOverrides(color_mode=ColorMode.DARK),
    )
    payload = overridden.to_dict()
    # Brand kit applied.
    assert payload["headlineFont"] == "METROPOLIS"
    # JTBD applied (no conflict with brand kit).
    assert payload["colorMode"] == "DARK"


def test_to_dict_omits_optional_fields_when_unset() -> None:
    theme = map_veg_to_material3("corporate")
    payload = theme.to_dict()
    # The mapper doesn't set override colors unless brand_kit provides them.
    assert "overridePrimaryColor" not in payload
    assert "overrideSecondaryColor" not in payload
    assert "designMd" not in payload


def test_to_dict_includes_design_md_when_set() -> None:
    theme = map_veg_to_material3(
        "corporate",
        design_md="# Hello",
    )
    assert theme.to_dict()["designMd"] == "# Hello"


def test_veg_notes_preserved() -> None:
    notes = ["JTBD-emocional: confianza", "Multi-form-factor: mobile-first"]
    theme = map_veg_to_material3("consumer", veg_notes=notes)
    # veg_notes lives on the dataclass for downstream serialisation into
    # DESIGN.md body, but is not in the wire payload sent to Stitch.
    assert theme.veg_notes == notes
    assert "vegNotes" not in theme.to_dict()


def test_legacy_font_field_not_in_output() -> None:
    # We must never emit the deprecated `font` key — Stitch rejects it.
    for archetype in ALL_ARCHETYPES:
        payload = map_veg_to_material3(archetype).to_dict()
        assert "font" not in payload


def test_reverse_map_corporate_theme() -> None:
    theme = {
        "colorMode": "LIGHT",
        "colorVariant": "NEUTRAL",
        "roundness": "ROUND_FOUR",
        "headlineFont": "INTER",
        "bodyFont": "INTER",
        "labelFont": "INTER",
    }
    hints = material3_to_veg_hints(theme)
    # Corporate should be the top match — exact field-for-field.
    assert hints["archetype_candidates"][0][0] == "corporate"
    assert hints["archetype_candidates"][0][1] == 6  # 6 matched fields


def test_reverse_map_partial_match() -> None:
    theme = {
        "colorMode": "DARK",
        "colorVariant": "RAINBOW",
        # Other fields missing — gen-z still wins by mode+variant.
    }
    hints = material3_to_veg_hints(theme)
    top, score = hints["archetype_candidates"][0]
    assert top == "gen_z"
    assert score == 2


def test_reverse_map_handles_empty_theme() -> None:
    hints = material3_to_veg_hints({})
    # Empty theme → all candidates tied at 0.
    scores = [s for _, s in hints["archetype_candidates"]]
    assert all(s == 0 for s in scores)
    assert hints["matched_fields"] == {}
