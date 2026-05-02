"""Validator for Stitch prompts.

Two operating modes:

* ``warn`` (default for v5.31.0): records issues but lets the prompt go
  through. Telemetry is captured so we can measure false-positive rate
  before promoting to strict.
* ``strict``: returns ``valid=False`` on any error; the calling skill is
  expected to ask the user to revise.

Errors detected:

E1  Named colors that aren't hex codes ("coral", "primary blue")
E2  Layer-content mixing: a single prompt that asks both for layout
    moves AND new component additions. Stitch generates better when
    these are separated; the validator emits a ``requires_split`` plan.

Warnings:

W1  Total length above ``MAX_PROMPT_CHARS`` (excludes DESIGN.md prefix)
W2  Layer 1 length above ``MAX_CONTEXT_WORDS``
W3  Layer 2 written as prose instead of a bullet list
W4  Color names mentioned with hex available — auto-resolved if a
    DESIGN.md palette is provided to ``validate_and_normalize``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from ..design_md.schema import Colors

# Limits per the plan §3.4.
MAX_PROMPT_CHARS = 500
MAX_CONTEXT_WORDS = 80

# A small dictionary of common natural-language color names that we
# refuse to let through. We do not aim to be exhaustive — we aim to
# catch the most common Stitch antipattern ("coral", "navy", "muted blue").
_NAMED_COLORS = frozenset(
    {
        "red", "blue", "green", "yellow", "orange", "purple", "pink",
        "violet", "indigo", "cyan", "magenta", "teal", "navy", "coral",
        "lime", "olive", "maroon", "silver", "gold", "beige", "tan",
        "salmon", "turquoise", "lavender", "crimson", "scarlet",
        "amber", "emerald", "jade", "ruby", "rose",
        "muted", "warm", "cool",  # qualifiers used standalone
    }
)

_HEX_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?\b")
_TOKEN_REF_PATTERN = re.compile(r"\{[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+\}")
# Words used to ask Stitch to *move* / *resize* / *reorder*.
_LAYOUT_VERBS = (
    "move", "resize", "reorder", "swap", "rearrange", "shift",
    "reposition", "relocate",
)
# Words used to ask Stitch to *add* / *replace* a component.
_COMPONENT_VERBS = (
    "add", "insert", "replace", "remove", "delete", "introduce",
    "include", "swap in", "swap out",
)
_SECTION_FENCE_RE = re.compile(
    r"^# DESIGN\.md \(canonical\)\n.*?^# End DESIGN\.md\n",
    re.S | re.M,
)


class ValidatorMode(str, Enum):
    WARN = "warn"
    STRICT = "strict"


@dataclass
class ValidationResult:
    valid: bool
    normalized_prompt: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requires_split: bool = False
    split_prompts: list[str] = field(default_factory=list)
    char_count_excluding_design_md: int = 0
    color_substitutions: dict[str, str] = field(default_factory=dict)


# ── Public API ─────────────────────────────────────────────────────────


def validate_and_normalize(
    prompt: str,
    palette: Colors | None = None,
    mode: ValidatorMode = ValidatorMode.WARN,
) -> ValidationResult:
    """Inspect ``prompt`` and either accept, normalize, or reject.

    ``palette`` is the DESIGN.md palette (or ``None`` if no DESIGN.md).
    When present, it's used to auto-resolve named colors to hex (e.g.
    "primary" → ``palette.primary``).
    """

    out = ValidationResult(valid=True, normalized_prompt=prompt)

    # 0. Strip the DESIGN.md fenced block before measuring length —
    #    the prefix can be large and shouldn't count against the user.
    body = _SECTION_FENCE_RE.sub("", prompt)
    out.char_count_excluding_design_md = len(body)

    # E1 / W4 — named colors
    normalized = body
    for name in _scan_named_colors(body):
        hex_for_name = _resolve_color_name(name, palette)
        if hex_for_name:
            normalized = re.sub(
                rf"\b{re.escape(name)}\b",
                hex_for_name,
                normalized,
                flags=re.I,
            )
            out.color_substitutions[name.lower()] = hex_for_name
            out.warnings.append(
                f"W4: replaced color name {name!r} with {hex_for_name} from DESIGN.md"
            )
        else:
            msg = (
                f"E1: color name {name!r} found without hex equivalent. "
                "Use #RRGGBB or {token.ref}."
            )
            out.errors.append(msg)

    # If we substituted colors, re-attach the prefix (if any) for the
    # final normalized_prompt.
    if out.color_substitutions:
        prefix = prompt[: len(prompt) - len(body)]
        out.normalized_prompt = prefix + normalized

    # W1 — total length
    if out.char_count_excluding_design_md > MAX_PROMPT_CHARS:
        out.warnings.append(
            f"W1: prompt body is {out.char_count_excluding_design_md} chars "
            f"(>{MAX_PROMPT_CHARS}). Consider trimming or splitting."
        )

    # W2 — Layer 1 length
    layer1 = _extract_layer(body, "CONTEXT")
    if layer1 and _word_count(layer1) > MAX_CONTEXT_WORDS:
        out.warnings.append(
            f"W2: Layer 1 (CONTEXT) is {_word_count(layer1)} words "
            f"(>{MAX_CONTEXT_WORDS}). Trim non-essential narrative."
        )

    # W3 — Layer 2 as prose
    layer2 = _extract_layer(body, "COMPONENTS")
    if layer2 and not _is_bullet_list(layer2):
        out.warnings.append(
            "W3: Layer 2 (COMPONENTS) reads like prose. "
            "Convert to a bullet list — Stitch parses bullets more reliably."
        )

    # E2 — layout + components mixing
    if _mentions_any(body, _LAYOUT_VERBS) and _mentions_any(body, _COMPONENT_VERBS):
        out.requires_split = True
        out.split_prompts = _propose_split(body)
        msg = (
            "E2: prompt mixes layout changes with component changes. "
            "Stitch generates better when these are separate calls. "
            "See requires_split / split_prompts."
        )
        if mode == ValidatorMode.STRICT:
            out.errors.append(msg)
        else:
            out.warnings.append(msg)

    if mode == ValidatorMode.STRICT and out.errors:
        out.valid = False

    return out


# ── Helpers ─────────────────────────────────────────────────────────────


def _scan_named_colors(text: str) -> list[str]:
    """Find color *names* that aren't part of a hex literal or {token.ref}."""

    found: list[str] = []
    lower = text.lower()
    for name in _NAMED_COLORS:
        for m in re.finditer(rf"\b{re.escape(name)}\b", lower):
            # Skip if this position is inside a hex code or token ref.
            if _is_inside_hex_or_ref(text, m.start()):
                continue
            found.append(name)
            break  # one report per color name is enough
    return found


