"""UC-503 — audit log of destructive operations.

Covers AC-12/13/14/15: ``delete_acceptance_criterion`` and ``archive_item``
record a row in ``audit_log`` AFTER the SQL succeeds; failed destructive ops
DO NOT write audit; the other 7 mutators NEVER write audit.

All tests require a reachable Postgres (Pooler or local dev). They share the
same fixture pattern as ``tests/test_native_mutation_authz.py``: each test
creates an isolated ``project_id`` with its own dev + token + membership +
US/UC/ACs seeded, so tests do not collide on the global state.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from server.backends.native_backend import NativeBackend
from server.coordination.audit import (
    OP_ARCHIVE_ITEM,
    OP_DELETE_AC,
    record_destructive,
)
from server.coordination.identity import (
    add_project_member,
    register_developer,
    register_mcp_token,
)
from server.db.pool import close_pool, get_pool, init_pool

from tests._native_db import DSN, reachable

_PG_OK, _PG_SKIP_REASON = reachable()

pytestmark = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def _pool_lifecycle():
    """Reset the asyncpg pool around each test so the cached gate sees a
    fresh module state (no leftover cache from a sibling test).

    Mirrors the lifecycle from test_native_mutation_authz.
    """
    await init_pool(dsn=DSN)
    try:
        yield
    finally:
        await close_pool()


async def _seed(
    project_id: str,
    developer_id: str,
    token: str,
    *,
    with_member: bool = True,
) -> tuple[str, str, list[str]]:
    """Create dev + mcp_token + (optional) project_member + US + UC + 3 ACs.

    Returns (us_id, uc_id, [ac_ids]) for the fixture rows.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Identity + token
        await register_developer(conn, developer_id=developer_id, display_name="Tester")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        # 2. Project row (idempotent upsert) + (optional) membership
        await conn.execute(
            """
            INSERT INTO projects (project_id, name, backend_type, board_url, meta)
            VALUES ($1, $1, 'native', '', '{}'::jsonb)
            ON CONFLICT (project_id) DO NOTHING
            """,
            project_id,
        )
        if with_member:
            await add_project_member(conn, project_id=project_id, developer_id=developer_id)

    # 3. US + UC + 3 ACs via the backend (uses the gate, which is fine — we
    #    are a member). The US/UC ids in Postgres are derived from the spec
    #    prefix in the name (parse_item_id regex captures \d+), so we use a
    #    numeric suffix to keep ids unique across the whole DB (user_stories.id
    #    is the PK, not (project_id, id)).
    suffix = uuid.uuid4().int % 1_000_000  # 6-digit numeric suffix
    us_spec = f"US-{suffix}"
    uc_spec = f"UC-{suffix}"
    backend = NativeBackend(project_id=project_id, dev_token=token)
    us = await backend.create_item(project_id, name=f"{us_spec}: UC-503 fixture", labels=["US"])
    uc = await backend.create_item(project_id, name=f"{uc_spec}: UC-503 fixture", labels=["UC"], parent_id=us.id)
    ac_specs = [("AC-01", "first AC"), ("AC-02", "second AC"), ("AC-03", "third AC")]
    await backend.create_acceptance_criteria(project_id, uc.id, ac_specs)
    return us.id, uc.id, [a[0] for a in ac_specs]


async def _count_audit(project_id: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT count(*) FROM audit_log WHERE project_id = $1",
            project_id,
        )


async def _latest_audit_row(project_id: str) -> asyncpg.Record | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT developer_id, project_id, operation, target_id
              FROM audit_log
             WHERE project_id = $1
             ORDER BY id DESC
             LIMIT 1
            """,
            project_id,
        )


async def _audit_rows_ordered(project_id: str) -> list[asyncpg.Record]:
    """All audit rows for a project, oldest first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT developer_id, operation, target_id FROM audit_log "
            "WHERE project_id = $1 ORDER BY id ASC",
            project_id,
        )


# ── AC-12: record_destructive writes the row ──────────────────────────


