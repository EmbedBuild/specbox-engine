"""Material 3 view of a :class:`DesignMd`.

The Stitch MCP server's ``create_design_system_from_design_md`` parses
the YAML frontmatter of an uploaded DESIGN.md and auto-populates the
resulting ``DesignTheme`` from canonical Material 3 token names. The
default SpecBox frontmatter (see :mod:`server.design_md.schema`) uses
SpecBox's own vocabulary (``primary``, ``background``, ``text_primary``
…) which the parser ignores.

This module produces an **additional** Material 3 frontmatter section
derived from the same VEG inputs, so the document can be uploaded to
Stitch and parsed correctly server-side without losing the SpecBox
view that humans + agents already read.

The mapping is deterministic and lossy in one direction (Material 3 is a
superset of what VEG models). The reverse is handled by
:func:`server.veg.material3_mapper.material3_to_veg_hints` for
migration case E.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..stitch_enums import (
    ColorMode,
    ColorVariant,
    Roundness,
    StitchFont,
)
from ..veg.material3_mapper import (
    BrandKit,
    JTBDOverrides,
    Material3Theme,
    VegArchetype,
    map_veg_to_material3,
)
from .archetypes import ArchetypeId
from .schema import DesignMd

# Mapping SpecBox's design_md ArchetypeId → veg.material3_mapper.VegArchetype.
# The two enums coincide on most values but use different spellings.
_ARCHETYPE_ID_TO_VEG: dict[ArchetypeId, VegArchetype] = {
    ArchetypeId.CORPORATE: "corporate",
    ArchetypeId.STARTUP: "startup",
    ArchetypeId.CREATIVE: "creative",
    ArchetypeId.CONSUMER: "consumer",
    ArchetypeId.GEN_Z: "gen_z",
    ArchetypeId.GOV: "gobierno",
}


# Roundness CSS px → enum mapping. Matches the values produced by
# :func:`archetypes.Archetype.rounded` and accepted by Stitch's
# ``Roundness`` enum.
_ROUNDED_TO_ENUM: dict[str, Roundness] = {
    "2px": Roundness.ROUND_TWO,
    "4px": Roundness.ROUND_FOUR,
    "8px": Roundness.ROUND_EIGHT,
    "12px": Roundness.ROUND_TWELVE,
    "9999px": Roundness.ROUND_FULL,
}


# Font family name (CSS-ish) → StitchFont enum. The Stitch server validates
# these against its 65-value enum. We only need to cover the families we
# actually emit; anything else falls back to INTER.
_FAMILY_TO_FONT: dict[str, StitchFont] = {
    "inter": StitchFont.INTER,
    "dm sans": StitchFont.DM_SANS,
    "space grotesk": StitchFont.SPACE_GROTESK,
    "montserrat": StitchFont.MONTSERRAT,
    "playfair display": StitchFont.PLAYFAIR_DISPLAY,
    "bebas neue": StitchFont.BEBAS_NEUE,
    "geist": StitchFont.GEIST,
    "manrope": StitchFont.MANROPE,
    "work sans": StitchFont.WORK_SANS,
    "be vietnam pro": StitchFont.BE_VIETNAM_PRO,
    "epilogue": StitchFont.EPILOGUE,
    "lexend": StitchFont.LEXEND,
    "plus jakarta sans": StitchFont.PLUS_JAKARTA_SANS,
    "public sans": StitchFont.PUBLIC_SANS,
    "spline sans": StitchFont.SPLINE_SANS,
    "noto serif": StitchFont.NOTO_SERIF,
    "noto sans": StitchFont.NOTO_SANS,
    "open sans": StitchFont.OPEN_SANS,
    "roboto flex": StitchFont.ROBOTO_FLEX,
    "ibm plex sans": StitchFont.IBM_PLEX_SANS,
    "jetbrains mono": StitchFont.JETBRAINS_MONO,
}


@dataclass
class Material3FrontMatter:
    """The YAML-ready dict for the Material 3 frontmatter block.

    Two responsibilities:
      1. Provide ``to_dict()`` ready to ``yaml.safe_dump`` into the
         DESIGN.md frontmatter.
      2. Expose ``theme`` (a :class:`Material3Theme`) for callers that
         need the enums directly (e.g. ``stitch_update_design_system``).
    """

    name: str
    theme: Material3Theme
    colors: dict[str, str]
    typography: dict[str, dict[str, Any]]
    veg_notes: list[str]

    def to_dict(self) -> dict:
        """Render to the dict shape expected by ``yaml.safe_dump``."""
        return {
            "name": self.name,
            "theme": self.theme.to_dict(),
            "colors": self.colors,
            "typography": self.typography,
        }


def _font_from_family(family: str | None, *, fallback: StitchFont) -> StitchFont:
    """Resolve a CSS-ish family name to a StitchFont enum, defaulting on miss."""
    if not family:
        return fallback
    key = family.strip().split(",")[0].strip().lower()
    return _FAMILY_TO_FONT.get(key, fallback)


def _roundness_from_rounded(value: str | None, *, fallback: Roundness) -> Roundness:
    if not value:
        return fallback
    return _ROUNDED_TO_ENUM.get(value.strip().lower(), fallback)


def _derive_m3_colors(theme: Material3Theme, primary_hex: str) -> dict[str, str]:
    """Build a Material 3 token table from the brand primary + overrides.

    Stitch's parser fills the full Material 3 palette from
    ``customColor`` + ``colorVariant`` server-side, so we only need
    to surface the **brand anchors** in the YAML frontmatter. The
    server expands them; we keep the YAML stable + small.

    Tokens emitted match the names the Stitch parser recognises:
    ``surface``, ``on-surface``, ``primary``, ``on-primary``,
    ``primary-container``, ``on-primary-container`` (anchors only).
    """
    anchors = {
        "surface": _surface_for(theme.color_mode),
        "on-surface": _on_surface_for(theme.color_mode),
        "background": _surface_for(theme.color_mode),
        "on-background": _on_surface_for(theme.color_mode),
        "primary": primary_hex,
        "on-primary": _on_color_for(primary_hex),
    }
    if theme.override_secondary_color:
        anchors["secondary"] = theme.override_secondary_color
    if theme.override_tertiary_color:
        anchors["tertiary"] = theme.override_tertiary_color
    return anchors


def _surface_for(mode: ColorMode) -> str:
    return "#FFFFFF" if mode == ColorMode.LIGHT else "#0F1115"


def _on_surface_for(mode: ColorMode) -> str:
    return "#1A1A1A" if mode == ColorMode.LIGHT else "#F2F2F2"


def _on_color_for(hex_color: str) -> str:
    """Pick #FFFFFF or #1A1A1A for legibility on top of hex_color.

    Simple luminance heuristic (Rec. 709). The Stitch server applies its
    own perceptual model on the fully-derived palette; this is for the
    handful of explicit anchors we surface in the frontmatter.
    """
    h = hex_color.lstrip("#")
    if len(h) < 6:
        return "#FFFFFF"
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return "#FFFFFF"
    # Rec. 709 luminance.
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#1A1A1A" if luma > 160 else "#FFFFFF"


def _derive_m3_typography(theme: Material3Theme) -> dict[str, dict[str, Any]]:
    """Map heading/body fonts into Material 3 typescale categories.

    The Stitch parser populates the rest of the typescale from these
    three anchors. We emit ``display-lg``, ``headline-md``, ``body-base``,
    and ``label-caps`` covering the four families Material 3 uses.
    """
    head = theme.headline_font.value
    body = theme.body_font.value
    label = theme.label_font.value
    return {
        "display-lg": {
            "fontFamily": head,
            "fontSize": "48px",
            "fontWeight": "800",
            "lineHeight": "56px",
            "letterSpacing": "-0.02em",
        },
        "headline-md": {
            "fontFamily": head,
            "fontSize": "24px",
            "fontWeight": "700",
            "lineHeight": "32px",
        },
        "body-base": {
            "fontFamily": body,
            "fontSize": "16px",
            "fontWeight": "400",
            "lineHeight": "24px",
        },
        "label-caps": {
            "fontFamily": label,
            "fontSize": "12px",
            "fontWeight": "500",
            "lineHeight": "16px",
            "letterSpacing": "0.08em",
        },
    }


def _format_veg_notes(doc: DesignMd, archetype: VegArchetype) -> list[str]:
    """Pull a short list of VEG-specific notes from the doc body.

    These notes survive in the DESIGN.md Markdown body as a dedicated
    section (see :func:`render_veg_notes_section`). They give downstream
    consumers (humans, agents reading the file) the VEG semantics that
    Material 3 enums can't express (mood, density, motion intensity).
    """
    notes: list[str] = [f"VEG archetype: {archetype}"]
    if doc.front_matter.colors.primary:
        notes.append(f"Brand primary anchor: {doc.front_matter.colors.primary}")
    return notes


def build_material3_frontmatter(
    doc: DesignMd,
    archetype: ArchetypeId,
    *,
    brand_kit: BrandKit | None = None,
    jtbd_overrides: JTBDOverrides | None = None,
) -> Material3FrontMatter:
    """Project a :class:`DesignMd` to a Material 3 frontmatter block.

    Args:
        doc: The DesignMd built by :func:`generator.generate_design_md`.
        archetype: The archetype the generator chose.
        brand_kit: Brand-kit overrides on top of archetype defaults.
        jtbd_overrides: Whitelisted JTBD-emotional deviations.

    Returns:
        A :class:`Material3FrontMatter` ready to serialise as YAML.
    """
    veg_arch = _ARCHETYPE_ID_TO_VEG[archetype]

    # Resolve the brand kit from the actual palette if the caller didn't
    # supply one explicitly. The colors come from the SpecBox view of
    # the DesignMd.
    if brand_kit is None:
        brand_kit = BrandKit(
            primary_color=doc.front_matter.colors.primary,
            secondary_color=doc.front_matter.colors.primary_hover,
            neutral_color=getattr(doc.front_matter.colors, "border", None),
            headline_font=_font_from_family(
                doc.front_matter.typography.fontFamily.heading,
                fallback=StitchFont.INTER,
            ),
            body_font=_font_from_family(
                doc.front_matter.typography.fontFamily.body,
                fallback=StitchFont.INTER,
            ),
            label_font=_font_from_family(
                doc.front_matter.typography.fontFamily.body,
                fallback=StitchFont.INTER,
            ),
        )

    if jtbd_overrides is None:
        # Derive roundness override from the actual md rounding scale.
        rounded_md = doc.front_matter.rounded.md if doc.front_matter.rounded else None
        derived_round = _roundness_from_rounded(
            rounded_md, fallback=Roundness.ROUND_EIGHT
        )
        # Only emit as override if it differs from the archetype's default.
        archetype_default_round = map_veg_to_material3(veg_arch).roundness
        if derived_round != archetype_default_round:
            jtbd_overrides = JTBDOverrides(roundness=derived_round)

    theme = map_veg_to_material3(
        veg_arch, brand_kit=brand_kit, jtbd_overrides=jtbd_overrides
    )
    colors = _derive_m3_colors(theme, theme.custom_color)
    typography = _derive_m3_typography(theme)
    notes = _format_veg_notes(doc, veg_arch)

    return Material3FrontMatter(
        name=doc.front_matter.name,
        theme=theme,
        colors=colors,
        typography=typography,
        veg_notes=notes,
    )


def render_veg_notes_section(notes: list[str]) -> str:
    """Build the Markdown body section that preserves VEG semantics.

    Lives below the standard design.md sections and serves as a hint
    layer for humans + agents — never parsed by Stitch.
    """
    if not notes:
        return ""
    lines = ["The following notes preserve VEG semantics that don't fit Material 3 enums:", ""]
    for n in notes:
        lines.append(f"- {n}")
    return "\n".join(lines)


__all__ = [
    "Material3FrontMatter",
    "build_material3_frontmatter",
    "render_veg_notes_section",
]
