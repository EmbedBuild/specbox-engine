"""VEG ↔ Material 3 deterministic mapper.

Bridges the 6 SpecBox VEG archetypes
(`doc/templates/veg-archetypes.md`) to the Material 3 `DesignTheme`
shape that Stitch's `update_design_system` server-side parser consumes.

Design choice
-------------
VEG remains the conceptual model (rich archetype + JTBD vocabulary).
Material 3 is the normative *output representation* in the
YAML frontmatter that Stitch parses server-side. The VEG semantics
that don't fit M3 enums survive as Markdown body content in the
DESIGN.md "VEG Notes" section. Two representations, one source of
truth (VEG), and the mapping is deterministic so it's audit-able.

The mapper is intentionally **opinionated**: each archetype produces a
single canonical theme. Brand-kit overrides apply on top. JTBD-emotional
overrides apply via a small whitelist of allowed deviations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..stitch_enums import (
    ColorMode,
    ColorVariant,
    Roundness,
    StitchFont,
)

VegArchetype = Literal[
    "corporate",
    "startup",
    "creative",
    "consumer",
    "gen_z",
    "gobierno",
]


@dataclass(frozen=True)
class BrandKit:
    """Brand-kit values that override the archetype defaults.

    All fields optional; only set what the brand provides explicitly.
    """

    primary_color: str | None = None  # hex e.g. "#0EA5E9"
    secondary_color: str | None = None
    tertiary_color: str | None = None
    neutral_color: str | None = None
    headline_font: StitchFont | None = None
    body_font: StitchFont | None = None
    label_font: StitchFont | None = None


@dataclass(frozen=True)
class JTBDOverrides:
    """JTBD-emotional overrides on top of archetype defaults.

    Only documented overrides are honoured; anything else is silently
    dropped so the mapping stays predictable.
    """

    color_mode: ColorMode | None = None
    color_variant: ColorVariant | None = None
    roundness: Roundness | None = None


@dataclass
class Material3Theme:
    """The shape of `designSystem.theme` that Stitch accepts.

    Use `.to_dict()` to get the JSON-ready payload for
    `update_design_system` / `stitch_update_design_system`.
    """

    color_mode: ColorMode
    color_variant: ColorVariant
    roundness: Roundness
    headline_font: StitchFont
    body_font: StitchFont
    label_font: StitchFont
    custom_color: str
    override_primary_color: str | None = None
    override_secondary_color: str | None = None
    override_tertiary_color: str | None = None
    override_neutral_color: str | None = None
    design_md: str | None = None
    veg_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Render to the JSON shape Stitch expects in update_design_system."""
        payload: dict = {
            "colorMode": self.color_mode.value,
            "colorVariant": self.color_variant.value,
            "roundness": self.roundness.value,
            "headlineFont": self.headline_font.value,
            "bodyFont": self.body_font.value,
            "labelFont": self.label_font.value,
            "customColor": self.custom_color,
        }
        if self.override_primary_color:
            payload["overridePrimaryColor"] = self.override_primary_color
        if self.override_secondary_color:
            payload["overrideSecondaryColor"] = self.override_secondary_color
        if self.override_tertiary_color:
            payload["overrideTertiaryColor"] = self.override_tertiary_color
        if self.override_neutral_color:
            payload["overrideNeutralColor"] = self.override_neutral_color
        if self.design_md:
            payload["designMd"] = self.design_md
        return payload


# Canonical 1:1 archetype → M3 theme.
# Values chosen for representativeness of each archetype's "default look";
# the brand kit always wins on top.
_ARCHETYPE_TABLE: dict[VegArchetype, dict] = {
    "corporate": {
        "color_mode": ColorMode.LIGHT,
        "color_variant": ColorVariant.NEUTRAL,
        "roundness": Roundness.ROUND_FOUR,
        "headline_font": StitchFont.INTER,
        "body_font": StitchFont.INTER,
        "label_font": StitchFont.INTER,
        "custom_color": "#1A56DB",  # corporate blue
    },
    "startup": {
        "color_mode": ColorMode.LIGHT,
        "color_variant": ColorVariant.FIDELITY,
        "roundness": Roundness.ROUND_EIGHT,
        "headline_font": StitchFont.SPACE_GROTESK,
        "body_font": StitchFont.INTER,
        "label_font": StitchFont.INTER,
        "custom_color": "#7C3AED",  # vibrant purple
    },
    "creative": {
        "color_mode": ColorMode.LIGHT,
        "color_variant": ColorVariant.EXPRESSIVE,
        "roundness": Roundness.ROUND_TWELVE,
        "headline_font": StitchFont.PLAYFAIR_DISPLAY,
        "body_font": StitchFont.INTER,
        "label_font": StitchFont.INTER,
        "custom_color": "#EC4899",  # editorial pink
    },
    "consumer": {
        "color_mode": ColorMode.LIGHT,
        "color_variant": ColorVariant.VIBRANT,
        "roundness": Roundness.ROUND_EIGHT,
        "headline_font": StitchFont.DM_SANS,
        "body_font": StitchFont.DM_SANS,
        "label_font": StitchFont.DM_SANS,
        "custom_color": "#F59E0B",  # warm amber
    },
    "gen_z": {
        "color_mode": ColorMode.DARK,
        "color_variant": ColorVariant.RAINBOW,
        "roundness": Roundness.ROUND_FULL,
        "headline_font": StitchFont.BEBAS_NEUE,
        "body_font": StitchFont.SPACE_GROTESK,
        "label_font": StitchFont.SPACE_GROTESK,
        "custom_color": "#14F195",  # neon green
    },
    "gobierno": {
        "color_mode": ColorMode.LIGHT,
        "color_variant": ColorVariant.MONOCHROME,
        "roundness": Roundness.ROUND_FOUR,
        "headline_font": StitchFont.INTER,
        "body_font": StitchFont.INTER,
        "label_font": StitchFont.INTER,
        "custom_color": "#1F2937",  # institutional charcoal
    },
}


