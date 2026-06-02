"""Batch ingestion of large freeform sources into Native (US-NATIVE-BATCH-INGEST).

Covers the v6.9.2 transport gap fix: a multi-call migration session
(start → append × N → commit) that accumulates the items.json in small,
hash-verified chunks server-side and ingests them atomically.

Layout:
  * Unit tests (no DB) — integrity hashing, the SessionStore staging + chunk
    verification, and the session lifecycle (UC-680, UC-681). These run
    everywhere.
  * Postgres-gated tests — ``NativeBackend.ingest_atomic`` atomicity + state
    preservation, and the full E2E with a ≥100 KB source crossing the real
    chunked transport (UC-682, UC-684). They SKIP cleanly when no dev DB.

The E2E (UC-684) is the test that was missing and let the gap ship: prior
suites used small in-memory fixtures, never a real-sized items.json crossing
the chunked path.
"""

from __future__ import annotations

import json
import uuid

import pytest

from server.migration.batch_session import SessionStore
from server.migration.integrity import sha256_hex

# ── Postgres reachability (shared probe, TLS-aware) ──────────────────────
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()


# ═══════════════════════════════════════════════════════════════════════
# UNIT — integrity hashing (UC-681)
# ═══════════════════════════════════════════════════════════════════════


def test_sha256_hex_is_deterministic_and_utf8():
    assert sha256_hex("hello") == sha256_hex("hello")
    # Known vector for "hello".
    assert sha256_hex("hello") == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )
    # UTF-8 sensitivity (accented chars hash differently from ASCII).
    assert sha256_hex("café") != sha256_hex("cafe")


# ═══════════════════════════════════════════════════════════════════════
# UNIT — SessionStore: open / append / lifecycle (UC-680, UC-681)
# ═══════════════════════════════════════════════════════════════════════


def _store(now_ref: list[float] | None = None, ttl: int = 600) -> SessionStore:
    """A store with a deterministic clock + id generator for assertions."""
    counter = {"n": 0}

    def _id() -> str:
        counter["n"] += 1
        return f"sess-{counter['n']}"

    clock = now_ref if now_ref is not None else [1000.0]
    return SessionStore(ttl_seconds=ttl, time_fn=lambda: clock[0], id_fn=_id)


def test_open_creates_session_without_writing():
    store = _store()
    s = store.open(
        developer_id="dev-1",
        target_project_id="proj-1",
        source_type="freeform",
        declared_items=568,
        declared_bytes=133000,
        source_sha256="abc",
        chunk_count=6,
    )
    assert s.session_id == "sess-1"
    assert s.chunks_received == 0
    assert s.chunks_expected == 6
    assert store.get("sess-1") is s  # registered


def test_append_chunk_accepts_matching_hash():
    store = _store()
    store.open(
        developer_id="d", target_project_id="p", source_type="freeform",
        declared_items=1, declared_bytes=10, source_sha256="x", chunk_count=2,
    )
    data = '{"part": 1}'
    out = store.append_chunk(
        session_id="sess-1", chunk_index=0, chunk_data=data, chunk_sha256=sha256_hex(data)
    )
    assert out["status"] == "accepted"
    assert out["chunks_received"] == 1
    assert out["chunks_expected"] == 2


def test_append_chunk_rejects_hash_mismatch_without_accumulating():
    store = _store()
    store.open(
        developer_id="d", target_project_id="p", source_type="freeform",
        declared_items=1, declared_bytes=10, source_sha256="x", chunk_count=1,
    )
    out = store.append_chunk(
        session_id="sess-1", chunk_index=0, chunk_data="corrupt", chunk_sha256="not-the-hash"
    )
    assert out["status"] == "CHUNK_HASH_MISMATCH"
    assert out["chunk_index"] == 0
    # Not accumulated.
    assert store.get("sess-1").chunks_received == 0


def test_append_chunk_unknown_session_is_not_found():
    store = _store()
    out = store.append_chunk(
        session_id="ghost", chunk_index=0, chunk_data="x", chunk_sha256=sha256_hex("x")
    )
    assert out["status"] == "SESSION_NOT_FOUND"


