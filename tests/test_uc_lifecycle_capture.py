"""US-12 / UC-1207 — formal suite for the UC lifecycle capture (0012-0016).

Covers, against a real Postgres (gated like the rest of the native suite):

- UC-1201 AC-01..05 — the 0012 triggers, exercised through the REAL writers:
  the raw UPDATE of ``start_uc_atomic`` (the rawest state writer in the
  codebase), plain SQL updates, and ingest-shaped INSERTs.
- UC-1202 — GUC context: ``start_uc_atomic`` and ``update_item`` attribute the
  transition to the real developer; writers without GUCs degrade honestly.
- UC-1203/UC-1206 E2E (UC-827 standard) — KPIs computed from a DIRTY state:
  imported-done UCs, re-cycles, never-started legacy rows.

Timestamps are controlled by writing the lifecycle columns / transition rows
directly where needed — the trigger semantics themselves are asserted with
real UPDATEs.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import asyncpg
import pytest

from server.backends.native_backend import NativeBackend
from server.coordination.identity import (
    add_project_member,
    register_developer,
    register_mcp_token,
)
from server.coordination.reservations import start_uc_atomic
from server.db.migrate import apply_migrations
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


async def _seed_project(project_id: str, developer_id: str, token: str) -> None:
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
        await conn.execute(
            "INSERT INTO user_stories (id, project_id, name, state) "
            "VALUES ('US-01', $1, 'US fixture', 'user_stories')",
            project_id,
        )


async def _mk_uc(project_id: str, uc: str, state: str = "backlog") -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO use_cases (id, project_id, us_id, name, state) "
            "VALUES ($1, $2, 'US-01', $1, $3)",
            uc, project_id, state,
        )


async def _set_state(project_id: str, uc: str, state: str) -> None:
    """Raw state UPDATE — the start_uc_atomic shape, no GUCs, no ORM."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE use_cases SET state = $3, updated_at = now() "
            "WHERE project_id = $1 AND id = $2",
            project_id, uc, state,
        )


async def _transitions(project_id: str, uc: str) -> list[asyncpg.Record]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM uc_state_transitions "
            "WHERE project_id = $1 AND uc_id = $2 ORDER BY id",
            project_id, uc,
        )


async def _lifecycle_cols(project_id: str, uc: str) -> asyncpg.Record:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT state, started_at, completed_at FROM use_cases "
            "WHERE project_id = $1 AND id = $2",
            project_id, uc,
        )


