"""UC claims for the SpecBox NativeBackend — coordination (H3).

Mutual exclusion so two developers never work the same UC at once. Lives
outside the SpecBackend ABC (see :mod:`server.coordination`). Operates on the
``uc_claims`` table (migration 0003).

Stable codes at the MCP boundary
================================
- :class:`AlreadyClaimedError` → ``ALREADY_CLAIMED`` (UC already held) [AC-16]
- :class:`NotClaimOwnerError`   → ``NOT_CLAIM_OWNER`` (release by non-owner) [AC-17]

Atomicity [AC-18]
=================
:func:`start_uc_atomic` claims the UC and flips its spec state to
``in_progress`` in a single transaction. If the state change fails, the claim
is rolled back too — there is never an orphan claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


# ── Errors ───────────────────────────────────────────────────────────


class AlreadyClaimedError(Exception):
    """A UC is already claimed by someone. Carries who/since/branch [AC-19]."""

    code = "ALREADY_CLAIMED"

    def __init__(self, uc_id: str, owner: str, claimed_at: str, branch: str) -> None:
        self.uc_id = uc_id
        self.owner = owner
        self.claimed_at = claimed_at
        self.branch = branch
        super().__init__(
            f"UC {uc_id!r} is already claimed by {owner!r} since {claimed_at} "
            f"(branch: {branch or 'n/a'})."
        )

    def to_conflict(self) -> dict[str, Any]:
        """Conflict payload with owner / claimed_at / branch [AC-19]."""
        return {
            "code": self.code,
            "uc_id": self.uc_id,
            "owner": self.owner,
            "claimed_at": self.claimed_at,
            "branch": self.branch,
        }


class NotClaimOwnerError(Exception):
    """A release attempted by a developer who does not own the claim [AC-17]."""

    code = "NOT_CLAIM_OWNER"

    def __init__(self, uc_id: str, owner: str, requester: str) -> None:
        self.uc_id = uc_id
        self.owner = owner
        self.requester = requester
        super().__init__(
            f"UC {uc_id!r} is claimed by {owner!r}; {requester!r} cannot release it."
        )


# ── Claim record ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class Claim:
    project_id: str
    uc_id: str
    developer_id: str
    branch: str
    claimed_at: str

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "Claim":
        claimed = row["claimed_at"]
        return cls(
            project_id=row["project_id"],
            uc_id=row["uc_id"],
            developer_id=row["developer_id"],
            branch=row["branch"],
            claimed_at=claimed.isoformat() if isinstance(claimed, datetime) else str(claimed),
        )

    def to_public(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "uc_id": self.uc_id,
            "owner": self.developer_id,
            "branch": self.branch,
            "claimed_at": self.claimed_at,
        }


# ── Reads ────────────────────────────────────────────────────────────


async def get_claim(
    conn: asyncpg.Connection, project_id: str, uc_id: str
) -> Claim | None:
    row = await conn.fetchrow(
        "SELECT * FROM uc_claims WHERE project_id = $1 AND uc_id = $2",
        project_id,
        uc_id,
    )
    return Claim.from_row(row) if row else None


async def list_active_claims(
    conn: asyncpg.Connection, project_id: str
) -> list[Claim]:
    rows = await conn.fetch(
        "SELECT * FROM uc_claims WHERE project_id = $1",
        project_id,
    )
    return [Claim.from_row(r) for r in rows]


async def claimed_uc_ids_by_others(
    conn: asyncpg.Connection, project_id: str, developer_id: str
) -> set[str]:
    """uc_ids in this project claimed by someone OTHER than developer_id [AC-20]."""
    rows = await conn.fetch(
        "SELECT uc_id FROM uc_claims WHERE project_id = $1 AND developer_id <> $2",
        project_id,
        developer_id,
    )
    return {r["uc_id"] for r in rows}


# ── Writes ───────────────────────────────────────────────────────────


async def claim_uc(
    conn: asyncpg.Connection,
    *,
    project_id: str,
    uc_id: str,
    developer_id: str,
    branch: str = "",
) -> Claim:
    """Claim a UC for a developer. Raises ALREADY_CLAIMED if held [AC-16].

    The UNIQUE(project_id, uc_id) constraint guarantees exactly one winner under
    concurrency: the loser's INSERT raises ``UniqueViolationError`` which we
    translate into :class:`AlreadyClaimedError`, surfacing the current owner.
    Idempotent for the same owner re-claiming (returns the existing claim).
    """
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO uc_claims (project_id, uc_id, developer_id, branch)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            project_id,
            uc_id,
            developer_id,
            branch,
        )
        logger.info("uc_claimed", project_id=project_id, uc_id=uc_id, developer_id=developer_id)
        return Claim.from_row(row)
    except asyncpg.UniqueViolationError:
        existing = await get_claim(conn, project_id, uc_id)
        if existing is None:
            # Extremely unlikely race: claim vanished between INSERT and SELECT.
            raise
        if existing.developer_id == developer_id:
            # Same dev re-claiming → idempotent success.
            return existing
        raise AlreadyClaimedError(
            uc_id, existing.developer_id, existing.claimed_at, existing.branch
        )


async def release_uc(
    conn: asyncpg.Connection,
    *,
    project_id: str,
    uc_id: str,
    developer_id: str,
) -> bool:
    """Release a UC claim. Only the owner may release it [AC-17].

    Returns True if a claim was released, False if there was no claim. Raises
    :class:`NotClaimOwnerError` if a different developer holds it (the claim is
    left intact).
    """
    existing = await get_claim(conn, project_id, uc_id)
    if existing is None:
        return False
    if existing.developer_id != developer_id:
        raise NotClaimOwnerError(uc_id, existing.developer_id, developer_id)
    await conn.execute(
        "DELETE FROM uc_claims WHERE project_id = $1 AND uc_id = $2",
        project_id,
        uc_id,
    )
    logger.info("uc_released", project_id=project_id, uc_id=uc_id, developer_id=developer_id)
    return True


async def start_uc_atomic(
    pool: asyncpg.Pool,
    *,
    project_id: str,
    uc_db_id: str,
    uc_id: str,
    developer_id: str,
    branch: str = "",
) -> Claim:
    """Claim the UC AND set its spec state to in_progress in ONE transaction.

    No orphan claim [AC-18]: if the state UPDATE fails, the claim INSERT rolls
    back with it. If the UC is already claimed by another dev, raises
    :class:`AlreadyClaimedError` (whose payload carries owner/claimed_at/branch
    for the conflict response [AC-19]) and nothing is mutated.

    Args:
        uc_db_id: the use_cases.id (DB primary key, e.g. "UC-301").
        uc_id: the short spec id used for the claim row (usually == uc_db_id).
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            claim = await claim_uc(
                conn,
                project_id=project_id,
                uc_id=uc_id,
                developer_id=developer_id,
                branch=branch,
            )
            result = await conn.execute(
                """
                UPDATE use_cases
                SET state = 'in_progress', version = version + 1, updated_at = now()
                WHERE project_id = $1 AND id = $2
                """,
                project_id,
                uc_db_id,
            )
            if result.split()[-1] == "0":
                # UC row not found → abort the whole tx (claim rolls back too).
                raise ValueError(
                    f"UC {uc_db_id!r} not found in project {project_id!r}; "
                    "claim rolled back (no orphan)."
                )
    return claim
