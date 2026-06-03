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
    role: str = "member",
) -> dict[str, Any]:
    """Register the migrating developer, mint a token, add them as member.

    Called when migrating **into** Native so the imported board has an
    identified owner [AC-08]. Idempotent on ``developer_id`` /
    ``(project_id, developer_id)``: ``register_developer`` upserts the
    ``developers`` row and ``add_project_member`` upserts the membership edge.

    The ``role`` (UC-819) is validated by ``add_project_member`` against
    :data:`server.coordination.identity.VALID_PROJECT_ROLES` and propagated to
    the membership edge. Provisioning a from-scratch migration passes
    ``role="project_admin"`` so the creator can later invite the rest of the
    team from the panel (decision D2).

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
                role=role,
            )

    logger.info(
        "native_identity_seeded",
        project_id=project_id,
        developer_id=developer_id,
        role=role,
    )

    return {
        "developer_id": developer_id,
        "registered": True,
        "member_added": True,
    }


# ── UC-820: provision tenant + creator membership (decision D2) ──────────


async def provision_native_project(
    pool: asyncpg.Pool,
    *,
    project_id: str,
    developer_id: str,
    display_name: str | None = None,
    role: str = "project_admin",
    name: str | None = None,
    validate_id: bool = True,
) -> dict[str, Any]:
    """Create the tenant + add the caller as ``project_admin``, atomically.

    This is the engine-side provisioning that breaks the egg-chicken bind
    (decision D2): when a native project is born from scratch, the caller
    cannot be a member because the ``projects`` row does not exist yet, and the
    ``project_members.project_id`` FK forbids the membership without it. This
    function creates both in **one transaction**, server-side:

    1. validate ``project_id`` against the canonical contract (UC-818);
    2. UPSERT ``public.projects`` (idempotent — re-provision is a no-op). The
       optional ``name`` (UC-824) is used on insert and refreshed on an existing
       row; when ``None`` the canonical project_id is used on insert and the
       stored name is preserved on conflict (never clobbered);
    3. register the developer + token-less identity row and the membership
       edge with ``role`` (defaults to ``project_admin``);
    4. append a non-destructive ``provision_project`` row to ``audit_log``.

    Idempotency (AC-10): re-provisioning a project the same caller already
    owns is a no-op — the projects UPSERT touches only ``updated_at`` and the
    membership UPSERT does NOT degrade an existing ``project_admin`` to a lower
    role (the SQL only ever promotes toward the requested role; we never call
    this with anything below the caller's current role).

    The caller (UC-821) is responsible for validating the dev_token BEFORE
    calling this (``require_dev_token`` + ``resolve_developer``), so a bad
    token never reaches here and Postgres is never touched (AC-08).

    Frontier 2 [AC-09]: writes only into the named tenant; the return dict
    carries stable ids only — never a token nor a DSN (safe to serialize).

    Returns:
        Dict with ``project_id``, ``developer_id``, ``role``, ``provisioned``
        (bool) and ``project_created`` (bool — False when the tenant already
        existed).
    """
    from ..coordination import audit as audit_mod
    from ..coordination.project_id import validate_project_id

    # ``validate_id=False`` (UC-824): ``setup_board`` reaches here for an
    # already-constructed NativeBackend whose project_id was accepted as-is
    # (the legacy bare INSERT never enforced the canonical contract). Skipping
    # validation keeps setup_board permissive on the id while still creating the
    # membership atomically — the orphan fix must not change the id contract.
    # The from-scratch migration path keeps ``validate_id=True`` (default).
    canonical = validate_project_id(project_id) if validate_id else project_id.strip()
    board_url = f"native://{canonical}"
    # ``name`` defaults to the canonical project_id (the original D2 behaviour).
    # When a caller supplies one (UC-824: ``setup_board`` delegating here), it is
    # used on insert and refreshed on an existing row. A ``None`` name on
    # re-provision preserves the stored name (COALESCE), never clobbering it.
    effective_name = name if name else canonical

    async with pool.acquire() as conn:
        async with conn.transaction():
            existed = bool(
                await conn.fetchval("SELECT 1 FROM projects WHERE project_id = $1", canonical)
            )
            await conn.execute(
                """
                INSERT INTO projects (project_id, name, backend_type, board_url, meta)
                VALUES ($1, $2, 'native', $3, '{}'::jsonb)
                ON CONFLICT (project_id) DO UPDATE
                    SET name = COALESCE($4, projects.name),
                        board_url = EXCLUDED.board_url,
                        updated_at = now()
                """,
                canonical,
                effective_name,
                board_url,
                name,
            )
            # Do NOT degrade an existing admin: only set the requested role when
            # the caller is being (re)provisioned as the creator. add_project_member
            # UPSERTs role; passing project_admin keeps/promotes, never lowers.
            await identity_mod.register_developer(
                conn,
                developer_id=developer_id,
                display_name=display_name or developer_id,
            )
            await identity_mod.add_project_member(
                conn,
                project_id=canonical,
                developer_id=developer_id,
                role=role,
            )
            await audit_mod.record_destructive(
                conn,
                developer_id=developer_id,
                project_id=canonical,
                operation=audit_mod.OP_PROVISION_PROJECT,
                target_id=canonical,
            )

    logger.info(
        "native_project_provisioned",
        project_id=canonical,
        developer_id=developer_id,
        role=role,
        project_created=not existed,
    )
    return {
        "project_id": canonical,
        "developer_id": developer_id,
        "role": role,
        "provisioned": True,
        "project_created": not existed,
    }


# ── AC-09: fail-fast dev_token guard for a native target ─────────────────


class MissingDevTokenError(RuntimeError):
    """Raised when a native target is requested without a dev_token (AC-09)."""


def require_dev_token(target_type: str, dev_token: str) -> None:
    """Fail fast when switching INTO native without a dev_token.

    Native (Cloud) requires a developer token minted by the panel. This guard
    runs BEFORE the source is read or anything is written, so a missing token
    never leaves a half-written project in Postgres (AC-09).

    Args:
        target_type: The target backend type.
        dev_token: The developer token (empty/whitespace means absent).

    Raises:
        MissingDevTokenError: when ``target_type == "native"`` and ``dev_token``
            is empty.
    """
    if target_type == "native" and not (dev_token or "").strip():
        raise MissingDevTokenError(
            "native target requires dev_token from the Cloud panel"
        )


# ── AC-07 rollback: delete a freshly-created native project ──────────────


async def delete_native_project(pool: asyncpg.Pool, project_id: str) -> None:
    """Delete a Native project and its rows (for atomic-switch data rollback).

    Used by the orchestrator when an atomic switch into native created the
    project fresh and a later step failed: deleting it restores the
    pre-migration "empty" state so nothing is left half-written (AC-07/AC-12).

    The ``ON DELETE CASCADE`` foreign keys on the native schema remove the
    project's items/AC/reservations/members; this issues the parent DELETE.
    """
    if not project_id:
        return
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
    logger.info("native_project_deleted_rollback", project_id=project_id)