class TestRecordDestructiveDirect:
    """The helper itself writes exactly the 4 fields we ask for [AC-12]."""

    async def test_ac12_record_destructive_writes_all_fields(self) -> None:
        project_id = f"test-uc503-direct-{uuid.uuid4().hex[:8]}"
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO projects (project_id, name, backend_type, board_url, meta)
                VALUES ($1, $1, 'native', '', '{}'::jsonb)
                ON CONFLICT (project_id) DO NOTHING
                """,
                project_id,
            )
            await register_developer(conn, developer_id="dev-direct", display_name="X")
            await record_destructive(
                conn,
                developer_id="dev-direct",
                project_id=project_id,
                operation=OP_DELETE_AC,
                target_id="AC-XX",
            )

        row = await _latest_audit_row(project_id)
        assert row is not None
        assert row["developer_id"] == "dev-direct"
        assert row["project_id"] == project_id
        assert row["operation"] == OP_DELETE_AC
        assert row["target_id"] == "AC-XX"


# ── AC-13: delete_acceptance_criterion writes audit on success only ────


class TestDeleteAcceptanceCriterionAudit:
    async def test_ac13_successful_delete_writes_audit(self) -> None:
        project_id = f"test-uc503-delok-{uuid.uuid4().hex[:8]}"
        token = f"tok-{uuid.uuid4().hex[:16]}"
        _us, uc_id, ac_ids = await _seed(project_id, "dev-delok", token)
        backend = NativeBackend(project_id=project_id, dev_token=token)

        before = await _count_audit(project_id)
        await backend.delete_acceptance_criterion(project_id, uc_id, ac_ids[0])
        after = await _count_audit(project_id)

        assert after == before + 1, "audit_log should grow by exactly 1"
        row = await _latest_audit_row(project_id)
        assert row is not None
        assert row["developer_id"] == "dev-delok"
        assert row["project_id"] == project_id
        assert row["operation"] == OP_DELETE_AC
        assert row["target_id"] == ac_ids[0]

    async def test_ac13_failed_delete_does_not_write_audit(self) -> None:
        """Deleting a non-existing AC raises and MUST NOT touch audit_log."""
        project_id = f"test-uc503-delfail-{uuid.uuid4().hex[:8]}"
        token = f"tok-{uuid.uuid4().hex[:16]}"
        _us, uc_id, _acs = await _seed(project_id, "dev-delfail", token)
        backend = NativeBackend(project_id=project_id, dev_token=token)

        before = await _count_audit(project_id)
        with pytest.raises(ValueError, match="not found"):
            await backend.delete_acceptance_criterion(project_id, uc_id, "AC-NEVER")
        after = await _count_audit(project_id)

        assert after == before, "failed delete must not write audit_log"


# ── AC-14: archive_item writes audit on success only ──────────────────


class TestArchiveItemAudit:
    async def test_ac14_archive_uc_writes_audit(self) -> None:
        project_id = f"test-uc503-arcuc-{uuid.uuid4().hex[:8]}"
        token = f"tok-{uuid.uuid4().hex[:16]}"
        _us, uc_id, _acs = await _seed(project_id, "dev-arcuc", token)
        backend = NativeBackend(project_id=project_id, dev_token=token)

        before = await _count_audit(project_id)
        result = await backend.archive_item(project_id, uc_id, reason="UC-503 test")
        after = await _count_audit(project_id)

        assert result["archive_location"] == "state=archived"
        assert after == before + 1
        row = await _latest_audit_row(project_id)
        assert row is not None
        assert row["developer_id"] == "dev-arcuc"
        assert row["operation"] == OP_ARCHIVE_ITEM
        assert row["target_id"] == uc_id

    async def test_ac14_archive_failure_does_not_write_audit(self) -> None:
        """Archiving an item that does not exist raises and MUST NOT audit."""
        project_id = f"test-uc503-arcfail-{uuid.uuid4().hex[:8]}"
        token = f"tok-{uuid.uuid4().hex[:16]}"
        await _seed(project_id, "dev-arcfail", token)
        backend = NativeBackend(project_id=project_id, dev_token=token)

        before = await _count_audit(project_id)
        with pytest.raises(ValueError, match="not found"):
            await backend.archive_item(project_id, "item-does-not-exist", reason="ghost")
        after = await _count_audit(project_id)

        assert after == before


# ── AC-25: mixed sequence — only destructive ops write audit ───────────


class TestMixedSequenceAuditPrecision:
    """A realistic mixed sequence audits exactly the progress + destructive
    ops, in order [AC-25, updated by UC-513].

    Contract after UC-513:
    - creates (create_acceptance_criteria) → NO audit.
    - update_ac (×2), mark_ac (×1) → audit (progress mutations, UC-513).
    - delete_ac (×2), archive_item (×1) → audit (destructive, UC-503).
    So the sequence below yields exactly 6 audit rows in deterministic order.
    """

    async def test_ac25_mixed_sequence_audit_order(self) -> None:
        project_id = f"test-uc503-mixed-{uuid.uuid4().hex[:8]}"
        token = f"tok-{uuid.uuid4().hex[:16]}"
        developer_id = "dev-mixed"
        _us, uc_id, ac_ids = await _seed(project_id, developer_id, token)
        backend = NativeBackend(project_id=project_id, dev_token=token)

        before = await _count_audit(project_id)

        # 3 creates — single-AC ``create_acceptance_criteria`` calls so the
        # sequence reads as "three create operations" (not one batch). None
        # of these may write to audit_log.
        await backend.create_acceptance_criteria(project_id, uc_id, [("AC-04", "fourth AC")])
        await backend.create_acceptance_criteria(project_id, uc_id, [("AC-05", "fifth AC")])
        await backend.create_acceptance_criteria(project_id, uc_id, [("AC-06", "sixth AC")])

        # 2 updates — update_acceptance_criterion text changes (UC-513: audit).
        await backend.update_acceptance_criterion(project_id, uc_id, ac_ids[0], text="AC-01 updated")
        await backend.update_acceptance_criterion(project_id, uc_id, ac_ids[1], text="AC-02 updated")

        # 1 mark — UC-513: audit (mark_ac).
        await backend.mark_acceptance_criterion(project_id, uc_id, ac_ids[2], True)

        # 2 destructive deletes — operation == OP_DELETE_AC.
        await backend.delete_acceptance_criterion(project_id, uc_id, "AC-04")
        await backend.delete_acceptance_criterion(project_id, uc_id, "AC-05")

        # 1 destructive archive — operation == OP_ARCHIVE_ITEM.
        await backend.archive_item(project_id, uc_id, reason="UC-513 mixed sequence")

        # ── Assertions ───────────────────────────────────────────────
        after = await _count_audit(project_id)
        assert after == before + 6, (
            f"expected exactly 6 audit rows (2 update_ac + 1 mark_ac + 2 delete_ac + "
            f"1 archive_item), got {after - before}"
        )

        rows = await _audit_rows_ordered(project_id)
        assert len(rows) == 6, f"project audit_log must contain exactly 6 rows, found {len(rows)}"
        for row in rows:
            assert row["developer_id"] == developer_id
        seq = [(r["operation"], r["target_id"]) for r in rows]
        assert seq == [
            ("update_ac", ac_ids[0]),
            ("update_ac", ac_ids[1]),
            ("mark_ac", ac_ids[2]),
            (OP_DELETE_AC, "AC-04"),
            (OP_DELETE_AC, "AC-05"),
            (OP_ARCHIVE_ITEM, uc_id),
        ], seq


# ── AC-15: which non-destructive mutators audit (contract updated by UC-513) ──


class TestNonDestructiveMutatorsLeaveAuditUntouched:
    """UC-513 (US-05) changed the UC-503 contract: progress mutations now DO
    audit so the realtime broadcast fires and the detail view refreshes live.

    - AUDIT (UC-513): update_item (US/UC), mark_acceptance_criterion,
      update_acceptance_criterion.
    - STILL SILENT: create_item / create_acceptance_criteria / add_comment /
      add_attachment (creates and side-channel writes are not progress signals).
    """

    async def test_ac15_progress_mutators_audit_creates_stay_silent(self) -> None:
        project_id = f"test-uc503-ndmut-{uuid.uuid4().hex[:8]}"
        token = f"tok-{uuid.uuid4().hex[:16]}"
        us_id, uc_id, ac_ids = await _seed(project_id, "dev-ndmut", token)
        backend = NativeBackend(project_id=project_id, dev_token=token)

        before = await _count_audit(project_id)

        # Progress mutators — each audits exactly one row (UC-513).
        await backend.update_item(project_id, us_id, name="US-99: renamed")  # update_us
        await backend.mark_acceptance_criterion(project_id, uc_id, ac_ids[1], True)  # mark_ac
        await backend.update_acceptance_criterion(
            project_id, uc_id, ac_ids[2], text="third AC updated"
        )  # update_ac

        # Non-progress writes — must NOT audit.
        await backend.create_acceptance_criteria(project_id, uc_id, [("AC-04", "fourth AC")])
        await backend.add_comment(project_id, uc_id, "non-destructive comment")
        await backend.add_attachment(project_id, uc_id, "ref.txt", b"hello world")

        after = await _count_audit(project_id)
        assert after == before + 3, (
            f"expected exactly 3 audit rows (update_us + mark_ac + update_ac), "
            f"got {after - before}"
        )
        rows = await _audit_rows_ordered(project_id)
        ops = [r["operation"] for r in rows[-3:]]
        assert ops == ["update_us", "mark_ac", "update_ac"], ops
