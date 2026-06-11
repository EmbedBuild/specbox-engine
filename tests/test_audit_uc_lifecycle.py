"""UC-506 (US-05) — audit log of UC lifecycle events.

Covers AC-01/02/03: ``reserve_uc`` and ``release_uc`` write a row in
``audit_log`` AFTER the SQL succeeds, with ``operation`` set to the canonical
lifecycle name and ``target_id`` carrying the uc_id. The idempotent re-reserve
path does NOT write a second event. No migration: the rows use the existing
``audit_log`` columns.

Postgres-gated like the rest of the native suite. Reuses the seeding pattern
from ``test_audit_log_destructive.py``.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from server.backends.native_backend import NativeBackend
from server.coordination.audit import (
    OP_RELEASE_UC,
    OP_RESERVE_UC,
)
from server.coordination.identity import (
    add_project_member,
    register_developer,
    register_mcp_token,
)
from server.coordination.reservations import release_uc, reserve_uc
from server.db.pool import close_pool, get_pool, init_pool

from tests._native_db import DSN, reachable

_PG_OK, _PG_SKIP_REASON = reachable()

pytestmark = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)


@pytest.fixture(autouse=True)
async def _pool_lifecycle():
    await init_pool(dsn=DSN)
    try:
        yield
    finally:
        await close_pool()


async def _seed_project_uc(project_id: str, developer_id: str, token: str) -> str:
    """Create dev + token + member + one US + one UC. Returns the uc spec id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Tester")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute(
            """
            INSERT INTO projects (project_id, name, backend_type, board_url, meta)
            VALUES ($1, $1, 'native', '', '{}'::jsonb)
            ON CONFLICT (project_id) DO NOTHING
            """,
            project_id,
        )
        await add_project_member(conn, project_id=project_id, developer_id=developer_id)

    suffix = uuid.uuid4().int % 1_000_000
    uc_spec = f"UC-{suffix}"
    backend = NativeBackend(project_id=project_id, dev_token=token)
    us = await backend.create_item(project_id, name=f"US-{suffix}: UC-506 fixture", labels=["US"])
    await backend.create_item(project_id, name=f"{uc_spec}: UC-506 fixture", labels=["UC"], parent_id=us.id)
    return uc_spec


async def _audit_rows(project_id: str) -> list[asyncpg.Record]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT developer_id, operation, target_id FROM audit_log "
            "WHERE project_id = $1 ORDER BY id ASC",
            project_id,
        )


class TestReserveAuditsEvent:
    async def test_ac01_reserve_writes_audit_row(self) -> None:
        project_id = f"test-uc506-res-{uuid.uuid4().hex[:8]}"
        uc_id = await _seed_project_uc(project_id, "dev-res", "tok-res-" + uuid.uuid4().hex)

        pool = await get_pool()
        async with pool.acquire() as conn:
            await reserve_uc(conn, project_id=project_id, uc_id=uc_id, developer_id="dev-res")

        rows = [r for r in await _audit_rows(project_id) if r["operation"] == OP_RESERVE_UC]
        assert len(rows) == 1, "exactly one reserve_uc event after a successful reserve"
        assert rows[0]["target_id"] == uc_id
        assert rows[0]["developer_id"] == "dev-res"

    async def test_ac01_idempotent_rereserve_does_not_double_audit(self) -> None:
        project_id = f"test-uc506-idem-{uuid.uuid4().hex[:8]}"
        uc_id = await _seed_project_uc(project_id, "dev-idem", "tok-idem-" + uuid.uuid4().hex)

        pool = await get_pool()
        async with pool.acquire() as conn:
            await reserve_uc(conn, project_id=project_id, uc_id=uc_id, developer_id="dev-idem")
            # Same owner re-reserving → idempotent, must NOT add a second event.
            await reserve_uc(conn, project_id=project_id, uc_id=uc_id, developer_id="dev-idem")

        rows = [r for r in await _audit_rows(project_id) if r["operation"] == OP_RESERVE_UC]
        assert len(rows) == 1, "re-reserve by the same owner is not a new lifecycle event"


