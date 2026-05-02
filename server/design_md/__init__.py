"""DESIGN.md generation and persistence (v5.31.0).

Implements Google Stitch's official DESIGN.md format
(https://github.com/google-labs-code/design.md) so that SpecBox projects
have a canonical visual identity contract that Stitch reads as persistent
context on every screen generation.

The format is YAML front-matter (design tokens) + Markdown body
(qualitative guidance: when-to-use, do/don't, voice). The generator
synthesises a DESIGN.md from existing SpecBox inputs:
  * doc/brand/brand_kit.md  (palette, typography from /visual-setup)
  * doc/veg/{archetype}.md  (motion, density, mood from VEG)
  * doc/app/app_prd.md      (vision + audience zones)
  * doc/app/app_spec.md     (stack + brand_visual zones)

The module is intentionally read/write-pure: the writer takes a model,
serialises it, and returns a string. Persistence to disk lives in
:func:`write_design_md`. Persistence to a Stitch project lives in the
upload tool (Phase 2).
"""

from __future__ import annotations

from .schema import (
    Colors,
    Components,
    DesignMd,
    FrontMatter,
    Rounded,
    Spacing,
    Typography,
)

__all__ = [
    "Colors",
    "Components",
    "DesignMd",
    "FrontMatter",
    "Rounded",
    "Spacing",
    "Typography",
]
