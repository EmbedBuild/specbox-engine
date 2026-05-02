"""Pydantic schema for DESIGN.md (v5.31.0).

Mirrors the spec in https://github.com/google-labs-code/design.md, restricted
to the subset SpecBox actually generates from Brand Kit + VEG. Token reference
strings of the form ``{path.to.token}`` are preserved verbatim — Stitch and
downstream consumers (CLI ``design.md export``) resolve them at use time.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Validators ──────────────────────────────────────────────────────────

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
TOKEN_REF_RE = re.compile(r"^\{[a-z][a-z0-9_]*(\.[a-z0-9_]+)+\}$")


def _validate_hex_or_ref(v: str) -> str:
    """Color values must be either a 6/8-hex literal or a {token.ref}.

    Accepting token refs lets components reference colors symbolically
    (``backgroundColor: "{colors.primary}"``) without forcing the writer
    to resolve them up-front. Stitch handles resolution.
    """
    if not isinstance(v, str):
        raise TypeError("color must be a string")
    if HEX_RE.match(v) or TOKEN_REF_RE.match(v):
        return v
    raise ValueError(f"color must be #RRGGBB[AA] hex or {{token.ref}}, got {v!r}")


HexOrRef = Annotated[str, Field(description="#RRGGBB hex or {token.ref}")]


# ── Models ──────────────────────────────────────────────────────────────


class Colors(BaseModel):
    """Palette. Hex codes only — Stitch generates more reliable output
    when colors are explicit (named colors drift between generations).
    """

    model_config = ConfigDict(extra="allow")

    primary: HexOrRef
    primary_hover: HexOrRef | None = None
    background: HexOrRef
    surface: HexOrRef | None = None
    text_primary: HexOrRef
    text_secondary: HexOrRef | None = None
    border: HexOrRef | None = None
    error: HexOrRef | None = None
    success: HexOrRef | None = None
    warning: HexOrRef | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _hex_or_ref(cls, v):
        if v is None:
            return v
        return _validate_hex_or_ref(v)


class FontFamily(BaseModel):
    model_config = ConfigDict(extra="allow")
    heading: str
    body: str


class FontSize(BaseModel):
    model_config = ConfigDict(extra="allow")
    h1: str
    h2: str
    h3: str | None = None
    body: str
    caption: str | None = None


class FontWeight(BaseModel):
    model_config = ConfigDict(extra="allow")
    regular: int = 400
    medium: int = 500
    semibold: int = 600
    bold: int = 700


class LineHeight(BaseModel):
    model_config = ConfigDict(extra="allow")
    tight: float = 1.2
    normal: float = 1.5
    relaxed: float = 1.75


class Typography(BaseModel):
    fontFamily: FontFamily
    fontSize: FontSize
    fontWeight: FontWeight = Field(default_factory=FontWeight)
    lineHeight: LineHeight = Field(default_factory=LineHeight)


class Rounded(BaseModel):
    model_config = ConfigDict(extra="allow")
    sm: str = "4px"
    md: str = "8px"
    lg: str = "12px"
    full: str = "9999px"


class Spacing(BaseModel):
    model_config = ConfigDict(extra="allow")
    xs: str = "4px"
    sm: str = "8px"
    md: str = "16px"
    lg: str = "24px"
    xl: str = "32px"
    xxl: str = "48px"


class ComponentSpec(BaseModel):
    """A reusable component pattern. Values can be hex or {token.ref}."""

    model_config = ConfigDict(extra="allow")

    backgroundColor: str | None = None
    textColor: str | None = None
    typography: str | None = None
    rounded: str | None = None
    padding: str | None = None
    size: str | None = None


class Components(BaseModel):
    """Named components. Extra keys are allowed so adapters can add
    bespoke patterns (toast, modal, etc.) without schema churn.
    """

    model_config = ConfigDict(extra="allow")

    button_primary: ComponentSpec | None = None
    button_secondary: ComponentSpec | None = None
    card: ComponentSpec | None = None
    input: ComponentSpec | None = None


class FrontMatter(BaseModel):
    """The YAML front-matter block. Mirrors the design.md spec keys."""

    model_config = ConfigDict(extra="allow")

    name: str
    version: str = "1.0.0"
    generated_by: str = "specbox-engine"
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    colors: Colors
    typography: Typography
    rounded: Rounded = Field(default_factory=Rounded)
    spacing: Spacing = Field(default_factory=Spacing)
    components: Components = Field(default_factory=Components)


# ── Top-level model ─────────────────────────────────────────────────────


class DesignMd(BaseModel):
    """A full DESIGN.md document: front-matter + Markdown body sections.

    The body is a dict keyed by Google's canonical section order
    (Overview, Colors, Typography, Layout, Elevation & Depth, Shapes,
    Components, Do's and Don'ts). The serializer (``writer.py``) emits
    them in that order; missing sections are omitted, present sections
    must be non-empty.
    """

    front_matter: FrontMatter
    overview: str
    colors_md: str = ""
    typography_md: str = ""
    layout: str = ""
    elevation: str = ""
    shapes: str = ""
    components_md: str = ""
    dos_and_donts: str = ""
