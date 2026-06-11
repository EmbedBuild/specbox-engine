"""UC reservations for the SpecBox NativeBackend — coordination (H3).

Mutual exclusion so two developers never work the same UC at once. Lives
outside the SpecBackend ABC (see :mod:`server.coordination`). Operates on the
``uc_reservations`` table (migration 0007 — renamed from ``uc_claims`` in
US-CLAIM-RENAME / UC-601).

Historical note
===============
The concept was originally called "claim" (see migrations 0003 and 0007).
Since v5.35.0 it is called "reservation" — universally understood (table,
room, library) and friendlier to non-technical users browsing the Control
Panel. Semantics are unchanged: a single developer temporarily holds
exclusive rights to work on a UC until they release it.

Stable codes at the MCP boundary
================================
- :class:`AlreadyReservedError` → ``ALREADY_RESERVED`` (UC already held) [AC-16]
- :class:`NotReservationOwnerError` → ``NOT_RESERVATION_OWNER`` (release by non-owner) [AC-17]

Atomicity [AC-18]
=================
:func:`start_uc_atomic` reserves the UC and flips its spec state to
``in_progress`` in a single transaction. If the state change fails, the
reservation is rolled back too — there is never an orphan reservation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg
import structlog

from . import audit

logger = structlog.get_logger(__name__)


# ── Errors ───────────────────────────────────────────────────────────


class AlreadyReservedError(Exception):
    """A UC is already reserved by someone. Carries who/since/branch [AC-19]."""

    code = "ALREADY_RESERVED"

    def __init__(self, uc_id: str, owner: str, reserved_at: str, branch: str) -> None:
        self.uc_id = uc_id
        self.owner = owner
        self.reserved_at = reserved_at
        self.branch = branch
        super().__init__(
            f"UC {uc_id!r} is already reserved by {owner!r} since {reserved_at} "
            f"(branch: {branch or 'n/a'})."
        )

    def to_payload(self) -> dict[str, Any]:
        """Conflict payload with owner / reserved_at / branch [AC-19]."""
        return {
            "code": self.code,
            "uc_id": self.uc_id,
            "owner": self.owner,
            "reserved_at": self.reserved_at,
            "branch": self.branch,
        }

    # Backwards-compatible alias for callers that have not migrated yet.
    # Removed in UC-612 / v5.37.0 along with the deprecated MCP tool aliases.
    to_conflict = to_payload


class NotReservationOwnerError(Exception):
    """A release attempted by a developer who does not own the reservation [AC-17]."""

    code = "NOT_RESERVATION_OWNER"

    def __init__(self, uc_id: str, owner: str, requester: str) -> None:
        self.uc_id = uc_id
        self.owner = owner
        self.requester = requester
        super().__init__(
            f"UC {uc_id!r} is reserved by {owner!r}; {requester!r} cannot release it."
        )


# ── Reservation record ───────────────────────────────────────────────


@dataclass(frozen=True)
class UCReservation:
    project_id: str
    uc_id: str
    developer_id: str
    branch: str
    reserved_at: str

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> "UCReservation":
        reserved = row["reserved_at"]
        return cls(
            project_id=row["project_id"],
            uc_id=row["uc_id"],
            developer_id=row["developer_id"],
            branch=row["branch"],
            reserved_at=reserved.isoformat() if isinstance(reserved, datetime) else str(reserved),
        )

    def to_public(self) -> dict[str, Any]:
        """Public projection used by the MCP boundary [AC-02].

        Returns exactly the four contractually-required keys:
        ``uc_id``, ``developer_id``, ``reserved_at``, ``branch``.
        ``project_id`` is intentionally omitted — the caller already knows
        which project they queried.
        """
        return {
            "uc_id": self.uc_id,
            "developer_id": self.developer_id,
            "reserved_at": self.reserved_at,
            "branch": self.branch,
        }


# ── Reads ────────────────────────────────────────────────────────────


async def get_reservation(
    conn: asyncpg.Connection, project_id: str, uc_id: str
) -> UCReservation | None:
    row = await conn.fetchrow(
        "SELECT * FROM uc_reservations WHERE project_id = $1 AND uc_id = $2",
        project_id,
        uc_id,
    )
    return UCReservation.from_row(row) if row else None


async def list_active_reservations(
    conn: asyncpg.Connection, project_id: str
) -> list[UCReservation]:
    rows = await conn.fetch(
        "SELECT * FROM uc_reservations WHERE project_id = $1",
        project_id,
    )
    return [UCReservation.from_row(r) for r in rows]


async def reserved_uc_ids_by_others(
    conn: asyncpg.Connection, project_id: str, developer_id: str
) -> set[str]:
    """uc_ids in this project reserved by someone OTHER than developer_id [AC-20]."""
    rows = await conn.fetch(
        "SELECT uc_id FROM uc_reservations WHERE project_id = $1 AND developer_id <> $2",
        project_id,
        developer_id,
    )
    return {r["uc_id"] for r in rows}


# ── Writes ───────────────────────────────────────────────────────────


async def reserve_uc(
    conn: asyncpg.Connection,
    *,
    project_id: str,
    uc_id: str,
    developer_id: str,
    branch: str = "",
) -> UCReservation:
    """Reserve a UC for a developer. Raises ALREADY_RESERVED if held [AC-16].

    The PRIMARY KEY (project_id, uc_id) guarantees exactly one winner under
    concurrency. We use ``INSERT ... ON CONFLICT DO NOTHING`` rather than
    catching :class:`asyncpg.UniqueViolationError`: when this runs inside a
    caller's transaction (``start_uc_atomic`` wraps reserve + state flip in one
    tx), a raised constraint violation would abort the *whole* transaction in
    Postgres, and a Python ``try/except`` does NOT open a savepoint to recover
    it — every later statement on that connection would then fail with "current
    transaction is aborted" (the UC-1203 bug: ``start_uc`` after the same dev
    already held the reservation). ``ON CONFLICT DO NOTHING`` never raises, so
    the transaction stays alive and the follow-up SELECT is safe.

    Idempotent for the same owner re-reserving (returns the existing reservation).
    """
    row = await conn.fetchrow(
        """
        INSERT INTO uc_reservations (project_id, uc_id, developer_id, branch)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (project_id, uc_id) DO NOTHING
        RETURNING *
        """,
        project_id,
        uc_id,
        developer_id,
        branch,
    )
    if row is not None:
        # Genuine first reservation: the INSERT actually wrote a row.
        logger.info("uc_reserved", project_id=project_id, uc_id=uc_id, developer_id=developer_id)
        # UC-506: audit the lifecycle event AFTER the INSERT succeeded, on the
        # same connection — so it participates in the caller's transaction
        # (start_uc_atomic) and rolls back with the reservation if a later step
        # fails. Only the genuine first reservation is recorded; the idempotent
        # re-reserve path below is not a new event.
        await audit.record_destructive(
            conn,
            developer_id=developer_id,
            project_id=project_id,
            operation=audit.OP_RESERVE_UC,
            target_id=uc_id,
        )
        return UCReservation.from_row(row)

    # Conflict: the row already existed (DO NOTHING returned nothing). The
    # transaction is intact (no statement failed), so this SELECT is safe.
    existing = await get_reservation(conn, project_id, uc_id)
    if existing is None:
        # Extremely unlikely race: reservation vanished between INSERT and SELECT.
        raise AlreadyReservedError(uc_id, "", "", "")
    if existing.developer_id == developer_id:
        # Same dev re-reserving → idempotent success.
        return existing
    raise AlreadyReservedError(
        uc_id, existing.developer_id, existing.reserved_at, existing.branch
    )


async def release_uc(
    conn: asyncpg.Connection,
    *,
    project_id: str,
    uc_id: str,
    developer_id: str,
) -> bool:
    """Release a UC reservation. Only the owner may release it [AC-17].

    Returns True if a reservation was released, False if there was none. Raises
    :class:`NotReservationOwnerError` if a different developer holds it (the
    reservation is left intact).
    """
    existing = await get_reservation(conn, project_id, uc_id)
    if existing is None:
        return False
    if existing.developer_id != developer_id:
        raise NotReservationOwnerError(uc_id, existing.developer_id, developer_id)
    await conn.execute(
        "DELETE FROM uc_reservations WHERE project_id = $1 AND uc_id = $2",
        project_id,
        uc_id,
    )
    logger.info("uc_released", project_id=project_id, uc_id=uc_id, developer_id=developer_id)
    # UC-506: audit the release on the same connection, after the DELETE
    # succeeded (we only reach here when an owned reservation existed).
    await audit.record_destructive(
        conn,
        developer_id=developer_id,
        project_id=project_id,
        operation=audit.OP_RELEASE_UC,
        target_id=uc_id,
    )
    return True


async def start_uc_atomic(
    pool: asyncpg.Pool,
    *,
    project_id: str,
    uc_db_id: str,
    uc_id: str,
    developer_id: str,
    branch: str = "",
) -> UCReservation:
    """Reserve the UC AND set its spec state to in_progress in ONE transaction.

    No orphan reservation [AC-18]: if the state UPDATE fails, the reservation
    INSERT rolls back with it. If the UC is already reserved by another dev,
    raises :class:`AlreadyReservedError` (whose payload carries
    owner/reserved_at/branch for the conflict response [AC-19]) and nothing
    is mutated.

    Args:
        uc_db_id: the use_cases.id (DB primary key, e.g. "UC-301").
        uc_id: the short spec id used for the reservation row (usually == uc_db_id).
    """
    from .lifecycle import set_lifecycle_context

    async with pool.acquire() as conn:
        async with conn.transaction():
            # UC-1202: the 0012 lifecycle triggers read app.developer_id from
            # this transaction's GUC — without it the transition row would
            # carry developer_id NULL.
            await set_lifecycle_context(conn, developer_id=developer_id)
            reservation = await reserve_uc(
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
                # UC row not found → abort the whole tx (reservation rolls back too).
                raise ValueError(
                    f"UC {uc_db_id!r} not found in project {project_id!r}; "
                    "reservation rolled back (no orphan)."
                )
    return reservation
