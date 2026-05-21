"""Unit tests for UC-401 — Supabase Pooler connection wiring.

These exercise the *pure* resolution logic of ``server.db.pool`` (SSL choice,
Supabase host detection, pool-size validation, DSN env-only rule) WITHOUT a
database, so they always run in CI regardless of whether Postgres is reachable.

The actual round-trip against the Supabase Pooler (statement_cache_size=0 not
raising DuplicatePreparedStatementError on the second call) is covered by the
conformance suite gated on ``SPECBOX_NATIVE_DSN`` — see
test_native_backend_conformance.py.

Acceptance criteria evidenced here:
- AC-24: ``init_pool`` passes ``statement_cache_size=0`` to asyncpg.
- AC-25: TLS is required for Supabase DSNs, plaintext for a local DSN, and the
  ``SPECBOX_NATIVE_SSL`` override wins both ways.
- AC-26: the DSN comes only from the env var; a missing env raises, and the
  resolved DSN is never embedded in the error message.
- AC-27: an oversized ``max_size`` fails fast with a message naming the ceiling.
"""

from __future__ import annotations

import pytest

from server.db import pool as pool_mod
from server.db.pool import (
    DSN_ENV_VAR,
    SSL_ENV_VAR,
    _is_supabase_dsn,
    _resolve_dsn,
    _resolve_ssl,
    _validate_max_size,
    init_pool,
)

_SUPABASE_POOLER_DSN = (
    "postgresql://postgres.nywjsvumsvxlpflpbord:pw@"
    "aws-0-eu-west-3.pooler.supabase.com:6543/postgres"
)
_SUPABASE_DIRECT_DSN = (
    "postgresql://postgres:pw@db.nywjsvumsvxlpflpbord.supabase.co:5432/postgres"
)
_LOCAL_DSN = "postgresql://specbox:specbox_dev_only@localhost:55432/specbox_native"


# ── AC-25: Supabase host detection ───────────────────────────────────────
@pytest.mark.parametrize(
    "dsn,expected",
    [
        (_SUPABASE_POOLER_DSN, True),
        (_SUPABASE_DIRECT_DSN, True),
        (_LOCAL_DSN, False),
        ("postgresql://u:p@127.0.0.1:5432/db", False),
    ],
)
def test_supabase_host_detection(dsn: str, expected: bool) -> None:
    assert _is_supabase_dsn(dsn) is expected


# ── AC-25: SSL resolution ────────────────────────────────────────────────
def test_ssl_required_for_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SSL_ENV_VAR, raising=False)
    assert _resolve_ssl(_SUPABASE_POOLER_DSN) == "require"
    assert _resolve_ssl(_SUPABASE_DIRECT_DSN) == "require"


def test_ssl_off_for_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SSL_ENV_VAR, raising=False)
    assert _resolve_ssl(_LOCAL_DSN) is False


def test_ssl_override_force_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SSL_ENV_VAR, "require")
    # Even a local DSN is forced to TLS when the override demands it.
    assert _resolve_ssl(_LOCAL_DSN) == "require"


def test_ssl_override_force_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SSL_ENV_VAR, "disable")
    # Even a Supabase DSN drops TLS when explicitly disabled (e.g. local proxy).
    assert _resolve_ssl(_SUPABASE_POOLER_DSN) is False


# ── AC-26: DSN env-only rule ─────────────────────────────────────────────
def test_dsn_explicit_override_wins() -> None:
    assert _resolve_dsn(_LOCAL_DSN) == _LOCAL_DSN


def test_dsn_missing_env_raises_without_leaking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(DSN_ENV_VAR, raising=False)
    with pytest.raises(RuntimeError) as exc:
        _resolve_dsn(None)
    msg = str(exc.value)
    assert DSN_ENV_VAR in msg
    # The error must not embed any credential material.
    assert "://" not in msg
    assert "password" not in msg.lower()


def test_dsn_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DSN_ENV_VAR, _SUPABASE_POOLER_DSN)
    assert _resolve_dsn(None) == _SUPABASE_POOLER_DSN


# ── AC-27: pool-size validation ──────────────────────────────────────────
def test_validate_max_size_ok() -> None:
    # Default max (10) is under the default ceiling (15) → no raise.
    _validate_max_size(10)


def test_validate_max_size_over_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pool_mod, "_MAX_POOL_SIZE_CEILING", 15, raising=False)
    with pytest.raises(RuntimeError) as exc:
        _validate_max_size(50)
    assert "ceiling" in str(exc.value).lower()
    assert "50" in str(exc.value)


# ── AC-24 + AC-27: init_pool passes the right kwargs / validates early ────
async def test_init_pool_disables_statement_cache_and_validates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_pool must (a) reject oversized pools BEFORE touching the DB and
    (b) hand asyncpg statement_cache_size=0 + the resolved ssl. We stub
    asyncpg.create_pool so no real connection is attempted."""
    captured: dict = {}

    async def _fake_create_pool(dsn, **kwargs):  # noqa: ANN001, ANN003
        captured["dsn"] = dsn
        captured.update(kwargs)
        return object()  # sentinel "pool"

    # Ensure a clean singleton and a known DSN.
    monkeypatch.setattr(pool_mod, "_pool", None, raising=False)
    monkeypatch.setattr(pool_mod.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.delenv(SSL_ENV_VAR, raising=False)

    # (a) Oversized pool fails fast, no create_pool call.
    with pytest.raises(RuntimeError):
        await init_pool(dsn=_SUPABASE_POOLER_DSN, max_size=999)
    assert captured == {}

    # (b) Normal init wires the PgBouncer-safe kwargs.
    await init_pool(dsn=_SUPABASE_POOLER_DSN, max_size=10)
    try:
        assert captured["statement_cache_size"] == 0
        assert captured["ssl"] == "require"
        assert captured["max_size"] == 10
    finally:
        monkeypatch.setattr(pool_mod, "_pool", None, raising=False)
