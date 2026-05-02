"""I/O helpers for DESIGN.md (load, save, signature)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from .schema import DesignMd, FrontMatter
from .writer import serialize, write_design_md

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)


def load(path: Path) -> DesignMd:
    """Parse a DESIGN.md from disk back into a model.

    Designed to round-trip with :func:`serialize`. Sections that are
    absent come back empty; unknown sections are dropped silently.
    """

    raw = path.read_text(encoding="utf-8")
    m = _FRONT_MATTER_RE.match(raw)
    if not m:
        raise ValueError(f"DESIGN.md at {path} is missing YAML front-matter")
    fm_yaml, body = m.group(1), m.group(2)
    fm_dict = yaml.safe_load(fm_yaml) or {}
    fm = FrontMatter(**fm_dict)

    # Split the body by H2 headings.
    sections: dict[str, str] = {}
    last_pos = 0
    last_name: str | None = None
    for match in _SECTION_RE.finditer(body):
        if last_name is not None:
            sections[last_name] = body[last_pos : match.start()].strip()
        last_name = match.group(1).strip().lower()
        last_pos = match.end()
    if last_name is not None:
        sections[last_name] = body[last_pos:].strip()

    return DesignMd(
        front_matter=fm,
        overview=sections.get("overview", ""),
        colors_md=sections.get("colors", ""),
        typography_md=sections.get("typography", ""),
        layout=sections.get("layout", ""),
        elevation=sections.get("elevation & depth", ""),
        shapes=sections.get("shapes", ""),
        components_md=sections.get("components", ""),
        dos_and_donts=sections.get("do's and don'ts", ""),
    )


def save(doc: DesignMd, path: Path) -> Path:
    """Write to disk. Convenience wrapper over :func:`write_design_md`."""
    return write_design_md(doc, path)


def compute_signature(doc: DesignMd) -> str:
    """SHA-256 of the canonical serialisation, minus volatile fields.

    Used to detect drift: if the brand kit changes but DESIGN.md isn't
    regenerated, signatures diverge and the sync layer flags it.
    Volatile fields excluded: ``generated_at``.
    """

    payload = doc.model_copy(deep=True)
    payload.front_matter = payload.front_matter.model_copy(
        update={"generated_at": "FROZEN"}
    )
    return hashlib.sha256(serialize(payload).encode("utf-8")).hexdigest()