class TestReleaseAuditsEvent:
    async def test_ac02_release_writes_audit_row(self) -> None:
        project_id = f"test-uc506-rel-{uuid.uuid4().hex[:8]}"
        uc_id = await _seed_project_uc(project_id, "dev-rel", "tok-rel-" + uuid.uuid4().hex)

        pool = await get_pool()
        async with pool.acquire() as conn:
            await reserve_uc(conn, project_id=project_id, uc_id=uc_id, developer_id="dev-rel")
            released = await release_uc(conn, project_id=project_id, uc_id=uc_id, developer_id="dev-rel")
            assert released is True

        rows = await _audit_rows(project_id)
        ops = [r["operation"] for r in rows]
        assert OP_RESERVE_UC in ops and OP_RELEASE_UC in ops
        rel = [r for r in rows if r["operation"] == OP_RELEASE_UC]
        assert len(rel) == 1
        assert rel[0]["target_id"] == uc_id

    async def test_ac02_release_of_missing_reservation_no_audit(self) -> None:
        project_id = f"test-uc506-norel-{uuid.uuid4().hex[:8]}"
        uc_id = await _seed_project_uc(project_id, "dev-norel", "tok-norel-" + uuid.uuid4().hex)

        pool = await get_pool()
        async with pool.acquire() as conn:
            released = await release_uc(conn, project_id=project_id, uc_id=uc_id, developer_id="dev-norel")
            assert released is False  # nothing was held

        rows = [r for r in await _audit_rows(project_id) if r["operation"] == OP_RELEASE_UC]
        assert rows == [], "no release event when there was no reservation to release"


class TestCompleteTransitionResilience:
    """US-12 / UC-1207 AC-02 — the done transition survives the best-effort leg.

    complete_uc is two steps: backend.update_item(state='done') (fires the
    0012 triggers) and then _release_uc_native (best-effort: audits the
    OP_COMPLETE_UC event + releases the reservation, swallowing EVERY
    failure). Before US-12, a failure there silently lost the completion
    record. Now the lifecycle transition is written transactionally by the
    trigger in step 1, so step 2 failing must not matter.
    """

    async def test_done_transition_survives_release_failure(self) -> None:
        from server.tools.spec_driven import _release_uc_native

        project_id = f"test-uc1207-res-{uuid.uuid4().hex[:8]}"
        token = "tok-resil-" + uuid.uuid4().hex
        uc_id = await _seed_project_uc(project_id, "dev-resil", token)

        # Step 1 of complete_uc: the state change (spec_driven.py flow).
        backend = NativeBackend(project_id=project_id, dev_token=token)
        await backend.update_item(project_id, uc_id, state="done")

        # Step 2 with INJECTED FAILURE: bogus token → auth fails inside and is
        # swallowed by design ("never raises"). No OP_COMPLETE_UC audit row.
        await _release_uc_native({"project_id": project_id, "dev_token": "bogus-token"}, uc_id)

        pool = await get_pool()
        async with pool.acquire() as conn:
            tr = await conn.fetch(
                "SELECT to_state, developer_id, source FROM uc_state_transitions "
                "WHERE project_id = $1 AND uc_id = $2 AND to_state = 'done'",
                project_id, uc_id,
            )
            cols = await conn.fetchrow(
                "SELECT state, completed_at FROM use_cases "
                "WHERE project_id = $1 AND id = $2",
                project_id, uc_id,
            )
        complete_events = [r for r in await _audit_rows(project_id) if r["operation"] == "complete_uc"]

        assert complete_events == [], "the best-effort audit leg did fail (precondition)"
        assert len(tr) == 1, "the lifecycle transition must exist anyway"
        assert tr[0]["developer_id"] == "dev-resil", "attributed by the update_item GUC"
        assert cols["state"] == "done" and cols["completed_at"] is not None
