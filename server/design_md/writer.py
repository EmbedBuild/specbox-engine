"""Serialise :class:`DesignMd` to the on-disk Markdown format.

Pure functions; no I/O. Persistence helpers live in :mod:`server.design_md.io`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

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


def serialize(doc: DesignMd) -> str:
    """Render a DesignMd to a UTF-8 string suitable for writing to disk.

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

    return "\n".join(parts).rstrip() + "\n"


def write_design_md(doc: DesignMd, path: Path) -> Path:
    """Serialise and write to ``path``. Returns the path written.

    Idempotent: overwrites if exists. Caller is responsible for backups.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize(doc), encoding="utf-8")
    return path
