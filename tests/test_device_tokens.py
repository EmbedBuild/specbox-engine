"""UC-3904 / UC-3902 AC-01 — one token per device, with an expiry date (migration 0025).

PG-gated (skips cleanly without a reachable Postgres, like the other native
modules). What it pins:

* ``public.issue_device_token`` replaces the device's active token instead of
  adding one (AC-01), renews only a token that still works, and adopts a legacy
  token (no device) as a device;
* whoever writes, a device never holds two active tokens (partial unique index);
* the identity resolver refuses an expired token and records real use in
  ``last_used_at`` at most once an hour;
* only service_role may execute the issuing function once Supabase's default
  grants are in place.
"""

from __future__ import annotations

import hashlib
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

_PG_OK, _PG_SKIP_REASON = reachable()
pytestmark = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)

ISSUE_SIGNATURE = "public.issue_device_token(text, text, text, text, text, text, text, text, text, integer)"


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
    dev_id = f"dev-uc3904-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=dev_id, display_name="Device Test")
    try:
        yield dev_id
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev_id)


def _device(tag: str) -> str:
    return hashlib.sha256(f"machine-{tag}-{uuid.uuid4().hex}:claude-code".encode()).hexdigest()


def _new_token() -> tuple[str, str, str]:
    """``(clear, hash, token_id)`` the way the cloud mints them."""
    clear = f"spbx_{uuid.uuid4().hex}{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(clear.encode()).hexdigest()
    return clear, token_hash, token_hash[:12]


async def _issue(
    conn: asyncpg.Connection,
    developer_id: str,
    device_id: str | None,
    *,
    supersedes: str | None = None,
    reason: str = "replaced",
    ttl_days: int = 90,
    issued_via: str = "cli",
) -> tuple[str, asyncpg.Record]:
    clear, token_hash, token_id = _new_token()
    row = await conn.fetchrow(
        "SELECT * FROM public.issue_device_token($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
        developer_id,
        token_id,
        token_hash,
        device_id,
        "Device Test · host · Claude Code",
        "claude-code",
        issued_via,
        supersedes,
        reason,
        ttl_days,
    )
    return clear, row


async def _active_for_device(conn: asyncpg.Connection, developer_id: str, device_id: str) -> list[str]:
    rows = await conn.fetch(
        "SELECT token_id FROM mcp_tokens WHERE developer_id = $1 AND device_id = $2 AND revoked_at IS NULL",
        developer_id,
        device_id,
    )
    return [r["token_id"] for r in rows]


# ── AC-01 — a new sign-in replaces, never adds ───────────────────────


async def test_first_token_of_a_device_expires_in_90_days(pool, developer):
    device = _device("first")
    async with pool.acquire() as conn:
        clear, row = await _issue(conn, developer, device)
        days = await conn.fetchval("SELECT extract(epoch FROM ($1 - now())) / 86400", row["issued_expires_at"])
        stored = await conn.fetchrow("SELECT * FROM mcp_tokens WHERE token_id = $1", row["issued_token_id"])
    assert row["revoked_token_ids"] == []
    assert 89.9 < float(days) <= 90.0
    assert stored["device_id"] == device and stored["client"] == "claude-code" and stored["issued_via"] == "cli"
    assert stored["name"] == stored["device_name"] == "Device Test · host · Claude Code"
    assert stored["token_hash"] == hashlib.sha256(clear.encode()).hexdigest()


async def test_signing_in_again_on_the_same_device_replaces_the_token(pool, developer):
    device = _device("again")
    async with pool.acquire() as conn:
        _, first = await _issue(conn, developer, device)
        _, second = await _issue(conn, developer, device, issued_via="vscode")
        old = await conn.fetchrow(
            "SELECT revoked_at, revoked_reason FROM mcp_tokens WHERE token_id = $1", first["issued_token_id"]
        )
        active = await _active_for_device(conn, developer, device)
    assert second["revoked_token_ids"] == [first["issued_token_id"]]
    assert old["revoked_at"] is not None and old["revoked_reason"] == "replaced"
    assert active == [second["issued_token_id"]]


async def test_other_devices_are_untouched(pool, developer):
    laptop, desktop = _device("laptop"), _device("desktop")
    async with pool.acquire() as conn:
        _, a = await _issue(conn, developer, laptop)
        _, b = await _issue(conn, developer, desktop)
        assert await _active_for_device(conn, developer, laptop) == [a["issued_token_id"]]
        assert await _active_for_device(conn, developer, desktop) == [b["issued_token_id"]]


async def test_a_device_never_holds_two_active_tokens_whoever_writes(pool, developer):
    device = _device("direct")
    async with pool.acquire() as conn:
        await _issue(conn, developer, device)
        _, token_hash, token_id = _new_token()
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                "INSERT INTO mcp_tokens (token_id, developer_id, token_hash, device_id) VALUES ($1, $2, $3, $4)",
                token_id,
                developer,
                token_hash,
                device,
            )


