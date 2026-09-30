"""DESIGN.md built from the project's system tokens (US-49 · UC-4901 AC-01).

When a project has ``design-system.tokens.json``, the brand kit and the VEG
archetypes are not read at all: every colour, font, size, weight, radius,
spacing and shadow of the document — front-matter, body and the Material 3
view Stitch parses — is a token value. The body names tokens and prints
their values; it never adds a value of its own, and
:func:`server.design_system.conformance.find_values_outside` checks that.
"""

from __future__ import annotations

from typing import Any

from ..design_system.tokens import (
    COLOR_ROLES,
    SYSTEM_TOKENS_FILENAME,
    SystemTokens,
    TextStyle,
    is_hex_color,
)
from ..stitch_enums import ColorMode, ColorVariant, Roundness, StitchFont
from ..veg.material3_mapper import Material3Theme
from .material3_view import (
    _FAMILY_TO_FONT,
    _ROUNDED_TO_ENUM,
    Material3FrontMatter,
)
from .schema import (
    Colors,
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

# Roles of the SpecBox front-matter view, in output order.
_FRONT_MATTER_COLOR_ROLES: tuple[str, ...] = tuple(COLOR_ROLES)
_WEIGHT_NAMES: dict[int, str] = {400: "regular", 500: "medium", 600: "semibold", 700: "bold"}
_TEXT_ROLE_ORDER: tuple[str, ...] = ("h1", "h2", "h3", "body", "caption", "label")
_SECTION_TITLES: dict[str, str] = {
    "density": "Densidad",
    "layout": "Layout",
    "stroke": "Trazos",
    "zIndex": "Capas",
    "duration": "Duraciones",
    "easing": "Curvas de movimiento",
}


def source_label(tokens: SystemTokens) -> str:
    return tokens.source or SYSTEM_TOKENS_FILENAME


# ── SpecBox view ────────────────────────────────────────────────────────


def build_design_md_from_system(
    tokens: SystemTokens,
    *,
    project_name: str,
    overview_text: str | None = None,
) -> DesignMd:
    theme = tokens.default_theme

    palette: dict[str, str] = {}
    for role in _FRONT_MATTER_COLOR_ROLES:
        value = tokens.role_color(role, theme)
        if is_hex_color(value):
            palette[role] = value  # type: ignore[assignment]
    for name, per_theme in tokens.colors.items():
        value = per_theme.get(theme)
        if name.startswith("status-") and is_hex_color(value):
            palette[name.replace("-", "_")] = value  # type: ignore[assignment]

    roles = {role: tokens.text_role(role) for role in _TEXT_ROLE_ORDER}
    h1, body = roles["h1"], roles["body"]
    assert h1 is not None and body is not None  # guaranteed by parse_system_tokens

    families: dict[str, Any] = {"heading": h1.family, "body": body.family}
    if "mono" in tokens.families:
        families["mono"] = tokens.families["mono"]

    sizes = {role: s.font_size for role, s in roles.items() if s is not None}
    line_heights: dict[str, Any] = {"tight": None, "normal": None, "relaxed": None}
    line_heights.update({role: s.line_height for role, s in roles.items() if s and s.line_height})
    weights: dict[str, Any] = {name: None for name in _WEIGHT_NAMES.values()}
    for weight in sorted(tokens.font_weights()):
        weights[_WEIGHT_NAMES.get(weight, f"w{weight}")] = weight

    rounded = {role: tokens.radius_role(role) for role in ("sm", "md", "lg", "full")}
    spacing = {role: tokens.spacing_role(role) for role in ("xs", "sm", "md", "lg", "xl", "xxl")}

    on_primary = "{colors.on_primary}" if "on_primary" in palette else None
    components = {
        "button_primary": {
            "backgroundColor": "{colors.primary}",
            "textColor": on_primary,
            "rounded": "{rounded.md}",
            "padding": "{spacing.sm} {spacing.md}",
        },
        "card": {
            "backgroundColor": "{colors.surface}" if "surface" in palette else "{colors.background}",
            "rounded": "{rounded.lg}",
            "padding": "{spacing.lg}",
        },
        "input": {
            "backgroundColor": "{colors.background}",
            "textColor": "{colors.text_primary}",
            "rounded": "{rounded.md}",
            "padding": "{spacing.sm} {spacing.md}",
        },
    }

    fm = FrontMatter(
        name=project_name,
        version="1.0.0",
        generated_by="specbox-engine",
        source=tokens.describe(),
        colors=Colors(**palette),
        typography=Typography(
            fontFamily=FontFamily(**families),
            fontSize=FontSize(**sizes),
            fontWeight=FontWeight(**weights),
            lineHeight=LineHeight(**line_heights),
        ),
        rounded=Rounded(**rounded),
        spacing=Spacing(**spacing),
        components=Components(**components),
    )

    return DesignMd(
        front_matter=fm,
        overview=_overview(tokens, project_name, overview_text),
        colors_md=_colors_md(tokens),
        typography_md=_typography_md(tokens),
        layout=_layout_md(tokens),
        elevation=_elevation_md(tokens),
        shapes=_shapes_md(tokens),
        components_md=_components_md(),
        dos_and_donts=_dos_and_donts(tokens),
    )


def _themed(tokens: SystemTokens, per_theme: dict[str, str]) -> str:
    if len(set(per_theme.values())) == 1:
        return f"`{next(iter(per_theme.values()))}`"
    return " · ".join(f"{theme} `{per_theme[theme]}`" for theme in tokens.themes if theme in per_theme)


def _overview(tokens: SystemTokens, project_name: str, overview_text: str | None) -> str:
    lead = overview_text.strip() if overview_text and overview_text.strip() else project_name
    version = f", versión {tokens.version}" if tokens.version else ""
    return (
        f"{lead}\n\n"
        f"**Fuente**: tokens del sistema `{source_label(tokens)}` ({tokens.name}{version}). "
        "Este documento se genera desde ellos y no se edita a mano: para cambiar el diseño "
        "se cambian los tokens y se vuelve a generar."
    )


def _colors_md(tokens: SystemTokens) -> str:
    lines = [
        "Colores del sistema por tema. Referenciar siempre por nombre de token; "
        "nunca escribir el valor directamente en el código.",
        "",
    ]
    for name, per_theme in tokens.colors.items():
        lines.append(f"- **{name}**: {_themed(tokens, per_theme)}")
    return "\n".join(lines)


def _style_line(style: TextStyle) -> str:
    parts = [style.font_size]
    if style.line_height:
        parts.append(f"/ {style.line_height}")
    text = f"- **{style.name}** ({style.family_key}): {' '.join(parts)}"
    if style.font_weight is not None:
        text += f", peso {style.font_weight}"
    if style.letter_spacing:
        text += f", tracking `{style.letter_spacing}`"
    return text


def _typography_md(tokens: SystemTokens) -> str:
    lines = ["**Familias**", ""]
    for key, stack in tokens.families.items():
        lines.append(f"- **{key}**: `{stack}`")
    lines += ["", "**Estilos de texto**", ""]
    lines += [_style_line(style) for style in tokens.styles.values()]
    return "\n".join(lines)


def _table_md(title: str, table: dict[str, str]) -> list[str]:
    if not table:
        return []
    return [f"**{title}**", "", *(f"- **{name}**: `{value}`" for name, value in table.items()), ""]


def _layout_md(tokens: SystemTokens) -> str:
    lines = _table_md("Espaciado", tokens.spacing)
    for key, table in tokens.sections.items():
        lines += _table_md(_SECTION_TITLES.get(key, key), table)
    return "\n".join(lines).strip()


def _elevation_md(tokens: SystemTokens) -> str:
    if not tokens.shadows:
        return ""
    lines = ["Sombras del sistema por tema.", ""]
    for name, per_theme in tokens.shadows.items():
        lines.append(f"- **{name}**: {_themed(tokens, per_theme)}")
    return "\n".join(lines)


def _shapes_md(tokens: SystemTokens) -> str:
    return "\n".join(_table_md("Radios", tokens.radius)).strip()


def _components_md() -> str:
    return (
        "Los componentes se construyen con los tokens de este documento y no introducen "
        "valores propios. Si el proyecto tiene un registro de componentes del sistema, se "
        "usan esos componentes en lugar de crear otros."
    )


def _dos_and_donts(tokens: SystemTokens) -> str:
    families = " y ".join(f"`{tokens.primary_family(key)}`" for key in tokens.families if tokens.primary_family(key))
    max_weight = max(tokens.font_weights()) if tokens.font_weights() else None
    donts = [
        "Colores, tamaños o radios escritos directamente: siempre el token",
        f"Fuentes distintas de {families}",
        "Gradientes en fondos",
    ]
    if max_weight is not None:
        donts.insert(2, f"Pesos por encima de {max_weight}")
    lines = [
        "**Do's**",
        "- Usar solo los tokens de este documento, por su nombre",
        "- Respetar el tema claro y el oscuro con los valores de cada token",
        "- Tratar los diseños de Stitch o Claude Design como candidatos: la fuente de producción son estos tokens",
        "",
        "**Don'ts**",
        *(f"- {d}" for d in donts),
    ]
    return "\n".join(lines)


# ── Material 3 view (what Stitch parses) ────────────────────────────────


def _stitch_font(style: TextStyle | None, warnings: list[str]) -> StitchFont:
    family = None
    if style is not None:
        names = [n for n in (style.family.split(",")) if n.strip()]
        family = names[0].strip().strip("\"'").strip() if names else None
    font = _FAMILY_TO_FONT.get((family or "").lower())
    if font is None:
        warnings.append(
            f"Stitch no tiene la fuente {family!r} del sistema; usará Inter y sus "
            "pantallas no representarán la tipografía del sistema."
        )
        return StitchFont.INTER
    return font


def _roundness(tokens: SystemTokens, warnings: list[str]) -> Roundness:
    def px(value: str | None) -> float | None:
        try:
            return float(value.lower().removesuffix("px")) if value else None
        except ValueError:
            return None

    md = tokens.radius_role("md")
    if md and md.lower() in _ROUNDED_TO_ENUM:
        return _ROUNDED_TO_ENUM[md.lower()]
    radii = {v.lower() for v in tokens.radius.values()}
    candidates = [(px(k), enum) for k, enum in _ROUNDED_TO_ENUM.items() if k in radii]
    target = px(md)
    if candidates and target is not None:
        return min(candidates, key=lambda c: (abs((c[0] or 0) - target), c[0] or 0))[1]
    if candidates:
        return candidates[0][1]
    warnings.append(
        "Ningún radio del sistema coincide con los redondeos de Stitch; se usa 8px, que no está en los tokens."
    )
    return Roundness.ROUND_EIGHT


def _m3_style(style: TextStyle, font: StitchFont) -> dict[str, Any]:
    out: dict[str, Any] = {"fontFamily": font.value, "fontSize": style.font_size}
    if style.font_weight is not None:
        out["fontWeight"] = str(style.font_weight)
    if style.line_height:
        out["lineHeight"] = style.line_height
    if style.letter_spacing:
        out["letterSpacing"] = style.letter_spacing
    return out


def build_material3_from_system(doc: DesignMd, tokens: SystemTokens) -> Material3FrontMatter:
    """Material 3 front-matter for Stitch, with every value taken from the tokens.

    Stitch generates in light mode (the engine's rule), so the light values are
    used; the dark ones stay in the Colors section of the body.
    """

    warnings: list[str] = []
    theme_id = tokens.default_theme

    def role(name: str) -> str | None:
        value = tokens.role_color(name, theme_id)
        return value if is_hex_color(value) else None

    colors: dict[str, str] = {}
    for m3_name, role_name in (
        ("surface", "surface"),
        ("on-surface", "text_primary"),
        ("background", "background"),
        ("on-background", "text_primary"),
        ("primary", "primary"),
        ("on-primary", "on_primary"),
        ("secondary", "primary_hover"),
        ("outline", "border"),
        ("error", "error"),
    ):
        value = role(role_name)
        if value:
            colors[m3_name] = value

    h1 = tokens.text_role("h1")
    h2 = tokens.text_role("h2")
    body = tokens.text_role("body")
    label = tokens.text_role("label") or tokens.text_role("caption") or body
    headline_font = _stitch_font(h1, warnings)
    body_font = _stitch_font(body, warnings)
    label_font = _stitch_font(label, warnings)

    typography: dict[str, dict[str, Any]] = {}
    for key, style, font in (
        ("display-lg", h1, headline_font),
        ("headline-md", h2, headline_font),
        ("body-base", body, body_font),
        ("label-caps", label, label_font),
    ):
        if style is not None:
            typography[key] = _m3_style(style, font)

    primary = role("primary")
    assert primary is not None  # guaranteed by parse_system_tokens
    theme = Material3Theme(
        color_mode=ColorMode.LIGHT,
        color_variant=ColorVariant.FIDELITY,
        roundness=_roundness(tokens, warnings),
        headline_font=headline_font,
        body_font=body_font,
        label_font=label_font,
        custom_color=primary,
        override_primary_color=primary,
        override_secondary_color=role("primary_hover"),
        override_neutral_color=role("border"),
    )

    version = f", versión {tokens.version}" if tokens.version else ""
    notes = [
        f"Fuente: tokens del sistema {source_label(tokens)} ({tokens.name}{version})",
        "Tema claro para Stitch; los valores del tema oscuro están en la sección Colors",
    ]
    return Material3FrontMatter(
        name=doc.front_matter.name,
        theme=theme,
        colors=colors,
        typography=typography,
        veg_notes=notes,
        warnings=warnings,
    )


__all__ = ["build_design_md_from_system", "build_material3_from_system", "source_label"]
