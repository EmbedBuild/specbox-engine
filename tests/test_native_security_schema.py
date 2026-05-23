"""Structural + idempotency tests for the UC-501 native security schema.

Covers the five acceptance criteria of UC-501 against a live Postgres reached
via ``SPECBOX_NATIVE_DSN`` (dev docker-compose by default; Supabase Pooler in
CI). The whole module skips cleanly if the DB is unreachable, mirroring the
pattern used by ``test_native_backend_conformance.py``.

What is checked:

* AC-01 — ``github_identities`` exists with the exact column types and the
  ``idx_github_identities_developer_id`` index.
* AC-02 — ``mcp_tokens`` exists with the exact column types, the two named
  indexes (``idx_mcp_tokens_token_hash`` UNIQUE, ``idx_mcp_tokens_developer_id``)
  and the two FKs (developer_id → developers ON DELETE CASCADE; github_user_id
  → github_identities ON DELETE SET NULL).
* AC-03 — ``developers.token_hash`` column AND ``idx_developers_token_hash``
  index are gone after the 0005 migration runs.
* AC-04 — ``audit_log`` exists with the exact column types and the
  ``idx_audit_log_project_occurred`` index; ``developer_id`` is NULLable and
  has no FK to ``developers``.
* AC-05 — ``apply_migrations`` is idempotent: a second call against the same
  DB does not raise and produces the same set of tables/indexes.

The tests run against the shared ``public`` schema (the migrations are
idempotent by contract, so co-existing state is fine). They never mutate
data — only DDL inspection via ``information_schema`` / ``pg_catalog``.
"""

from __future__ import annotations

import asyncpg
import pytest

from server.db.migrate import apply_migrations
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()

pytestmark = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


# ── Helpers ──────────────────────────────────────────────────────────────


async def _connect() -> asyncpg.Connection:
    """Open a single connection against the configured DSN, TLS-aware."""
    from server.db.pool import _resolve_ssl

    ssl = _resolve_ssl(DSN)
    return await asyncpg.connect(DSN, ssl=ssl)


async def _columns(conn: asyncpg.Connection, table: str) -> dict[str, dict]:
    """Return ``{column_name: {data_type, is_nullable}}`` for a table."""
    rows = await conn.fetch(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        """,
        table,
    )
    return {r["column_name"]: {"data_type": r["data_type"], "is_nullable": r["is_nullable"]} for r in rows}


async def _indexes(conn: asyncpg.Connection, table: str) -> dict[str, str]:
    """Return ``{index_name: indexdef}`` for a table (public schema)."""
    rows = await conn.fetch(
        """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public' AND tablename = $1
        """,
        table,
    )
    return {r["indexname"]: r["indexdef"] for r in rows}


async def _table_exists(conn: asyncpg.Connection, table: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = $1
            """,
            table,
        )
    )


async def _fks(conn: asyncpg.Connection, table: str) -> list[dict]:
    """Return FK rows for a table: column, foreign_table, foreign_column, delete_rule."""
    rows = await conn.fetch(
        """
        SELECT
            kcu.column_name        AS column_name,
            ccu.table_name         AS foreign_table,
            ccu.column_name        AS foreign_column,
            rc.delete_rule         AS delete_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema    = kcu.table_schema
        JOIN information_schema.referential_constraints rc
          ON tc.constraint_name = rc.constraint_name
         AND tc.table_schema    = rc.constraint_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema    = tc.table_schema
        WHERE tc.table_schema = 'public'
          AND tc.table_name   = $1
          AND tc.constraint_type = 'FOREIGN KEY'
        """,
        table,
    )
    return [dict(r) for r in rows]


async def _snapshot(conn: asyncpg.Connection) -> tuple[set[str], set[str]]:
    """Snapshot of (table names, index names) in public schema."""
    tables = {
        r["table_name"]
        for r in await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    }
    indexes = {r["indexname"] for r in await conn.fetch("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")}
    return tables, indexes


# ── Module-scoped fixture: apply migrations once ─────────────────────────