class TestTransitionCapture:
    """UC-1201 — the 0012 triggers capture every state change, transactionally."""

    async def test_ac01_raw_update_captures_transition(self) -> None:
        project_id = f"test-uc1207-cap-{uuid.uuid4().hex[:8]}"
        await _seed_project(project_id, "dev-cap", "tok-cap-" + uuid.uuid4().hex)
        await _mk_uc(project_id, "UC-1")

        await _set_state(project_id, "UC-1", "in_progress")
        rows = await _transitions(project_id, "UC-1")
        assert len(rows) == 1
        assert rows[0]["from_state"] == "backlog"
        assert rows[0]["to_state"] == "in_progress"
        assert rows[0]["us_id"] == "US-01"
        assert rows[0]["project_id"] == project_id
        assert rows[0]["occurred_at"] is not None

        # Same-state UPDATE → WHEN (OLD IS DISTINCT FROM NEW) suppresses the row.
        await _set_state(project_id, "UC-1", "in_progress")
        assert len(await _transitions(project_id, "UC-1")) == 1

    async def test_ac02_recycle_preserves_started_at(self) -> None:
        project_id = f"test-uc1207-rec-{uuid.uuid4().hex[:8]}"
        await _seed_project(project_id, "dev-rec", "tok-rec-" + uuid.uuid4().hex)
        await _mk_uc(project_id, "UC-1")

        await _set_state(project_id, "UC-1", "in_progress")
        first = await _lifecycle_cols(project_id, "UC-1")
        assert first["started_at"] is not None and first["completed_at"] is None

        await _set_state(project_id, "UC-1", "done")
        done1 = await _lifecycle_cols(project_id, "UC-1")
        assert done1["completed_at"] is not None
        assert done1["started_at"] == first["started_at"]

        # Re-cycle: reopen + close again. First start wins, last completion wins.
        await _set_state(project_id, "UC-1", "in_progress")
        await _set_state(project_id, "UC-1", "done")
        done2 = await _lifecycle_cols(project_id, "UC-1")
        assert done2["started_at"] == first["started_at"], "re-cycle must not overwrite started_at"
        assert done2["completed_at"] >= done1["completed_at"], "last completion wins"
        cycles = [r for r in await _transitions(project_id, "UC-1") if r["to_state"] == "in_progress"]
        assert len(cycles) == 2

    async def test_ac03_insert_done_fires_nothing(self) -> None:
        """The ingest shape: INSERT rows already done → no transitions, NULL columns."""
        project_id = f"test-uc1207-imp-{uuid.uuid4().hex[:8]}"
        await _seed_project(project_id, "dev-imp", "tok-imp-" + uuid.uuid4().hex)
        await _mk_uc(project_id, "UC-IMP", state="done")

        assert await _transitions(project_id, "UC-IMP") == []
        cols = await _lifecycle_cols(project_id, "UC-IMP")
        assert cols["started_at"] is None and cols["completed_at"] is None

    async def test_ac04_trigger_failure_rolls_back_state(self) -> None:
        """The history INSERT participates in the UPDATE's transaction."""
        project_id = f"test-uc1207-rb-{uuid.uuid4().hex[:8]}"
        await _seed_project(project_id, "dev-rb", "tok-rb-" + uuid.uuid4().hex)
        await _mk_uc(project_id, "UC-1")
        await _set_state(project_id, "UC-1", "in_progress")

        pool = await get_pool()
        async with pool.acquire() as conn:
            with pytest.raises(asyncpg.CheckViolationError):
                async with conn.transaction():
                    # Injected failure: any insert with to_state='review' violates.
                    await conn.execute(
                        "ALTER TABLE uc_state_transitions "
                        "ADD CONSTRAINT uc1207_fail CHECK (to_state <> 'review') NOT VALID"
                    )
                    await conn.execute(
                        "UPDATE use_cases SET state = 'review' "
                        "WHERE project_id = $1 AND id = 'UC-1'",
                        project_id,
                    )

        cols = await _lifecycle_cols(project_id, "UC-1")
        assert cols["state"] == "in_progress", "state change must roll back with the history insert"
        assert all(r["to_state"] != "review" for r in await _transitions(project_id, "UC-1"))

    async def test_ac05_migrations_idempotent(self) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            applied1 = await apply_migrations(conn)
            applied2 = await apply_migrations(conn)
        assert applied1 == applied2
        assert "0012_uc_lifecycle_capture.sql" in applied1


