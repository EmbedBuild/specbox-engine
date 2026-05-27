"""Serialise :class:`DesignMd` to the on-disk Markdown format.

Pure functions; no I/O. Persistence helpers live in :mod:`server.design_md.io`.

v6.5.0 adds an optional Material 3 frontmatter projection (the YAML block
that Stitch's ``create_design_system_from_design_md`` parses server-side).
Pass ``material3=<Material3FrontMatter>`` to :func:`serialize` to emit
the M3 view instead of the SpecBox-native view.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .material3_view import Material3FrontMatter, render_veg_notes_section
from .schema import DesignMd

# Section order is fixed by the design.md spec.
_SECTION_ORDER: tuple[tuple[str, str], ...] = (
    ("overview", "Overview"),
    ("colors_md", "Colors"),
    ("typography_md", "Typography"),
    ("layout", "Layout"),
    ("elevation", "Elevation & Depth"),
    ("shapes", "Shapes"),
    ("components_md", "Components"),
    ("dos_and_donts", "Do's and Don'ts"),
)

VEG_NOTES_HEADING = "VEG Notes"


def serialize(
    doc: DesignMd,
    *,
    material3: Material3FrontMatter | None = None,
) -> str:
    """Render a DesignMd to a UTF-8 string suitable for writing to disk.

    Args:
        doc: The DesignMd to serialise.
        material3: When supplied, the YAML frontmatter follows the
            Material 3 token names that Stitch's
            ``create_design_system_from_design_md`` parses (``surface``,
            ``on-surface``, ``primary``, etc.) and includes a ``theme``
            block consumable by ``update_design_system``. The Markdown
            body is unchanged plus a final ``## VEG Notes`` section
            preserving VEG semantics. When omitted, behaviour is
            unchanged from v6.1.x (SpecBox-native frontmatter).

    Output format::

        ---
        {yaml front-matter}
        ---

        ## Overview
        {body}

        ## Colors
        {body}
        ...
    """

    if material3 is not None:
        fm_dict = material3.to_dict()
    else:
        fm_dict = doc.front_matter.model_dump(exclude_none=True)
    fm_yaml = yaml.safe_dump(
        fm_dict,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    ).strip()

    parts: list[str] = ["---", fm_yaml, "---", ""]

    for attr, heading in _SECTION_ORDER:
        body = (getattr(doc, attr) or "").strip()
        if not body:
            continue
        parts.append(f"## {heading}")
        parts.append("")
        parts.append(body)
        parts.append("")

    if material3 is not None:
        notes_body = render_veg_notes_section(material3.veg_notes)
        if notes_body:
            parts.append(f"## {VEG_NOTES_HEADING}")
            parts.append("")
            parts.append(notes_body)
            parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def write_design_md(
    doc: DesignMd,
    path: Path,
    *,
    material3: Material3FrontMatter | None = None,
) -> Path:
    """Serialise and write to ``path``. Returns the path written.

    Idempotent: overwrites if exists. Caller is responsible for backups.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize(doc, material3=material3), encoding="utf-8")
    return path
