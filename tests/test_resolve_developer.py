"""PG-gated tests for ``resolve_developer`` against the mcp_tokens table — AC-17.

UC-504 moved token storage from ``developers.token_hash`` (dropped in
migration 0005) to ``mcp_tokens``. ``resolve_developer`` is now a JOIN that
filters ``revoked_at IS NULL``. These tests pin that contract end-to-end:

- Test 1: an active token resolves to the right Developer.
- Test 2: a revoked token raises UNAUTHENTICATED (no enumeration).
- Test 3: an unknown token raises UNAUTHENTICATED.
- Test 4: an empty/whitespace token raises UNAUTHENTICATED (historical, short-circuits).

Module-level skip mirrors :mod:`tests._native_db`: the whole file skips
cleanly when the dev Postgres is not reachable.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest

from server.coordination.identity import (
    UnauthenticatedError,
    add_project_member,
    register_developer,
    register_mcp_token,
    resolve_developer,
    revoke_mcp_token,
)
from server.db.migrate import apply_migrations
from server.db.pool import close_pool, init_pool
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()

pytestmark = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


@pytest.fixture
async def native_pool() -> AsyncIterator[asyncpg.Pool]:
    """A migrated shared pool; closes on teardown."""
    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    try:
        yield pool
    finally:
        await close_pool()


def _unique_pid(tag: str) -> str:
    return f"test-uc504-{tag}-{uuid.uuid4().hex[:8]}"


def _unique_dev(tag: str) -> str:
    return f"dev-{tag}-{uuid.uuid4().hex[:6]}"


# ── AC-17 ─────────────────────────────────────────────────────────────


async def test_resolve_developer_returns_active_token_owner(native_pool):
    """An active token resolves to the right Developer via the mcp_tokens JOIN."""
    pid = _unique_pid("ok")
    dev_id = _unique_dev("ok")
    token = f"tok-active-{uuid.uuid4().hex}"
    async with native_pool.acquire() as conn:
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, $2)", pid, "uc-504 ok")
        try:
            await register_developer(conn, developer_id=dev_id, display_name="Resolver Test")
            await register_mcp_token(conn, developer_id=dev_id, token=token)
            await add_project_member(conn, project_id=pid, developer_id=dev_id)

            dev = await resolve_developer(conn, token)
            assert dev.developer_id == dev_id
            assert dev.display_name == "Resolver Test"
        finally:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev_id)


async def test_resolve_developer_rejects_revoked_token(native_pool):
    """Once revoked_at IS NOT NULL, resolve_developer must raise UNAUTHENTICATED."""
    pid = _unique_pid("rev")
    dev_id = _unique_dev("rev")
    token = f"tok-revoked-{uuid.uuid4().hex}"
    async with native_pool.acquire() as conn:
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, $2)", pid, "uc-504 rev")
        try:
            await register_developer(conn, developer_id=dev_id, display_name="Revoke Me")
            token_id = await register_mcp_token(conn, developer_id=dev_id, token=token)

            # Active first.
            dev = await resolve_developer(conn, token)
            assert dev.developer_id == dev_id

            # Revoke and verify the token is now refused.
            assert await revoke_mcp_token(conn, token_id=token_id) is True
            with pytest.raises(UnauthenticatedError):
                await resolve_developer(conn, token)

            # Idempotent revoke: second call returns False, behaviour unchanged.
            assert await revoke_mcp_token(conn, token_id=token_id) is False
        finally:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev_id)


async def test_resolve_developer_rejects_unknown_token(native_pool):
    """A token whose hash matches no mcp_tokens row → UNAUTHENTICATED."""
    async with native_pool.acquire() as conn:
        with pytest.raises(UnauthenticatedError):
            await resolve_developer(conn, f"never-registered-{uuid.uuid4().hex}")


async def test_resolve_developer_rejects_empty_token(native_pool):
    """Empty / whitespace token short-circuits before any DB query [AC-12]."""
    async with native_pool.acquire() as conn:
        with pytest.raises(UnauthenticatedError):
            await resolve_developer(conn, "")
        with pytest.raises(UnauthenticatedError):
            await resolve_developer(conn, "   ")
        with pytest.raises(UnauthenticatedError):
            await resolve_developer(conn, None)
