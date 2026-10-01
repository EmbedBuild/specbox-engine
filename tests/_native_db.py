"""Shared native-DB test helpers (UC-405).

Centralises the DSN resolution + reachability probe used by the native test
modules (``test_native_schema``, ``test_native_backend_conformance``,
``test_native_dispatch``). Having one place means the Supabase TLS handling is
applied consistently: a probe that did a plain ``asyncpg.connect(dsn)`` would
fail the Supabase handshake (TLS required) and make the suite *skip* as if no
DB existed, even when Supabase is reachable — defeating AC-38.

The probe reuses the project's own SSL resolution (:func:`server.db.pool._resolve_ssl`)
so it matches exactly how ``init_pool`` will connect:

- Supabase DSN (``*.supabase.co`` / ``*.supabase.com``) → ``ssl="require"``.
- Local throwaway Postgres → plaintext.
- ``SPECBOX_NATIVE_SSL`` override honoured either way.

It runs in a dedicated, fully torn-down event loop so it never leaves a closed
loop as the asyncio default (which would poison the pool created later under
pytest-asyncio's own loop on Python 3.14).
"""

from __future__ import annotations

import asyncio
import os
import uuid

import asyncpg

from server.db.pool import _resolve_ssl

#: Frontier 2: DSN is normally env-only. Tests honour an explicit override and
#: fall back to the documented dev DSN (docker-compose.dev.yml). To run against
#: Supabase, export SPECBOX_NATIVE_DSN with the Pooler transaction-mode URI.
#: UC-5903: the dev port follows SPECBOX_NATIVE_PG_PORT, the same variable
#: docker-compose.dev.yml publishes, so a busy 55432 only needs one export.
DEV_PORT = os.environ.get("SPECBOX_NATIVE_PG_PORT") or "55432"
_DEV_DSN = f"postgresql://specbox:specbox_dev_only@localhost:{DEV_PORT}/specbox_native"
DSN = os.environ.get("SPECBOX_NATIVE_DSN", _DEV_DSN)


def probe(dsn: str = DSN) -> None:
    """Confirm Postgres is reachable, TLS-aware, in a throwaway event loop.

    Raises whatever ``asyncpg`` raises when the DB is not reachable; callers
    turn that into a clean module-level skip.
    """
    ssl = _resolve_ssl(dsn)

    async def _connect() -> None:
        conn = await asyncio.wait_for(asyncpg.connect(dsn, ssl=ssl), timeout=5.0)
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_connect())
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def reachable() -> tuple[bool, str]:
    """Return ``(ok, skip_reason)`` for module-level skip guards."""
    try:
        probe(DSN)
        return True, ""
    except Exception as exc:  # noqa: BLE001 — any failure means "no DB", just skip
        target = "Supabase" if "supabase.co" in DSN or "supabase.com" in DSN else "dev Postgres"
        return False, (
            f"{target} not reachable ({exc!r}); export SPECBOX_NATIVE_DSN "
            "(Supabase Pooler transaction-mode URI) or run "
            "docker compose -f docker-compose.dev.yml up -d"
        )


#: Prefix of the organizations the tests create, so abandoned ones can be swept.
TEST_ORG_PREFIX = "test-org-"


async def seed_organization(conn: asyncpg.Connection, developer_id: str) -> str:
    """Give a test developer the organization that provisioning requires.

    ``provision_native_project`` — and with it ``setup_board`` — resolves the
    organization of a new project from the caller and refuses to create one for
    a developer without any (``OrgResolutionError``). In production the signup
    (UC-1303) gives every developer an organization; a test that registers a
    developer by hand has to do the same before provisioning a project for them.
    The developer is ``org_admin``, as a signup leaves the creator.

    Organizations left without members nor projects by earlier tests (their
    cleanup deletes projects and developers, not organizations) are swept first,
    so a reused dev database does not pile them up. Returns the organization id.
    """
    org_id = f"{TEST_ORG_PREFIX}{uuid.uuid4().hex[:12]}"
    async with conn.transaction():
        await conn.execute(
            """
            DELETE FROM organizations o
             WHERE o.id LIKE $1 || '%'
               AND NOT EXISTS (SELECT 1 FROM organization_members m WHERE m.organization_id = o.id)
               AND NOT EXISTS (SELECT 1 FROM projects p WHERE p.organization_id = o.id)
            """,
            TEST_ORG_PREFIX,
        )
        await conn.execute(
            "INSERT INTO organizations (id, name, slug, created_by) VALUES ($1, $1, $1, $2)",
            org_id,
            developer_id,
        )
        await conn.execute(
            "INSERT INTO organization_members (organization_id, developer_id, role) VALUES ($1, $2, 'org_admin')",
            org_id,
            developer_id,
        )
    return org_id