def test_append_chunk_duplicate_index_does_not_overwrite():
    store = _store()
    store.open(
        developer_id="d", target_project_id="p", source_type="freeform",
        declared_items=1, declared_bytes=10, source_sha256="x", chunk_count=2,
    )
    first = "first"
    store.append_chunk(
        session_id="sess-1", chunk_index=0, chunk_data=first, chunk_sha256=sha256_hex(first)
    )
    second = "second"
    out = store.append_chunk(
        session_id="sess-1", chunk_index=0, chunk_data=second, chunk_sha256=sha256_hex(second)
    )
    assert out["status"] == "DUPLICATE_CHUNK_INDEX"
    assert store.get("sess-1").chunks[0] == first  # original preserved


def test_reassemble_orders_chunks_by_index():
    store = _store()
    store.open(
        developer_id="d", target_project_id="p", source_type="freeform",
        declared_items=1, declared_bytes=10, source_sha256="x", chunk_count=3,
    )
    parts = ["AAA", "BBB", "CCC"]
    # Send out of order to prove the store sorts on reassembly.
    for idx in (2, 0, 1):
        store.append_chunk(
            session_id="sess-1", chunk_index=idx, chunk_data=parts[idx],
            chunk_sha256=sha256_hex(parts[idx]),
        )
    assert store.get("sess-1").reassemble() == "AAABBBCCC"


def test_close_frees_session():
    store = _store()
    store.open(
        developer_id="d", target_project_id="p", source_type="freeform",
        declared_items=1, declared_bytes=10, source_sha256="x", chunk_count=1,
    )
    store.close("sess-1")
    assert store.get("sess-1") is None


def test_expired_session_reads_as_not_found():
    clock = [1000.0]
    store = _store(now_ref=clock, ttl=600)
    store.open(
        developer_id="d", target_project_id="p", source_type="freeform",
        declared_items=1, declared_bytes=10, source_sha256="x", chunk_count=1,
    )
    clock[0] = 1000.0 + 601  # advance past TTL
    assert store.get("sess-1") is None


# ═══════════════════════════════════════════════════════════════════════
# Helpers to build a real-sized freeform items.json
# ═══════════════════════════════════════════════════════════════════════


def _make_large_items_json(n_ucs: int = 120) -> str:
    """Build a freeform items.json with 1 US + n_ucs UCs (mixed states) + ACs.

    Returns a JSON string ≥100 KB so the E2E crosses the real chunked path.
    """
    items: list[dict] = []
    us_item_id = "item-us-batch"
    items.append({
        "id": us_item_id,
        "name": "[US-BATCH] Large batch source",
        "external_id": "US-BATCH", "external_source": None,
        "description": "A real-sized source for the batch ingestion E2E. " * 8,
        "labels": ["US"], "priority": "high", "state": "in_progress", "parent_id": None,
        "meta": {"tipo": "US", "us_id": "US-BATCH", "horas": "40", "screens": ""},
        "created_at": "2026-06-02T00:00:00+00:00", "updated_at": "2026-06-02T00:00:00+00:00",
    })
    for i in range(1, n_ucs + 1):
        uc_id = f"UC-{900 + i}"
        uc_item_id = f"item-uc-{i}"
        state = "done" if i % 4 != 0 else "backlog"  # mixed states
        items.append({
            "id": uc_item_id,
            "name": f"[{uc_id}] Use case number {i} with a descriptive title",
            "external_id": uc_id, "external_source": None,
            "description": f"Detailed description of use case {i}. " * 6,
            "labels": ["UC"], "priority": "high", "state": state, "parent_id": us_item_id,
            "meta": {"tipo": "UC", "uc_id": uc_id, "us_id": "US-BATCH", "actor": "Sistema", "horas": "2", "screens": ""},
            "created_at": "2026-06-02T00:00:00+00:00", "updated_at": "2026-06-02T00:00:00+00:00",
        })
        for a in range(1, 4):  # 3 ACs per UC
            ac_id = f"AC-{a:02d}"
            items.append({
                "id": f"ac-{i}-{a}",
                "name": f"[{ac_id}] Acceptance criterion {a} of use case {i}, specific and testable. " * 2,
                "external_id": None, "external_source": None,
                "description": "", "labels": ["AC"],
                "priority": "high", "state": "user_stories", "parent_id": uc_item_id,
                "meta": {"tipo": "AC", "ac_id": ac_id, "uc_id": uc_id},
                "created_at": "2026-06-02T00:00:00+00:00", "updated_at": "2026-06-02T00:00:00+00:00",
            })
    return json.dumps(items, ensure_ascii=False, indent=1)


def _chunk(text: str, size: int = 16 * 1024) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]


