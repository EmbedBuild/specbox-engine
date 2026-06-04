"""UC-606 — provision_project audit events only on REAL provisioning.

The bug (found dogfooding US-06): every ``set_auth_token`` native re-auth ran
``provision_native_project``, which wrote a ``provision_project`` row to
``audit_log`` **unconditionally** — even on a re-provisioning no-op (tenant
already exists with members). The activity feed then showed "created the
project" N times for one real creation.

The fix emits the event only when provisioning really provisions: a tenant born
from scratch (``created``) or an orphan tenant adopted (``adopted_orphan``), and
tags the row with metadata so a consumer can tell the cases apart.

Postgres-gated; SKIP cleanly when no dev DB is reachable
(``docker compose -f docker-compose.dev.yml up -d``).
"""

from __future__ import annotations

import uuid

import pytest

from tests._native_db import DSN, reachable
from tests.test_native_provision import _cleanup, _register_dev

PG_OK, PG_SKIP_REASON = reachable()
pytestmark = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


async def _pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _count_provision_events(pool, project_id: str) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT count(*) FROM audit_log "
            "WHERE project_id = $1 AND operation = 'provision_project'",
            project_id,
        )


async def _provision_rows(pool, project_id: str):
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT metadata FROM audit_log "
            "WHERE project_id = $1 AND operation = 'provision_project' ORDER BY id",
            project_id,
        )


async def test_ac17_first_provision_emits_exactly_one_created_event():
    """AC-17: provisioning from scratch writes exactly one provision_project
    row, with metadata distinguishing the case (``created``)."""
    import json

    from server.db.pool import close_pool
    from server.migration.native_handling import provision_native_project

    pool = await _pool()
    pid = f"Acme/uc606-created-{uuid.uuid4().hex[:8]}"
    dev_id, _ = await _register_dev(pool)
    try:
        await provision_native_project(
            pool, project_id=pid, developer_id=dev_id, role="project_admin",
            validate_id=False,
        )
        assert await _count_provision_events(pool, pid) == 1
        rows = await _provision_rows(pool, pid)
        meta = rows[0]["metadata"]
        meta = json.loads(meta) if isinstance(meta, str) else meta
        assert meta == {"case": "created"}
    finally:
        await _cleanup(pool, pid, dev_id)
        await close_pool()


async def test_ac16_reprovision_no_op_emits_no_new_event():
    """AC-16: re-provisioning a project that already exists WITH members (the
    re-auth no-op) writes NO new audit row — delta of N re-provisions is 0."""
    from server.db.pool import close_pool
    from server.migration.native_handling import provision_native_project

    pool = await _pool()
    pid = f"Acme/uc606-noop-{uuid.uuid4().hex[:8]}"
    dev_id, _ = await _register_dev(pool)
    try:
        # First provision (real) → 1 event.
        await provision_native_project(
            pool, project_id=pid, developer_id=dev_id, role="project_admin",
            validate_id=False,
        )
        baseline = await _count_provision_events(pool, pid)
        assert baseline == 1

        # Re-provision 4 times (simulates 4 set_auth_token re-auths).
        for _ in range(4):
            await provision_native_project(
                pool, project_id=pid, developer_id=dev_id, role="project_admin",
                validate_id=False,
            )

        # AC-16: delta is 0 — no phantom "created the project" events.
        assert await _count_provision_events(pool, pid) == baseline
    finally:
        await _cleanup(pool, pid, dev_id)
        await close_pool()


async def test_ac17_orphan_adoption_emits_adopted_orphan_event():
    """AC-17: adopting an orphan tenant (row exists, zero members) emits one
    event tagged ``adopted_orphan`` — distinct from a no-op."""
    import json

    from server.db.pool import close_pool
    from server.migration.native_handling import provision_native_project

    pool = await _pool()
    pid = f"Acme/uc606-orphan-{uuid.uuid4().hex[:8]}"
    dev_id, _ = await _register_dev(pool)
    try:
        # Create an ORPHAN tenant: projects row with ZERO members (the dirty
        # state setup_board used to leave before v6.9.4 FIX A).
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO projects (project_id, name, backend_type, board_url, meta) "
                "VALUES ($1, $1, 'native', '', '{}'::jsonb) ON CONFLICT DO NOTHING",
                pid,
            )
        assert await _count_provision_events(pool, pid) == 0  # no event yet

        # Adopt it.
        await provision_native_project(
            pool, project_id=pid, developer_id=dev_id, role="project_admin",
            validate_id=False,
        )
        assert await _count_provision_events(pool, pid) == 1
        rows = await _provision_rows(pool, pid)
        meta = rows[0]["metadata"]
        meta = json.loads(meta) if isinstance(meta, str) else meta
        assert meta == {"case": "adopted_orphan"}
    finally:
        await _cleanup(pool, pid, dev_id)
        await close_pool()


async def test_record_destructive_metadata_is_additive():
    """record_destructive without metadata keeps the {} default (unchanged);
    with metadata, it persists the payload — backwards-compatible (AC-19)."""
    import json

    from server.coordination import audit as audit_mod
    from server.db.pool import close_pool

    pool = await _pool()
    pid = f"Acme/uc606-audit-{uuid.uuid4().hex[:8]}"
    dev_id, _ = await _register_dev(pool)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO projects (project_id, name, backend_type, board_url, meta) "
                "VALUES ($1, $1, 'native', '', '{}'::jsonb) ON CONFLICT DO NOTHING",
                pid,
            )
            # No metadata → default {}.
            await audit_mod.record_destructive(
                conn, developer_id=dev_id, project_id=pid,
                operation="delete_acceptance_criterion", target_id="AC-X",
            )
            # With metadata → persisted.
            await audit_mod.record_destructive(
                conn, developer_id=dev_id, project_id=pid,
                operation=audit_mod.OP_PROVISION_PROJECT, target_id=pid,
                metadata={"case": "created"},
            )
            rows = await conn.fetch(
                "SELECT operation, metadata FROM audit_log WHERE project_id = $1 ORDER BY id",
                pid,
            )
        by_op = {r["operation"]: (json.loads(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"]) for r in rows}
        assert by_op["delete_acceptance_criterion"] == {}
        assert by_op["provision_project"] == {"case": "created"}
    finally:
        await _cleanup(pool, pid, dev_id)
        await close_pool()
