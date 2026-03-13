"""PRD Writer — UC-002 of US-01 Spec-Code Sync Layer.

Locates PRD files and appends Implementation Status sections (append-only).

Pure Python module — no FastMCP or backend dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .delta_generator import compile_uc_status


def find_prd_path(
    project_path: str | Path,
    feature: str | None = None,
    us_id: str | None = None,
) -> Path | None:
    """Find the PRD file for a project/feature/US.

    Search order:
      1. doc/prds/{feature}_prd.md
      2. doc/prds/{us_id normalized}_prd.md (e.g. US-01 -> us_01)
      3. doc/prd/{feature}.md (legacy format)
      4. doc/prds/*.md (single file → that's the one)
      5. None if not found
    """
    root = Path(project_path)

    # 1. By feature name in doc/prds/
    if feature:
        candidate = root / "doc" / "prds" / f"{feature}_prd.md"
        if candidate.exists():
            return candidate
        # Also try without _prd suffix
        candidate = root / "doc" / "prds" / f"{feature}.md"
        if candidate.exists():
            return candidate

    # 2. By US-id normalized
    if us_id:
        normalized = us_id.lower().replace("-", "_")
        candidate = root / "doc" / "prds" / f"{normalized}_prd.md"
        if candidate.exists():
            return candidate

    # 3. Legacy format
    if feature:
        candidate = root / "doc" / "prd" / f"{feature}.md"
        if candidate.exists():
            return candidate

    # 4. Single PRD in doc/prds/
    prds_dir = root / "doc" / "prds"
    if prds_dir.exists():
        md_files = list(prds_dir.glob("*.md"))
        if len(md_files) == 1:
            return md_files[0]

    return None


def append_implementation_status(
    prd_path: Path,
    uc_id: str,
    branch: str,
    phase_deltas: list[str],
    timestamp: str | None = None,
) -> bool:
    """Append Implementation Status section to the end of a PRD file.

    This is append-only (AC-07): existing content is never modified.
    If previous Implementation Status sections exist, the new one is added
    after them in chronological order (AC-08).

    Args:
        prd_path: Path to the PRD markdown file.
        uc_id: Use Case identifier (e.g. "UC-001").
        branch: Git branch name.
        phase_deltas: List of phase delta Markdown blocks.
        timestamp: ISO 8601 timestamp. Auto-generated if None.

    Returns:
        True if written successfully, False otherwise.
    """
    if not prd_path.exists():
        return False

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        content = prd_path.read_text(encoding="utf-8")
    except OSError:
        return False

    # Build the UC status block
    uc_block = compile_uc_status(uc_id, branch, phase_deltas, timestamp)

    # Check if Implementation Status section already exists
    has_impl_status = "## Implementation Status" in content

    if has_impl_status:
        # Append new UC block after existing content (AC-08)
        new_content = content.rstrip() + "\n\n" + uc_block + "\n"
    else:
        # Add new section separator + header + UC block (AC-06)
        new_content = (
            content.rstrip()
            + "\n\n---\n\n## Implementation Status\n\n"
            + uc_block
            + "\n"
        )

    try:
        prd_path.write_text(new_content, encoding="utf-8")
        return True
    except OSError:
        return False