def test_large_fixture_exceeds_100kb_and_chunks_cleanly():
    """Sanity: the fixture is real-sized and round-trips through chunking."""
    blob = _make_large_items_json(120)
    assert len(blob.encode("utf-8")) >= 100 * 1024, "fixture must be ≥100 KB"
    chunks = _chunk(blob)
    assert len(chunks) >= 4
    assert "".join(chunks) == blob  # lossless


# ═══════════════════════════════════════════════════════════════════════
# Postgres-gated: ingest_atomic + E2E (UC-682, UC-684)
# ═══════════════════════════════════════════════════════════════════════

pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


async def _seed_identity(pool, project_id: str) -> tuple[str, str]:
    from server.coordination.identity import (
        add_project_member,
        register_developer,
        register_mcp_token,
    )

    developer_id = f"batch-dev-{uuid.uuid4().hex[:8]}"
    token = f"batch-tok-{uuid.uuid4().hex[:16]}"
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Batch Tester")
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
    return developer_id, token


async def _count_rows(pool, project_id: str) -> dict[str, int]:
    async with pool.acquire() as conn:
        us = await conn.fetchval("SELECT count(*) FROM user_stories WHERE project_id = $1", project_id)
        uc = await conn.fetchval("SELECT count(*) FROM use_cases WHERE project_id = $1", project_id)
        ac = await conn.fetchval("SELECT count(*) FROM acceptance_criteria WHERE project_id = $1", project_id)
    return {"us": us, "uc": uc, "ac": ac}


