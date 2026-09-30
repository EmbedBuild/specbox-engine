"""Does a document use only values of the system? (US-49 · UC-4901 AC-01).

``find_values_outside`` scans a DESIGN.md (YAML front-matter + Markdown body)
and returns every design value that the system tokens do not define: colours
(hex, ``rgb()``/``rgba()``/``hsl()``), lengths and durations (px, rem, em, ch,
%, ms, s), font weights, unitless line heights, font families and Stitch
enums that stand for a value (``roundness``, ``headlineFont``…).

The allowed set is built from the token *values* only (never from the prose
``usage`` notes), so a value that appears in the document but not in a token
is a deviation — exactly what "the document contains no value outside the
system" means.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

from ..stitch_enums import Roundness, StitchFont
from .tokens import SystemTokens, split_family_stack

_HEX_RE = re.compile(r"#(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3,4})\b")
_COLOR_FN_RE = re.compile(r"\b(?:rgba?|hsla?)\([^)]*\)", re.I)
_LENGTH_RE = re.compile(
    r"(?<![\w.#-])-?(?:\d+(?:\.\d+)?|\.\d+)(?:px|rem|em|ch|vh|vw|ms|s|%)(?![\w%])",
    re.I,
)
_WEIGHT_IN_TEXT_RE = re.compile(
    r"(?i)\b(?:font-?weight|weight|pesos?)\b[^\n\d]{0,24}((?:[1-9]00)(?:\s*/\s*[1-9]00)*)\b"
)
_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)

# Stitch enum ↔ value, so an enum in the M3 theme is checked as the value it stands for.
_ROUNDNESS_PX: dict[str, str] = {
    Roundness.ROUND_TWO.value: "2px",
    Roundness.ROUND_FOUR.value: "4px",
    Roundness.ROUND_EIGHT.value: "8px",
    Roundness.ROUND_TWELVE.value: "12px",
    Roundness.ROUND_FULL.value: "9999px",
}
_FONT_KEYS = frozenset({"fontfamily", "headlinefont", "bodyfont", "labelfont"})
_FAMILY_SUBKEYS = frozenset({"heading", "body", "mono", "label", "display"})
_GENERIC_FAMILIES = frozenset(
    {
        "serif",
        "sans-serif",
        "monospace",
        "cursive",
        "fantasy",
        "system-ui",
        "ui-monospace",
        "ui-sans-serif",
        "ui-serif",
        "-apple-system",
    }
)

# Font names that, if they show up in prose, are a family choice. The Stitch
# catalogue plus the usual web fonts: enough to catch an archetype default
# ("Inter", "Roboto") leaking into a document generated from the system.
_KNOWN_FAMILIES: tuple[str, ...] = tuple(
    sorted(
        {f.value.replace("_", " ").lower() for f in StitchFont}
        | {"roboto", "arial", "helvetica", "poppins", "inter", "ibm plex mono", "segoe ui"},
        key=len,
        reverse=True,
    )
)


@dataclass(frozen=True)
class AllowedValues:
    colors: frozenset[str]
    lengths: frozenset[str]
    weights: frozenset[int]
    families: frozenset[str]


@dataclass(frozen=True)
class Deviation:
    """A value in the document that no token defines."""

    kind: str  # color | length | font_weight | line_height | font_family
    value: str
    where: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "value": self.value, "where": self.where}


def normalize_color(value: str) -> str:
    value = value.strip()
    if value.startswith("#"):
        return value.upper()
    return re.sub(r"\s+", "", value).lower()


def normalize_length(value: str) -> str:
    return value.strip().lower()


def allowed_values(tokens: SystemTokens) -> AllowedValues:
    colors: set[str] = set()
    lengths: set[str] = set()
    for per_theme in tokens.colors.values():
        for v in per_theme.values():
            _collect(v, colors, lengths)
    for per_theme in tokens.shadows.values():
        for v in per_theme.values():
            _collect(v, colors, lengths)
    for table in (tokens.radius, tokens.spacing, *tokens.sections.values()):
        for v in table.values():
            _collect(v, colors, lengths)
    for style in tokens.styles.values():
        for v in (style.font_size, style.line_height, style.letter_spacing):
            if v:
                _collect(v, colors, lengths)

    families: set[str] = set()
    for stack in tokens.families.values():
        families.update(name.lower() for name in split_family_stack(stack))

    return AllowedValues(
        colors=frozenset(colors),
        lengths=frozenset(lengths),
        weights=frozenset(tokens.font_weights()),
        families=frozenset(families),
    )


def _collect(text: str, colors: set[str], lengths: set[str]) -> None:
    stripped = text.strip()
    if stripped.startswith("#") or _COLOR_FN_RE.fullmatch(stripped):
        colors.add(normalize_color(stripped))
    for m in _COLOR_FN_RE.finditer(text):
        colors.add(normalize_color(m.group(0)))
    for m in _HEX_RE.finditer(text):
        colors.add(normalize_color(m.group(0)))
    for m in _LENGTH_RE.finditer(text):
        lengths.add(normalize_length(m.group(0)))


def find_values_outside(document: str, tokens: SystemTokens) -> list[Deviation]:
    """Every design value of ``document`` that the system tokens do not define."""

    allowed = allowed_values(tokens)
    out: list[Deviation] = []
    seen: set[tuple[str, str, str]] = set()

    def add(kind: str, value: str, where: str) -> None:
        key = (kind, value, where)
        if key not in seen:
            seen.add(key)
            out.append(Deviation(kind, value, where))

    m = _FRONT_MATTER_RE.match(document)
    if m:
        front, body = m.group(1), m.group(2)
        body_first_line = document.count("\n", 0, m.start(2)) + 1
        data = yaml.safe_load(front) or {}
        _walk(data, (), allowed, add)
    else:
        body, body_first_line = document, 1

    for offset, line in enumerate(body.splitlines()):
        _scan_line(line, f"line {body_first_line + offset}", allowed, add)
    return out


def _walk(node: Any, path: tuple[str, ...], allowed: AllowedValues, add) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            _walk(v, (*path, str(k)), allowed, add)
        return
    if isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, (*path, str(i)), allowed, add)
        return

    where = "front-matter: " + ".".join(path)
    keys = [p.lower() for p in path]
    last = keys[-1] if keys else ""

    if "fontweight" in keys or "weight" in last:
        try:
            weight = int(str(node))
        except ValueError:
            weight = None
        if weight is not None and weight not in allowed.weights:
            add("font_weight", str(node), where)
        return
    if "lineheight" in keys and isinstance(node, (int, float)) and not isinstance(node, bool):
        add("line_height", str(node), where)
        return
    if last == "roundness" and isinstance(node, str):
        px = _ROUNDNESS_PX.get(node)
        if px and normalize_length(px) not in allowed.lengths:
            add("length", f"{node} ({px})", where)
        return
    if isinstance(node, str) and (
        last in _FONT_KEYS or (len(keys) >= 2 and keys[-2] == "fontfamily" and last in _FAMILY_SUBKEYS)
    ):
        for name in _family_names(node):
            if name not in allowed.families and name not in _GENERIC_FAMILIES:
                add("font_family", name, where)
        return
    if isinstance(node, str):
        _scan_values(node, where, allowed, add)


def _family_names(value: str) -> list[str]:
    if "," not in value and "_" in value and value.upper() == value:
        return [value.replace("_", " ").lower()]  # Stitch enum, e.g. IBM_PLEX_SANS
    return [name.lower() for name in split_family_stack(value)]


def _scan_values(text: str, where: str, allowed: AllowedValues, add) -> None:
    for m in _COLOR_FN_RE.finditer(text):
        if normalize_color(m.group(0)) not in allowed.colors:
            add("color", m.group(0), where)
    stripped = _COLOR_FN_RE.sub(" ", text)
    for m in _HEX_RE.finditer(stripped):
        value = m.group(0)
        digits = value[1:]
        if len(digits) in (3, 4) and not re.search(r"[A-Fa-f]", digits):
            continue  # "#128" is an issue number, not a colour
        if normalize_color(value) not in allowed.colors:
            add("color", value, where)
    for m in _LENGTH_RE.finditer(stripped):
        if normalize_length(m.group(0)) not in allowed.lengths:
            add("length", m.group(0), where)


def _scan_line(line: str, where: str, allowed: AllowedValues, add) -> None:
    _scan_values(line, where, allowed, add)
    for m in _WEIGHT_IN_TEXT_RE.finditer(line):
        for part in m.group(1).split("/"):
            weight = int(part.strip())
            if weight not in allowed.weights:
                add("font_weight", str(weight), where)
    lowered = line.lower()
    for family in _KNOWN_FAMILIES:
        if family in allowed.families:
            continue
        if re.search(rf"(?<![\w-]){re.escape(family)}(?![\w-])", lowered):
            add("font_family", family, where)