# ── AC-03 — renewal with the current token ───────────────────────────


async def test_renewal_rotates_the_token_of_the_same_device(pool, developer):
    device = _device("renew")
    async with pool.acquire() as conn:
        _, current = await _issue(conn, developer, device)
        _, renewed = await _issue(conn, developer, device, supersedes=current["issued_token_id"], reason="renewed")
        old_reason = await conn.fetchval(
            "SELECT revoked_reason FROM mcp_tokens WHERE token_id = $1", current["issued_token_id"]
        )
        assert await _active_for_device(conn, developer, device) == [renewed["issued_token_id"]]
    assert renewed["revoked_token_ids"] == [current["issued_token_id"]]
    assert old_reason == "renewed"


async def test_a_revoked_or_expired_token_cannot_renew(pool, developer):
    device = _device("dead")
    async with pool.acquire() as conn:
        _, current = await _issue(conn, developer, device)
        _, _replacement = await _issue(conn, developer, device)  # revokes `current`
        with pytest.raises(asyncpg.InvalidAuthorizationSpecificationError, match="TOKEN_NOT_RENEWABLE"):
            await _issue(conn, developer, device, supersedes=current["issued_token_id"], reason="renewed")

        _, live = await _issue(conn, developer, _device("expired"))
        await conn.execute(
            "UPDATE mcp_tokens SET expires_at = now() - interval '1 minute' WHERE token_id = $1",
            live["issued_token_id"],
        )
        with pytest.raises(asyncpg.InvalidAuthorizationSpecificationError, match="TOKEN_NOT_RENEWABLE"):
            await _issue(conn, developer, None, supersedes=live["issued_token_id"], reason="renewed")


async def test_someone_else_s_token_cannot_be_renewed(pool, developer):
    other = f"dev-uc3904-other-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=other, display_name="Other")
        try:
            _, theirs = await _issue(conn, other, _device("theirs"))
            with pytest.raises(asyncpg.InvalidAuthorizationSpecificationError, match="TOKEN_NOT_RENEWABLE"):
                await _issue(conn, developer, None, supersedes=theirs["issued_token_id"], reason="renewed")
        finally:
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", other)


async def test_a_legacy_token_is_adopted_as_a_device_on_renewal(pool, developer):
    device = _device("legacy")
    async with pool.acquire() as conn:
        legacy_id = await register_mcp_token(conn, developer_id=developer, token=f"legacy-{uuid.uuid4().hex}")
        _, adopted = await _issue(conn, developer, device, supersedes=legacy_id, reason="renewed")
        legacy = await conn.fetchrow("SELECT revoked_at, revoked_reason FROM mcp_tokens WHERE token_id = $1", legacy_id)
        assert await _active_for_device(conn, developer, device) == [adopted["issued_token_id"]]
    assert adopted["revoked_token_ids"] == [legacy_id]
    assert legacy["revoked_at"] is not None and legacy["revoked_reason"] == "renewed"


@pytest.mark.parametrize(("reason", "ttl"), [("user", 90), ("replaced", 0), ("renewed", 400)])
async def test_bad_reason_or_ttl_is_rejected(pool, developer, reason, ttl):
    async with pool.acquire() as conn:
        with pytest.raises(asyncpg.InvalidParameterValueError):
            await _issue(conn, developer, _device("bad"), reason=reason, ttl_days=ttl)


@pytest.mark.parametrize(
    ("column", "value"),
    [("device_id", "not-a-hash"), ("client", "Claude Code"), ("issued_via", "email"), ("revoked_reason", "whim")],
)
async def test_columns_only_take_known_values(pool, developer, column, value):
    _, token_hash, token_id = _new_token()
    async with pool.acquire() as conn:
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                f"INSERT INTO mcp_tokens (token_id, developer_id, token_hash, {column}) VALUES ($1, $2, $3, $4)",
                token_id,
                developer,
                token_hash,
                value,
            )


# ── UC-3902 AC-01 — an expired token stops authenticating ────────────


async def test_an_expired_token_no_longer_authenticates(pool, developer):
    async with pool.acquire() as conn:
        clear, row = await _issue(conn, developer, _device("expiry"))
        assert (await resolve_developer(conn, clear)).developer_id == developer
        await conn.execute(
            "UPDATE mcp_tokens SET expires_at = now() - interval '1 second' WHERE token_id = $1",
            row["issued_token_id"],
        )
        with pytest.raises(UnauthenticatedError):
            await resolve_developer(conn, clear)


async def test_a_token_without_expiry_keeps_working(pool, developer):
    token = f"legacy-{uuid.uuid4().hex}"
    async with pool.acquire() as conn:
        await register_mcp_token(conn, developer_id=developer, token=token)
        assert (await resolve_developer(conn, token)).developer_id == developer


