"""US-NATIVE-PROVISION — provision tenant+membership & canonical project_id.

Closes the two gaps found dogfooding v6.9.2 (see
``HALLAZGO-v6.9.3-provision-y-project-id.md``):

- GAP 1: the batch-ingest path never provisioned ``public.projects`` +
  ``public.project_members`` when a project is born from scratch, so the
  membership gate blocked the very first "upload my project to Cloud".
- GAP 2: engine (``owner/repo``) and panel (slug) never agreed on a
  ``project_id`` format.

Unit tests for the canonical helper (UC-818) run everywhere. The provisioning,
batch-integration and E2E tests (UC-820/821/822) are Postgres-gated and SKIP
cleanly when no dev DB is reachable (``docker compose -f docker-compose.dev.yml
up -d``).
"""

from __future__ import annotations

import json
import uuid

import pytest

from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


# ═══════════════════════════════════════════════════════════════════════
# UC-818 — Canonical project_id helper (pure, runs everywhere)
# ═══════════════════════════════════════════════════════════════════════


class TestCanonicalProjectId:
    """AC-01..03: canonical_project_id / display_slug / validate_project_id."""

    def test_canonical_project_id_is_case_preserving_single_slash(self):
        """AC-01: owner/repo joined verbatim, case preserved, one slash."""
        from server.coordination.project_id import canonical_project_id

        assert canonical_project_id("EmbedBuild", "specbox_cloud") == "EmbedBuild/specbox_cloud"
        # Surrounding whitespace on the segments is trimmed, never embedded.
        assert canonical_project_id("  EmbedBuild ", " specbox_cloud ") == "EmbedBuild/specbox_cloud"

    def test_display_slug_lowercases_and_dashes_and_is_idempotent(self):
        """AC-02: owner/repo → owner-repo (lowercase, '/'+'_' → '-'); idempotent."""
        from server.coordination.project_id import display_slug

        slug = display_slug("EmbedBuild/specbox_cloud")
        assert slug == "embedbuild-specbox-cloud"
        # Idempotent: re-slugifying an already-derived slug is a no-op.
        assert display_slug(slug) == slug

    def test_validate_accepts_canonical_and_rejects_malformed(self):
        """AC-03: a well-formed owner/repo passes unchanged; bad ids raise."""
        from server.coordination.project_id import (
            InvalidProjectIdError,
            validate_project_id,
        )

        assert validate_project_id("EmbedBuild/specbox_cloud") == "EmbedBuild/specbox_cloud"

        for bad in ["", "   ", "no-owner", "a/b/c", "owner/", "/repo", "owner /repo", " owner/repo"]:
            with pytest.raises(InvalidProjectIdError):
                validate_project_id(bad)

    def test_display_slug_rejects_unusable_input(self):
        """AC-02/03 edge: an all-separator id yields no usable slug → raise."""
        from server.coordination.project_id import InvalidProjectIdError, display_slug

        with pytest.raises(InvalidProjectIdError):
            display_slug("///")

    def test_humanize_project_name_capitalizes_repo_words(self):
        """UC-504 AC-02: derive a human title from the repo segment, each word
        capitalized (first letter upper)."""
        from server.coordination.project_id import humanize_project_name

        assert humanize_project_name("EmbedBuild/specbox-manager") == "Specbox Manager"
        assert humanize_project_name("acme/web") == "Web"
        assert humanize_project_name("acme/my_cool_api") == "My Cool Api"
        # bare repo segment (no owner/slash) still humanizes
        assert humanize_project_name("standalone") == "Standalone"
        # preserves already-uppercase rest of a word (only forces leading char)
        assert humanize_project_name("acme/API-gateway") == "API Gateway"


# ═══════════════════════════════════════════════════════════════════════
# Postgres-gated helpers
# ═══════════════════════════════════════════════════════════════════════


async def _register_dev(pool, project_member: bool = False):
    """Register a developer + token. Optionally NOT a project member.

    Unlike the batch suite's ``_seed_identity``, this deliberately does NOT
    create the ``projects`` row nor the membership by default — the whole point
    of US-NATIVE-PROVISION is that the engine provisions those itself.
    """
    from server.coordination.identity import register_developer, register_mcp_token

    developer_id = f"prov-dev-{uuid.uuid4().hex[:8]}"
    token = f"prov-tok-{uuid.uuid4().hex[:16]}"
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Provision Tester")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
    return developer_id, token


async def _project_exists(pool, project_id: str) -> bool:
    async with pool.acquire() as conn:
        return bool(
            await conn.fetchval("SELECT 1 FROM projects WHERE project_id = $1", project_id)
        )