class TestLifecycleContext:
    """UC-1202 — GUCs attribute transitions; absence degrades honestly."""

    async def test_start_uc_atomic_attributes_developer(self) -> None:
        project_id = f"test-uc1207-guc-{uuid.uuid4().hex[:8]}"
        await _seed_project(project_id, "dev-guc", "tok-guc-" + uuid.uuid4().hex)
        await _mk_uc(project_id, "UC-1")

        pool = await get_pool()
        await start_uc_atomic(
            pool, project_id=project_id, uc_db_id="UC-1", uc_id="UC-1", developer_id="dev-guc"
        )
        rows = await _transitions(project_id, "UC-1")
        assert len(rows) == 1
        assert rows[0]["developer_id"] == "dev-guc"
        assert rows[0]["source"] == "interactive"
        assert (await _lifecycle_cols(project_id, "UC-1"))["started_at"] is not None

    async def test_update_item_attributes_developer(self) -> None:
        project_id = f"test-uc1207-upd-{uuid.uuid4().hex[:8]}"
        token = "tok-upd-" + uuid.uuid4().hex
        await _seed_project(project_id, "dev-upd", token)
        await _mk_uc(project_id, "UC-1")

        backend = NativeBackend(project_id=project_id, dev_token=token)
        await backend.update_item(project_id, "UC-1", state="in_progress")

        rows = await _transitions(project_id, "UC-1")
        assert len(rows) == 1
        assert rows[0]["developer_id"] == "dev-upd"
        assert rows[0]["to_state"] == "in_progress"

    async def test_no_guc_degrades_honestly(self) -> None:
        project_id = f"test-uc1207-nog-{uuid.uuid4().hex[:8]}"
        await _seed_project(project_id, "dev-nog", "tok-nog-" + uuid.uuid4().hex)
        await _mk_uc(project_id, "UC-1")

        await _set_state(project_id, "UC-1", "in_progress")  # raw, no GUC
        rows = await _transitions(project_id, "UC-1")
        assert rows[0]["developer_id"] is None
        assert rows[0]["source"] == "interactive"

    async def test_import_guc_skips_lifecycle_columns(self) -> None:
        project_id = f"test-uc1207-igc-{uuid.uuid4().hex[:8]}"
        await _seed_project(project_id, "dev-igc", "tok-igc-" + uuid.uuid4().hex)
        await _mk_uc(project_id, "UC-1")

        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.change_source', 'import', true)")
                await conn.execute(
                    "UPDATE use_cases SET state = 'in_progress' "
                    "WHERE project_id = $1 AND id = 'UC-1'",
                    project_id,
                )
        rows = await _transitions(project_id, "UC-1")
        assert rows[0]["source"] == "import"
        assert (await _lifecycle_cols(project_id, "UC-1"))["started_at"] is None


class TestDirtyStateKpisE2E:
    """UC-827 standard — KPIs computed from a realistic DIRTY tenant.

    Mixed population: 2 interactive completions with known leads (2h / 4h),
    1 imported-as-done (no lifecycle), 1 legacy done with no signal at all,
    1 re-cycled UC, 1 WIP. Coverage and percentiles must be exact and the
    non-interactive rows must be excluded but visible.
    """

    async def test_kpis_from_dirty_state(self) -> None:
        project_id = f"test-uc1207-e2e-{uuid.uuid4().hex[:8]}"
        await _seed_project(project_id, "dev-e2e", "tok-e2e-" + uuid.uuid4().hex)
        pool = await get_pool()

        # Two clean interactive completions with controlled leads.
        for uc, hours in (("UC-A", 2), ("UC-B", 4)):
            await _mk_uc(project_id, uc)
            await _set_state(project_id, uc, "in_progress")
            await _set_state(project_id, uc, "done")
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE use_cases SET started_at = completed_at - $3::interval "
                    "WHERE project_id = $1 AND id = $2",
                    project_id, uc, timedelta(hours=hours),
                )
        # Imported as done (ingest shape) + legacy done with no signal.
        await _mk_uc(project_id, "UC-IMP", state="done")
        await _mk_uc(project_id, "UC-LEG", state="done")
        # Re-cycled (still measurable; cycles=2; lead defined by columns).
        await _mk_uc(project_id, "UC-REC")
        for s in ("in_progress", "done", "in_progress", "done"):
            await _set_state(project_id, "UC-REC", s)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE use_cases SET started_at = completed_at - interval '3 hours' "
                "WHERE project_id = $1 AND id = 'UC-REC'",
                project_id,
            )
        # WIP.
        await _mk_uc(project_id, "UC-WIP")
        await _set_state(project_id, "UC-WIP", "in_progress")

        async with pool.acquire() as conn:
            k = await conn.fetchrow("SELECT * FROM fn_lifecycle_kpis($1)", project_id)
            rec = await conn.fetchrow(
                "SELECT cycles, measurable FROM v_uc_lifecycle "
                "WHERE project_id = $1 AND uc_id = 'UC-REC'",
                project_id,
            )

        assert k["done_total"] == 5
        assert k["done_measurable"] == 3  # A, B, REC
        assert float(k["coverage_pct"]) == 60.0
        assert k["lead_time_p50"] == timedelta(hours=3)  # leads 2h, 3h, 4h
        assert k["wip"] == 1
        assert k["done_unmeasured"] == 2  # IMP + LEG, visible, never averaged
        assert rec["cycles"] == 2 and rec["measurable"] is True