@pytestmark_pg
class TestSessionToolsAgainstPostgres:
    """UC-680 / UC-681 / UC-682 at the MCP tool layer (start/append/commit)."""

    async def _setup(self):
        from server.db.migrate import apply_migrations
        from server.db.pool import init_pool

        pool = await init_pool(dsn=DSN)
        await apply_migrations(pool)
        pid = f"test-batch-tool-{uuid.uuid4().hex[:8]}"
        dev_id, token = await _seed_identity(pool, pid)
        return pool, pid, dev_id, token

    async def _teardown(self, pool, pid, dev_id):
        from server.db.pool import close_pool

        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev_id)
        await close_pool()

    def _ctx(self):
        # A bare object: extract_locale_from_ctx falls back to "en" cleanly.
        # (Avoids AsyncMock returning coroutines for header lookups.)
        return object()

    async def test_start_session_opens_without_writing(self):
        """AC-01: start opens a session and writes nothing to the spec tables."""
        from server.coordination.identity import _clear_auth_cache
        from server.migration.batch_session import get_session_store
        from server.tools.migration import start_migration_session

        pool, pid, dev_id, token = await self._setup()
        try:
            _clear_auth_cache()
            before = await _count_rows(pool, pid)
            out = await start_migration_session(
                target_project_id=pid, source_type="freeform",
                declared_items=568, declared_bytes=133000, source_sha256="abc",
                chunk_count=6, ctx=self._ctx(), dev_token=token,
            )
            assert out["status"] == "open"
            assert out["declared_items"] == 568
            assert out["chunks_expected"] == 6
            assert out["chunks_received"] == 0
            assert "session_id" in out
            after = await _count_rows(pool, pid)
            assert after == before == {"us": 0, "uc": 0, "ac": 0}
            get_session_store().close(out["session_id"])
        finally:
            await self._teardown(pool, pid, dev_id)

    async def test_start_session_unauthenticated_fail_fast(self):
        """AC-02: missing/invalid dev_token → UNAUTHENTICATED, no session opened."""
        from server.tools.migration import start_migration_session

        pool, pid, dev_id, token = await self._setup()
        try:
            # Empty token.
            out = await start_migration_session(
                target_project_id=pid, source_type="freeform",
                declared_items=1, declared_bytes=10, source_sha256="x",
                chunk_count=1, ctx=self._ctx(), dev_token="",
            )
            assert out["code"] == "UNAUTHENTICATED"
            # Garbage token.
            out2 = await start_migration_session(
                target_project_id=pid, source_type="freeform",
                declared_items=1, declared_bytes=10, source_sha256="x",
                chunk_count=1, ctx=self._ctx(), dev_token="not-a-real-token",
            )
            assert out2["code"] == "UNAUTHENTICATED"
        finally:
            await self._teardown(pool, pid, dev_id)

    async def test_append_reuses_cached_identity_no_extra_query(self):
        """AC-03: start does 1 identity query; appends within TTL do 0."""
        import server.coordination.identity as identity_mod
        from server.coordination.identity import _clear_auth_cache
        from server.migration.batch_session import get_session_store
        from server.tools.migration import (
            append_migration_chunk,
            start_migration_session,
        )

        pool, pid, dev_id, token = await self._setup()
        try:
            _clear_auth_cache()
            # Count calls to the UNCACHED gate (a cache hit never calls it).
            calls = {"n": 0}
            real = identity_mod.authenticate_and_authorize

            async def counting(*args, **kwargs):
                calls["n"] += 1
                return await real(*args, **kwargs)

            identity_mod.authenticate_and_authorize = counting
            try:
                started = await start_migration_session(
                    target_project_id=pid, source_type="freeform",
                    declared_items=1, declared_bytes=10, source_sha256="x",
                    chunk_count=2, ctx=self._ctx(), dev_token=token,
                )
                assert calls["n"] == 1, "start must resolve identity exactly once"
                sid = started["session_id"]
                for idx in (0, 1):
                    data = f"chunk-{idx}"
                    await append_migration_chunk(
                        session_id=sid, chunk_index=idx, chunk_data=data,
                        chunk_sha256=sha256_hex(data), ctx=self._ctx(), dev_token=token,
                    )
                # Appends use the per-token owner key (hash_token) — they never
                # call the uncached gate again within the cache TTL.
                assert calls["n"] == 1, "appends must not re-query identity"
                get_session_store().close(sid)
            finally:
                identity_mod.authenticate_and_authorize = real
        finally:
            await self._teardown(pool, pid, dev_id)

    async def test_commit_preflight_count_mismatch_writes_nothing(self):
        """AC-09: wrong confirmed_count → PREFLIGHT_FAILED, zero INSERT."""
        from server.coordination.identity import _clear_auth_cache
        from server.migration.batch_session import get_session_store
        from server.tools.migration import (
            append_migration_chunk,
            commit_migration_session,
            start_migration_session,
        )

        pool, pid, dev_id, token = await self._setup()
        try:
            _clear_auth_cache()
            blob = _make_large_items_json(10)  # 1 US + 10 UC + 30 AC = 41 items
            chunks = _chunk(blob)
            started = await start_migration_session(
                target_project_id=pid, source_type="freeform",
                declared_items=41, declared_bytes=len(blob.encode()),
                source_sha256=sha256_hex(blob), chunk_count=len(chunks),
                ctx=self._ctx(), dev_token=token,
            )
            sid = started["session_id"]
            for idx, c in enumerate(chunks):
                await append_migration_chunk(
                    session_id=sid, chunk_index=idx, chunk_data=c,
                    chunk_sha256=sha256_hex(c), ctx=self._ctx(), dev_token=token,
                )
            # Confirm a WRONG count.
            out = await commit_migration_session(
                session_id=sid, ctx=self._ctx(), confirmed_count=999, dev_token=token,
            )
            assert out["status"] == "PREFLIGHT_FAILED"
            assert out["reason"] == "count_mismatch"
            assert await _count_rows(pool, pid) == {"us": 0, "uc": 0, "ac": 0}
            get_session_store().close(sid)
        finally:
            await self._teardown(pool, pid, dev_id)

    async def test_commit_happy_path_writes_and_frees_staging(self):
        """AC-08 + AC-11: correct commit writes == source and frees the session."""
        from server.coordination.identity import _clear_auth_cache
        from server.migration.batch_session import get_session_store
        from server.tools.migration import (
            append_migration_chunk,
            commit_migration_session,
            start_migration_session,
        )

        pool, pid, dev_id, token = await self._setup()
        try:
            _clear_auth_cache()
            blob = _make_large_items_json(10)
            chunks = _chunk(blob)
            started = await start_migration_session(
                target_project_id=pid, source_type="freeform",
                declared_items=41, declared_bytes=len(blob.encode()),
                source_sha256=sha256_hex(blob), chunk_count=len(chunks),
                ctx=self._ctx(), dev_token=token,
            )
            sid = started["session_id"]
            for idx, c in enumerate(chunks):
                await append_migration_chunk(
                    session_id=sid, chunk_index=idx, chunk_data=c,
                    chunk_sha256=sha256_hex(c), ctx=self._ctx(), dev_token=token,
                )
            out = await commit_migration_session(
                session_id=sid, ctx=self._ctx(), confirmed_count=41, dev_token=token,
            )
            assert out["status"] == "committed", out
            assert out["migrated"]["us"] == 1
            assert out["migrated"]["uc"] == 10
            assert out["migrated"]["ac"] == 30
            assert await _count_rows(pool, pid) == {"us": 1, "uc": 10, "ac": 30}
            # Staging freed (AC-11): a second commit reads as not-found.
            again = await commit_migration_session(
                session_id=sid, ctx=self._ctx(), confirmed_count=41, dev_token=token,
            )
            assert again["status"] == "SESSION_NOT_FOUND"
            assert get_session_store().get(sid) is None
        finally:
            await self._teardown(pool, pid, dev_id)


