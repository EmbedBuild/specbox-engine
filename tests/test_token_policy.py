"""UC-3902 AC-03 / AC-04 (US-39) — token policy: idle revocation and the device limit (migration 0027).

PG-gated like the other native modules. What it pins:

* ``public.revoke_idle_mcp_tokens`` revokes (``revoked_reason = 'idle'``) only the
  active, unexpired tokens whose last real use is older than the window, writes
  one ``audit_log`` row per token and returns what it revoked;
* the idle clock never starts before ``p_floor`` (the day the engine began
  recording MCP use), so nobody is cut off on data the engine never had;
* an idle-revoked token no longer authenticates;
* ``public.issue_device_token`` refuses the sixth device (``DEVICE_LIMIT``,
  SQLSTATE 53400) and leaves the board as it was, while a known device signs in,
  renews or replaces freely, and legacy or expired tokens take no slot;
* only service_role may run the idle revocation once Supabase's default grants
  are in place.
"""

from __future__ import annotations

import json
import uuid

import asyncpg
import pytest

from server.coordination.identity import (
    UnauthenticatedError,
    register_developer,
    register_mcp_token,
    resolve_developer,
)
from server.db.migrate import apply_migrations
from server.db.pool import close_pool, get_pool, init_pool
from tests._native_db import DSN, reachable
from tests.test_device_tokens import _device, _issue

_PG_OK, _PG_SKIP_REASON = reachable()
pytestmark = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)

IDLE_SIGNATURE = "public.revoke_idle_mcp_tokens(integer, timestamptz)"


@pytest.fixture
async def pool():
    await init_pool(dsn=DSN)
    pool = await get_pool()
    try:
        await apply_migrations(pool)
        yield pool
    finally:
        await close_pool()


@pytest.fixture
async def developer(pool):
    dev_id = f"dev-uc3902-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=dev_id, display_name="Policy Test")
    try:
        yield dev_id
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM audit_log WHERE developer_id = $1", dev_id)
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev_id)


async def _active_devices(conn: asyncpg.Connection, developer_id: str) -> int:
    return await conn.fetchval(
        """
        SELECT count(*) FROM mcp_tokens
         WHERE developer_id = $1 AND device_id IS NOT NULL AND revoked_at IS NULL
           AND (expires_at IS NULL OR expires_at > now())
        """,
        developer_id,
    )


async def _touch(conn: asyncpg.Connection, token_id: str, *, used_days_ago: int | None, created_days_ago: int) -> None:
    await conn.execute(
        """
        UPDATE mcp_tokens
           SET created_at = now() - make_interval(days => $2),
               last_used_at = CASE WHEN $3::int IS NULL THEN NULL ELSE now() - make_interval(days => $3) END
         WHERE token_id = $1
        """,
        token_id,
        created_days_ago,
        used_days_ago,
    )


async def _revoke_idle(conn: asyncpg.Connection, days: int = 60, floor: str | None = "2000-01-01") -> list[str]:
    rows = await conn.fetch(
        "SELECT revoked_token_id FROM public.revoke_idle_mcp_tokens($1, $2::text::timestamptz)", days, floor
    )
    return [r["revoked_token_id"] for r in rows]


# ── AC-03 — idle tokens are revoked, and the panel can tell why ─────────