async def test_legacy_tokens_get_the_operator_deadline_and_nothing_else_moves(pool, developer):
    """0026: active tokens without an expiry date get 2026-12-28; nothing else changes."""
    legacy = f"legacy-{uuid.uuid4().hex}"
    revoked = f"legacy-{uuid.uuid4().hex}"
    async with pool.acquire() as conn:
        await register_mcp_token(conn, developer_id=developer, token=legacy)
        await register_mcp_token(conn, developer_id=developer, token=revoked)
        await conn.execute(
            "UPDATE mcp_tokens SET revoked_at = now() WHERE token_hash = $1",
            hashlib.sha256(revoked.encode()).hexdigest(),
        )
        _clear, device = await _issue(conn, developer, _device("deadline"))
        device_expiry = await conn.fetchval(
            "SELECT expires_at FROM mcp_tokens WHERE token_id = $1", device["issued_token_id"]
        )
    await apply_migrations(pool)
    async with pool.acquire() as conn:
        rows = {
            r["token_hash"]: r["expires_at"]
            for r in await conn.fetch(
                "SELECT token_hash, expires_at FROM mcp_tokens WHERE developer_id = $1", developer
            )
        }
        after_device = await conn.fetchval(
            "SELECT expires_at FROM mcp_tokens WHERE token_id = $1", device["issued_token_id"]
        )
    assert rows[hashlib.sha256(legacy.encode()).hexdigest()].isoformat() == "2026-12-28T00:00:00+00:00"
    assert rows[hashlib.sha256(revoked.encode()).hexdigest()] is None
    assert after_device == device_expiry


# ── Real use is recorded, at most once an hour ───────────────────────


async def test_resolving_records_last_use_at_most_once_an_hour(pool, developer):
    async with pool.acquire() as conn:
        clear, row = await _issue(conn, developer, _device("use"))
        token_id = row["issued_token_id"]
        assert await conn.fetchval("SELECT last_used_at FROM mcp_tokens WHERE token_id = $1", token_id) is None

        await resolve_developer(conn, clear)
        first = await conn.fetchval("SELECT last_used_at FROM mcp_tokens WHERE token_id = $1", token_id)
        assert first is not None

        await resolve_developer(conn, clear)  # within the hour: untouched
        assert await conn.fetchval("SELECT last_used_at FROM mcp_tokens WHERE token_id = $1", token_id) == first

        await conn.execute(
            "UPDATE mcp_tokens SET last_used_at = now() - interval '2 hours' WHERE token_id = $1", token_id
        )
        await resolve_developer(conn, clear)
        refreshed = await conn.fetchval("SELECT last_used_at FROM mcp_tokens WHERE token_id = $1", token_id)
        assert refreshed is not None and refreshed >= first


async def test_a_rejected_token_records_nothing(pool, developer):
    async with pool.acquire() as conn:
        clear, row = await _issue(conn, developer, _device("rejected"))
        await conn.execute("UPDATE mcp_tokens SET revoked_at = now() WHERE token_id = $1", row["issued_token_id"])
        with pytest.raises(UnauthenticatedError):
            await resolve_developer(conn, clear)
        used = await conn.fetchval("SELECT last_used_at FROM mcp_tokens WHERE token_id = $1", row["issued_token_id"])
    assert used is None


# ── Only the cloud API may issue tokens ──────────────────────────────


async def test_only_service_role_may_execute_the_issuing_function(pool):
    async with pool.acquire() as conn:
        for role, options in (("anon", ""), ("authenticated", ""), ("service_role", " BYPASSRLS")):
            if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", role):
                await conn.execute(f"CREATE ROLE {role} NOLOGIN{options}")
        # What Supabase's default privileges hand every new function (only this
        # one, so the shared test database keeps its other grants intact).
        await conn.execute(f"GRANT EXECUTE ON FUNCTION {ISSUE_SIGNATURE} TO PUBLIC, anon, authenticated")
    await apply_migrations(pool)
    async with pool.acquire() as conn:
        grants = {
            role: await conn.fetchval("SELECT has_function_privilege($1, $2, 'EXECUTE')", role, ISSUE_SIGNATURE)
            for role in ("anon", "authenticated", "service_role")
        }
        proconfig = await conn.fetchval("SELECT proconfig FROM pg_proc WHERE oid = $1::regprocedure", ISSUE_SIGNATURE)
        definer = await conn.fetchval("SELECT prosecdef FROM pg_proc WHERE oid = $1::regprocedure", ISSUE_SIGNATURE)
    assert grants == {"anon": False, "authenticated": False, "service_role": True}
    assert proconfig == ["search_path=public, pg_temp"]
    assert definer is False
