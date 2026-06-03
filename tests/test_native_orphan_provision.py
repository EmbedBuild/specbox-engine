"""US-ORPHAN-PROVISION (v6.9.4) — the orphan tenant that disabled auto-provision.

Closes the gap found dogfooding v6.9.3 (see
``HALLAZGO-v6.9.4-setup-board-tenant-huerfano.md``): v6.9.3's auto-provision
logic is correct, but ``setup_board`` created a ``public.projects`` row WITHOUT
a membership (a *tenant orphan*) outside the atomic provision. Any prior
operation (``set_auth_token`` → ``setup_board``, ``import_spec``, a legacy
migration) left that orphan, and ``_maybe_auto_provision`` then saw
``exists=True`` → ``return False`` → the membership gate → spurious ``FORBIDDEN``.

The fix is defense-in-depth:

- **FIX A (UC-824)**: ``setup_board`` for native delegates to
  ``provision_native_project`` (tenant + membership in one transaction), so it
  can never leave a project with zero members.
- **FIX B (UC-825)**: ``_maybe_auto_provision`` treats "project exists with ZERO
  members" as adoptable (an orphan has no owner to protect, AC-13 only guards
  tenants with ≥1 member).

DIRTY-STATE STANDARD (cross-cutting, this dogfooding chain): the E2E here starts
from a **realistic dirty state** (an orphan row created FIRST), not a virgin DB.
The previous E2E (UC-822) only exercised the clean path, which is exactly why the
gap shipped. Migration E2Es must start dirty.

All Postgres-gated; SKIP cleanly when no dev DB is reachable
(``docker compose -f docker-compose.dev.yml up -d``).
"""

from __future__ import annotations

import uuid

import pytest

from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


# ── Shared helpers (mirror tests/test_native_provision.py) ─────────────────


def _ctx():
    # A bare object: extract_locale_from_ctx falls back to "en" cleanly.
    return object()


async def _pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _register_dev(pool):
    """Register a developer + token, but NEITHER the projects row NOR membership."""
    from server.coordination.identity import register_developer, register_mcp_token

    developer_id = f"orph-dev-{uuid.uuid4().hex[:8]}"
    token = f"orph-tok-{uuid.uuid4().hex[:16]}"
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Orphan Tester")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
    return developer_id, token


