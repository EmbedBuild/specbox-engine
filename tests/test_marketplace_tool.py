"""Tests for server/tools/marketplace.py — UC-11903 (US-119).

get_marketplace_stats reads the daily snapshot from ``external_signal_daily``
(UC-11901, written by the VPS task of UC-11902) instead of a local jsonl file.

- AC-02: the summary of the stored rows (Marketplace, npm, GitHub stars/forks),
  the query only asks for public figures and errors never leak detail.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

import asyncpg

from server.tools.marketplace import (
    MAX_WINDOW_DAYS,
    _ROWS_SQL,
    fetch_marketplace_stats,
    summarize_external_signals,
)

TODAY = date(2026, 11, 12)
CAPTURED = datetime(2026, 11, 12, 6, 15, tzinfo=timezone.utc)


def snapshot(days: int = 5, base: int = 100, step: int = 4) -> list[dict]:
    rows = []
    for i in range(days):
        d = TODAY - timedelta(days=days - 1 - i)
        rows += [
            {"day": d, "source": "marketplace", "metric": "installs", "value": base + i * step, "captured_at": CAPTURED - timedelta(days=days - 1 - i)},
            {"day": d, "source": "marketplace", "metric": "updates", "value": 300 + i, "captured_at": CAPTURED},
            {"day": d, "source": "npm", "metric": "downloads", "value": 10 * (i + 1), "captured_at": CAPTURED},
        ]
    rows += [
        {"day": TODAY - timedelta(days=40), "source": "github", "metric": "stars", "value": 12, "captured_at": CAPTURED},
        {"day": TODAY, "source": "github", "metric": "stars", "value": 19, "captured_at": CAPTURED},
        {"day": TODAY, "source": "github", "metric": "forks", "value": 4, "captured_at": CAPTURED},
    ]
    return rows


# ── Summary (pure) ──────────────────────────────────────────────────────────────


def test_ac02_summary_of_the_stored_snapshot():
    out = summarize_external_signals(snapshot(), 30, TODAY)
    assert out["status"] == "ok"
    assert out["source"] == "external_signal_daily"
    assert out["total_installs"] == 116  # 100 + 4·4, the latest day
    assert out["total_updates"] == 304
    assert out["install_growth_pct"] == 16.0
    assert [p["installs"] for p in out["daily_series"]] == [100, 104, 108, 112, 116]
    assert [p["delta"] for p in out["daily_series"]] == [0, 4, 4, 4, 4]
    assert out["npm"]["downloads_in_window"] == 150
    assert len(out["npm"]["daily_series"]) == 5
    assert out["github"] == {"stars": 19, "forks": 4}
    assert out["from"] == "2026-10-13" and out["to"] == "2026-11-12"
    assert out["last_captured_at"] == CAPTURED.isoformat()


def test_rows_outside_the_window_are_ignored():
    out = summarize_external_signals(snapshot(days=5), 2, TODAY)
    assert [p["date"] for p in out["daily_series"]] == ["2026-11-10", "2026-11-11", "2026-11-12"]
    assert out["github"]["stars"] == 19  # the star 40 days back is outside


def test_no_marketplace_snapshot_is_no_data_yet():
    rows = [r for r in snapshot() if r["source"] != "marketplace"]
    out = summarize_external_signals(rows, 30, TODAY)
    assert out == {"status": "no_data_yet", "reason": "no_snapshot_in_window",
                   "source": "external_signal_daily", "window_days": 30}


def test_zero_first_installs_gives_zero_growth():
    out = summarize_external_signals(snapshot(base=0), 30, TODAY)
    assert out["install_growth_pct"] == 0.0


# ── Query (fake pool) ───────────────────────────────────────────────────────────


class FakeConn:
    def __init__(self, rows=None, exc=None):
        self.rows, self.exc, self.calls = rows or [], exc, []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        if self.exc:
            raise self.exc
        return self.rows


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


def test_ac02_reads_the_window_from_the_database():
    conn = FakeConn(rows=snapshot())
    out = asyncio.run(fetch_marketplace_stats(30, pool=FakePool(conn), today=TODAY))
    assert out["status"] == "ok" and out["total_installs"] == 116
    sql, args = conn.calls[0]
    assert "FROM public.external_signal_daily" in sql
    assert args == (TODAY - timedelta(days=30), TODAY)


def test_the_query_only_asks_for_public_figures():
    # GitHub traffic (clones, views) is admin-only on GitHub: it never leaves this tool.
    assert "clones" not in _ROWS_SQL and "views" not in _ROWS_SQL
    assert "metric IN ('stars', 'forks')" in _ROWS_SQL


def test_window_is_clamped():
    conn = FakeConn(rows=[])
    asyncio.run(fetch_marketplace_stats(10_000, pool=FakePool(conn), today=TODAY))
    assert conn.calls[0][1][0] == TODAY - timedelta(days=MAX_WINDOW_DAYS)
    asyncio.run(fetch_marketplace_stats(0, pool=FakePool(conn), today=TODAY))
    assert conn.calls[1][1][0] == TODAY - timedelta(days=1)


def test_missing_table_is_no_data_yet():
    conn = FakeConn(exc=asyncpg.UndefinedTableError("relation does not exist"))
    out = asyncio.run(fetch_marketplace_stats(30, pool=FakePool(conn), today=TODAY))
    assert out["status"] == "no_data_yet" and out["reason"] == "snapshot_table_missing"


def test_database_errors_never_leak_detail():
    conn = FakeConn(exc=OSError("connection refused to 10.0.0.5:5432 password=secret"))
    out = asyncio.run(fetch_marketplace_stats(30, pool=FakePool(conn), today=TODAY))
    assert out == {"status": "no_data_yet", "reason": "database_unavailable",
                   "source": "external_signal_daily", "window_days": 30}
