"""Design gaps in code — what the design gate blocks (US-49 · UC-4902).

Scans UI source files and reports, with file and line, the four gaps the
system does not allow:

- ``direct_color``  — a colour written in the code (hex, ``rgb()``/``hsl()``…,
  Tailwind palette classes such as ``bg-blue-500``, Flutter ``Color(0x…)`` /
  ``Colors.x``) instead of a system token.
- ``font_outside``  — a font family the system does not define.
- ``weight_above``  — a font weight above the system maximum (600 in Tinta).
- ``gradient``      — a gradient (the system paints backgrounds flat).

The same rules live in ``.claude/hooks/lib/design-gaps.mjs`` (the hook that
blocks in autopilot); ``tests/fixtures/design_system/code_gap_cases.json`` is
the contract both implementations must meet.

Escape hatches: ``design-gate:ignore`` on the line or the line above;
``design-gate:disable-file`` anywhere in the file. Say why next to it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote_plus

from .tokens import SystemTokens, split_family_stack

UI_EXTENSIONS = frozenset(
    {
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".astro",
        ".vue",
        ".svelte",
        ".html",
        ".dart",
    }
)
_EXCLUDED_SEGMENTS = frozenset(
    {"node_modules", "dist", "build", ".astro", ".next", "coverage", "public", "__tests__", "tests", "test", "e2e"}
)
_EXCLUDED_PREFIXES = ("doc/", "docs/")
_EXCLUDED_FRAGMENTS = ("styles/tokens/", "packages/tokens/")
_EXCLUDED_NAME_RE = re.compile(r"\.(test|spec)\.[a-z]+$|\.d\.ts$")

GENERIC_FAMILIES = frozenset(
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
        "ui-rounded",
        "-apple-system",
        "blinkmacsystemfont",
        "emoji",
        "math",
        "inherit",
        "initial",
        "unset",
        "revert",
        "revert-layer",
    }
)

IGNORE_MARK = "design-gate:ignore"
DISABLE_FILE_MARK = "design-gate:disable-file"

KINDS = ("direct_color", "font_outside", "weight_above", "gradient")

# ── patterns (kept identical to design-gaps.mjs) ────────────────────────

_GRADIENT_RE = re.compile(r"\b(?:repeating-)?(?:linear|radial|conic)-gradient(?=\()")
_TW_GRADIENT_RE = re.compile(
    r"(?<![\w-])bg-(?:gradient-to-[a-z]{1,2}|linear-[a-z0-9-]+|radial(?:-[a-z0-9-]+)?|conic(?:-[a-z0-9-]+)?)(?![\w-])"
)
_DART_GRADIENT_RE = re.compile(r"\b(?:Linear|Radial|Sweep)Gradient(?=\()")

_HEX_RE = re.compile(r"(?:(?<=[:\s,(\[='\"`])|^)#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![0-9a-zA-Z_(-])")
_FUNC_COLOR_RE = re.compile(r"\b(?:rgba?|hsla?|oklch|oklab|lab|lch|hwb)\(([^)]*)\)")
_PALETTE = (
    "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|"
    "indigo|violet|purple|fuchsia|pink|rose"
)
_TW_PREFIX = (
    "bg|text|border(?:-[trblxyse])?|ring|ring-offset|fill|stroke|from|via|to|outline|divide|"
    "placeholder|decoration|shadow|accent|caret"
)
_TW_PALETTE_RE = re.compile(rf"(?<![\w-])(?:{_TW_PREFIX})-(?:{_PALETTE})-(?:50|[1-9]00|950)(?![\w-])")
_TW_BW_RE = re.compile(
    r"(?<![\w-])(?:bg|text|border|ring|fill|stroke|from|via|to|outline|divide)-(?:white|black)(?![\w-])"
)
_DART_COLOR_RE = re.compile(
    r"\bColor\(\s*0x[0-9A-Fa-f]{6,8}\s*\)|\bColor\.from(?:ARGB|RGBO)\(|\bColors\.(?!transparent\b)[a-z][A-Za-z]*(?:\[\d+\])?"
)

_CSS_FONT_RE = re.compile(r"font-family\s*:\s*([^;{}]+)")
_JS_FONT_RE = re.compile(r"fontFamily\s*:\s*(['\"`])([^'\"`]+)\1")
_TW_FONT_RE = re.compile(r"(?<![\w-])font-\[([^\]]+)\]")
_GFONTS_RE = re.compile(r"fonts\.googleapis\.com/css2?\?([^'\"\s)]+)")
_GOOGLEFONTS_DART_RE = re.compile(r"\bGoogleFonts\.([a-z][A-Za-z0-9]*)\(")

_CSS_WEIGHT_RE = re.compile(r"font-weight\s*:\s*(\d{3}|bold|bolder)\b")
_JS_WEIGHT_RE = re.compile(r"fontWeight\s*:\s*['\"]?(\d{3}|bold|bolder)\b")
_TW_WEIGHT_RE = re.compile(r"(?<![\w-])font-(bold|extrabold|black)(?![\w-])")
_TW_WEIGHT_ARBITRARY_RE = re.compile(r"(?<![\w-])font-\[(\d{3})\]")
_DART_WEIGHT_RE = re.compile(r"\bFontWeight\.(w[1-9]00|bold)\b")

_NAMED_WEIGHTS = {"bold": 700, "bolder": 900, "extrabold": 800, "black": 900}


@dataclass(frozen=True)
class DesignSystemRules:
    """What the gate compares against: allowed families and maximum weight."""

    families: frozenset[str]
    max_weight: int

    @classmethod
    def from_tokens(cls, tokens: SystemTokens) -> DesignSystemRules:
        families = {name.lower() for stack in tokens.families.values() for name in split_family_stack(stack)}
        return cls(frozenset(families), max(tokens.font_weights() or {600}))


@dataclass(frozen=True)
class CodeGap:
    kind: str
    file: str
    line: int
    column: int
    value: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "value": self.value,
            "location": f"{self.file}:{self.line}",
        }


def is_ui_source(path: str) -> bool:
    """Is this file part of the UI code the gate checks?"""
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    dot = p.rfind(".")
    if dot == -1 or p[dot:].lower() not in UI_EXTENSIONS:
        return False
    if p.startswith(_EXCLUDED_PREFIXES) or any(f in p for f in _EXCLUDED_FRAGMENTS):
        return False
    if any(seg in _EXCLUDED_SEGMENTS for seg in p.split("/")[:-1]):
        return False
    return not _EXCLUDED_NAME_RE.search(p)


def fix_for(kind: str, rules: DesignSystemRules) -> str:
    families = ", ".join(sorted(f for f in rules.families if f not in GENERIC_FAMILIES)) or "las del sistema"
    return {
        "direct_color": "Usa un token del sistema (su clase o var(--…)) en lugar del color escrito.",
        "font_outside": f"Usa las familias del sistema ({families}) con su clase o variable.",
        "weight_above": f"El peso máximo del sistema es {rules.max_weight}: usa ese peso o uno menor.",
        "gradient": "El sistema pinta los fondos planos: usa un color de superficie del sistema.",
    }[kind]


def scan_files(files: dict[str, str], rules: DesignSystemRules) -> list[CodeGap]:
    """All design gaps of the UI files in ``files`` ({relpath: content})."""
    gaps: list[CodeGap] = []
    for path in sorted(files):
        if is_ui_source(path):
            gaps.extend(scan_file(path, files[path], rules))
    return gaps


def scan_file(path: str, content: str, rules: DesignSystemRules) -> list[CodeGap]:
    if DISABLE_FILE_MARK in content:
        return []
    gaps: list[CodeGap] = []
    in_block: str | None = None  # "*/" or "-->" while inside a block comment
    prev_raw = ""
    for number, raw in enumerate(content.splitlines(), start=1):
        ignored = IGNORE_MARK in raw or IGNORE_MARK in prev_raw
        prev_raw = raw
        line, in_block = _strip_comments(raw, in_block)
        if ignored or not line.strip():
            continue
        for kind, column, value in _line_gaps(line, rules):
            gaps.append(CodeGap(kind, path, number, column, value))
    gaps.sort(key=lambda g: (g.line, g.column, g.kind))
    return gaps


def _strip_comments(raw: str, in_block: str | None) -> tuple[str, str | None]:
    line = raw
    if in_block:
        end = line.find(in_block)
        if end == -1:
            return "", in_block
        line = " " * (end + len(in_block)) + line[end + len(in_block) :]
        in_block = None
    for opener, closer in (("/*", "*/"), ("<!--", "-->")):
        while True:
            start = line.find(opener)
            if start == -1:
                break
            end = line.find(closer, start + len(opener))
            if end == -1:
                line = line[:start]
                in_block = closer
                break
            line = line[:start] + " " * (end + len(closer) - start) + line[end + len(closer) :]
    line = re.sub(r"(^|\s)//.*$", r"\1", line)
    return line, in_block


def _families_of(value: str) -> list[str]:
    out: list[str] = []
    for name in split_family_stack(value.replace("!important", "")):
        name = name.strip().lower()
        if name and not name.startswith(("var(", "theme(")):
            out.append(name)
    return out


def _camel_to_words(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z0-9])", " ", name).lower()


def _line_gaps(line: str, rules: DesignSystemRules):
    def outside(family: str) -> bool:
        return family not in rules.families and family not in GENERIC_FAMILIES

    # gradients
    for rx in (_GRADIENT_RE, _TW_GRADIENT_RE, _DART_GRADIENT_RE):
        for m in rx.finditer(line):
            yield "gradient", m.start(), m.group(0)

    # direct colours
    for m in _HEX_RE.finditer(line):
        digits = m.group(0)[1:]
        before = line[: m.start()]
        if before.endswith("url("):
            continue
        if len(digits) in (3, 4) and digits.isdigit():
            in_value = before[-1:] in ("'", '"', "`", "[", "(") or ":" in before
            if not in_value:
                continue  # "#128" is an issue number unless it sits in a value
        yield "direct_color", m.start(), m.group(0)
    for m in _FUNC_COLOR_RE.finditer(line):
        if "var(" not in m.group(1):
            yield "direct_color", m.start(), m.group(0)
    for rx in (_TW_PALETTE_RE, _TW_BW_RE, _DART_COLOR_RE):
        for m in rx.finditer(line):
            yield "direct_color", m.start(), m.group(0)

    # fonts
    for m in _CSS_FONT_RE.finditer(line):
        for family in _families_of(m.group(1)):
            if outside(family):
                yield "font_outside", m.start(), family
    for m in _JS_FONT_RE.finditer(line):
        for family in _families_of(m.group(2)):
            if outside(family):
                yield "font_outside", m.start(), family
    for m in _TW_FONT_RE.finditer(line):
        raw = m.group(1)
        if raw.isdigit() or raw.startswith(("var(", "length:")):
            continue
        for family in _families_of(raw.replace("_", " ")):
            if outside(family):
                yield "font_outside", m.start(), family
    for m in _GFONTS_RE.finditer(line):
        for part in m.group(1).split("&"):
            if part.startswith("family="):
                family = unquote_plus(part[len("family=") :]).split(":")[0].strip().lower()
                if family and outside(family):
                    yield "font_outside", m.start(), family
    for m in _GOOGLEFONTS_DART_RE.finditer(line):
        if m.group(1) in ("getFont", "config", "asMap"):
            continue
        family = _camel_to_words(m.group(1))
        if outside(family):
            yield "font_outside", m.start(), family

    # weights
    for rx in (_CSS_WEIGHT_RE, _JS_WEIGHT_RE):
        for m in rx.finditer(line):
            value = m.group(1)
            weight = int(value) if value.isdigit() else _NAMED_WEIGHTS[value]
            if weight > rules.max_weight:
                yield "weight_above", m.start(), value
    for m in _TW_WEIGHT_RE.finditer(line):
        if _NAMED_WEIGHTS[m.group(1)] > rules.max_weight:
            yield "weight_above", m.start(), m.group(0)
    for m in _TW_WEIGHT_ARBITRARY_RE.finditer(line):
        if int(m.group(1)) > rules.max_weight:
            yield "weight_above", m.start(), m.group(0)
    for m in _DART_WEIGHT_RE.finditer(line):
        weight = 700 if m.group(1) == "bold" else int(m.group(1)[1:])
        if weight > rules.max_weight:
            yield "weight_above", m.start(), m.group(0)


def design_gap_report(files: dict[str, str], rules: DesignSystemRules, *, system_path: str | None) -> dict:
    """The design section of the visual gap report: findings, verdict and what to do."""
    ui_files = sorted(p for p in files if is_ui_source(p))
    gaps = scan_files(files, rules)
    by_kind = {kind: sum(1 for g in gaps if g.kind == kind) for kind in KINDS}
    return {
        "status": "gaps" if gaps else "clean",
        "gate": "block" if gaps else "pass",
        "total": len(gaps),
        "by_kind": by_kind,
        "findings": [{**g.to_dict(), "fix": fix_for(g.kind, rules)} for g in gaps],
        "how_to_fix": {kind: fix_for(kind, rules) for kind in KINDS if by_kind[kind]},
        "checked_files": ui_files,
        "skipped_files": sorted(p for p in files if p not in ui_files),
        "system": {
            "path": system_path,
            "families": sorted(rules.families),
            "max_weight": rules.max_weight,
        },
        "warnings": [],
    }