async def _insert_orphan_project(pool, project_id: str) -> None:
    """Reproduce the v6.9.4 bug: a projects row WITHOUT any membership.

    This is exactly the dirty state a pre-fix ``setup_board`` left behind — the
    bare ``INSERT INTO projects`` with no ``project_members`` companion.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO projects (project_id, name, backend_type, board_url, meta) "
            "VALUES ($1, $1, 'native', '', '{}'::jsonb) ON CONFLICT DO NOTHING",
            project_id,
        )


async def _member_count(pool, project_id: str) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT count(*) FROM project_members WHERE project_id = $1", project_id
        )


async def _member_role(pool, project_id: str, developer_id: str) -> str | None:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT role FROM project_members WHERE project_id = $1 AND developer_id = $2",
            project_id,
            developer_id,
        )


async def _project_exists(pool, project_id: str) -> bool:
    async with pool.acquire() as conn:
        return bool(
            await conn.fetchval("SELECT 1 FROM projects WHERE project_id = $1", project_id)
        )


async def _audit_count(pool, project_id: str) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT count(*) FROM audit_log WHERE project_id = $1", project_id
        )


async def _cleanup(pool, project_id: str, *developer_ids: str):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        for did in developer_ids:
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", did)


# ═══════════════════════════════════════════════════════════════════════
# UC-825 — _maybe_auto_provision adopts the orphan tenant (FIX B)
# ═══════════════════════════════════════════════════════════════════════


@pytestmark_pg
class TestMaybeAutoProvisionAdoptsOrphan:
    """AC-04..06: orphan adopted, real tenant protected, cache cleared."""

    async def test_adopts_orphan_with_zero_members(self):
        """AC-04: project exists with 0 members → provision adopts (members=1 + audit)."""
        from server.coordination.identity import _clear_auth_cache
        from server.db.pool import close_pool
        from server.tools.migration import _maybe_auto_provision

        pool = await _pool()
        pid = f"Acme/orphan-adopt-{uuid.uuid4().hex[:8]}"
        dev_id, token = await _register_dev(pool)
        try:
            _clear_auth_cache()
            await _insert_orphan_project(pool, pid)
            assert await _project_exists(pool, pid)
            assert await _member_count(pool, pid) == 0  # precondition: orphan

            provisioned = await _maybe_auto_provision(pool, token, pid)

            assert provisioned is True  # adopted, not skipped
            assert await _member_role(pool, pid, dev_id) == "project_admin"
            assert await _member_count(pool, pid) == 1
            assert await _audit_count(pool, pid) >= 1
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()

    async def test_does_not_adopt_tenant_with_members(self):
        """AC-05: a tenant with ≥1 (other) member is NOT adopted → returns False.

        The membership of the existing owner is left untouched and the caller is
        NOT added — AC-13 / decision D2 preserved.
        """
        from server.coordination.identity import _clear_auth_cache, add_project_member
        from server.db.pool import close_pool
        from server.tools.migration import _maybe_auto_provision

        pool = await _pool()
        pid = f"Acme/real-tenant-{uuid.uuid4().hex[:8]}"
        owner_id, _owner_token = await _register_dev(pool)
        caller_id, caller_token = await _register_dev(pool)
        try:
            _clear_auth_cache()
            # Pre-existing tenant WITH an owner (the real case AC-13 protects).
            await _insert_orphan_project(pool, pid)  # creates the row...
            async with pool.acquire() as conn:
                await add_project_member(
                    conn, project_id=pid, developer_id=owner_id, role="project_admin"
                )  # ...then give it a real owner → no longer an orphan
            assert await _member_count(pool, pid) == 1

            provisioned = await _maybe_auto_provision(pool, caller_token, pid)

            assert provisioned is False  # not adopted
            # The caller was NOT silently added; the owner is untouched.
            assert await _member_role(pool, pid, caller_id) is None
            assert await _member_role(pool, pid, owner_id) == "project_admin"
            assert await _member_count(pool, pid) == 1
        finally:
            await _cleanup(pool, pid, owner_id, caller_id)
            await close_pool()

    async def test_adopt_clears_auth_cache(self):
        """AC-06: after adopting, the auth cache is cleared so the gate re-reads.

        We exercise the public effect: a full ``start_migration_session`` against
        an orphan opens (the gate sees the fresh membership in the same call),
        which only works if the cache was invalidated after the adopt.
        """
        from server.coordination.identity import _clear_auth_cache
        from server.db.pool import close_pool
        from server.migration.batch_session import get_session_store
        from server.tools.migration import start_migration_session

        pool = await _pool()
        pid = f"Acme/orphan-cache-{uuid.uuid4().hex[:8]}"
        dev_id, token = await _register_dev(pool)
        try:
            _clear_auth_cache()
            await _insert_orphan_project(pool, pid)
            assert await _member_count(pool, pid) == 0

            out = await start_migration_session(
                target_project_id=pid, source_type="freeform",
                declared_items=1, declared_bytes=10, source_sha256="abc",
                chunk_count=1, ctx=_ctx(), dev_token=token,
            )
            assert out["status"] == "open", out  # no FORBIDDEN — cache was fresh
            assert await _member_role(pool, pid, dev_id) == "project_admin"
            get_session_store().close(out["session_id"])
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()


# ═══════════════════════════════════════════════════════════════════════
# UC-824 — setup_board native never leaves a tenant without a member (FIX A)
# ═══════════════════════════════════════════════════════════════════════


@pytestmark_pg
class TestSetupBoardProvisionsMembership:
    """AC-01..03: setup_board creates membership, idempotent, no orphan left."""

    async def test_setup_board_creates_membership(self):
        """AC-01: setup_board on a fresh native project → projects + member≥1."""
        from server.backends.native_backend import NativeBackend
        from server.db.pool import close_pool

        pool = await _pool()
        pid = f"Acme/setup-fresh-{uuid.uuid4().hex[:8]}"
        dev_id, token = await _register_dev(pool)
        try:
            be = NativeBackend(project_id=pid, dev_token=token)
            cfg = await be.setup_board("My Board Name")

            assert cfg.board_id == pid
            assert await _project_exists(pool, pid)
            assert await _member_count(pool, pid) >= 1
            assert await _member_role(pool, pid, dev_id) == "project_admin"
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()

    async def test_setup_board_idempotent_no_admin_degrade(self):
        """AC-02: re-running setup_board is idempotent and keeps admin role."""
        from server.backends.native_backend import NativeBackend
        from server.db.pool import close_pool

        pool = await _pool()
        pid = f"Acme/setup-idem-{uuid.uuid4().hex[:8]}"
        dev_id, token = await _register_dev(pool)
        try:
            be = NativeBackend(project_id=pid, dev_token=token)
            await be.setup_board("Board v1")
            await be.setup_board("Board v2")  # re-run

            assert await _member_count(pool, pid) == 1
            assert await _member_role(pool, pid, dev_id) == "project_admin"
            # The caller-supplied name is refreshed (UC-824 name passthrough).
            assert await be.get_board_name(pid) == "Board v2"
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()

    async def test_setup_board_adopts_preexisting_orphan(self):
        """AC-03: setup_board over an orphan row completes it (no orphan left).

        Reproduces the recurring symptom: an orphan row already exists (e.g. a
        prior bare INSERT). setup_board must complete it with a membership, not
        leave it at zero members.
        """
        from server.backends.native_backend import NativeBackend
        from server.db.pool import close_pool

        pool = await _pool()
        pid = f"Acme/setup-orphan-{uuid.uuid4().hex[:8]}"
        dev_id, token = await _register_dev(pool)
        try:
            await _insert_orphan_project(pool, pid)
            assert await _member_count(pool, pid) == 0  # orphan present first

            be = NativeBackend(project_id=pid, dev_token=token)
            await be.setup_board("Adopted Board")

            assert await _member_count(pool, pid) == 1  # no orphan left
            assert await _member_role(pool, pid, dev_id) == "project_admin"
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()


# ═══════════════════════════════════════════════════════════════════════
# UC-826 — E2E DIRTY PATH: orphan first, then migration recovers
# ═══════════════════════════════════════════════════════════════════════


@pytestmark_pg
class TestDirtyPathE2E:
    """AC-07..09: the real dogfooding path — orphan row exists FIRST, then a
    full from-scratch batch migration must recover (no FORBIDDEN) and preserve
    states 1:1. This is the test that was missing and let the v6.9.4 gap ship.
    """

    async def test_e2e_orphan_then_migrate_recovers(self):
        """AC-07..09: orphan first → start/append/commit recovers + verifies."""
        from server.coordination.identity import _clear_auth_cache
        from server.coordination.project_id import display_slug
        from server.db.pool import close_pool
        from server.migration.integrity import sha256_hex
        from server.tools.migration import (
            append_migration_chunk,
            commit_migration_session,
            start_migration_session,
        )
        from tests.test_native_batch_ingestion import _chunk, _make_large_items_json

        pool = await _pool()
        pid = f"EmbedBuild/e2e-dirty-{uuid.uuid4().hex[:8]}"
        dev_id, token = await _register_dev(pool)
        try:
            _clear_auth_cache()

            # ── DIRTY STATE: an orphan tenant row exists BEFORE the migration.
            # This is the v6.9.4 bug condition — projects row, zero members.
            await _insert_orphan_project(pool, pid)
            assert await _project_exists(pool, pid)
            assert await _member_count(pool, pid) == 0

            blob = _make_large_items_json(40)  # 1 US + 40 UC + 120 AC, ~91 KB (>64 KB → batch)
            assert len(blob.encode()) > 64 * 1024  # AC-09: crosses the batch threshold
            chunks = _chunk(blob)
            assert len(chunks) > 1  # genuinely chunked transport

            started = await start_migration_session(
                target_project_id=pid, source_type="freeform",
                declared_items=161, declared_bytes=len(blob.encode()),
                source_sha256=sha256_hex(blob), chunk_count=len(chunks),
                ctx=_ctx(), dev_token=token,
            )
            # AC-07: the dirty state did NOT produce FORBIDDEN — it recovered.
            assert started.get("code") != "FORBIDDEN", started
            assert started["status"] == "open", started
            sid = started["session_id"]

            for idx, c in enumerate(chunks):
                acc = await append_migration_chunk(
                    session_id=sid, chunk_index=idx, chunk_data=c,
                    chunk_sha256=sha256_hex(c), ctx=_ctx(), dev_token=token,
                )
                assert acc["status"] == "accepted", acc

            out = await commit_migration_session(
                session_id=sid, ctx=_ctx(), confirmed_count=161, dev_token=token,
            )
            assert out["status"] == "committed", out

            # AC-08: exactly one canonical project row, creator is project_admin.
            async with pool.acquire() as conn:
                proj_count = await conn.fetchval(
                    "SELECT count(*) FROM projects WHERE project_id = $1", pid
                )
            assert proj_count == 1
            assert await _member_role(pool, pid, dev_id) == "project_admin"

            # AC-08: US/UC/AC == source 1:1, states preserved verbatim.
            async with pool.acquire() as conn:
                us = await conn.fetchval("SELECT count(*) FROM user_stories WHERE project_id = $1", pid)
                uc = await conn.fetchval("SELECT count(*) FROM use_cases WHERE project_id = $1", pid)
                ac = await conn.fetchval("SELECT count(*) FROM acceptance_criteria WHERE project_id = $1", pid)
                done = await conn.fetchval(
                    "SELECT count(*) FROM use_cases WHERE project_id = $1 AND state = 'done'", pid
                )
                backlog = await conn.fetchval(
                    "SELECT count(*) FROM use_cases WHERE project_id = $1 AND state = 'backlog'", pid
                )
            assert (us, uc, ac) == (1, 40, 120)
            assert done == 30  # i%4!=0 → done
            assert backlog == 10  # i%4==0 → backlog
            assert display_slug(pid) == pid.lower().replace("/", "-")
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()
