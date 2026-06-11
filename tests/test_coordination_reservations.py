"""Unit + PG-gated tests for the NativeBackend reservations layer — H3.

Covers UC-301..304 acceptance criteria. The concept was renamed from "claim"
to "reservation" in v5.35.0 (US-CLAIM-RENAME); the file name is preserved
for now (UC-605 will rename to test_coordination_reservations.py) but the
identifiers below use the new vocabulary:

- AC-16: uc_reservations UNIQUE → exactly one of two concurrent reservations
  wins, the other gets ALREADY_RESERVED (verified for real in the PG-gated
  race test).
- AC-17: release_uc only by the owner; NOT_RESERVATION_OWNER otherwise
  (reservation kept).
- AC-18: start_uc_atomic reserves + sets in_progress in one tx — no orphan
  reservation if the state UPDATE fails.
- AC-19: the ALREADY_RESERVED conflict carries owner / reserved_at / branch.
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
from server.coordination.reservations import (
    AlreadyReservedError,
    NotReservationOwnerError,
    UCReservation,
    release_uc,
    reserve_uc,
)


# ── Fake conn ────────────────────────────────────────────────────────


class FakeConn:
    """Fake asyncpg connection.

    ``insert_conflict=True`` models the real ``INSERT ... ON CONFLICT DO
    NOTHING`` behaviour: the INSERT statement returns no row (None) on a
    primary-key conflict instead of raising, leaving the transaction intact so
    the follow-up SELECT (served by ``fetchrow``) succeeds. This mirrors the
    UC-1203 fix — the old code raised ``UniqueViolationError`` and poisoned the
    enclosing transaction.
    """

    def __init__(self, *, fetchrow=None, insert_conflict=False) -> None:
        self.executed: list[tuple[str, tuple]] = []
        self._fetchrow = fetchrow
        self._insert_conflict = insert_conflict

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        return "DELETE 1"

    async def fetchrow(self, sql, *args):
        if "INSERT INTO uc_reservations" in sql:
            # ON CONFLICT DO NOTHING RETURNING *: None on conflict, row on insert.
            if self._insert_conflict:
                return None
            return self._fetchrow(sql, *args) if self._fetchrow else None
        # Plain SELECT (get_reservation) after a conflict.
        return self._fetchrow(sql, *args) if self._fetchrow else None

    @asynccontextmanager
    async def transaction(self):
        yield


def _reservation_row(uc_id="UC-301", dev="alice", branch="feature/uc-301"):
    return {
        "project_id": "p",
        "uc_id": uc_id,
        "developer_id": dev,
        "branch": branch,
        "reserved_at": "2026-05-21T20:00:00+00:00",
    }


# ── reserve_uc [AC-16, AC-19] ────────────────────────────────────────


async def test_reserve_uc_success():
    conn = FakeConn(fetchrow=lambda sql, *a: _reservation_row(dev="alice"))
    claim = await reserve_uc(conn, project_id="p", uc_id="UC-301", developer_id="alice")
    assert isinstance(claim, UCReservation)
    assert claim.developer_id == "alice"
    assert claim.uc_id == "UC-301"


async def test_reserve_uc_already_reserved_carries_owner_info():
    """AC-19: ALREADY_RESERVED conflict includes owner / reserved_at / branch."""

    def fetchrow(sql, *args):
        # The SELECT after the unique violation returns the existing reservation.
        return _reservation_row(dev="bob", branch="feature/uc-301-bob")

    conn = FakeConn(
        fetchrow=fetchrow,
        insert_conflict=True,
    )
    with pytest.raises(AlreadyReservedError) as exc:
        await reserve_uc(conn, project_id="p", uc_id="UC-301", developer_id="alice")

    conflict = exc.value.to_payload()
    assert conflict["code"] == "ALREADY_RESERVED"
    assert conflict["owner"] == "bob"
    assert conflict["branch"] == "feature/uc-301-bob"
    assert conflict["reserved_at"] == "2026-05-21T20:00:00+00:00"


def test_already_reserved_payload_contains_no_legacy_claim_vocabulary():
    """UC-603 AC-02: the conflict payload exposes ZERO occurrences of the
    legacy 'claim' vocabulary — neither in keys nor in string values.

    The MCP tool wrapper in server/tools/coordination.py returns
    ``{"error": str(e), **e.to_payload()}`` on AlreadyReservedError. The
    error message is what the client sees first, so 'claim' must not appear
    there either. This is what makes the UC-603 rename observable to a
    consumer that does not read source code, only payloads.
    """
    err = AlreadyReservedError(
        uc_id="UC-301",
        owner="bob",
        reserved_at="2026-05-21T20:00:00+00:00",
        branch="feature/uc-301-bob",
    )
    payload = {"error": str(err), **err.to_payload()}

    # Keys
    forbidden = ("claim", "claimed_at", "Claim", "ALREADY_CLAIMED", "NOT_CLAIM_OWNER")
    for key in payload:
        for token in forbidden:
            assert token not in key, f"key {key!r} contains legacy token {token!r}"

    # Values (string-stringified — exception __str__ is the error message)
    for key, value in payload.items():
        text = value if isinstance(value, str) else str(value)
        for token in forbidden:
            assert token not in text, (
                f"value at {key!r} = {text!r} contains legacy token {token!r}"
            )


def test_not_reservation_owner_payload_contains_no_legacy_claim_vocabulary():
    """UC-603 AC-03 sibling: the release_uc error payload also exposes
    ZERO occurrences of the legacy 'claim' vocabulary.

    Mirrors the assertion above for ``NOT_RESERVATION_OWNER`` so the rename
    is enforced symmetrically on both H3 tools.
    """
    err = NotReservationOwnerError(uc_id="UC-301", owner="bob", requester="alice")
    # release_uc tool builds: {"error": str(e), "code": "NOT_RESERVATION_OWNER",
    #                          "uc_id": uc_id, "owner": e.owner}
    payload = {
        "error": str(err),
        "code": "NOT_RESERVATION_OWNER",
        "uc_id": "UC-301",
        "owner": err.owner,
    }

    forbidden = ("claim", "claimed_at", "Claim", "ALREADY_CLAIMED", "NOT_CLAIM_OWNER")
    for key, value in payload.items():
        for token in forbidden:
            assert token not in key, f"key {key!r} contains legacy token {token!r}"
            text = value if isinstance(value, str) else str(value)
            assert token not in text, (
                f"value at {key!r} = {text!r} contains legacy token {token!r}"
            )


async def test_reserve_uc_idempotent_for_same_owner():
    """Same dev re-reserving → returns existing reservation, not ALREADY_RESERVED."""

    conn = FakeConn(
        fetchrow=lambda sql, *a: _reservation_row(dev="alice"),
        insert_conflict=True,
    )
    claim = await reserve_uc(conn, project_id="p", uc_id="UC-301", developer_id="alice")
    assert claim.developer_id == "alice"
    # No audit row on the idempotent path: only the SELECT (get_reservation) ran,
    # the INSERT wrote nothing (ON CONFLICT DO NOTHING).
    assert not any("audit_log" in sql for sql, _ in conn.executed)


# ── release_uc [AC-17] ───────────────────────────────────────────────


async def test_release_uc_owner_succeeds():
    conn = FakeConn(fetchrow=lambda sql, *a: _reservation_row(dev="alice"))
    released = await release_uc(conn, project_id="p", uc_id="UC-301", developer_id="alice")
    assert released is True
    assert any("DELETE FROM uc_reservations" in sql for sql, _ in conn.executed)


async def test_release_uc_non_owner_rejected_and_reservation_kept():
    conn = FakeConn(fetchrow=lambda sql, *a: _reservation_row(dev="bob"))
    with pytest.raises(NotReservationOwnerError) as exc:
        await release_uc(conn, project_id="p", uc_id="UC-301", developer_id="alice")
    assert exc.value.owner == "bob"
    assert exc.value.requester == "alice"
    # Reservation must NOT be deleted.
    assert not any("DELETE FROM uc_reservations" in sql for sql, _ in conn.executed)


async def test_release_uc_no_reservation_returns_false():
    conn = FakeConn(fetchrow=lambda sql, *a: None)
    released = await release_uc(conn, project_id="p", uc_id="UC-999", developer_id="alice")
    assert released is False


# ── branches [AC-23] ─────────────────────────────────────────────────


def test_suggest_branch_name_embeds_uc_id():
    assert suggest_branch_name("UC-301") == "feature/uc-301"
    assert suggest_branch_name("UC-301", "Tabla de claims") == "feature/uc-301-tabla-de-claims"


async def test_register_branch_success():
    conn = FakeConn(
        fetchrow=lambda sql, *a: (
            None
            if "SELECT" in sql
            else {
                "project_id": "p",
                "branch": "feature/uc-301",
                "uc_id": "UC-301",
                "developer_id": "alice",
            }
        )
    )
    # First fetchrow (SELECT existing) returns None; INSERT ... RETURNING returns the row.
    calls = {"n": 0}

    def fetchrow(sql, *a):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # no existing branch
        return {"project_id": "p", "branch": "feature/uc-301", "uc_id": "UC-301", "developer_id": "alice"}

    conn = FakeConn(fetchrow=fetchrow)
    entry = await register_branch(conn, project_id="p", branch="feature/uc-301", uc_id="UC-301", developer_id="alice")
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
        await register_branch(conn, project_id="p", branch="feature/x", uc_id="UC-301", developer_id="alice")
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
    _PG_SKIP_REASON = f"dev Postgres not reachable ({exc!r}); run docker compose -f docker-compose.dev.yml up -d"


@pytest.mark.skipif(not _PG_REACHABLE, reason=_PG_SKIP_REASON)
class TestReservationsRacePG:
    async def _seed(self, pg, pid, devs):
        from server.coordination.identity import (
            add_project_member,
            register_developer,
            register_mcp_token,
        )

        async with pg.acquire() as conn:
            await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, $2)", pid, "H3 race")
            for d in devs:
                # UC-504: register_developer is identity-only; tokens live in mcp_tokens.
                await register_developer(conn, developer_id=d, display_name=d)
                await register_mcp_token(conn, developer_id=d, token=f"tok-{d}")
                await add_project_member(conn, project_id=pid, developer_id=d)

    async def test_concurrent_reservations_exactly_one_winner(self):
        """AC-16: two parallel reserve_uc on the same UC → one OK, one ALREADY_RESERVED."""
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
                        c = await reserve_uc(conn, project_id=pid, uc_id="UC-301", developer_id=dev)
                        return ("ok", c.developer_id)
                    except AlreadyReservedError as e:
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
        """AC-18: if the UC row is missing, the reservation rolls back (no orphan)."""
        from server.coordination.reservations import start_uc_atomic
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

            # No orphan reservation left behind.
            async with pg.acquire() as conn:
                count = await conn.fetchval("SELECT count(*) FROM uc_reservations WHERE project_id = $1", pid)
                assert count == 0, "reservation was orphaned despite the failed state update"
                await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                await conn.execute("DELETE FROM developers WHERE developer_id = $1", "alice")
        finally:
            await close_pool()

    async def test_start_uc_atomic_after_reserve_same_dev_does_not_abort_tx(self):
        """UC-1203 regression: reserve_uc then start_uc_atomic for the SAME dev
        on the SAME UC must NOT abort the transaction.

        This reproduces the real bug seen in dogfooding: ``reserve_uc`` followed
        by ``start_uc`` raised "current transaction is aborted, commands ignored
        until end of transaction block". Root cause: start_uc_atomic re-reserves
        inside one tx; the old reserve_uc let the duplicate INSERT raise
        UniqueViolationError, poisoning the enclosing transaction so the SELECT
        recovery (and the later state UPDATE) failed. With ON CONFLICT DO NOTHING
        the INSERT never raises, the tx stays alive, and the re-reserve is
        idempotent. The UC must end up in_progress with exactly one reservation.
        """
        from server.coordination.reservations import start_uc_atomic
        from server.db.migrate import apply_migrations
        from server.db.pool import close_pool, init_pool

        pid = f"test-h3r-{uuid.uuid4().hex[:8]}"
        pg = await init_pool(dsn=DSN)
        try:
            await apply_migrations(pg)
            await self._seed(pg, pid, ["alice"])
            # A real UC row to flip to in_progress.
            async with pg.acquire() as conn:
                await conn.execute(
                    "INSERT INTO use_cases (project_id, id, name, state) VALUES ($1, $2, $3, 'backlog')",
                    pid,
                    "UC-301",
                    "Regression UC",
                )

            # Pre-reserve as alice (the standalone reserve_uc path, own tx).
            async with pg.acquire() as conn:
                await reserve_uc(conn, project_id=pid, uc_id="UC-301", developer_id="alice")

            # Now start_uc_atomic for the SAME dev — the path that used to abort.
            reservation = await start_uc_atomic(
                pg,
                project_id=pid,
                uc_db_id="UC-301",
                uc_id="UC-301",
                developer_id="alice",
            )
            assert reservation.developer_id == "alice"

            async with pg.acquire() as conn:
                state = await conn.fetchval(
                    "SELECT state FROM use_cases WHERE project_id = $1 AND id = $2",
                    pid,
                    "UC-301",
                )
                assert state == "in_progress", f"expected in_progress, got {state!r}"
                count = await conn.fetchval(
                    "SELECT count(*) FROM uc_reservations WHERE project_id = $1 AND uc_id = $2",
                    pid,
                    "UC-301",
                )
                assert count == 1, f"expected exactly one reservation, got {count}"
                await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                await conn.execute("DELETE FROM developers WHERE developer_id = $1", "alice")
        finally:
            await close_pool()


# ── UC-604 deprecated alias — minimum AC-02 surface in this file ─────
#
# AC-02 of UC-605 mandates that
# ``test_coordination_reservations.py::test_deprecated_claim_uc_alias_emits_warning``
# exists and asserts both (a) the DeprecationWarning emission and (b) the
# dual payload (reserved_at + claimed_at). The exhaustive surface lives in
# tests/test_deprecated_claim_uc_alias.py (10 tests); this single test is
# the contract point in the renamed coordination test file so AC-02 is
# verifiable mechanically without grepping into a sibling module.


async def test_deprecated_claim_uc_alias_emits_warning(monkeypatch):
    """UC-605 AC-02: calling the deprecated ``claim_uc`` MCP tool emits a
    DeprecationWarning AND returns a payload that carries both vocabularies
    (``reserved_at`` and ``claimed_at`` with identical values, ``code`` and
    ``legacy_code``).

    Stubs out ``reserve_uc`` so this test is pure-logic and does not need
    the FastMCP context, DB pool, or asyncpg session machinery.
    """
    import server.tools.coordination as coord

    async def _fake_reserve_uc(uc_id, ctx, branch=""):
        return {
            "success": True,
            "code": "RESERVED",
            "uc_id": uc_id,
            "developer_id": "alice",
            "reserved_at": "2026-05-25T10:00:00+00:00",
            "branch": branch or "",
            "summary": f"UC {uc_id} reservado por alice.",
        }

    monkeypatch.setattr(coord, "reserve_uc", _fake_reserve_uc)

    with pytest.warns(DeprecationWarning) as captured:
        payload = await coord.claim_uc("UC-301", ctx=object())

    # DeprecationWarning emission + migration hint in the message.
    assert len(captured) == 1, f"expected 1 DeprecationWarning, got {len(captured)}"
    msg = str(captured[0].message)
    assert "claim_uc" in msg
    assert "reserve_uc" in msg
    assert "v5.35.0" in msg
    assert "v5.37.0" in msg

    # Dual payload: BOTH vocabularies present, same timestamp.
    assert payload["code"] == "RESERVED"
    assert payload["legacy_code"] == "CLAIMED"
    assert payload["reserved_at"] == "2026-05-25T10:00:00+00:00"
    assert payload["claimed_at"] == payload["reserved_at"]
