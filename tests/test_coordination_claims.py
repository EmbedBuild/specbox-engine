"""Unit + PG-gated tests for the NativeBackend claims layer — H3.

Covers UC-301..304 acceptance criteria:

- AC-16: uc_claims UNIQUE → exactly one of two concurrent claims wins, the
  other gets ALREADY_CLAIMED (verified for real in the PG-gated race test).
- AC-17: release_uc only by the owner; NOT_CLAIM_OWNER otherwise (claim kept).
- AC-18: start_uc_atomic claims + sets in_progress in one tx — no orphan claim
  if the state UPDATE fails.
- AC-19: the ALREADY_CLAIMED conflict carries owner / claimed_at / branch.
- AC-23: branch_registry rejects a colliding branch and suggests
  feature/{uc_id}-... naming.

Unit tests use a fake asyncpg connection; the PG-gated class runs the real
concurrency race and skips cleanly without a dev DB.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager

import asyncpg
import pytest

from server.coordination.branches import (
    BranchCollisionError,
    register_branch,
    suggest_branch_name,
)
from server.coordination.claims import (
    AlreadyClaimedError,
    Claim,
    NotClaimOwnerError,
    claim_uc,
    release_uc,
)


# ── Fake conn ────────────────────────────────────────────────────────


class FakeConn:
    def __init__(self, *, fetchrow=None, insert_raises=None) -> None:
        self.executed: list[tuple[str, tuple]] = []
        self._fetchrow = fetchrow
        self._insert_raises = insert_raises

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        return "DELETE 1"

    async def fetchrow(self, sql, *args):
        if "INSERT INTO uc_claims" in sql and self._insert_raises:
            raise self._insert_raises
        return self._fetchrow(sql, *args) if self._fetchrow else None

    @asynccontextmanager
    async def transaction(self):
        yield


def _claim_row(uc_id="UC-301", dev="alice", branch="feature/uc-301"):
    return {
        "project_id": "p",
        "uc_id": uc_id,
        "developer_id": dev,
        "branch": branch,
        "claimed_at": "2026-05-21T20:00:00+00:00",
    }


# ── claim_uc [AC-16, AC-19] ──────────────────────────────────────────


async def test_claim_uc_success():
    conn = FakeConn(fetchrow=lambda sql, *a: _claim_row(dev="alice"))
    claim = await claim_uc(conn, project_id="p", uc_id="UC-301", developer_id="alice")
    assert isinstance(claim, Claim)
    assert claim.developer_id == "alice"
    assert claim.uc_id == "UC-301"


async def test_claim_uc_already_claimed_carries_owner_info():
    """AC-19: ALREADY_CLAIMED conflict includes owner / claimed_at / branch."""

    def fetchrow(sql, *args):
        # The SELECT after the unique violation returns the existing claim.
        return _claim_row(dev="bob", branch="feature/uc-301-bob")

    conn = FakeConn(
        fetchrow=fetchrow,
        insert_raises=asyncpg.UniqueViolationError("dup"),
    )
    with pytest.raises(AlreadyClaimedError) as exc:
        await claim_uc(conn, project_id="p", uc_id="UC-301", developer_id="alice")

    conflict = exc.value.to_conflict()
    assert conflict["code"] == "ALREADY_CLAIMED"
    assert conflict["owner"] == "bob"
    assert conflict["branch"] == "feature/uc-301-bob"
    assert conflict["claimed_at"] == "2026-05-21T20:00:00+00:00"


async def test_claim_uc_idempotent_for_same_owner():
    """Same dev re-claiming → returns existing claim, not ALREADY_CLAIMED."""

    conn = FakeConn(
        fetchrow=lambda sql, *a: _claim_row(dev="alice"),
        insert_raises=asyncpg.UniqueViolationError("dup"),
    )
    claim = await claim_uc(conn, project_id="p", uc_id="UC-301", developer_id="alice")
    assert claim.developer_id == "alice"


# ── release_uc [AC-17] ───────────────────────────────────────────────


async def test_release_uc_owner_succeeds():
    conn = FakeConn(fetchrow=lambda sql, *a: _claim_row(dev="alice"))
    released = await release_uc(conn, project_id="p", uc_id="UC-301", developer_id="alice")
    assert released is True
    assert any("DELETE FROM uc_claims" in sql for sql, _ in conn.executed)


async def test_release_uc_non_owner_rejected_and_claim_kept():
    conn = FakeConn(fetchrow=lambda sql, *a: _claim_row(dev="bob"))
    with pytest.raises(NotClaimOwnerError) as exc:
        await release_uc(conn, project_id="p", uc_id="UC-301", developer_id="alice")
    assert exc.value.owner == "bob"
    assert exc.value.requester == "alice"
    # Claim must NOT be deleted.
    assert not any("DELETE FROM uc_claims" in sql for sql, _ in conn.executed)


async def test_release_uc_no_claim_returns_false():
    conn = FakeConn(fetchrow=lambda sql, *a: None)
    released = await release_uc(conn, project_id="p", uc_id="UC-999", developer_id="alice")
    assert released is False


# ── branches [AC-23] ─────────────────────────────────────────────────


def test_suggest_branch_name_embeds_uc_id():
    assert suggest_branch_name("UC-301") == "feature/uc-301"
    assert suggest_branch_name("UC-301", "Tabla de claims") == "feature/uc-301-tabla-de-claims"


async def test_register_branch_success():
    conn = FakeConn(fetchrow=lambda sql, *a: None if "SELECT" in sql else {
        "project_id": "p", "branch": "feature/uc-301", "uc_id": "UC-301", "developer_id": "alice",
    })
    # First fetchrow (SELECT existing) returns None; INSERT ... RETURNING returns the row.
    calls = {"n": 0}

    def fetchrow(sql, *a):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # no existing branch
        return {"project_id": "p", "branch": "feature/uc-301", "uc_id": "UC-301", "developer_id": "alice"}

    conn = FakeConn(fetchrow=fetchrow)
    entry = await register_branch(
        conn, project_id="p", branch="feature/uc-301", uc_id="UC-301", developer_id="alice"
    )
    assert entry.branch == "feature/uc-301"
    assert entry.uc_id == "UC-301"


async def test_register_branch_collision_rejected():
    conn = FakeConn(
        fetchrow=lambda sql, *a: {
            "project_id": "p",
            "branch": "feature/x",
            "uc_id": "UC-999",
            "developer_id": "bob",
        }
    )
    with pytest.raises(BranchCollisionError) as exc:
        await register_branch(
            conn, project_id="p", branch="feature/x", uc_id="UC-301", developer_id="alice"
        )
    assert exc.value.existing_uc == "UC-999"
    assert exc.value.existing_dev == "bob"


# ── PG-gated: real concurrency race [AC-16] + atomic start [AC-18] ───

_DEV_DSN = "postgresql://specbox:specbox_dev_only@localhost:55432/specbox_native"
DSN = os.environ.get("SPECBOX_NATIVE_DSN", _DEV_DSN)


def _probe(dsn: str) -> None:
    async def _connect() -> None:
        conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=2.0)
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


try:
    _probe(DSN)
    _PG_REACHABLE = True
    _PG_SKIP_REASON = ""
except Exception as exc:  # noqa: BLE001
    _PG_REACHABLE = False
    _PG_SKIP_REASON = (
        f"dev Postgres not reachable ({exc!r}); "
        "run docker compose -f docker-compose.dev.yml up -d"
    )


@pytest.mark.skipif(not _PG_REACHABLE, reason=_PG_SKIP_REASON)
class TestClaimsRacePG:
    async def _seed(self, pg, pid, devs):
        from server.coordination.identity import add_project_member, register_developer

        async with pg.acquire() as conn:
            await conn.execute(
                "INSERT INTO projects (project_id, name) VALUES ($1, $2)", pid, "H3 race"
            )
            for d in devs:
                await register_developer(conn, developer_id=d, display_name=d, token=f"tok-{d}")
                await add_project_member(conn, project_id=pid, developer_id=d)

    async def test_concurrent_claims_exactly_one_winner(self):
        """AC-16: two parallel claim_uc on the same UC → one OK, one ALREADY_CLAIMED."""
        from server.db.migrate import apply_migrations
        from server.db.pool import close_pool, init_pool

        pid = f"test-h3-{uuid.uuid4().hex[:8]}"
        pg = await init_pool(dsn=DSN)
        try:
            await apply_migrations(pg)
            await self._seed(pg, pid, ["alice", "bob"])

            async def attempt(dev):
                async with pg.acquire() as conn:
                    try:
                        c = await claim_uc(conn, project_id=pid, uc_id="UC-301", developer_id=dev)
                        return ("ok", c.developer_id)
                    except AlreadyClaimedError as e:
                        return ("rejected", e.owner)

            results = await asyncio.gather(attempt("alice"), attempt("bob"))
            statuses = sorted(r[0] for r in results)
            assert statuses == ["ok", "rejected"], f"expected one ok + one rejected, got {results}"

            async with pg.acquire() as conn:
                await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                await conn.execute(
                    "DELETE FROM developers WHERE developer_id = ANY($1::text[])",
                    ["alice", "bob"],
                )
        finally:
            await close_pool()

    async def test_start_uc_atomic_no_orphan_on_missing_uc(self):
        """AC-18: if the UC row is missing, the claim rolls back (no orphan)."""
        from server.coordination.claims import start_uc_atomic
        from server.db.migrate import apply_migrations
        from server.db.pool import close_pool, init_pool

        pid = f"test-h3o-{uuid.uuid4().hex[:8]}"
        pg = await init_pool(dsn=DSN)
        try:
            await apply_migrations(pg)
            await self._seed(pg, pid, ["alice"])

            with pytest.raises(ValueError):
                await start_uc_atomic(
                    pg,
                    project_id=pid,
                    uc_db_id="UC-NONEXISTENT",
                    uc_id="UC-NONEXISTENT",
                    developer_id="alice",
                )

            # No orphan claim left behind.
            async with pg.acquire() as conn:
                count = await conn.fetchval(
                    "SELECT count(*) FROM uc_claims WHERE project_id = $1", pid
                )
                assert count == 0, "claim was orphaned despite the failed state update"
                await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                await conn.execute("DELETE FROM developers WHERE developer_id = $1", "alice")
        finally:
            await close_pool()
