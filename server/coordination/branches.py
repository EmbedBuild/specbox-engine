"""Branch registry for the SpecBox NativeBackend — coordination (H3, UC-304).

Maps a git branch name to a (project, UC, developer) so two developers cannot
collide on a branch. Operates on the ``branch_registry`` table (migration 0003)
and lives outside the SpecBackend ABC.

Naming [AC-23]
==============
:func:`suggest_branch_name` produces ``feature/{uc_id}-{slug}`` so the uc_id is
embedded in the branch — making natural collisions across UCs impossible while
keeping names human-readable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


class BranchCollisionError(Exception):
    """A branch name is already registered for a different UC/developer [AC-23]."""

    code = "BRANCH_COLLISION"

    def __init__(self, branch: str, existing_uc: str, existing_dev: str) -> None:
        self.branch = branch
        self.existing_uc = existing_uc
        self.existing_dev = existing_dev
        super().__init__(
            f"Branch {branch!r} is already registered for UC {existing_uc!r} "
            f"by {existing_dev!r}."
        )


@dataclass(frozen=True)
class BranchEntry:
    project_id: str
    branch: str
    uc_id: str
    developer_id: str

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "BranchEntry":
        return cls(
            project_id=row["project_id"],
            branch=row["branch"],
            uc_id=row["uc_id"],
            developer_id=row["developer_id"],
        )


def _slugify(text: str, max_len: int = 40) -> str:
    """Lowercase, hyphenate, strip to a branch-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].strip("-") or "work"


def suggest_branch_name(uc_id: str, title: str = "") -> str:
    """Return ``feature/{uc_id}-{slug}`` — uc_id embedded to avoid collisions [AC-23]."""
    uc_slug = _slugify(uc_id)
    if title:
        return f"feature/{uc_slug}-{_slugify(title)}"
    return f"feature/{uc_slug}"


async def register_branch(
    conn: asyncpg.Connection,
    *,
    project_id: str,
    branch: str,
    uc_id: str,
    developer_id: str,
) -> BranchEntry:
    """Register a branch ↔ UC mapping. Rejects collisions [AC-23].

    Idempotent for the same (branch, uc_id, dev). Raises
    :class:`BranchCollisionError` if the branch is already registered for a
    different UC or developer (the existing row is left intact).
    """
    existing = await conn.fetchrow(
        "SELECT * FROM branch_registry WHERE project_id = $1 AND branch = $2",
        project_id,
        branch,
    )
    if existing is not None:
        entry = BranchEntry.from_row(existing)
        if entry.uc_id == uc_id and entry.developer_id == developer_id:
            return entry  # idempotent re-register
        raise BranchCollisionError(branch, entry.uc_id, entry.developer_id)

    row = await conn.fetchrow(
        """
        INSERT INTO branch_registry (project_id, branch, uc_id, developer_id)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        project_id,
        branch,
        uc_id,
        developer_id,
    )
    logger.info(
        "branch_registered",
        project_id=project_id,
        branch=branch,
        uc_id=uc_id,
        developer_id=developer_id,
    )
    return BranchEntry.from_row(row)