def _is_inside_hex_or_ref(text: str, pos: int) -> bool:
    for m in _HEX_PATTERN.finditer(text):
        if m.start() <= pos < m.end():
            return True
    for m in _TOKEN_REF_PATTERN.finditer(text):
        if m.start() <= pos < m.end():
            return True
    return False


def _resolve_color_name(name: str, palette: Colors | None) -> str | None:
    """Map a color name to a DESIGN.md palette entry if obvious."""
    if palette is None:
        return None
    n = name.lower()
    # The palette dict carries the SpecBox semantic names (primary,
    # background, etc.). We accept synonyms only when they match.
    pdict = palette.model_dump()
    direct = pdict.get(n)
    if isinstance(direct, str) and direct.startswith("#"):
        return direct
    return None


def _extract_layer(text: str, label: str) -> str:
    """Return the body of a ``# Layer N — LABEL`` block, or empty."""
    pattern = rf"#\s*Layer\s*\d+\s*—\s*{label}\b(.*?)(?=\n#\s*Layer\s*\d+|\Z)"
    m = re.search(pattern, text, re.S | re.I)
    return m.group(1).strip() if m else ""


def _word_count(text: str) -> int:
    return len([w for w in text.split() if w])


def _is_bullet_list(text: str) -> bool:
    """Heuristic: at least 50% of non-empty lines start with ``-`` or ``*``."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) <= 1:
        return False
    bullets = sum(1 for ln in lines if ln.lstrip().startswith(("-", "*")))
    return bullets >= max(2, len(lines) // 2)


def _mentions_any(text: str, verbs: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(re.search(rf"\b{re.escape(v)}\b", lower) for v in verbs)


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _propose_split(prompt: str) -> list[str]:
    """Naive split — produces two prompts, one per intent class.

    Splits at sentence and line boundaries so a single line containing
    both intents ("Move X. Add Y.") gets routed correctly. The plan
    calls for layout-first, components-second so Stitch can settle the
    geometry before the next pass introduces new elements.
    """

    layout_units: list[str] = []
    component_units: list[str] = []
    other_units: list[str] = []

    for line in prompt.splitlines():
        for sentence in _SENTENCE_SPLIT_RE.split(line):
            s = sentence.strip()
            if not s:
                continue
            l = s.lower()
            is_layout = any(re.search(rf"\b{re.escape(v)}\b", l) for v in _LAYOUT_VERBS)
            is_component = any(
                re.search(rf"\b{re.escape(v)}\b", l) for v in _COMPONENT_VERBS
            )
            if is_layout and not is_component:
                layout_units.append(s)
            elif is_component and not is_layout:
                component_units.append(s)
            elif is_layout and is_component:
                # Truly ambiguous — duplicate to both buckets so the
                # human can decide on the next pass.
                layout_units.append(s)
                component_units.append(s)
            else:
                other_units.append(s)

    base = " ".join(other_units).strip()
    layout_prompt = (base + "\n" + "\n".join(layout_units)).strip()
    component_prompt = (base + "\n" + "\n".join(component_units)).strip()
    return [layout_prompt, component_prompt]
