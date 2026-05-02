"""Prompt construction and validation for Stitch generations (v5.31.0).

The 4-layer template (Context / Components / Style / Platform) and the
validator that enforces:

* hex codes only (named colors rejected and auto-resolved when DESIGN.md
  is present)
* Layer 1 ≤80 words
* Layer 2 is a list, not narrative
* prompts that mix layout + components are split into two calls
* total length ≤500 chars on initial generation (warn, not block)

The validator runs in **warn-only** mode by default during the first
two weeks post-release; tightening to ``strict`` is a settings change,
not a code change (see ``server/stitch_prompt/validator.py``).
"""

from __future__ import annotations

from .builder import (
    PromptLayers,
    StitchPrompt,
    build_prompt,
    render_prompt,
)
from .validator import (
    ValidationResult,
    ValidatorMode,
    validate_and_normalize,
)

__all__ = [
    "PromptLayers",
    "StitchPrompt",
    "build_prompt",
    "render_prompt",
    "ValidationResult",
    "ValidatorMode",
    "validate_and_normalize",
]
