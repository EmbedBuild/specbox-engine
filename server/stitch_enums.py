"""Stitch MCP enums — sourced from the real server schema, not public docs.

These enums were extracted via `tools/list` on https://stitch.googleapis.com/mcp
on 2026-05-26. Public documentation lags substantially behind the server:

- Public docs list 9 fonts; the server exposes **65**.
- Public docs use `TONAL` for ColorVariant; the server uses **TONAL_SPOT**.
- Public docs do not mention `NEUTRAL` ColorVariant; it exists server-side.
- Public docs do not mention `ROUND_TWO` Roundness; it exists server-side.

The canonical source for these values is
`.quality/evidence/stitch_smoke/mcp_tools_schema.json`, refreshed by
re-running `.quality/evidence/stitch_smoke/smoke_test_mcp_v2.py`.

USAGE
-----
    from server.stitch_enums import StitchFont, ColorMode, ColorVariant, Roundness

    theme = {
        "colorMode": ColorMode.LIGHT.value,
        "headlineFont": StitchFont.INTER.value,
        "roundness": Roundness.ROUND_EIGHT.value,
        "colorVariant": ColorVariant.FIDELITY.value,
    }
"""

from __future__ import annotations

from enum import StrEnum


class ColorMode(StrEnum):
    """Color mode for the design system."""

    UNSPECIFIED = "COLOR_MODE_UNSPECIFIED"
    LIGHT = "LIGHT"
    DARK = "DARK"


class ColorVariant(StrEnum):
    """Material 3 ColorScheme variants supported by Stitch.

    See https://material.io/blog/announcing-material-3 for canonical
    definitions. `TONAL_SPOT` is the Material 3 default.
    """

    UNSPECIFIED = "COLOR_VARIANT_UNSPECIFIED"
    MONOCHROME = "MONOCHROME"
    NEUTRAL = "NEUTRAL"
    TONAL_SPOT = "TONAL_SPOT"  # Material 3 default
    VIBRANT = "VIBRANT"
    EXPRESSIVE = "EXPRESSIVE"
    FIDELITY = "FIDELITY"
    CONTENT = "CONTENT"
    RAINBOW = "RAINBOW"
    FRUIT_SALAD = "FRUIT_SALAD"


class Roundness(StrEnum):
    """Corner radius scale for design system components."""

    UNSPECIFIED = "ROUNDNESS_UNSPECIFIED"
    ROUND_TWO = "ROUND_TWO"  # 2px — sharp
    ROUND_FOUR = "ROUND_FOUR"  # 4px — restrained
    ROUND_EIGHT = "ROUND_EIGHT"  # 8px — balanced
    ROUND_TWELVE = "ROUND_TWELVE"  # 12px — friendly
    ROUND_FULL = "ROUND_FULL"  # 9999px — pill