async def _member_role(pool, project_id: str, developer_id: str) -> str | None:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT role FROM project_members WHERE project_id = $1 AND developer_id = $2",
            project_id,
            developer_id,
        )


async def _cleanup(pool, project_id: str, *developer_ids: str):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        for developer_id in developer_ids:
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)


# ═══════════════════════════════════════════════════════════════════════
# UC-819 — seed_native_identity parametrized by role (creator as admin)
# ═══════════════════════════════════════════════════════════════════════


@pytestmark_pg
class TestSeedRole:
    """AC-04..06: role propagates, idempotent, validated."""

    async def _pool(self):
        from server.db.migrate import apply_migrations
        from server.db.pool import init_pool

        pool = await init_pool(dsn=DSN)
        await apply_migrations(pool)
        return pool

    async def test_seed_grants_requested_role(self):
        """AC-04: seed_native_identity(role='project_admin') sets that role."""
        from server.db.pool import close_pool
        from server.migration.native_handling import seed_native_identity

        pool = await self._pool()
        pid = f"Acme/admin-seed-{uuid.uuid4().hex[:8]}"
        dev_id, _ = await _register_dev(pool)
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO projects (project_id, name, backend_type, board_url, meta) "
                    "VALUES ($1, $1, 'native', '', '{}'::jsonb) ON CONFLICT DO NOTHING",
                    pid,
                )
            await seed_native_identity(pool, project_id=pid, developer_id=dev_id, role="project_admin")
            assert await _member_role(pool, pid, dev_id) == "project_admin"
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()

    async def test_seed_is_idempotent(self):
        """AC-05: re-seeding the same (project, dev, role) does not duplicate/raise."""
        from server.db.pool import close_pool
        from server.migration.native_handling import seed_native_identity

        pool = await self._pool()
        pid = f"Acme/idem-seed-{uuid.uuid4().hex[:8]}"
        dev_id, _ = await _register_dev(pool)
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO projects (project_id, name, backend_type, board_url, meta) "
                    "VALUES ($1, $1, 'native', '', '{}'::jsonb) ON CONFLICT DO NOTHING",
                    pid,
                )
            await seed_native_identity(pool, project_id=pid, developer_id=dev_id, role="project_admin")
            await seed_native_identity(pool, project_id=pid, developer_id=dev_id, role="project_admin")
            async with pool.acquire() as conn:
                count = await conn.fetchval(
                    "SELECT count(*) FROM project_members WHERE project_id = $1 AND developer_id = $2",
                    pid,
                    dev_id,
                )
            assert count == 1
            assert await _member_role(pool, pid, dev_id) == "project_admin"
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()

    async def test_invalid_role_rejected_before_insert(self):
        """AC-06: an unknown role raises and persists nothing."""
        from server.coordination.identity import add_project_member
        from server.db.pool import close_pool

        pool = await self._pool()
        pid = f"Acme/bad-role-{uuid.uuid4().hex[:8]}"
        dev_id, _ = await _register_dev(pool)
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO projects (project_id, name, backend_type, board_url, meta) "
                    "VALUES ($1, $1, 'native', '', '{}'::jsonb) ON CONFLICT DO NOTHING",
                    pid,
                )
                with pytest.raises(ValueError):
                    await add_project_member(conn, project_id=pid, developer_id=dev_id, role="superuser")
            assert await _member_role(pool, pid, dev_id) is None
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()


# ═══════════════════════════════════════════════════════════════════════
# UC-820 — Server-side provision of tenant + membership before the gate
# ═══════════════════════════════════════════════════════════════════════


