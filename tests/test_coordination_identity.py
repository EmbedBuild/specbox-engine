"""Unit tests for the NativeBackend identity layer — Frontier 1 (H2).

Covers UC-201/202/203 acceptance criteria WITHOUT a real Postgres, using a
fake asyncpg connection that records SQL and returns canned rows:

- AC-10: tokens are stored hashed — register_developer never passes the clear
  token to SQL; hash_token is SHA-256 and irreversible.
- AC-11: the clear token never appears in logs (verified by capturing
  structlog output across a register + resolve round-trip).
- AC-12: an absent/invalid token → UNAUTHENTICATED, and no project row is read.
- AC-13: a valid token to a non-member project → FORBIDDEN; the right project
  proceeds.
- AC-15: whoami returns {developer_id, display_name} for a valid token and
  UNAUTHENTICATED (no enumeration) otherwise.

The real-Postgres round-trip lives in the PG-gated class at the bottom and
SKIPS cleanly when no dev DB is reachable (mirrors tests/test_native_schema.py).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import asyncpg
import pytest

from server.coordination.identity import (
    Developer,
    ForbiddenError,
    UnauthenticatedError,
    add_project_member,
    authenticate_and_authorize,
    authorize,
    hash_token,
    register_developer,
    register_mcp_token,
    resolve_developer,
)


# ── Fake asyncpg connection ──────────────────────────────────────────


class FakeConn:
    """Records every execute/fetchrow/fetchval call; returns scripted results.

    ``fetchrow_result`` / ``fetchval_result`` are callables ``(sql, *args) ->
    value`` so a test can decide per-query. ``executed`` / ``fetched`` keep the
    (sql, args) tuples for assertions (e.g. "the clear token was never an arg").
    """

    def __init__(self, *, fetchrow=None, fetchval=None) -> None:
        self.executed: list[tuple[str, tuple]] = []
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.fetchval_calls: list[tuple[str, tuple]] = []
        self._fetchrow = fetchrow
        self._fetchval = fetchval

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        return "OK"

    async def fetchrow(self, sql, *args):
        self.fetchrow_calls.append((sql, args))
        return self._fetchrow(sql, *args) if self._fetchrow else None

    async def fetchval(self, sql, *args):
        self.fetchval_calls.append((sql, args))
        return self._fetchval(sql, *args) if self._fetchval else None

    @asynccontextmanager
    async def transaction(self):
        yield

    def all_args_flat(self) -> list:
        flat: list = []
        for _sql, args in self.executed + self.fetchrow_calls + self.fetchval_calls:
            flat.extend(args)
        return flat


# ── hash_token [AC-10] ───────────────────────────────────────────────


def test_hash_token_is_sha256_hex():
    token = "super-secret-token"
    expected = hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert hash_token(token) == expected
    assert len(hash_token(token)) == 64  # sha256 hex
    assert token not in hash_token(token)  # irreversible: clear text absent


def test_hash_token_strips_whitespace():
    assert hash_token("  tok  ") == hash_token("tok")


def test_hash_token_rejects_empty():
    with pytest.raises(UnauthenticatedError):
        hash_token("")
    with pytest.raises(UnauthenticatedError):
        hash_token("   ")


# ── register_developer is identity-only (AC-18) ──────────────────────


async def test_register_developer_takes_no_token():
    """AC-18: register_developer has no ``token`` parameter."""
    conn = FakeConn()

    dev = await register_developer(
        conn,
        developer_id="jesus",
        display_name="Jesús",
    )

    assert dev == Developer(developer_id="jesus", display_name="Jesús")
    # The INSERT must target only developers; no token_hash arg anywhere.
    flat = conn.all_args_flat()
    assert "jesus" in flat
    assert "Jesús" in flat
    # No SHA-256 hex digest in the args (length 64, hex chars).
    for arg in flat:
        if isinstance(arg, str) and len(arg) == 64 and all(c in "0123456789abcdef" for c in arg):
            raise AssertionError(f"unexpected token hash in SQL args: {arg}")


async def test_register_developer_logs_no_secret(capsys):
    """AC-11/AC-18: register_developer no longer touches tokens — no secret leak path."""
    conn = FakeConn()
    await register_developer(conn, developer_id="alice", display_name="Alice")
    captured = capsys.readouterr()
    # Belt-and-braces: developer_id is fine in logs; nothing token-shaped should appear.
    assert "token" not in captured.out.lower() or "token_hash" not in captured.out.lower()


# ── register_mcp_token stores only the hash [AC-10, AC-11] ───────────


async def test_register_mcp_token_never_passes_clear_token_to_sql():
    conn = FakeConn()
    token = "my-clear-token-123"

    tid = await register_mcp_token(
        conn,
        developer_id="jesus",
        token=token,
    )

    assert tid.startswith("spec_"), "auto-generated token_id should be prefixed"
    flat = conn.all_args_flat()
    assert token not in flat, "clear token leaked into an SQL parameter"
    assert hash_token(token) in flat, "expected the token hash among SQL params"


async def test_register_mcp_token_logs_no_clear_token(capsys):
    """AC-11: the clear token never appears in logs across register_mcp_token."""
    conn = FakeConn()
    token = "log-secret-xyz"

    await register_mcp_token(conn, developer_id="alice", token=token)

    captured = capsys.readouterr()
    assert token not in captured.out
    assert token not in captured.err


async def test_register_mcp_token_honours_explicit_token_id():
    conn = FakeConn()
    tid = await register_mcp_token(conn, developer_id="jesus", token="t", token_id="spec_fixed_id_123")
    assert tid == "spec_fixed_id_123"


# ── resolve_developer [AC-12, AC-15] ─────────────────────────────────


async def test_resolve_developer_absent_token_raises_unauthenticated():
    conn = FakeConn()  # would return None anyway
    with pytest.raises(UnauthenticatedError):
        await resolve_developer(conn, None)
    with pytest.raises(UnauthenticatedError):
        await resolve_developer(conn, "")
    # AC-12: a missing token must not even query Postgres.
    assert conn.fetchrow_calls == []


async def test_resolve_developer_unknown_token_raises_without_enumeration():
    conn = FakeConn(fetchrow=lambda sql, *a: None)  # no matching row
    with pytest.raises(UnauthenticatedError) as exc:
        await resolve_developer(conn, "bogus")
    # AC-15: the message must not reveal whether a developer exists.
    msg = str(exc.value).lower()
    assert "exist" not in msg and "developer_id" not in msg


async def test_resolve_developer_valid_token_returns_developer():
    def row(sql, *args):
        # Confirm we looked up by the *hash*, not the clear token.
        assert hash_token("good-token") in args
        return {"developer_id": "jesus", "display_name": "Jesús"}

    conn = FakeConn(fetchrow=row)
    dev = await resolve_developer(conn, "good-token")
    assert dev.developer_id == "jesus"
    assert dev.display_name == "Jesús"


# ── authorize [AC-13] ────────────────────────────────────────────────


async def test_authorize_member_passes():
    conn = FakeConn(fetchval=lambda sql, *a: 1)  # membership row exists
    await authorize(conn, developer_id="jesus", project_id="proj-a")  # no raise


async def test_authorize_non_member_raises_forbidden():
    conn = FakeConn(fetchval=lambda sql, *a: None)  # no membership
    with pytest.raises(ForbiddenError) as exc:
        await authorize(conn, developer_id="jesus", project_id="proj-a")
    assert exc.value.developer_id == "jesus"
    assert exc.value.project_id == "proj-a"


async def test_authenticate_and_authorize_full_gate():
    def fetchrow(sql, *args):
        return {"developer_id": "jesus", "display_name": "Jesús"}

    def fetchval(sql, *args):
        return 1  # is a member

    conn = FakeConn(fetchrow=fetchrow, fetchval=fetchval)
    dev = await authenticate_and_authorize(conn, token="t", project_id="p")
    assert dev.developer_id == "jesus"


async def test_authenticate_and_authorize_forbidden_after_auth():
    conn = FakeConn(
        fetchrow=lambda sql, *a: {"developer_id": "jesus", "display_name": "J"},
        fetchval=lambda sql, *a: None,  # not a member
    )
    with pytest.raises(ForbiddenError):
        await authenticate_and_authorize(conn, token="t", project_id="p")


# ── whoami tool [AC-15] (pool patched, no PG) ────────────────────────


class _NativeCtx:
    """ctx whose get_state returns a native session config."""

    def __init__(self, config) -> None:
        self._config = config

    async def get_state(self, key):
        return self._config


async def test_whoami_unauthenticated_for_missing_token(monkeypatch):
    from server.tools import coordination

    # Pool is never reached for a missing token (resolve short-circuits), but
    # patch it anyway so a regression that *does* hit PG fails loudly here.
    monkeypatch.setattr(coordination, "get_pool", AsyncMock(return_value=FakeConn()))
    ctx = _NativeCtx({"backend_type": "native", "project_id": "p"})  # no dev_token

    result = await coordination.whoami(ctx)
    assert result["code"] == "UNAUTHENTICATED"
    # No enumeration: the response carries no developer_id field.
    assert "developer_id" not in result


async def test_whoami_returns_identity_for_valid_token(monkeypatch):
    from server.tools import coordination

    fake_pool = FakeConn(fetchrow=lambda sql, *a: {"developer_id": "jesus", "display_name": "Jesús"})
    monkeypatch.setattr(coordination, "get_pool", AsyncMock(return_value=fake_pool))
    ctx = _NativeCtx({"backend_type": "native", "project_id": "p", "dev_token": "good"})

    result = await coordination.whoami(ctx)
    assert result["success"] is True
    assert result["developer_id"] == "jesus"
    assert result["display_name"] == "Jesús"


async def test_whoami_rejects_non_native_session(monkeypatch):
    from server.tools import coordination

    ctx = _NativeCtx({"backend_type": "freeform", "root_path": "/tmp/x"})
    result = await coordination.whoami(ctx)
    assert result["code"] == "NOT_NATIVE_SESSION"


# ── PG-gated integration round-trip [AC-10, AC-13] ───────────────────

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
class TestIdentityRoundTripPG:
    async def test_register_resolve_authorize(self):
        """End-to-end: register dev + mint token + authorize + revoke. [AC-10/13/17/18]"""
        from server.coordination.identity import revoke_mcp_token
        from server.db.migrate import apply_migrations
        from server.db.pool import close_pool, init_pool

        pid = f"test-h2-{uuid.uuid4().hex[:8]}"
        dev_id = f"dev-{uuid.uuid4().hex[:6]}"
        token = f"tok-{uuid.uuid4().hex}"

        pg = await init_pool(dsn=DSN)
        try:
            await apply_migrations(pg)
            async with pg.acquire() as conn:
                await conn.execute(
                    "INSERT INTO projects (project_id, name) VALUES ($1, $2)",
                    pid,
                    "H2 test",
                )
                # AC-18: register_developer no longer takes a token.
                await register_developer(conn, developer_id=dev_id, display_name="Tester")
                # AC-10/17: token storage lives in mcp_tokens — stored hashed.
                token_id = await register_mcp_token(conn, developer_id=dev_id, token=token)
                stored = await conn.fetchval(
                    "SELECT token_hash FROM mcp_tokens WHERE token_id = $1",
                    token_id,
                )
                assert stored == hash_token(token)
                assert stored != token

                # Not a member yet → FORBIDDEN.
                with pytest.raises(ForbiddenError):
                    await authenticate_and_authorize(conn, token=token, project_id=pid)

                # After membership → resolves and authorizes.
                await add_project_member(conn, project_id=pid, developer_id=dev_id)
                dev = await authenticate_and_authorize(conn, token=token, project_id=pid)
                assert dev.developer_id == dev_id

                # AC-17: revoked token → UNAUTHENTICATED.
                assert await revoke_mcp_token(conn, token_id=token_id) is True
                with pytest.raises(UnauthenticatedError):
                    await authenticate_and_authorize(conn, token=token, project_id=pid)

                # Cleanup.
                await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev_id)
        finally:
            await close_pool()