async def test_idle_tokens_are_revoked_with_the_reason_and_an_audit_row(pool, developer):
    async with pool.acquire() as conn:
        ids: dict[str, str] = {}
        for tag in ("idle", "recent", "never", "expired", "revoked_by_user"):
            _, row = await _issue(conn, developer, _device(tag))
            ids[tag] = row["issued_token_id"]

        await _touch(conn, ids["idle"], used_days_ago=61, created_days_ago=100)
        await _touch(conn, ids["recent"], used_days_ago=59, created_days_ago=100)
        await _touch(conn, ids["never"], used_days_ago=None, created_days_ago=61)
        await _touch(conn, ids["expired"], used_days_ago=61, created_days_ago=100)
        await conn.execute(
            "UPDATE mcp_tokens SET expires_at = now() - interval '1 day' WHERE token_id = $1", ids["expired"]
        )
        await _touch(conn, ids["revoked_by_user"], used_days_ago=61, created_days_ago=100)
        await conn.execute(
            "UPDATE mcp_tokens SET revoked_at = now() - interval '1 day', revoked_reason = 'user' WHERE token_id = $1",
            ids["revoked_by_user"],
        )

        revoked = await _revoke_idle(conn)
        rows = {
            r["token_id"]: r
            for r in await conn.fetch(
                "SELECT token_id, revoked_at, revoked_reason FROM mcp_tokens WHERE developer_id = $1", developer
            )
        }
        audit = await conn.fetch(
            "SELECT target_id, metadata FROM audit_log WHERE developer_id = $1 AND operation = 'revoke_mcp_token'",
            developer,
        )

    assert revoked == sorted([ids["idle"], ids["never"]])
    assert rows[ids["idle"]]["revoked_reason"] == "idle" and rows[ids["idle"]]["revoked_at"] is not None
    assert rows[ids["never"]]["revoked_reason"] == "idle"
    assert rows[ids["recent"]]["revoked_at"] is None
    assert rows[ids["expired"]]["revoked_at"] is None  # already dead: stays "expired", not "revoked"
    assert rows[ids["revoked_by_user"]]["revoked_reason"] == "user"  # nothing rewrites history
    assert {a["target_id"] for a in audit} == {ids["idle"], ids["never"]}
    metadata = [json.loads(a["metadata"]) if isinstance(a["metadata"], str) else a["metadata"] for a in audit]
    assert all(m == {"via": "idle", "idle_days": 60} for m in metadata)


async def test_the_idle_clock_never_starts_before_the_floor(pool, developer):
    """A token last used 61 days ago is safe while the floor is more recent than the window."""
    async with pool.acquire() as conn:
        _, row = await _issue(conn, developer, _device("floor"))
        await _touch(conn, row["issued_token_id"], used_days_ago=61, created_days_ago=100)
        floor = await conn.fetchval("SELECT (now() - interval '30 days')::text")
        assert await _revoke_idle(conn, 60, floor) == []
        assert await _revoke_idle(conn, 60, "2000-01-01") == [row["issued_token_id"]]


async def test_the_default_floor_is_the_day_the_engine_began_recording_use(pool, developer):
    async with pool.acquire() as conn:
        default = await conn.fetchval("SELECT pg_get_function_arguments($1::regprocedure)", IDLE_SIGNATURE)
    assert "p_floor timestamp with time zone DEFAULT '2026-09-29 00:00:00+00'::timestamp with time zone" in default
    assert "p_idle_days integer DEFAULT 60" in default


async def test_running_it_twice_revokes_nothing_new(pool, developer):
    async with pool.acquire() as conn:
        _, row = await _issue(conn, developer, _device("twice"))
        await _touch(conn, row["issued_token_id"], used_days_ago=90, created_days_ago=100)
        assert await _revoke_idle(conn) == [row["issued_token_id"]]
        assert await _revoke_idle(conn) == []


async def test_an_idle_revoked_token_no_longer_authenticates(pool, developer):
    async with pool.acquire() as conn:
        clear, row = await _issue(conn, developer, _device("auth"))
        assert (await resolve_developer(conn, clear)).developer_id == developer
        await _touch(conn, row["issued_token_id"], used_days_ago=61, created_days_ago=100)
        await _revoke_idle(conn)
        with pytest.raises(UnauthenticatedError):
            await resolve_developer(conn, clear)


@pytest.mark.parametrize("days", [0, -5, None])
async def test_the_window_must_be_positive(pool, developer, days):
    async with pool.acquire() as conn:
        with pytest.raises(asyncpg.InvalidParameterValueError, match="INVALID_IDLE_DAYS"):
            await _revoke_idle(conn, days)


# ── AC-04 — at most five devices per person ──────────────────────────────


async def test_the_sixth_device_is_refused_and_nothing_changes(pool, developer):
    async with pool.acquire() as conn:
        for i in range(5):
            await _issue(conn, developer, _device(f"d{i}"))
        assert await _active_devices(conn, developer) == 5
        before = await conn.fetch("SELECT token_id, revoked_at FROM mcp_tokens WHERE developer_id = $1", developer)

        with pytest.raises(asyncpg.ConfigurationLimitExceededError, match="DEVICE_LIMIT") as exc:
            await _issue(conn, developer, _device("sixth"))
        assert exc.value.detail == "5 active devices; the limit is 5"

        after = await conn.fetch("SELECT token_id, revoked_at FROM mcp_tokens WHERE developer_id = $1", developer)
    assert [dict(r) for r in before] == [dict(r) for r in after]