@pytestmark_pg
class TestProvisionNativeProject:
    """AC-07..10: provision creates tenant+admin atomically, idempotent, audited."""

    async def _pool(self):
        from server.db.migrate import apply_migrations
        from server.db.pool import init_pool

        pool = await init_pool(dsn=DSN)
        await apply_migrations(pool)
        return pool

    async def _audit_count(self, pool, project_id: str) -> int:
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT count(*) FROM audit_log WHERE project_id = $1 AND operation = 'provision_project'",
                project_id,
            )

    async def test_provision_creates_tenant_and_admin_membership(self):
        """AC-07: provisioning a non-existent project creates projects + admin member."""
        from server.db.pool import close_pool
        from server.migration.native_handling import provision_native_project

        pool = await self._pool()
        pid = f"Acme/from-scratch-{uuid.uuid4().hex[:8]}"
        dev_id, _ = await _register_dev(pool)
        try:
            assert not await _project_exists(pool, pid)
            out = await provision_native_project(pool, project_id=pid, developer_id=dev_id)
            assert out["project_created"] is True
            assert await _project_exists(pool, pid)
            assert await _member_role(pool, pid, dev_id) == "project_admin"
            # AC-09: the return never carries a token or DSN.
            blob = json.dumps(out)
            assert "token" not in blob.lower() and "dsn" not in blob.lower()
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()

    async def test_provision_writes_audit_row(self):
        """AC-09: a provision_project audit row is appended after success."""
        from server.db.pool import close_pool
        from server.migration.native_handling import provision_native_project

        pool = await self._pool()
        pid = f"Acme/audited-{uuid.uuid4().hex[:8]}"
        dev_id, _ = await _register_dev(pool)
        try:
            await provision_native_project(pool, project_id=pid, developer_id=dev_id)
            assert await self._audit_count(pool, pid) == 1
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()

    async def test_provision_is_idempotent_and_does_not_degrade_admin(self):
        """AC-10: re-provisioning is a no-op and keeps the creator as admin."""
        from server.db.pool import close_pool
        from server.migration.native_handling import provision_native_project

        pool = await self._pool()
        pid = f"Acme/idempotent-{uuid.uuid4().hex[:8]}"
        dev_id, _ = await _register_dev(pool)
        try:
            first = await provision_native_project(pool, project_id=pid, developer_id=dev_id)
            assert first["project_created"] is True
            second = await provision_native_project(pool, project_id=pid, developer_id=dev_id)
            assert second["project_created"] is False
            assert await _member_role(pool, pid, dev_id) == "project_admin"
            async with pool.acquire() as conn:
                proj_count = await conn.fetchval(
                    "SELECT count(*) FROM projects WHERE project_id = $1", pid
                )
            assert proj_count == 1
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()

    async def test_provision_rejects_invalid_project_id_without_writing(self):
        """AC-07/08 edge: a malformed project_id raises and writes nothing."""
        from server.coordination.project_id import InvalidProjectIdError
        from server.db.pool import close_pool
        from server.migration.native_handling import provision_native_project

        pool = await self._pool()
        dev_id, _ = await _register_dev(pool)
        try:
            with pytest.raises(InvalidProjectIdError):
                await provision_native_project(pool, project_id="not-canonical", developer_id=dev_id)
            assert not await _project_exists(pool, "not-canonical")
        finally:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev_id)
            await close_pool()


# ═══════════════════════════════════════════════════════════════════════
# UC-821 — Batch integration: auto-provision before the membership gate
# ═══════════════════════════════════════════════════════════════════════


def _ctx():
    # A bare object: extract_locale_from_ctx falls back to "en" cleanly.
    return object()


