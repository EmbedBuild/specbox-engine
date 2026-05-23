"""TTL cache behavior for the UC-502 mutation gate.

Unit tests — no Postgres required. We monkeypatch
``authenticate_and_authorize`` (the uncached gate that
``authenticate_and_authorize_cached`` falls back to) with an async stub that
returns a canned :class:`Developer` and counts invocations. The cache is
cleared between tests via :func:`_clear_auth_cache`.

Acceptance criteria covered:

* AC-01: repeated calls with the same ``(token, project_id)`` within the TTL
  hit the cache and result in a single uncached invocation.
* AC-02: the TTL constant ``_CACHE_TTL_SECONDS`` equals 30 and is therefore
  not exposed as a tunable setting — UC-502 freezes it.
"""

from __future__ import annotations

import pytest

from server.coordination import identity
from server.coordination.identity import (
    Developer,
    _CACHE_TTL_SECONDS,
    _clear_auth_cache,
    authenticate_and_authorize_cached,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_cache():
    """Every test starts with a fresh cache so call counts are deterministic."""
    _clear_auth_cache()
    yield
    _clear_auth_cache()


class _CountingStub:
    """Replaces ``authenticate_and_authorize`` for the unit tests."""

    def __init__(self, developer: Developer) -> None:
        self._developer = developer
        self.calls = 0

    async def __call__(self, conn, *, token, project_id):  # noqa: ANN001 — signature mirrored
        self.calls += 1
        return self._developer


# ── AC-01: hot path collapses to a single uncached call ──────────────


async def test_ac01_five_consecutive_calls_hit_cache_once(monkeypatch):
    """5 calls with the same key within TTL → exactly 1 uncached invocation."""
    stub = _CountingStub(Developer(developer_id="dev-1", display_name="Dev One"))
    monkeypatch.setattr(identity, "authenticate_and_authorize", stub)

    conn = object()  # never touched: cache returns the Developer directly
    for _ in range(5):
        dev = await authenticate_and_authorize_cached(conn, token="tok-A", project_id="proj-A")
        assert dev.developer_id == "dev-1"

    assert stub.calls == 1, f"expected 1 uncached gate call, got {stub.calls} — cache is not memoising"


async def test_ac01_distinct_keys_each_miss_once(monkeypatch):
    """Different (token, project_id) tuples each trigger their own miss."""
    stub = _CountingStub(Developer(developer_id="dev-2", display_name="Dev Two"))
    monkeypatch.setattr(identity, "authenticate_and_authorize", stub)

    conn = object()
    # Different tokens → different cache keys.
    await authenticate_and_authorize_cached(conn, token="tok-A", project_id="proj-X")
    await authenticate_and_authorize_cached(conn, token="tok-B", project_id="proj-X")
    # Same token, different project → still a different cache key.
    await authenticate_and_authorize_cached(conn, token="tok-A", project_id="proj-Y")
    # Repeat the first key → hit.
    await authenticate_and_authorize_cached(conn, token="tok-A", project_id="proj-X")

    assert stub.calls == 3, f"expected 3 uncached calls (3 unique keys), got {stub.calls}"


async def test_ac01_clear_cache_forces_revalidation(monkeypatch):
    """_clear_auth_cache() simulates expiry without sleeping the TTL."""
    stub = _CountingStub(Developer(developer_id="dev-3", display_name="Dev Three"))
    monkeypatch.setattr(identity, "authenticate_and_authorize", stub)

    conn = object()
    await authenticate_and_authorize_cached(conn, token="tok-C", project_id="proj-Z")
    await authenticate_and_authorize_cached(conn, token="tok-C", project_id="proj-Z")
    assert stub.calls == 1, "second call should hit cache"

    _clear_auth_cache()
    await authenticate_and_authorize_cached(conn, token="tok-C", project_id="proj-Z")
    assert stub.calls == 2, "after clear, next call must re-enter the uncached gate"


# ── AC-02: TTL is frozen at 30 seconds ───────────────────────────────


def test_ac02_ttl_is_hardcoded_to_30_seconds():
    """The cache TTL is a hardcoded constant, not a setting."""
    assert _CACHE_TTL_SECONDS == 30, (
        "UC-502 AC-02 freezes the cache TTL at 30 seconds; do not make it "
        "configurable. If a longer TTL is needed, lift it through a new AC."
    )