class StitchFont(StrEnum):
    """All 65 fonts the Stitch MCP server accepts in DesignTheme.

    Server-validated; values not in this enum will be rejected by
    `update_design_system` and `create_design_system`.

    Categorised hint (not authoritative — just for human cognition):
    - Sans-serif: INTER, ROBOTO_FLEX, DM_SANS, MANROPE, etc.
    - Serif: NEWSREADER, NOTO_SERIF, EB_GARAMOND, etc.
    - Display: BEBAS_NEUE, ANTON, PLAYFAIR_DISPLAY, etc.
    - Monospace: JETBRAINS_MONO, SPACE_MONO, COURIER_PRIME.
    - Google Sans family: GOOGLE_SANS, GOOGLE_SANS_TEXT,
      GOOGLE_SANS_CODE, GOOGLE_SANS_MONO, GOOGLE_SANS_FLEX.
    """

    UNSPECIFIED = "FONT_UNSPECIFIED"
    BE_VIETNAM_PRO = "BE_VIETNAM_PRO"
    EPILOGUE = "EPILOGUE"
    INTER = "INTER"
    LEXEND = "LEXEND"
    MANROPE = "MANROPE"
    NEWSREADER = "NEWSREADER"
    NOTO_SERIF = "NOTO_SERIF"
    PLUS_JAKARTA_SANS = "PLUS_JAKARTA_SANS"
    PUBLIC_SANS = "PUBLIC_SANS"
    SPACE_GROTESK = "SPACE_GROTESK"
    SPLINE_SANS = "SPLINE_SANS"
    WORK_SANS = "WORK_SANS"
    DOMINE = "DOMINE"
    LIBRE_CASLON_TEXT = "LIBRE_CASLON_TEXT"
    EB_GARAMOND = "EB_GARAMOND"
    LITERATA = "LITERATA"
    SOURCE_SERIF_FOUR = "SOURCE_SERIF_FOUR"
    MONTSERRAT = "MONTSERRAT"
    METROPOLIS = "METROPOLIS"
    SOURCE_SANS_THREE = "SOURCE_SANS_THREE"
    NUNITO_SANS = "NUNITO_SANS"
    ARIMO = "ARIMO"
    HANKEN_GROTESK = "HANKEN_GROTESK"
    RUBIK = "RUBIK"
    GEIST = "GEIST"
    DM_SANS = "DM_SANS"
    IBM_PLEX_SANS = "IBM_PLEX_SANS"
    SORA = "SORA"
    ANYBODY = "ANYBODY"
    ANTON = "ANTON"
    ARCHIVO_NARROW = "ARCHIVO_NARROW"
    ATKINSON_HYPERLEGIBLE_NEXT = "ATKINSON_HYPERLEGIBLE_NEXT"
    BARLOW_CONDENSED = "BARLOW_CONDENSED"
    BEBAS_NEUE = "BEBAS_NEUE"
    BODONI_MODA = "BODONI_MODA"
    BRICOLAGE_GROTESQUE = "BRICOLAGE_GROTESQUE"
    CHIVO = "CHIVO"
    CLIMATE_CRISIS = "CLIMATE_CRISIS"
    COMFORTAA = "COMFORTAA"
    COURIER_PRIME = "COURIER_PRIME"
    FIRA_SANS = "FIRA_SANS"
    GOOGLE_SANS = "GOOGLE_SANS"
    GOOGLE_SANS_CODE = "GOOGLE_SANS_CODE"
    GOOGLE_SANS_FLEX = "GOOGLE_SANS_FLEX"
    GOOGLE_SANS_MONO = "GOOGLE_SANS_MONO"
    GOOGLE_SANS_TEXT = "GOOGLE_SANS_TEXT"
    IBM_PLEX_SERIF = "IBM_PLEX_SERIF"
    JETBRAINS_MONO = "JETBRAINS_MONO"
    KARLA = "KARLA"
    LIBRE_FRANKLIN = "LIBRE_FRANKLIN"
    MERRIWEATHER = "MERRIWEATHER"
    NOTO_SANS = "NOTO_SANS"
    OPEN_SANS = "OPEN_SANS"
    OSWALD = "OSWALD"
    OUTFIT = "OUTFIT"
    PLAYFAIR_DISPLAY = "PLAYFAIR_DISPLAY"
    POIRET_ONE = "POIRET_ONE"
    QUESTRIAL = "QUESTRIAL"
    QUICKSAND = "QUICKSAND"
    RALEWAY = "RALEWAY"
    ROBOTO_FLEX = "ROBOTO_FLEX"
    SPACE_MONO = "SPACE_MONO"
    SYNE = "SYNE"
    VOLLKORN = "VOLLKORN"


class DeviceType(StrEnum):
    """Device type for generation and DS scoping. AGNOSTIC is NOT supported."""

    DESKTOP = "DESKTOP"
    MOBILE = "MOBILE"
    TABLET = "TABLET"


class CreativeRange(StrEnum):
    """How creative generate_variants can be."""

    REFINE = "REFINE"
    EXPLORE = "EXPLORE"
    REIMAGINE = "REIMAGINE"


class VariantAspect(StrEnum):
    """Aspects targetable by generate_variants."""

    LAYOUT = "LAYOUT"
    COLOR_SCHEME = "COLOR_SCHEME"
    IMAGES = "IMAGES"
    TEXT_FONT = "TEXT_FONT"
    TEXT_CONTENT = "TEXT_CONTENT"


class ScreenType(StrEnum):
    """Screen type for batchCreate REST upload."""

    DOCUMENT = "DOCUMENT"  # HTML or Markdown content
    IMAGE = "IMAGE"  # Raster image (png/jpeg/webp)


__all__ = [
    "ColorMode",
    "ColorVariant",
    "Roundness",
    "StitchFont",
    "DeviceType",
    "CreativeRange",
    "VariantAspect",
    "ScreenType",
]
