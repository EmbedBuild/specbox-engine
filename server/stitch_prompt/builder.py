"""Build a structured 4-layer prompt for Stitch generation.

Stitch's official prompting guide (Google Stitch docs) recommends:
1. Context (≤80 words) — purpose, audience, platform
2. Components — bulleted list with explicit states
3. Style — hex codes only, token references to DESIGN.md when available
4. Platform — device, breakpoints, interaction model

This module produces strings that conform to that contract by
construction; the validator (``validator.py``) double-checks them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class PromptLayers:
    """Structured input. Builders accept this shape rather than a raw string."""

    # Layer 1
    screen_purpose: str
    audience: str
    platform: str  # DESKTOP | MOBILE | TABLET
    feature_name: str = ""
    prev_screen: str = ""
    next_screen: str = ""

    # Layer 2: components, each as "name (states)" or just "name"
    components: list[str] = field(default_factory=list)

    # Layer 3: style — hex codes only or {token.refs}
    primary_color: str = ""  # required
    background_color: str = ""
    text_color: str = ""
    spacing_token: str = ""  # e.g. "{spacing.md}" or "16px"
    typography_family: str = ""
    typography_h1_px: str = ""
    typography_body_px: str = ""

    # Layer 4
    device: str = "DESKTOP"
    form_factor_breakpoints: list[str] = field(default_factory=list)
    interaction_model: str = "mouse"  # touch | mouse | both


@dataclass
class StitchPrompt:
    """The fully rendered prompt + metadata for telemetry."""

    rendered: str
    char_count: int
    layer_word_counts: dict[str, int]
    components_count: int
    has_design_md_prefix: bool


# ── Builders ────────────────────────────────────────────────────────────


def build_prompt(layers: PromptLayers, design_md_body: str | None = None) -> StitchPrompt:
    """Return a structured 4-layer prompt.

    If ``design_md_body`` is provided, it is prepended verbatim and
    fenced — Stitch reads it as authoritative context for the entire
    generation. The fence marker also lets the validator skip the body
    when measuring prompt length.
    """

    rendered = render_prompt(layers, design_md_body)

    layer_word_counts = {
        "context": _count_words(_render_context(layers)),
        "components": _count_words(_render_components(layers)),
        "style": _count_words(_render_style(layers)),
        "platform": _count_words(_render_platform(layers)),
    }

    return StitchPrompt(
        rendered=rendered,
        char_count=len(rendered),
        layer_word_counts=layer_word_counts,
        components_count=len(layers.components),
        has_design_md_prefix=design_md_body is not None,
    )


def render_prompt(layers: PromptLayers, design_md_body: str | None = None) -> str:
    parts: list[str] = []
    if design_md_body:
        parts.append("# DESIGN.md (canonical)")
        parts.append(design_md_body.strip())
        parts.append("# End DESIGN.md")
        parts.append("")
    parts.append(_render_context(layers))
    parts.append("")
    parts.append(_render_components(layers))
    parts.append("")
    parts.append(_render_style(layers))
    parts.append("")
    parts.append(_render_platform(layers))
    return "\n".join(parts).strip() + "\n"


# ── Layer renderers ─────────────────────────────────────────────────────


def _render_context(l: PromptLayers) -> str:
    bits = [f"# Layer 1 — CONTEXT"]
    line = f"{l.screen_purpose} for {l.audience} on {l.platform}."
    bits.append(line)
    if l.feature_name:
        nav = f"Part of {l.feature_name} flow."
        if l.prev_screen:
            nav += f" Previous screen: {l.prev_screen}."
        if l.next_screen:
            nav += f" Next screen: {l.next_screen}."
        bits.append(nav)
    return "\n".join(bits)


def _render_components(l: PromptLayers) -> str:
    bits = ["# Layer 2 — COMPONENTS"]
    for c in l.components:
        bits.append(f"- {c}")
    return "\n".join(bits)


def _render_style(l: PromptLayers) -> str:
    bits = ["# Layer 3 — STYLE (hex codes only)"]
    if l.primary_color:
        bits.append(f"Primary: {l.primary_color}")
    if l.background_color:
        bits.append(f"Background: {l.background_color}")
    if l.text_color:
        bits.append(f"Text: {l.text_color}")
    if l.spacing_token:
        bits.append(f"Spacing: {l.spacing_token}")
    typo_parts = []
    if l.typography_family:
        typo_parts.append(l.typography_family)
    sizes = []
    if l.typography_h1_px:
        sizes.append(f"h1={l.typography_h1_px}")
    if l.typography_body_px:
        sizes.append(f"body={l.typography_body_px}")
    if typo_parts or sizes:
        line = "Typography: "
        if typo_parts:
            line += ", ".join(typo_parts)
        if sizes:
            line += ", sizes " + "/".join(sizes)
        bits.append(line)
    bits.append("Component patterns: see DESIGN.md > Components")
    return "\n".join(bits)


def _render_platform(l: PromptLayers) -> str:
    bits = ["# Layer 4 — PLATFORM"]
    bits.append(f"Device: {l.device}")
    if l.form_factor_breakpoints:
        bits.append(f"Form factor breakpoints: {', '.join(l.form_factor_breakpoints)}")
    bits.append(f"Interaction model: {l.interaction_model}")
    return "\n".join(bits)


# ── Helpers ─────────────────────────────────────────────────────────────


def _count_words(text: str) -> int:
    return len([w for w in text.split() if w])
