"""System design tokens — what the engine's design tools read (US-49 · UC-4901).

A project *has system tokens* when it carries a ``design-system.tokens.json``:
the Design System tokens format that ``@specbox/tokens`` publishes into every
SpecBox app (and that a claude.ai Design System artifact consumes). When it is
present, the design tools take colours, typography, radii and states from it
instead of a separate brand kit or an archetype default.

Pure module: it parses a string and never touches the filesystem, so it works
the same with a local or a remote MCP server (the client sends the content).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

SYSTEM_TOKENS_FILENAME = "design-system.tokens.json"

SYSTEM_TOKENS_GUIDE_URL = "https://github.com/EmbedBuild/specbox-engine/blob/main/doc/guides/design-system-tokens.md"

#: Where the file usually lives, relative to the project root. The skills look
#: here before calling a tool; with a local server the tool looks here itself.
#: The first four are where ``npm run sync`` of ``@specbox/tokens`` writes it.
SYSTEM_TOKENS_CANDIDATE_PATHS: tuple[str, ...] = (
    "doc/design/design-system.tokens.json",
    "src/styles/tokens/design-system.tokens.json",
    "apps/web/src/styles/tokens/design-system.tokens.json",
    "web/src/styles/tokens/design-system.tokens.json",
    "packages/tokens/dist/design-system.tokens.json",
    "design-system.tokens.json",
)

#: Semantic role → token names accepted for it, in order of preference. The
#: first names are the SpecBox system's own («Tinta»); the rest let any
#: project that uses the same format with plainer names be read too.
COLOR_ROLES: dict[str, tuple[str, ...]] = {
    "primary": ("accent", "primary", "brand"),
    "primary_hover": ("accent-hover", "primary-hover"),
    "on_primary": ("on-accent", "on-primary"),
    "background": ("paper-000", "background", "bg"),
    "surface": ("paper-100", "surface"),
    "text_primary": ("ink-900", "text-primary", "text", "foreground"),
    "text_secondary": ("ink-700", "text-secondary", "muted"),
    "border": ("line-200", "border"),
    "error": ("danger-text", "status-blocked-text", "error"),
    "success": ("success-text", "status-done-text", "success"),
    "warning": ("warning-text", "status-review-text", "warning"),
}
REQUIRED_COLOR_ROLES: tuple[str, ...] = ("primary", "background", "text_primary")

TEXT_ROLES: dict[str, tuple[str, ...]] = {
    "h1": ("display-xl", "h1", "display"),
    "h2": ("display-lg", "h2", "headline"),
    "h3": ("display-md", "h3", "title"),
    "body": ("body-md", "body", "body-lg"),
    "caption": ("caption",),
    "label": ("label",),
}
REQUIRED_TEXT_ROLES: tuple[str, ...] = ("h1", "h2", "body")

RADIUS_ROLES: dict[str, tuple[str, ...]] = {
    "sm": ("radius-sm", "sm"),
    "md": ("radius-md", "md"),
    "lg": ("radius-lg", "lg"),
    "full": ("radius-pill", "radius-full", "pill", "full"),
}

SPACING_ROLES: dict[str, tuple[str, ...]] = {
    "xs": ("space-1", "xs"),
    "sm": ("space-2", "sm"),
    "md": ("space-4", "md"),
    "lg": ("space-6", "lg"),
    "xl": ("space-8", "xl"),
    "xxl": ("space-12", "xxl"),
}

# Sections with their own model; any other ``{"tokens": [...]}`` section
# (density, layout, stroke, zIndex, duration, easing…) is kept as-is.
_MODELLED_SECTIONS = frozenset({"color", "type", "spacing", "radius", "shadow"})
_ALIAS_RE = re.compile(r"^\{([A-Za-z0-9_.-]+)\}$")
_HEX_RE = re.compile(r"^#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
_MAX_ALIAS_DEPTH = 10


class SystemTokensError(ValueError):
    """The tokens file is there but cannot be used (malformed or incomplete)."""


def is_hex_color(value: str | None) -> bool:
    return bool(value) and bool(_HEX_RE.match(value))


@dataclass(frozen=True)
class TextStyle:
    """One named text style (``display-xl``, ``body-md``…)."""

    name: str
    family_key: str
    family: str
    font_size: str
    line_height: str | None
    font_weight: int | None
    letter_spacing: str | None = None


@dataclass(frozen=True)
class SystemTokens:
    """The parsed system: every value the design tools may use, and nothing else."""

    name: str
    version: str
    source: str | None
    themes: tuple[str, ...]
    colors: dict[str, dict[str, str]]
    families: dict[str, str]
    styles: dict[str, TextStyle]
    radius: dict[str, str]
    spacing: dict[str, str]
    shadows: dict[str, dict[str, str]]
    sections: dict[str, dict[str, str]]

    # ── lookups ─────────────────────────────────────────────────────────

    @property
    def default_theme(self) -> str:
        return "light" if "light" in self.themes else self.themes[0]

    def color(self, token: str, theme: str | None = None) -> str | None:
        per_theme = self.colors.get(token)
        if not per_theme:
            return None
        return per_theme.get(theme or self.default_theme)

    def role_color_name(self, role: str) -> str | None:
        for name in COLOR_ROLES.get(role, ()):
            if name in self.colors:
                return name
        return None

    def role_color(self, role: str, theme: str | None = None) -> str | None:
        name = self.role_color_name(role)
        return self.color(name, theme) if name else None

    def text_role(self, role: str) -> TextStyle | None:
        for name in TEXT_ROLES.get(role, ()):
            if name in self.styles:
                return self.styles[name]
        return None

    def radius_role(self, role: str) -> str | None:
        return _first(self.radius, RADIUS_ROLES.get(role, ()))

    def spacing_role(self, role: str) -> str | None:
        return _first(self.spacing, SPACING_ROLES.get(role, ()))

    def family_names(self, key: str) -> list[str]:
        """Font names of a family stack, unquoted, in order."""
        return split_family_stack(self.families.get(key, ""))

    def primary_family(self, key: str) -> str | None:
        names = self.family_names(key)
        return names[0] if names else None

    def font_weights(self) -> set[int]:
        return {s.font_weight for s in self.styles.values() if s.font_weight is not None}

    def describe(self) -> dict[str, Any]:
        """Short provenance record for tool responses and front-matter."""
        return {
            "kind": "system_tokens",
            "path": self.source,
            "name": self.name,
            "version": self.version,
        }


def split_family_stack(stack: str) -> list[str]:
    return [part.strip().strip("\"'").strip() for part in stack.split(",") if part.strip()]


def _first(table: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        if name in table:
            return table[name]
    return None


# ── parsing ─────────────────────────────────────────────────────────────


def parse_system_tokens(content: str, *, source: str | None = None) -> SystemTokens:
    """Parse a ``design-system.tokens.json`` string.

    Raises :class:`SystemTokensError` with an actionable message when the file
    is not JSON, does not follow the format, or lacks a role the design tools
    need (primary, background and text colours; h1, h2 and body styles).
    """

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise SystemTokensError(f"{SYSTEM_TOKENS_FILENAME} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemTokensError(f"{SYSTEM_TOKENS_FILENAME} must be a JSON object")

    themes, colors = _parse_colors(data.get("color"))
    families, styles = _parse_type(data.get("type"))
    radius = _parse_flat(data.get("radius"))
    spacing = _parse_flat(data.get("spacing"))
    shadows = _parse_themed(data.get("shadow"), themes)
    sections: dict[str, dict[str, str]] = {}
    for key, section in data.items():
        if key in _MODELLED_SECTIONS or not isinstance(section, dict):
            continue
        if isinstance(section.get("tokens"), list):
            sections[key] = {
                str(t.get("name")): _plain(t.get("value"))
                for t in section["tokens"]
                if isinstance(t, dict) and t.get("name") is not None
            }

    tokens = SystemTokens(
        name=str(data.get("name") or "design system"),
        version=str(data.get("version") or ""),
        source=source,
        themes=themes,
        colors=colors,
        families=families,
        styles=styles,
        radius=radius,
        spacing=spacing,
        shadows=shadows,
        sections=sections,
    )
    _require_roles(tokens)
    return tokens


def _parse_colors(section: Any) -> tuple[tuple[str, ...], dict[str, dict[str, str]]]:
    if not isinstance(section, dict) or not isinstance(section.get("tokens"), list):
        raise SystemTokensError("the file has no colour tokens (color.tokens)")

    themes = tuple(str(t["id"]) for t in section.get("themes") or [] if isinstance(t, dict) and t.get("id"))
    raw: dict[str, Any] = {}
    for entry in section["tokens"]:
        if isinstance(entry, dict) and entry.get("name"):
            raw[str(entry["name"])] = entry.get("value")
    if not raw:
        raise SystemTokensError("the file has no colour tokens (color.tokens)")
    if not themes:
        found = {k for v in raw.values() if isinstance(v, dict) for k in v}
        themes = tuple(sorted(found)) or ("light",)

    def per_theme(value: Any) -> dict[str, str]:
        if isinstance(value, dict):
            return {th: str(value[th]) for th in themes if value.get(th) is not None}
        return {th: str(value) for th in themes}

    unresolved = {name: per_theme(value) for name, value in raw.items()}

    def resolve(name: str, theme: str, depth: int = 0) -> str:
        if depth > _MAX_ALIAS_DEPTH:
            raise SystemTokensError(f"alias cycle while resolving colour {name!r}")
        value = unresolved.get(name, {}).get(theme)
        if value is None:
            raise SystemTokensError(f"colour {name!r} has no value for theme {theme!r}")
        alias = _ALIAS_RE.match(value.strip())
        if not alias:
            return value.strip()
        target = alias.group(1)
        if target not in unresolved:
            raise SystemTokensError(f"colour {name!r} points to {target!r}, which does not exist")
        return resolve(target, theme, depth + 1)

    colors = {name: {theme: resolve(name, theme) for theme in values} for name, values in unresolved.items()}
    return themes, colors


def _parse_type(section: Any) -> tuple[dict[str, str], dict[str, TextStyle]]:
    if not isinstance(section, dict):
        raise SystemTokensError("the file has no typography (type)")
    families = {str(k): str(v) for k, v in (section.get("families") or {}).items() if v}
    if not families:
        raise SystemTokensError("the file has no font families (type.families)")

    styles: dict[str, TextStyle] = {}
    for group in section.get("groups") or []:
        if not isinstance(group, dict):
            continue
        for style in group.get("styles") or []:
            if not isinstance(style, dict) or not style.get("name"):
                continue
            family_key = str(style.get("family") or group.get("family") or "")
            if family_key not in families:
                raise SystemTokensError(
                    f"text style {style['name']!r} uses family {family_key!r}, which type.families does not define"
                )
            weight = style.get("fontWeight")
            styles[str(style["name"])] = TextStyle(
                name=str(style["name"]),
                family_key=family_key,
                family=families[family_key],
                font_size=str(style.get("fontSize") or ""),
                line_height=_opt(style.get("lineHeight")),
                font_weight=int(weight) if weight is not None else None,
                letter_spacing=_opt(style.get("letterSpacing")),
            )
    return families, styles


def _parse_flat(section: Any) -> dict[str, str]:
    if not isinstance(section, dict):
        return {}
    return {
        str(t["name"]): _plain(t.get("value"))
        for t in section.get("tokens") or []
        if isinstance(t, dict) and t.get("name")
    }


def _parse_themed(section: Any, themes: tuple[str, ...]) -> dict[str, dict[str, str]]:
    if not isinstance(section, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for t in section.get("tokens") or []:
        if not isinstance(t, dict) or not t.get("name"):
            continue
        value = t.get("value")
        if isinstance(value, dict):
            out[str(t["name"])] = {str(k): str(v) for k, v in value.items()}
        else:
            out[str(t["name"])] = {th: str(value) for th in themes}
    return out


def _plain(value: Any) -> str:
    if isinstance(value, dict):
        return " · ".join(f"{k} {v}" for k, v in value.items())
    return "" if value is None else str(value)


def _opt(value: Any) -> str | None:
    return None if value is None or value == "" else str(value)


def _require_roles(tokens: SystemTokens) -> None:
    missing: list[str] = []
    for role in REQUIRED_COLOR_ROLES:
        value = tokens.role_color(role)
        if not is_hex_color(value):
            names = " | ".join(COLOR_ROLES[role])
            missing.append(f"colour {role} ({names}) as a #RRGGBB value")
    for role in REQUIRED_TEXT_ROLES:
        if tokens.text_role(role) is None:
            names = " | ".join(TEXT_ROLES[role])
            missing.append(f"text style {role} ({names})")
    if missing:
        raise SystemTokensError(f"{SYSTEM_TOKENS_FILENAME} lacks what the design tools need: " + "; ".join(missing))