@pytestmark_pg
class TestStartSessionAutoProvision:
    """AC-11..13: start_migration_session auto-provisions a from-scratch tenant."""

    async def _pool(self):
        from server.db.migrate import apply_migrations
        from server.db.pool import init_pool

        pool = await init_pool(dsn=DSN)
        await apply_migrations(pool)
        return pool

    async def test_start_from_scratch_auto_provisions_and_opens(self):
        """AC-11: start on a non-existent native project provisions + opens."""
        from server.coordination.identity import _clear_auth_cache
        from server.db.pool import close_pool
        from server.migration.batch_session import get_session_store
        from server.tools.migration import start_migration_session

        pool = await self._pool()
        pid = f"Acme/start-from-scratch-{uuid.uuid4().hex[:8]}"
        dev_id, token = await _register_dev(pool)
        try:
            _clear_auth_cache()
            assert not await _project_exists(pool, pid)
            out = await start_migration_session(
                target_project_id=pid, source_type="freeform",
                declared_items=1, declared_bytes=10, source_sha256="abc",
                chunk_count=1, ctx=_ctx(), dev_token=token,
            )
            assert out["status"] == "open", out
            # The tenant + admin membership now exist (the gate passed).
            assert await _project_exists(pool, pid)
            assert await _member_role(pool, pid, dev_id) == "project_admin"
            get_session_store().close(out["session_id"])
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()

    async def test_start_bad_token_writes_nothing(self):
        """AC-13 edge: a bad token on a from-scratch id provisions nothing."""
        from server.coordination.identity import _clear_auth_cache
        from server.db.pool import close_pool
        from server.tools.migration import start_migration_session

        pool = await self._pool()
        pid = f"Acme/bad-token-scratch-{uuid.uuid4().hex[:8]}"
        try:
            _clear_auth_cache()
            out = await start_migration_session(
                target_project_id=pid, source_type="freeform",
                declared_items=1, declared_bytes=10, source_sha256="abc",
                chunk_count=1, ctx=_ctx(), dev_token="not-a-real-token",
            )
            assert out["code"] == "UNAUTHENTICATED"
            assert not await _project_exists(pool, pid)
        finally:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
            await close_pool()

    async def test_start_does_not_add_caller_to_preexisting_project(self):
        """AC-13: a project that already has an owner is NOT auto-joined; gate decides.

        The caller is a valid developer but NOT a member of the pre-existing
        project, which already has a different owner (≥1 member) → the gate must
        FORBID, and the caller must NOT have been silently added as a member.

        NOTE (UC-825, v6.9.4): the project must have a real member here. A project
        row with ZERO members is now an *orphan* and is adopted, not forbidden
        (that path is covered by ``test_native_orphan_provision.py``). AC-13 only
        protects tenants that actually have owners — which is the real theft case.
        """
        from server.coordination.identity import _clear_auth_cache, add_project_member
        from server.db.pool import close_pool
        from server.tools.migration import start_migration_session

        pool = await self._pool()
        pid = f"Acme/preexisting-{uuid.uuid4().hex[:8]}"
        dev_id, token = await _register_dev(pool)
        owner_id, _owner_token = await _register_dev(pool)
        try:
            # Project exists WITH an owner (real tenant), but our caller is NOT a member.
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO projects (project_id, name, backend_type, board_url, meta) "
                    "VALUES ($1, $1, 'native', '', '{}'::jsonb) ON CONFLICT DO NOTHING",
                    pid,
                )
                await add_project_member(
                    conn, project_id=pid, developer_id=owner_id, role="project_admin"
                )
            _clear_auth_cache()
            out = await start_migration_session(
                target_project_id=pid, source_type="freeform",
                declared_items=1, declared_bytes=10, source_sha256="abc",
                chunk_count=1, ctx=_ctx(), dev_token=token,
            )
            # Not a member of an owned pre-existing project → FORBIDDEN, not auto-joined.
            assert out.get("code") == "FORBIDDEN"
            assert await _member_role(pool, pid, dev_id) is None
            # The real owner is untouched.
            assert await _member_role(pool, pid, owner_id) == "project_admin"
        finally:
            await _cleanup(pool, pid, dev_id, owner_id)
            await close_pool()


# ═══════════════════════════════════════════════════════════════════════
# UC-822 — E2E: provision + migrate a brand-new native project from scratch
# ═══════════════════════════════════════════════════════════════════════


@pytestmark_pg
class TestProvisionMigrateE2E:
    """AC-14..17: BD vacía → start (auto-provision) → append → commit → verify.

    This is the path that had no coverage and let the gap ship: prior batch
    tests pre-seeded the project + membership. Here the project is born from
    scratch and the engine provisions it itself.
    """

    async def _pool(self):
        from server.db.migrate import apply_migrations
        from server.db.pool import init_pool

        pool = await init_pool(dsn=DSN)
        await apply_migrations(pool)
        return pool

    async def test_e2e_provision_then_migrate_from_scratch(self):
        """AC-14..17: full from-scratch provision + batch migration."""
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

        pool = await self._pool()
        pid = f"EmbedBuild/e2e-from-scratch-{uuid.uuid4().hex[:8]}"
        dev_id, token = await _register_dev(pool)
        try:
            _clear_auth_cache()
            # AC-14 precondition: the target project does NOT exist.
            assert not await _project_exists(pool, pid)

            blob = _make_large_items_json(40)  # 1 US + 40 UC + 120 AC, mixed states
            chunks = _chunk(blob)
            started = await start_migration_session(
                target_project_id=pid, source_type="freeform",
                declared_items=161, declared_bytes=len(blob.encode()),
                source_sha256=sha256_hex(blob), chunk_count=len(chunks),
                ctx=_ctx(), dev_token=token,
            )
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

            # AC-14: exactly one project row, with the canonical owner/repo id.
            async with pool.acquire() as conn:
                proj_count = await conn.fetchval(
                    "SELECT count(*) FROM projects WHERE project_id = $1", pid
                )
            assert proj_count == 1

            # AC-15: creator is project_admin.
            assert await _member_role(pool, pid, dev_id) == "project_admin"

            # AC-16: US/UC/AC == source 1:1, states preserved verbatim.
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
            # Mixed states from the fixture: i%4==0 → backlog (10 of 40), else done (30).
            assert done == 30
            assert backlog == 10

            # AC-17: the display slug is the URL-safe projection of the canonical id.
            assert display_slug(pid) == pid.lower().replace("/", "-")
        finally:
            await _cleanup(pool, pid, dev_id)
            await close_pool()
