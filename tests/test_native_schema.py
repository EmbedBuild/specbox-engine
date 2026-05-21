"""Acceptance test for UC-102 — NativeBackend multi-tenant Postgres schema.

Evidences the UC-102 acceptance criteria against a real Postgres:

- AC-02: the project's asyncpg pool opens and round-trips a query.
- AC-03: ``version`` defaults to 1 on insert (column presence + default).
- AC-04: ``apply_migrations`` is idempotent — a second apply does not raise.
- AC-05: tenant isolation — querying by ``project_id`` never leaks another
  project's rows, across all three spec tables.

The test exercises the project's own pool (``init_pool`` / ``close_pool``) and
migration runner (``apply_migrations``) so it doubles as coverage for those.

It SKIPS cleanly (module level) when no dev Postgres is reachable, so CI
machines without a database stay green instead of hanging or hard-failing.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import asyncpg
import pytest

from server.db.migrate import apply_migrations
from server.db.pool import close_pool, init_pool

# ── Module-level skip guard ──────────────────────────────────────────────
# Frontier 2: the DSN is normally env-only. For tests we honour an explicit
# override and fall back to the documented dev DSN (docker-compose.dev.yml).
_DEV_DSN = "postgresql://specbox:specbox_dev_only@localhost:55432/specbox_native"
DSN = os.environ.get("SPECBOX_NATIVE_DSN", _DEV_DSN)


def _probe(dsn: str) -> None:
    """Confirm Postgres is reachable, in a throwaway event loop.

    Runs at import time. We build a dedicated loop and tear it down fully so
    we never leave a closed loop as the asyncio default — that would poison
    the pool created later under pytest-asyncio's own loop (Python 3.14).
    """

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
except Exception as exc:  # noqa: BLE001 — any failure means "no DB", just skip
    pytest.skip(
        f"dev Postgres not reachable ({exc!r}); run docker compose -f docker-compose.dev.yml up -d",
        allow_module_level=True,
    )


# ── Fixture: pool + migrations, with per-test row cleanup ────────────────
@pytest.fixture
async def pool():
    """Yield a migrated pool against the dev DB; clean up test rows after.

    - Opens the project pool via ``init_pool(dsn=...)`` [AC-02].
    - Applies migrations via the ``migrate.py`` runner [AC-04].
    - Tracks inserted ``project_id`` values and DELETEs them on teardown so
      the shared dev DB is left untouched (CASCADE removes child rows).
    - Never drops tables — other devs share this database.
    """
    pg = await init_pool(dsn=DSN)
    await apply_migrations(pg)

    # Tests append the project_ids they create to this list so teardown can
    # DELETE exactly those rows (asyncpg.Pool has __slots__, so we cannot
    # attach the registrar to the pool object itself).
    created_project_ids: list[str] = []

    try:
        yield pg, created_project_ids
    finally:
        if created_project_ids:
            async with pg.acquire() as conn:
                await conn.execute(
                    "DELETE FROM projects WHERE project_id = ANY($1::text[])",
                    created_project_ids,
                )
        await close_pool()


def _unique_pid(tag: str) -> str:
    """Unique, collision-proof test project id."""
    return f"test-uc102-{tag}-{uuid.uuid4().hex[:8]}"


async def _insert_project(conn: asyncpg.Connection, project_id: str) -> None:
    await conn.execute(
        "INSERT INTO projects (project_id, name) VALUES ($1, $2)",
        project_id,
        f"UC-102 test {project_id}",
    )


# ── Tests ────────────────────────────────────────────────────────────────
async def test_migration_idempotent(pool):
    """Applying migrations a second time must not raise. [AC-04]"""
    pg, _created = pool
    applied = await apply_migrations(pg)
    assert applied, "expected at least one migration file to be applied"
    # A second apply on the now-populated DB must be a clean no-op.
    again = await apply_migrations(pg)
    assert again == applied


async def test_pool_roundtrip(pool):
    """A connection from the project pool round-trips a query. [AC-02]"""
    pg, _created = pool
    async with pg.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
    assert result == 1


async def test_version_default(pool):
    """A user_story inserted without ``version`` defaults to 1. [AC-03]"""
    pg, created = pool
    pid = _unique_pid("ver")
    created.append(pid)
    async with pg.acquire() as conn:
        await _insert_project(conn, pid)
        await conn.execute(
            "INSERT INTO user_stories (id, project_id, name) VALUES ($1, $2, $3)",
            f"{pid}::US-01",
            pid,
            "Story without explicit version",
        )
        version = await conn.fetchval("SELECT version FROM user_stories WHERE id = $1", f"{pid}::US-01")
    assert version == 1


async def test_project_isolation(pool):
    """Querying by project_id returns only that tenant's rows. [AC-05]"""
    pg, created = pool
    pid_a = _unique_pid("isoA")
    pid_b = _unique_pid("isoB")
    created.extend([pid_a, pid_b])

    async with pg.acquire() as conn:
        # Seed two isolated projects, each with a US, UC and AC.
        for pid in (pid_a, pid_b):
            await _insert_project(conn, pid)
            us_id = f"{pid}::US-01"
            uc_id = f"{pid}::UC-101"
            ac_id = f"{pid}::UC-101::AC-01"
            await conn.execute(
                "INSERT INTO user_stories (id, project_id, name) VALUES ($1, $2, $3)",
                us_id,
                pid,
                f"US for {pid}",
            )
            await conn.execute(
                "INSERT INTO use_cases (id, project_id, us_id, name) VALUES ($1, $2, $3, $4)",
                uc_id,
                pid,
                us_id,
                f"UC for {pid}",
            )
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text) VALUES ($1, $2, $3, $4, $5)",
                ac_id,
                pid,
                uc_id,
                "AC-01",
                f"AC for {pid}",
            )

        # For each spec table, querying project A must return ONLY A's rows.
        for table in ("user_stories", "use_cases", "acceptance_criteria"):
            rows = await conn.fetch(
                f"SELECT project_id FROM {table} WHERE project_id = $1",  # noqa: S608 — table name is a fixed literal from a trusted tuple
                pid_a,
            )
            assert len(rows) == 1, f"{table}: expected exactly one row for A"
            assert all(r["project_id"] == pid_a for r in rows), f"{table}: project A query leaked another tenant's rows"
            # And B's id must never appear in A's result set.
            assert all(r["project_id"] != pid_b for r in rows), f"{table}: project B row leaked into project A query"