@pytest.fixture(scope="module", autouse=True)
async def _apply_migrations_once():
    """Apply all migrations once for the module. Safe to re-run."""
    conn = await _connect()
    try:
        await apply_migrations(conn)
    finally:
        await conn.close()


# ── AC-01: github_identities structure ───────────────────────────────────


async def test_ac01_github_identities_structure():
    """github_identities exists with the AC-01 shape + dev index."""
    conn = await _connect()
    try:
        assert await _table_exists(conn, "github_identities")

        cols = await _columns(conn, "github_identities")
        # Required columns + types
        assert cols["github_user_id"]["data_type"] == "bigint"
        assert cols["github_user_id"]["is_nullable"] == "NO"
        assert cols["github_login"]["data_type"] == "text"
        assert cols["github_login"]["is_nullable"] == "NO"
        assert cols["developer_id"]["data_type"] == "text"
        assert cols["developer_id"]["is_nullable"] == "NO"
        assert cols["linked_at"]["data_type"] == "timestamp with time zone"
        assert cols["linked_at"]["is_nullable"] == "NO"

        # PK on github_user_id
        pk_col = await conn.fetchval(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_schema = 'public'
              AND tc.table_name   = 'github_identities'
              AND tc.constraint_type = 'PRIMARY KEY'
            """,
        )
        assert pk_col == "github_user_id"

        # Reverse-lookup index on developer_id
        idx = await _indexes(conn, "github_identities")
        assert "idx_github_identities_developer_id" in idx
        assert "developer_id" in idx["idx_github_identities_developer_id"]

        # FK developer_id → developers ON DELETE CASCADE
        fks = await _fks(conn, "github_identities")
        dev_fk = next((f for f in fks if f["column_name"] == "developer_id"), None)
        assert dev_fk is not None
        assert dev_fk["foreign_table"] == "developers"
        assert dev_fk["foreign_column"] == "developer_id"
        assert dev_fk["delete_rule"] == "CASCADE"
    finally:
        await conn.close()


# ── AC-02: mcp_tokens structure ──────────────────────────────────────────


async def test_ac02_mcp_tokens_structure():
    """mcp_tokens exists with full column set, both indexes and both FKs."""
    conn = await _connect()
    try:
        assert await _table_exists(conn, "mcp_tokens")

        cols = await _columns(conn, "mcp_tokens")
        assert cols["token_id"]["data_type"] == "text"
        assert cols["token_id"]["is_nullable"] == "NO"
        assert cols["developer_id"]["data_type"] == "text"
        assert cols["developer_id"]["is_nullable"] == "NO"
        assert cols["github_user_id"]["data_type"] == "bigint"
        assert cols["github_user_id"]["is_nullable"] == "YES"
        assert cols["token_hash"]["data_type"] == "text"
        assert cols["token_hash"]["is_nullable"] == "NO"
        assert cols["created_at"]["data_type"] == "timestamp with time zone"
        assert cols["created_at"]["is_nullable"] == "NO"
        assert cols["last_used_at"]["data_type"] == "timestamp with time zone"
        assert cols["last_used_at"]["is_nullable"] == "YES"
        assert cols["revoked_at"]["data_type"] == "timestamp with time zone"
        assert cols["revoked_at"]["is_nullable"] == "YES"

        # Both named indexes present, token_hash one is UNIQUE.
        idx = await _indexes(conn, "mcp_tokens")
        assert "idx_mcp_tokens_token_hash" in idx
        assert "UNIQUE" in idx["idx_mcp_tokens_token_hash"].upper()
        assert "token_hash" in idx["idx_mcp_tokens_token_hash"]
        assert "idx_mcp_tokens_developer_id" in idx
        assert "developer_id" in idx["idx_mcp_tokens_developer_id"]

        # Two FKs: developer_id CASCADE, github_user_id SET NULL.
        fks = await _fks(conn, "mcp_tokens")
        by_col = {f["column_name"]: f for f in fks}
        assert "developer_id" in by_col
        assert by_col["developer_id"]["foreign_table"] == "developers"
        assert by_col["developer_id"]["foreign_column"] == "developer_id"
        assert by_col["developer_id"]["delete_rule"] == "CASCADE"
        assert "github_user_id" in by_col
        assert by_col["github_user_id"]["foreign_table"] == "github_identities"
        assert by_col["github_user_id"]["foreign_column"] == "github_user_id"
        assert by_col["github_user_id"]["delete_rule"] == "SET NULL"
    finally:
        await conn.close()


# ── AC-03: developers.token_hash and its index are gone ──────────────────


async def test_ac03_developers_token_hash_dropped():
    """developers.token_hash column AND idx_developers_token_hash index removed."""
    conn = await _connect()
    try:
        cols = await _columns(conn, "developers")
        assert "token_hash" not in cols, (
            f"developers.token_hash must be dropped by 0005 (AC-03); found columns: {sorted(cols)}"
        )

        idx = await _indexes(conn, "developers")
        assert "idx_developers_token_hash" not in idx, (
            f"idx_developers_token_hash must be dropped by 0005 (AC-03); found indexes: {sorted(idx)}"
        )
    finally:
        await conn.close()


# ── AC-04: audit_log structure ───────────────────────────────────────────


async def test_ac04_audit_log_structure():
    """audit_log exists with the AC-04 shape, no FK on developer_id."""
    conn = await _connect()
    try:
        assert await _table_exists(conn, "audit_log")

        cols = await _columns(conn, "audit_log")
        # id is BIGSERIAL → bigint, NOT NULL
        assert cols["id"]["data_type"] == "bigint"
        assert cols["id"]["is_nullable"] == "NO"
        # developer_id is NULLable, no FK (see below)
        assert cols["developer_id"]["data_type"] == "text"
        assert cols["developer_id"]["is_nullable"] == "YES"
        # project_id, operation, target_id are NOT NULL
        assert cols["project_id"]["data_type"] == "text"
        assert cols["project_id"]["is_nullable"] == "NO"
        assert cols["operation"]["data_type"] == "text"
        assert cols["operation"]["is_nullable"] == "NO"
        assert cols["target_id"]["data_type"] == "text"
        assert cols["target_id"]["is_nullable"] == "NO"
        assert cols["occurred_at"]["data_type"] == "timestamp with time zone"
        assert cols["occurred_at"]["is_nullable"] == "NO"

        # Index for the tail-read pattern
        idx = await _indexes(conn, "audit_log")
        assert "idx_audit_log_project_occurred" in idx
        idxdef = idx["idx_audit_log_project_occurred"]
        assert "project_id" in idxdef
        assert "occurred_at" in idxdef

        # Explicit decision: audit_log has NO FKs (developer can be deleted,
        # the trail must survive). Verify there are zero FKs on the table.
        fks = await _fks(conn, "audit_log")
        assert fks == [], (
            f"audit_log must have no FKs (developer hard-delete must not cascade into the audit trail); found: {fks}"
        )
    finally:
        await conn.close()


# ── AC-05: idempotency — re-applying migrations is a no-op ───────────────


async def test_ac05_apply_migrations_idempotent():
    """Re-running apply_migrations does not raise and leaves the DB intact."""
    conn = await _connect()
    try:
        before_tables, before_indexes = await _snapshot(conn)

        # Second application — must not raise.
        await apply_migrations(conn)

        after_tables, after_indexes = await _snapshot(conn)
        assert before_tables == after_tables, (
            f"tables drifted on re-apply: added={after_tables - before_tables} removed={before_tables - after_tables}"
        )
        assert before_indexes == after_indexes, (
            f"indexes drifted on re-apply: "
            f"added={after_indexes - before_indexes} removed={before_indexes - after_indexes}"
        )

        # Third application — paranoid second pass.
        await apply_migrations(conn)
        after2_tables, after2_indexes = await _snapshot(conn)
        assert after2_tables == before_tables
        assert after2_indexes == before_indexes
    finally:
        await conn.close()