def map_veg_to_material3(
    archetype: VegArchetype,
    brand_kit: BrandKit | None = None,
    jtbd_overrides: JTBDOverrides | None = None,
    design_md: str | None = None,
    veg_notes: list[str] | None = None,
) -> Material3Theme:
    """Translate a VEG archetype (plus optional overrides) into a M3 theme.

    Resolution order (highest priority last):
        archetype defaults → JTBD-emotional overrides → brand-kit overrides

    Args:
        archetype: One of the 6 canonical VEG archetypes.
        brand_kit: Brand-kit values that override defaults (colors,
            fonts). Anything not specified falls back to the archetype.
        jtbd_overrides: Documented JTBD-emotional deviations. Only
            color_mode, color_variant and roundness are settable.
        design_md: Optional Markdown body to send back in the theme
            payload as `designMd` (Stitch keeps it for later reads).
        veg_notes: Free-form VEG semantics that don't fit M3 enums —
            preserved on the Theme object for downstream serialisation
            into the DESIGN.md "VEG Notes" section.

    Raises:
        ValueError: if `archetype` is unknown.
    """
    if archetype not in _ARCHETYPE_TABLE:
        raise ValueError(
            f"Unknown VEG archetype {archetype!r}. "
            f"Valid: {sorted(_ARCHETYPE_TABLE)}"
        )
    base = dict(_ARCHETYPE_TABLE[archetype])

    # Apply JTBD overrides (whitelist of 3 fields).
    if jtbd_overrides:
        if jtbd_overrides.color_mode:
            base["color_mode"] = jtbd_overrides.color_mode
        if jtbd_overrides.color_variant:
            base["color_variant"] = jtbd_overrides.color_variant
        if jtbd_overrides.roundness:
            base["roundness"] = jtbd_overrides.roundness

    # Apply brand-kit overrides (highest priority).
    override_primary = None
    override_secondary = None
    override_tertiary = None
    override_neutral = None
    if brand_kit:
        if brand_kit.headline_font:
            base["headline_font"] = brand_kit.headline_font
        if brand_kit.body_font:
            base["body_font"] = brand_kit.body_font
        if brand_kit.label_font:
            base["label_font"] = brand_kit.label_font
        if brand_kit.primary_color:
            base["custom_color"] = brand_kit.primary_color
            override_primary = brand_kit.primary_color
        if brand_kit.secondary_color:
            override_secondary = brand_kit.secondary_color
        if brand_kit.tertiary_color:
            override_tertiary = brand_kit.tertiary_color
        if brand_kit.neutral_color:
            override_neutral = brand_kit.neutral_color

    return Material3Theme(
        color_mode=base["color_mode"],
        color_variant=base["color_variant"],
        roundness=base["roundness"],
        headline_font=base["headline_font"],
        body_font=base["body_font"],
        label_font=base["label_font"],
        custom_color=base["custom_color"],
        override_primary_color=override_primary,
        override_secondary_color=override_secondary,
        override_tertiary_color=override_tertiary,
        override_neutral_color=override_neutral,
        design_md=design_md,
        veg_notes=veg_notes or [],
    )


def material3_to_veg_hints(theme: dict) -> dict:
    """Reverse-map a Material 3 theme dict to plausible VEG hints.

    Used for migration case E (user-customised DESIGN.md not following
    SpecBox conventions): given a `designSystem.theme`, propose which
    VEG archetype the theme most closely resembles, so the user has a
    starting point to validate / adjust.

    Returns:
        ``{"archetype_candidates": [(archetype, score), ...],
         "matched_fields": {...}}``

        Scores are heuristic, summing field matches against
        :data:`_ARCHETYPE_TABLE`. Not authoritative — pure hint.
    """
    scores: dict[VegArchetype, int] = {a: 0 for a in _ARCHETYPE_TABLE}
    matched: dict[str, str] = {}
    target = {
        "color_mode": theme.get("colorMode"),
        "color_variant": theme.get("colorVariant"),
        "roundness": theme.get("roundness"),
        "headline_font": theme.get("headlineFont"),
        "body_font": theme.get("bodyFont"),
        "label_font": theme.get("labelFont"),
    }
    for archetype, defaults in _ARCHETYPE_TABLE.items():
        for field_name, target_val in target.items():
            if target_val is None:
                continue
            default_val = defaults[field_name]
            default_str = default_val.value if hasattr(default_val, "value") else default_val
            if target_val == default_str:
                scores[archetype] += 1
                matched[field_name] = target_val
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    return {
        "archetype_candidates": ranked,
        "matched_fields": matched,
    }


__all__ = [
    "BrandKit",
    "JTBDOverrides",
    "Material3Theme",
    "VegArchetype",
    "map_veg_to_material3",
    "material3_to_veg_hints",
]