@pytestmark_pg
class TestSwitchBatchIntegration:
    """UC-683: the batch session is the write step of switch_project_backend.

    ``switch_project_backend._write`` calls ``_commit_batch_session`` when a
    ``batch_session_id`` is set and the target is native. The orchestrator's
    all-or-nothing contract (config changes only if write succeeds) is already
    covered by ``test_backend_switch_native.test_orchestrator_rolls_back_data_on_switch_failure``;
    here we prove the write step itself: success ingests, failure surfaces a
    non-``committed`` status that makes ``_write`` raise (so run_switch rolls back
    and touches no config — AC-13 / AC-14).
    """

    async def _setup(self):
        from server.db.migrate import apply_migrations
        from server.db.pool import init_pool

        pool = await init_pool(dsn=DSN)
        await apply_migrations(pool)
        pid = f"test-batch-sw-{uuid.uuid4().hex[:8]}"
        dev_id, token = await _seed_identity(pool, pid)
        return pool, pid, dev_id, token

    async def _teardown(self, pool, pid, dev_id):
        from server.db.pool import close_pool

        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev_id)
        await close_pool()

    async def test_write_step_commits_staged_session(self):
        """AC-13: a complete staged session ingests via the switch write step."""
        from server.migration.batch_session import get_session_store
        from server.tools.migration import _commit_batch_session

        pool, pid, dev_id, token = await self._setup()
        try:
            blob = _make_large_items_json(10)
            chunks = _chunk(blob)
            store = get_session_store()
            session = store.open(
                developer_id="x", target_project_id=pid, source_type="freeform",
                declared_items=41, declared_bytes=len(blob.encode()),
                source_sha256=sha256_hex(blob), chunk_count=len(chunks),
            )
            for idx, c in enumerate(chunks):
                store.append_chunk(
                    session_id=session.session_id, chunk_index=idx,
                    chunk_data=c, chunk_sha256=sha256_hex(c),
                )
            out = await _commit_batch_session(session.session_id, pid, token, "freeform")
            assert out["status"] == "committed"
            assert await _count_rows(pool, pid) == {"us": 1, "uc": 10, "ac": 30}
        finally:
            await self._teardown(pool, pid, dev_id)

    async def test_write_step_incomplete_session_fails_and_writes_nothing(self):
        """AC-14: an incomplete session → non-committed status, zero rows.

        ``switch_project_backend._write`` turns this into a SwitchOrchestrationError,
        so run_switch rolls back and never switches the config.
        """
        from server.migration.batch_session import get_session_store
        from server.tools.migration import _commit_batch_session

        pool, pid, dev_id, token = await self._setup()
        try:
            blob = _make_large_items_json(10)
            chunks = _chunk(blob)
            store = get_session_store()
            session = store.open(
                developer_id="x", target_project_id=pid, source_type="freeform",
                declared_items=41, declared_bytes=len(blob.encode()),
                source_sha256=sha256_hex(blob), chunk_count=len(chunks),
            )
            # Send all chunks but ONE — the session is incomplete.
            for idx, c in enumerate(chunks[:-1]):
                store.append_chunk(
                    session_id=session.session_id, chunk_index=idx,
                    chunk_data=c, chunk_sha256=sha256_hex(c),
                )
            out = await _commit_batch_session(session.session_id, pid, token, "freeform")
            assert out["status"] == "PREFLIGHT_FAILED"
            assert out["reason"] == "incomplete_chunks"
            assert await _count_rows(pool, pid) == {"us": 0, "uc": 0, "ac": 0}
            store.close(session.session_id)
        finally:
            await self._teardown(pool, pid, dev_id)