async def test_a_known_device_signs_in_renews_and_replaces_freely_at_the_limit(pool, developer):
    devices = [_device(f"k{i}") for i in range(5)]
    async with pool.acquire() as conn:
        tokens = [await _issue(conn, developer, d) for d in devices]
        # Sign in again on device 2 (replaces), then renew its new token.
        _, again = await _issue(conn, developer, devices[2], issued_via="vscode")
        _, renewed = await _issue(conn, developer, devices[2], supersedes=again["issued_token_id"], reason="renewed")
        # The current token of device 4 expired: signing in there still works.
        await conn.execute(
            "UPDATE mcp_tokens SET expires_at = now() - interval '1 hour' WHERE token_id = $1",
            tokens[4][1]["issued_token_id"],
        )
        _, back = await _issue(conn, developer, devices[4])
        assert await _active_devices(conn, developer) == 5
    assert again["revoked_token_ids"] == [tokens[2][1]["issued_token_id"]]
    assert renewed["revoked_token_ids"] == [again["issued_token_id"]]
    assert back["revoked_token_ids"] == [tokens[4][1]["issued_token_id"]]


async def test_legacy_and_expired_tokens_take_no_slot(pool, developer):
    async with pool.acquire() as conn:
        for i in range(4):
            await _issue(conn, developer, _device(f"s{i}"))
        await register_mcp_token(conn, developer_id=developer, token=f"legacy-{uuid.uuid4().hex}")
        _, gone = await _issue(conn, developer, _device("gone"))
        await conn.execute(
            "UPDATE mcp_tokens SET expires_at = now() - interval '1 day' WHERE token_id = $1", gone["issued_token_id"]
        )
        # 4 live devices + 1 legacy + 1 expired device: the fifth device fits…
        await _issue(conn, developer, _device("fifth"))
        # …and the sixth does not.
        with pytest.raises(asyncpg.ConfigurationLimitExceededError, match="DEVICE_LIMIT"):
            await _issue(conn, developer, _device("sixth"))


async def test_adopting_a_legacy_token_counts_as_a_new_device(pool, developer):
    async with pool.acquire() as conn:
        for i in range(5):
            await _issue(conn, developer, _device(f"a{i}"))
        legacy_id = await register_mcp_token(conn, developer_id=developer, token=f"legacy-{uuid.uuid4().hex}")
        with pytest.raises(asyncpg.ConfigurationLimitExceededError, match="DEVICE_LIMIT"):
            await _issue(conn, developer, _device("adopted"), supersedes=legacy_id, reason="renewed")
        # The refusal rolled back: the legacy token still works.
        assert await conn.fetchval("SELECT revoked_at FROM mcp_tokens WHERE token_id = $1", legacy_id) is None


# ── Only the operator and the cloud API may revoke idle tokens ───────────


async def test_only_service_role_may_run_the_idle_revocation(pool):
    async with pool.acquire() as conn:
        for role, options in (("anon", ""), ("authenticated", ""), ("service_role", " BYPASSRLS")):
            if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", role):
                await conn.execute(f"CREATE ROLE {role} NOLOGIN{options}")
        await conn.execute(f"GRANT EXECUTE ON FUNCTION {IDLE_SIGNATURE} TO PUBLIC, anon, authenticated")
    await apply_migrations(pool)
    async with pool.acquire() as conn:
        grants = {
            role: await conn.fetchval("SELECT has_function_privilege($1, $2, 'EXECUTE')", role, IDLE_SIGNATURE)
            for role in ("anon", "authenticated", "service_role")
        }
        proconfig = await conn.fetchval("SELECT proconfig FROM pg_proc WHERE oid = $1::regprocedure", IDLE_SIGNATURE)
        definer = await conn.fetchval("SELECT prosecdef FROM pg_proc WHERE oid = $1::regprocedure", IDLE_SIGNATURE)
    assert grants == {"anon": False, "authenticated": False, "service_role": True}
    assert proconfig == ["search_path=public, pg_temp"]
    assert definer is False


async def test_the_issuing_function_keeps_its_grants_after_0027(pool):
    signature = "public.issue_device_token(text, text, text, text, text, text, text, text, text, integer)"
    async with pool.acquire() as conn:
        grants = {
            role: await conn.fetchval("SELECT has_function_privilege($1, $2, 'EXECUTE')", role, signature)
            for role in ("anon", "authenticated", "service_role")
            if await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", role)
        }
    assert grants.get("anon") is not True and grants.get("authenticated") is not True
