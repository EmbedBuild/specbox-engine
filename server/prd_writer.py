"""PRD Writer — UC-002 of US-01 Spec-Code Sync Layer.

Locates PRD files and appends Implementation Status sections (append-only).

Pure Python module — no FastMCP or backend dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .delta_generator import compile_uc_status
from .app_docs.workspace import as_path


def find_prd_path(
    project_path: str | Path,
    feature: str | None = None,
    us_id: str | None = None,
) -> Path | None:
    """Find the PRD file for a project/feature/US.

    Search order:
      1. doc/prds/{feature}_prd.md (or doc/prds/{feature}.md)
      2. doc/prds/{us_id normalized}_prd.md (e.g. US-01 -> us_01)
      3. doc/prd/{feature}.md (legacy format) or the folder per feature: doc/prd/{feature}/prd.md,
         PRD.md or {feature}_prd.md (UC-12211, UC-12219)
      4. the only PRD that defines the US (a heading or «>» line names it; UC-12219), or else
         the only one that mentions it (``prd_candidates``; UC-12211)
      5. doc/prds/*.md (single file → that's the one)
      6. None if not found

    A PRD marked as superseded (UC-12605) is still the PRD of its stories: it is found the same.

    Every path is returned with the name it has on disk: a disk that ignores case would also
    find ``PRD.md`` when asked for ``prd.md``, and the hook compares it with the files of a PR
    (UC-12219). `.claude/hooks/lib/prd-locate.mjs` follows the same order (tests compare them).
    """
    root = as_path(project_path)

    # 1. By feature name in doc/prds/
    if feature:
        for rel in (f"doc/prds/{feature}_prd.md", f"doc/prds/{feature}.md"):
            if found := _exact(root, rel):
                return found

    # 2. By US-id normalized
    if us_id:
        normalized = us_id.lower().replace("-", "_")
        if found := _exact(root, f"doc/prds/{normalized}_prd.md"):
            return found

    # 3. Legacy format, and the folder per feature
    if feature:
        for rel in (
            f"doc/prd/{feature}.md",
            f"doc/prd/{feature}/prd.md",
            f"doc/prd/{feature}/PRD.md",
            f"doc/prd/{feature}/{feature}_prd.md",
        ):
            if found := _exact(root, rel):
                return found

    # 4. The only PRD that defines the US — a heading or a «>» header line names it (UC-12219) —,
    #    or else the only one that mentions it anywhere (UC-12211)
    if us_id:
        import re

        word = re.compile(rf"\b{re.escape(us_id)}\b")
        texts = {p: _read(p) for p in prd_candidates(root)}
        defining = [p for p, text in texts.items() if any(
            line.lstrip().startswith(("#", ">")) and word.search(line) for line in text.splitlines()
        )]
        if len(defining) == 1:
            return defining[0]
        named = [p for p, text in texts.items() if word.search(text)]
        if len(named) == 1:
            return named[0]

    # 5. Single PRD in doc/prds/
    md_files = [root / "doc" / "prds" / n for n in _names(root / "doc" / "prds") if n.endswith(".md")]
    md_files = [p for p in md_files if p.is_file()]
    if len(md_files) == 1:
        return md_files[0]

    return None


def _names(directory: Path) -> list[str]:
    """The entries of ``directory`` as they are on disk, sorted; [] if it does not exist."""
    try:
        return sorted(entry.name for entry in directory.iterdir())
    except OSError:
        return []


def _exact(root: Path, rel: str) -> Path | None:
    """``root/rel`` if a file with exactly that name exists (case included), else None."""
    path = root / rel
    return path if path.name in _names(path.parent) and path.is_file() else None


def prd_candidates(root: Path) -> list[Path]:
    """Every PRD file of the project, in a stable order (names as on disk).

    For each folder of doc/prd/: prd.md, PRD.md and <folder>_prd.md (UC-12219); then doc/prd/*.md
    and doc/prds/*.md.
    """
    found: list[Path] = []
    prd_dir = root / "doc" / "prd"
    for folder in _names(prd_dir):
        names = _names(prd_dir / folder)
        for name in ("prd.md", "PRD.md", f"{folder}_prd.md"):
            if name in names and (prd_dir / folder / name).is_file():
                found.append(prd_dir / folder / name)
    for directory in (prd_dir, root / "doc" / "prds"):
        found.extend(directory / n for n in _names(directory) if n.endswith(".md") and (directory / n).is_file())
    return found


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def append_implementation_status(
    prd_path: Path,
    uc_id: str,
    branch: str,
    phase_deltas: list[str],
    timestamp: str | None = None,
    behaviors: dict[str, str] | None = None,
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
    uc_block = compile_uc_status(uc_id, branch, phase_deltas, timestamp, behaviors)

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