@pytestmark_pg
class TestIngestAtomicAgainstPostgres:
    async def _setup(self):
        from server.db.migrate import apply_migrations
        from server.db.pool import init_pool

        pool = await init_pool(dsn=DSN)
        await apply_migrations(pool)
        pid = f"test-batch-{uuid.uuid4().hex[:8]}"
        dev_id, token = await _seed_identity(pool, pid)
        return pool, pid, dev_id, token

    async def _teardown(self, pool, pid, dev_id):
        from server.db.pool import close_pool

        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev_id)
        await close_pool()

    async def test_e2e_large_source_roundtrip_preserves_states(self):
        """AC-16: ≥100 KB source, ≥4 chunks → Postgres == source, states 1:1."""
        from server.backends.freeform_backend import FreeformBackend
        from server.backends.native_backend import NativeBackend
        from server.migration.batch_session import SessionStore
        from server.tools.migration import _read_source

        pool, pid, dev_id, token = await self._setup()
        try:
            blob = _make_large_items_json(120)
            chunks = _chunk(blob)
            assert len(chunks) >= 4

            # Drive a real session through the store (start → append × N).
            store = SessionStore()
            session = store.open(
                developer_id="x", target_project_id=pid, source_type="freeform",
                declared_items=0, declared_bytes=len(blob.encode()),
                source_sha256=sha256_hex(blob), chunk_count=len(chunks),
            )
            for idx, c in enumerate(chunks):
                out = store.append_chunk(
                    session_id=session.session_id, chunk_index=idx,
                    chunk_data=c, chunk_sha256=sha256_hex(c),
                )
                assert out["status"] == "accepted"

            # Reassemble + ingest atomically via the backend directly.
            reassembled = session.reassemble()
            assert reassembled == blob
            src = FreeformBackend(items_content=reassembled)
            try:
                source = await _read_source(src, ".")
            finally:
                await src.close()

            backend = NativeBackend(project_id=pid, dev_token=token)
            result = await backend.ingest_atomic(pid, source, source_type="freeform")

            # Postgres == source counts.
            counts = await _count_rows(pool, pid)
            assert counts["us"] == 1
            assert counts["uc"] == 120
            assert counts["ac"] == 360
            assert result["migrated"]["uc"] == 120

            # States preserved 1:1 (AC-12 within the E2E).
            async with pool.acquire() as conn:
                done = await conn.fetchval(
                    "SELECT count(*) FROM use_cases WHERE project_id = $1 AND state = 'done'", pid
                )
                backlog = await conn.fetchval(
                    "SELECT count(*) FROM use_cases WHERE project_id = $1 AND state = 'backlog'", pid
                )
            expected_done = sum(1 for i in range(1, 121) if i % 4 != 0)
            expected_backlog = 120 - expected_done
            assert done == expected_done
            assert backlog == expected_backlog
        finally:
            await self._teardown(pool, pid, dev_id)

    async def test_e2e_atomicity_rollback_then_clean_retry(self):
        """AC-10/AC-17: mid-write failure → 0 rows; clean retry rebuilds all."""
        from server.backends.freeform_backend import FreeformBackend
        from server.backends.native_backend import NativeBackend
        from server.tools.migration import _read_source

        pool, pid, dev_id, token = await self._setup()
        try:
            blob = _make_large_items_json(40)
            src = FreeformBackend(items_content=blob)
            try:
                source = await _read_source(src, ".")
            finally:
                await src.close()

            backend = NativeBackend(project_id=pid, dev_token=token)

            # Inject a failure mid-write: NULL out one AC's text. acceptance_criteria.text
            # is NOT NULL, so the INSERT raises in phase 2 AFTER the US and earlier
            # UCs/ACs were already inserted in the SAME transaction — the exact
            # mid-write failure that must roll back everything (AC-10).
            import copy

            bad_source = copy.deepcopy(source)
            last_uc = bad_source["classified"]["uc"][-1]
            bad_acs = bad_source["ac_data"][last_uc.id]
            assert bad_acs, "fixture must give the last UC at least one AC"
            bad_acs[-1]["text"] = None  # violates NOT NULL mid-transaction

            with pytest.raises(Exception):
                await backend.ingest_atomic(pid, bad_source, source_type="freeform")

            # Rollback total: nothing written.
            counts = await _count_rows(pool, pid)
            assert counts == {"us": 0, "uc": 0, "ac": 0}, f"rollback incomplete: {counts}"

            # Clean retry rebuilds the full project.
            result = await backend.ingest_atomic(pid, source, source_type="freeform")
            counts = await _count_rows(pool, pid)
            assert counts["us"] == 1
            assert counts["uc"] == 40
            assert counts["ac"] == 120
            assert result["migrated"]["uc"] == 40
        finally:
            await self._teardown(pool, pid, dev_id)
