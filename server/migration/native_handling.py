"""Native-specific migration handling for the N×N backend switch (UC-403).

The Native backend (Postgres/Supabase) is the only multi-developer backend.
When migrating **into** Native (AC-08) we must seed a developer identity so the
imported board has an identified owner. When migrating **out of** Native (AC-07)
we must surface the multi-developer coordination state that is *intentionally
not* carried over to single-user backends (Trello/Plane/FreeForm) — reservations,
developer roster and branch registrations — so the migration report is honest
about what was discarded.

Frontier 2 [AC-09]
==================
This module never reads or builds a DSN. It receives an already-constructed
``asyncpg.Pool`` and operates only through it. None of its return values ever
carry a token (clear or hashed) or any connection credential — only stable
identifiers (uc_id, developer_id, branch names). Serializing any output of this
module is safe: it can never leak ``SPECBOX_NATIVE_DSN``.
"""

from __future__ import annotations

import secrets
from typing import Any

import asyncpg
import structlog

from ..coordination import identity as identity_mod
from ..coordination import reservations as reservations_mod

logger = structlog.get_logger(__name__)

#: Note prepended to the discarded-state section of a Native→other report.
DISCARD_NOTE = "Reservations, developer identity and branch registrations are NOT migrated to single-user backends."


# ── AC-07: Native → other (collect what is discarded) ────────────────────


async def collect_discarded_native_state(pool: asyncpg.Pool, project_id: str) -> dict[str, Any]:
    """Collect the multi-developer coordination state that won't be migrated.

    Reads the three Native-only coordination tables for ``project_id``:
    ``uc_reservations`` (active reservations), ``developers`` joined via
    ``project_members`` (the roster) and ``branch_registry`` (registered
    feature branches). None of these have an equivalent on
    Trello/Plane/FreeForm, so they are reported but not carried over.

    Frontier 2 [AC-09]: the returned dict never contains a token (the developer
    roster exposes only ``developer_id`` / ``display_name``, never
    ``token_hash``) nor any DSN.

    Args:
        pool: An already-constructed asyncpg pool (never a DSN).
        project_id: The Native project whose coordination state to read.

    Returns:
        Dict with ``reservations`` (list), ``developers`` (list), ``branches``
        (list) and ``counts`` (dict with the three lengths).
    """
    async with pool.acquire() as conn:
        active_reservations = await reservations_mod.list_active_reservations(conn, project_id)

        member_rows = await conn.fetch(
            """
            SELECT d.developer_id, d.display_name, pm.role
            FROM project_members pm
            JOIN developers d ON d.developer_id = pm.developer_id
            WHERE pm.project_id = $1
            ORDER BY d.developer_id
            """,
            project_id,
        )

        branch_rows = await conn.fetch(
            """
            SELECT branch, uc_id, developer_id
            FROM branch_registry
            WHERE project_id = $1
            ORDER BY branch
            """,
            project_id,
        )

    reservations_out = [
        {
            "uc_id": reservation.uc_id,
            "developer_id": reservation.developer_id,
            "branch": reservation.branch,
            "reserved_at": reservation.reserved_at,
        }
        for reservation in active_reservations
    ]
    developers_out = [
        {
            "developer_id": row["developer_id"],
            "display_name": row["display_name"],
            "role": row["role"],
        }
        for row in member_rows
    ]
    branches_out = [
        {
            "branch": row["branch"],
            "uc_id": row["uc_id"],
            "developer_id": row["developer_id"],
        }
        for row in branch_rows
    ]

    logger.info(
        "discarded_native_state_collected",
        project_id=project_id,
        reservations=len(reservations_out),
        developers=len(developers_out),
        branches=len(branches_out),
    )

    return {
        "reservations": reservations_out,
        "developers": developers_out,
        "branches": branches_out,
        "counts": {
            "reservations": len(reservations_out),
            "developers": len(developers_out),
            "branches": len(branches_out),
        },
    }


def build_native_exit_report(discarded: dict[str, Any]) -> dict[str, Any]:
    """Format the ``discarded_native_state`` section of a Native→other report.

    Pure formatter (no I/O): wraps the dict from
    :func:`collect_discarded_native_state` under a stable section key and adds
    an explanatory note. Safe to serialize [AC-09] — the input never carries
    credentials and this function adds none.

    Args:
        discarded: The dict returned by :func:`collect_discarded_native_state`.

    Returns:
        Dict with ``discarded_native_state`` (the collected state) and ``note``.
    """
    return {
        "discarded_native_state": discarded,
        "note": DISCARD_NOTE,
    }


# ── AC-08: other → Native (seed developer identity) ──────────────────────


async def seed_native_identity(
    pool: asyncpg.Pool,
    project_id: str,
    developer_id: str,
    display_name: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Register the migrating developer, mint a token, add them as member.

    Called when migrating **into** Native so the imported board has an
    identified owner [AC-08]. Idempotent on ``developer_id`` /
    ``(project_id, developer_id)``: ``register_developer`` upserts the
    ``developers`` row and ``add_project_member`` upserts the membership edge.

    The clear token is never persisted — only its SHA-256 hash lands in
    ``mcp_tokens`` [AC-09/AC-10]. When ``token`` is ``None`` a random
    throwaway is generated so the migrated developer has something to
    authenticate with; its clear value is discarded immediately and never
    returned.

    Token semantics (UC-504): token storage moved out of ``developers`` to
    ``mcp_tokens``. Each call mints a **new** ``mcp_tokens`` row, even when
    re-seeding the same developer — that mirrors how a real migration would
    rotate the credential. Old rows remain (revocation is a separate panel
    operation).

    Args:
        pool: An already-constructed asyncpg pool (never a DSN).
        project_id: The Native project to associate the developer with.
        developer_id: Stable, human-readable developer id (e.g. ``"jesus"``).
        display_name: Human-readable name; defaults to ``developer_id``.
        token: The developer's clear token; hashed and discarded. If ``None``
            a random throwaway is used so registration can proceed.

    Returns:
        Dict with ``developer_id``, ``registered`` (bool) and ``member_added``
        (bool). Never carries the token nor the minted ``token_id``.
    """
    effective_token = token if token else secrets.token_hex(32)

    async with pool.acquire() as conn:
        async with conn.transaction():
            await identity_mod.register_developer(
                conn,
                developer_id=developer_id,
                display_name=display_name or developer_id,
            )
            await identity_mod.register_mcp_token(
                conn,
                developer_id=developer_id,
                token=effective_token,
            )
            await identity_mod.add_project_member(
                conn,
                project_id=project_id,
                developer_id=developer_id,
            )

    logger.info(
        "native_identity_seeded",
        project_id=project_id,
        developer_id=developer_id,
    )

    return {
        "developer_id": developer_id,
        "registered": True,
        "member_added": True,
    }
