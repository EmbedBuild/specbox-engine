"""A per-identity call limit on the hosted MCP (UC-11401, US-114).

- AC-01: over 1,200 calls in an hour or 5,000 in a day from one identity, the
  hosted MCP answers RATE_LIMITED with the seconds to wait and the tool does
  not run. (The minute is UC-3903's: 429 over 60 tool calls a minute.)
- AC-02: every rejected call stays in the access log with RATE_LIMITED and the
  identity that made it — also for a tool whose result is a list.
- AC-03: SPECBOX_RATE_LIMITS changes the limits without a release; "off"
  turns them off.

AC-04 (no legitimate identity of the last 30 days reaches the defaults) is
measured on production's ``tool_access_log``; AC-05 is read there too, after
the deploy.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client, FastMCP

from server.coordination import access_log as al
from server.coordination import rate_limit as rl
from server.coordination.rate_limit import RateLimiter, RateLimitMiddleware, Window, parse_limits
from server.transport import TRANSPORT_ENV


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


# ── Limits from the environment (AC-03) ─────────────────────────────


def test_defaults_are_an_hour_and_a_day_the_minute_is_uc3903s():
    # Highest sliding use of any other identity in 30 days: 218/h and 1,100/day.
    assert parse_limits(None) == (Window(1200, 3600), Window(5000, 86400))
    assert parse_limits("") == parse_limits(None)


def test_ac03_the_variable_changes_the_limits_and_off_turns_them_off(monkeypatch):
    monkeypatch.setenv(rl.RATE_LIMITS_ENV, "60/min, 600/h ,3000/d")
    assert rl.limits_from_env() == (Window(60, 60), Window(600, 3600), Window(3000, 86400))
    monkeypatch.setenv(rl.RATE_LIMITS_ENV, "10/s")
    assert rl.limits_from_env() == (Window(10, 1),)
    for off in ("off", "OFF", "none"):
        monkeypatch.setenv(rl.RATE_LIMITS_ENV, off)
        assert rl.limits_from_env() == ()
        assert not RateLimitMiddleware(remote_only=False).limiter.enabled


@pytest.mark.parametrize("raw", ["120", "120/week", "0/min", "abc/min", "120/min,,5/h"])
def test_a_malformed_value_keeps_the_defaults(monkeypatch, raw):
    with pytest.raises(ValueError):
        parse_limits(raw)
    monkeypatch.setenv(rl.RATE_LIMITS_ENV, raw)
    assert rl.limits_from_env() == parse_limits(None)


# ── Sliding windows (AC-01) ─────────────────────────────────────────


def test_ac01_the_call_over_the_limit_is_refused_with_the_seconds_to_wait():
    clock = _Clock()
    limiter = RateLimiter((Window(3, 60),), clock=clock)
    for second in (0, 10, 20):
        clock.now = 1_000 + second
        assert limiter.check("developer:ana") is None
    clock.now = 1_030
    window, retry = limiter.check("developer:ana")
    assert window == Window(3, 60) and retry == 30  # the call of second 0 leaves at second 60
    # A refused call does not count: once the first call leaves, there is room.
    clock.now = 1_060
    assert limiter.check("developer:ana") is None
    # Another identity has its own windows.
    assert limiter.check("developer:luis") is None


def test_ac01_every_window_counts_and_the_longest_one_catches_a_steady_poller():
    clock = _Clock()
    limiter = RateLimiter((Window(120, 60), Window(1200, 3600), Window(5000, 86400)), clock=clock)
    refused: list[tuple[Window, int]] = []
    # The client that filled the quota: one call every ~5 s, all day.
    for n in range(17_280):
        clock.now = 1_000 + n * 5
        verdict = limiter.check("developer:poller")
        if verdict:
            refused.append(verdict)
    assert refused, "a steady poller must hit a window"
    windows = {w for w, _ in refused}
    assert windows == {Window(5000, 86400)}  # 12/min and 720/h are under the shorter windows
    assert 17_280 - len(refused) == 5000


def test_ac01_the_hour_window_catches_the_poller_at_its_peak():
    clock = _Clock()
    limiter = RateLimiter(parse_limits(None), clock=clock)
    verdicts = []
    for n in range(1_473):  # the poller's busiest hour, under 60 a minute
        clock.now = 1_000 + n * 2.44
        verdicts.append(limiter.check("developer:poller"))
    assert all(v is None for v in verdicts[:1200])
    window, retry = verdicts[1200]
    assert window == Window(1200, 3600) and 1 <= retry <= 3600


def test_idle_identities_are_forgotten():
    clock = _Clock()
    limiter = RateLimiter((Window(2, 60),), clock=clock)
    limiter.check("developer:ana")
    clock.now += 61
    limiter.forget_idle()
    assert limiter._calls == {}


# ── Through the MCP, with the access log around it (AC-01, AC-02) ────


@pytest.fixture
def server(monkeypatch):
    """A tiny MCP with a dict tool and a list tool, the access log and a limit of 3 per minute."""
    monkeypatch.setenv(TRANSPORT_ENV, "http")
    ran: list[str] = []

    async def identified(_ctx: Any) -> tuple[str | None, str, str | None]:
        return "dev-poller", al.KIND_DEVELOPER, "otro/proyecto"

    monkeypatch.setattr(al, "identity_for_log", identified)
    monkeypatch.setattr(rl, "identity_for_log", identified)

    mcp = FastMCP(name="t-rate-limit")

    @mcp.tool
    def ficha(uc_id: str) -> dict:
        ran.append(f"ficha:{uc_id}")
        return {"uc_id": uc_id}

    @mcp.tool
    def tabla() -> list[str]:
        ran.append("tabla")
        return ["UC-1", "UC-2"]

    store = al.MemoryStore()
    clock = _Clock()
    mcp.add_middleware(al.ToolAccessLogMiddleware(store, transport="http", blocking=True))
    mcp.add_middleware(RateLimitMiddleware(RateLimiter((Window(3, 60),), clock=clock)))
    return mcp, store, ran, clock


async def test_ac01_ac02_the_tool_does_not_run_and_the_log_says_rate_limited(server):
    mcp, store, ran, _clock = server
    async with Client(mcp) as client:
        for n in range(3):
            assert (await client.call_tool("ficha", {"uc_id": f"UC-{n}"})).data == {"uc_id": f"UC-{n}"}
        refused = await client.call_tool("ficha", {"uc_id": "UC-9"}, raise_on_error=False)
        listed = await client.call_tool("tabla", {}, raise_on_error=False)

    assert ran == ["ficha:UC-0", "ficha:UC-1", "ficha:UC-2"]  # neither refused call ran
    payload = refused.structured_content
    assert payload["code"] == "RATE_LIMITED" and payload["limit"] == "3/min"
    assert payload["retry_after_s"] >= 1
    assert listed.is_error  # a list tool cannot carry the object: an error result

    records = [r for r in store.records]
    assert [(r.tool, r.outcome, r.error_code) for r in records] == [
        ("ficha", "ok", None),
        ("ficha", "ok", None),
        ("ficha", "ok", None),
        ("ficha", "error", "RATE_LIMITED"),
        ("tabla", "error", "RATE_LIMITED"),
    ]
    assert {r.developer_id for r in records} == {"dev-poller"}


async def test_waiting_is_enough_to_get_through_again(server):
    mcp, _store, ran, clock = server
    async with Client(mcp) as client:
        for n in range(4):
            await client.call_tool("ficha", {"uc_id": f"UC-{n}"}, raise_on_error=False)
        clock.now += 60
        assert (await client.call_tool("ficha", {"uc_id": "UC-later"})).data == {"uc_id": "UC-later"}
    assert ran[-1] == "ficha:UC-later"


async def test_a_local_server_is_not_limited(server, monkeypatch):
    mcp, store, ran, _clock = server
    monkeypatch.setenv(TRANSPORT_ENV, "stdio")
    async with Client(mcp) as client:
        for n in range(5):
            await client.call_tool("ficha", {"uc_id": f"UC-{n}"})
    assert len(ran) == 5
    assert all(r.outcome == "ok" for r in store.records)
