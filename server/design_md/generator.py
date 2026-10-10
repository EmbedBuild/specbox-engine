"""Build a :class:`DesignMd` from SpecBox project inputs.

When the project has system tokens (``design-system.tokens.json``, US-49 ·
UC-4901) they are the only source: the document is built by
:mod:`server.design_md.system_view` and nothing below is read.

Otherwise the generator reads, in order of preference, from:

1. ``doc/brand/brand_kit.md`` — palette, typography (canonical from ``/visual-setup``)
2. ``doc/veg/{archetype}.md`` — motion, density, mood (from VEG)
3. ``doc/app/app_prd.md`` zone ``vision`` + zone ``audience``
4. ``doc/app/app_spec.md`` zone ``brand_visual``

Where an input is missing or partial, defaults from the closest VEG
archetype (corporate / startup / creative / consumer / gen_z / gov)
fill the gap. The generator never raises on missing inputs — it always
produces a valid DesignMd, marking auto-filled fields in the body
sections so the user sees what came from where.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ..design_system.tokens import SystemTokens
from .archetypes import ARCHETYPES, ArchetypeId, default_archetype
from .schema import (
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
from .system_view import build_design_md_from_system

# ── Inputs ──────────────────────────────────────────────────────────────


@dataclass
class GeneratorInputs:
    """Opaque bag of optional inputs the generator may use.

    Each input can come as a path (local server) or as text the client sent
    (content-passing, the only mode of a remote server). Text wins.
    """

    project_root: Path | None
    project_name: str
    brand_kit_path: Path | None = None
    veg_path: Path | None = None
    app_prd_path: Path | None = None
    app_spec_path: Path | None = None
    archetype_override: ArchetypeId | None = None
    brand_kit_text: str | None = None
    veg_text: str | None = None
    app_prd_text: str | None = None
    app_spec_text: str | None = None
    system_tokens: SystemTokens | None = None


# ── Public API ──────────────────────────────────────────────────────────


def generate_design_md(inputs: GeneratorInputs) -> DesignMd:
    """Synthesise a DesignMd. Always returns a valid model."""

    app_prd = _text(inputs.app_prd_text, inputs.app_prd_path)

    if inputs.system_tokens is not None:
        return build_design_md_from_system(
            inputs.system_tokens,
            project_name=inputs.project_name,
            overview_text=_vision_paragraph(app_prd),
        )

    archetype = (
        inputs.archetype_override
        or _detect_archetype(inputs)
        or default_archetype()
    )
    base = ARCHETYPES[archetype]

    brand_kit = _text(inputs.brand_kit_text, inputs.brand_kit_path)
    veg = _text(inputs.veg_text, inputs.veg_path)
    app_spec = _text(inputs.app_spec_text, inputs.app_spec_path)

    palette = _extract_palette(brand_kit) or base.palette
    typo = _extract_typography(brand_kit, app_spec) or base.typography
    rounded = base.rounded
    spacing = base.spacing
    components = base.components

    fm = FrontMatter(
        name=inputs.project_name,
        version="1.0.0",
        generated_by="specbox-engine v5.31.0",
        colors=Colors(**palette),
        typography=Typography(**typo),
        rounded=Rounded(**rounded),
        spacing=Spacing(**spacing),
        components=Components(**components),
    )

    overview = _build_overview(app_prd, base.tone, inputs.project_name)
    colors_md = _build_colors_md(palette, base.color_guidance)
    typography_md = _build_typography_md(typo, base.typography_guidance)
    layout = base.layout_guidance
    elevation = base.elevation_guidance
    shapes = base.shapes_guidance
    components_md = base.components_guidance
    dos_and_donts = _build_dos_and_donts(
        base.dos, base.donts, veg, refusals=_extract_refusals(brand_kit)
    )

    return DesignMd(
        front_matter=fm,
        overview=overview,
        colors_md=colors_md,
        typography_md=typography_md,
        layout=layout,
        elevation=elevation,
        shapes=shapes,
        components_md=components_md,
        dos_and_donts=dos_and_donts,
    )


# ── Detection ───────────────────────────────────────────────────────────


def _detect_archetype(inputs: GeneratorInputs) -> ArchetypeId | None:
    """Map VEG archetype mentioned in inputs to our 6 canonical ids."""

    veg = _text(inputs.veg_text, inputs.veg_path)
    if veg:
        text = veg.lower()
        # VEG templates name the archetype on the "Arquetipo" line.
        for ar in ARCHETYPES:
            if f"arquetipo: {ar.value}" in text or f"archetype: {ar.value}" in text:
                return ar
    return None


# ── Brand kit extraction ────────────────────────────────────────────────

# Brand Kits in SpecBox follow a loose Markdown convention; we extract
# defensively. Missing values fall back to the archetype.

_HEX_LINE_RE = re.compile(r"#([0-9A-Fa-f]{6,8})")
_KV_RE = re.compile(r"^[-*]?\s*([A-Za-z][\w \-]+?)\s*[:=]\s*(.+?)\s*$", re.M)
# Fila de la tabla «Paleta» del brand kit de /visual-setup: | Rol | #hex | Función |
_TABLE_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*`?(#[0-9A-Fa-f]{6,8})\b", re.M)

# Rol (en inglés o en español, sin tildes) → clave del DESIGN.md. Las claves que no
# están en el esquema (secondary, accent, neutral) viajan como extra: Colors las admite.
_ROLE_KEYS = {
    "primary": "primary", "primary_color": "primary", "accion": "primary", "action": "primary",
    "primario": "primary",
    "primary_hover": "primary_hover", "hover": "primary_hover",
    "background": "background", "bg": "background", "fondo": "background",
    "surface": "surface", "superficie": "surface",
    "text": "text_primary", "text_primary": "text_primary", "texto": "text_primary",
    "text_secondary": "text_secondary", "muted": "text_secondary",
    "texto_secundario": "text_secondary",
    "border": "border", "borde": "border",
    "error": "error", "danger": "error",
    "success": "success", "exito": "success",
    "warning": "warning", "aviso": "warning",
    "secondary": "secondary", "secundario": "secondary",
    "accent": "accent", "acento": "accent",
    "neutral": "neutral",
}


def _role_key(raw: str) -> str | None:
    plain = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    key = re.sub(r"[*`]", "", plain).strip().lower().replace(" ", "_").replace("-", "_")
    return _ROLE_KEYS.get(key)


def _extract_palette(text: str | None) -> dict | None:
    if not text:
        return None
    palette: dict[str, str] = {}
    for m in _KV_RE.finditer(text):
        key = _role_key(m.group(1))
        hex_match = _HEX_LINE_RE.search(m.group(2).strip())
        if key and hex_match:
            palette[key] = "#" + hex_match.group(1).upper()
    for m in _TABLE_ROW_RE.finditer(text):
        key = _role_key(m.group(1))
        if key and key not in palette:
            palette[key] = m.group(2).upper()
    if not {"primary", "background", "text_primary"} <= palette.keys():
        return None
    return palette


_FONT_ROLE_RE = re.compile(
    r"^[-*]\s*\*\*(heading|headline|titulos|títulos|body|texto)\*\*\s*:\s*([A-Za-z][A-Za-z0-9 \-]+)",
    re.I | re.M,
)


def _extract_typography(brand_kit: str | None, app_spec: str | None) -> dict | None:
    """Pull font families from brand kit; sizes default to archetype.

    Reads the brand kit of /visual-setup («- **Heading**: Familia (…)» and
    «- **Body**: …») and, failing that, a «font-family: …» line.
    """
    text = (brand_kit or "") + "\n" + (app_spec or "")
    if not text.strip():
        return None
    roles: dict[str, str] = {}
    for m in _FONT_ROLE_RE.finditer(brand_kit or ""):
        role = "heading" if m.group(1).lower() in {"heading", "headline", "titulos", "títulos"} else "body"
        roles.setdefault(role, m.group(2).strip())
    if roles:
        heading = roles.get("heading") or roles["body"]
        body = roles.get("body") or heading
    else:
        fam_match = re.search(
            r"(?:font[_ -]?family|tipografia|typography)\s*[:=]\s*['\"]?([A-Za-z][A-Za-z0-9 ,\-]+)",
            text,
            re.I,
        )
        if not fam_match:
            return None
        heading = body = fam_match.group(1).strip().rstrip(",")
    return {
        "fontFamily": {"heading": heading, "body": body},
        "fontSize": {"h1": "32px", "h2": "24px", "h3": "20px", "body": "16px", "caption": "13px"},
        "fontWeight": {"regular": 400, "medium": 500, "semibold": 600, "bold": 700},
        "lineHeight": {"tight": 1.2, "normal": 1.5, "relaxed": 1.75},
    }


# ── Builders for body sections ──────────────────────────────────────────


def _read_text(path: Path | None) -> str | None:
    if path and path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None
    return None


def _text(text: str | None, path: Path | None) -> str | None:
    """Client-sent text wins over a path (content-passing contract)."""
    return text if text is not None else _read_text(path)


def _vision_paragraph(app_prd: str | None) -> str | None:
    """First paragraph after a "Vision"/"Visión" heading of app_prd.md."""
    if not app_prd:
        return None
    m = re.search(
        r"(?:^|\n)#{1,3}\s*(?:vision|visión|visio?n)\b[^\n]*\n+(.+?)(?:\n#{1,3}\s|$)",
        app_prd,
        re.I | re.S,
    )
    if not m:
        return None
    return m.group(1).strip().split("\n\n", 1)[0]


def _build_overview(app_prd: str | None, tone: str, project_name: str) -> str:
    paragraph = _vision_paragraph(app_prd)
    if paragraph:
        return f"{paragraph}\n\n**Voice & tone**: {tone}"
    return (
        f"{project_name} — visión consolidada por SpecBox a partir del Brand Kit "
        f"y la VEG del proyecto.\n\n**Voice & tone**: {tone}"
    )


def _build_colors_md(palette: dict, guidance: str) -> str:
    lines = ["Paleta canónica del proyecto. Siempre referenciar por hex code o por token reference, nunca por nombre de color en lenguaje natural.", ""]
    for k, v in palette.items():
        lines.append(f"- **{k}**: `{v}`")
    if guidance:
        lines.append("")
        lines.append(guidance)
    return "\n".join(lines)


def _build_typography_md(typo: dict, guidance: str) -> str:
    fam = typo.get("fontFamily", {})
    sizes = typo.get("fontSize", {})
    parts = [
        f"**Heading**: `{fam.get('heading', 'Inter, sans-serif')}`",
        f"**Body**: `{fam.get('body', 'Inter, sans-serif')}`",
        "",
        "**Tamaños**: " + ", ".join(f"{k}={v}" for k, v in sizes.items()),
    ]
    if guidance:
        parts.append("")
        parts.append(guidance)
    return "\n".join(parts)


_REFUSALS_HEADING_RE = re.compile(
    r"^#{2,4}\s*(?:lo que se rehúsa|lo que se rehusa|refuse|what we refuse)\b[^\n]*$", re.I | re.M
)


def _extract_refusals(brand_kit: str | None) -> list[str]:
    """Bullets of the «Lo que se rehúsa» section the direction writes (US-90 · UC-9002)."""
    if not brand_kit:
        return []
    m = _REFUSALS_HEADING_RE.search(brand_kit)
    if not m:
        return []
    items: list[str] = []
    for line in brand_kit[m.end():].splitlines():
        if re.match(r"^#{1,4}\s", line):
            break
        bullet = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
        if bullet:
            items.append(bullet.group(1))
    return items


def _build_dos_and_donts(
    dos: list[str], donts: list[str], veg: str | None, refusals: list[str] | None = None
) -> str:
    lines = ["**Do's**"]
    for d in dos:
        lines.append(f"- {d}")
    lines.append("")
    lines.append("**Don'ts**")
    for d in donts:
        lines.append(f"- {d}")
    if refusals:
        # La dirección del proyecto (UC-9002): manda sobre los don'ts genéricos del arquetipo.
        lines.append("")
        lines.append("**Lo que se rehúsa (dirección del proyecto)**")
        for r in refusals:
            lines.append(f"- {r}")
    if veg:
        # Surface VEG-specific overrides if present (≤120 chars, single line).
        m = re.search(r"(?:^|\n)#+\s*(?:override|do)s?[^\n]*\n+(.+?)(?:\n#|$)", veg, re.I | re.S)
        if m:
            lines.append("")
            lines.append("**VEG overrides**")
            lines.append(m.group(1).strip()[:500])
    return "\n".join(lines)
