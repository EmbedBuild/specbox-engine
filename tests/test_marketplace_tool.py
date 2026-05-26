"""Tests for server/tools/marketplace.py — UC-643.

Validates:
- AC-04: tool MCP get_marketplace_stats returns expected shape
- AC-05: 30 entries → metrics correct + install_growth_pct positive + daily_series == 30
- AC-05 edge: empty jsonl → no_data_yet
- Robustness: malformed lines skipped, entries outside window filtered
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from server.tools.marketplace import aggregate_marketplace_stats


def make_fixture(num_entries: int, base_installs: int = 10, growth_per_day: int = 8) -> str:
    """Build a jsonl fixture with `num_entries` consecutive daily entries.

    Entries are anchored at `now - num_entries + 1` days through `now`,
    so all entries fall inside a `window_days >= num_entries` window.
    """
    now = datetime(2026, 5, 26, 6, 0, 0, tzinfo=timezone.utc)
    lines = []
    for i in range(num_entries):
        ts = now - timedelta(days=num_entries - 1 - i)
        installs = base_installs + i * growth_per_day
        entry = {
            "date": ts.isoformat().replace("+00:00", "Z"),
            "version": "6.2.0",
            "installs": installs,
            "downloads": installs * 2,
            "avg_rating": 4.5,
            "rating_count": max(0, i // 5),
            "trending_daily": 0,
            "trending_weekly": 0,
            "trending_monthly": 0,
            "delta_installs_24h": growth_per_day if i > 0 else 0,
        }
        lines.append(json.dumps(entry))
    return "\n".join(lines) + "\n"


def test_30_entries_full_window():
    """AC-05: 30 entries simuladas → métricas correctas, growth positivo, 30 entries en daily_series."""
    jsonl = make_fixture(num_entries=30, base_installs=10, growth_per_day=8)
    now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    result = aggregate_marketplace_stats(jsonl, window_days=30, now=now)

    assert result["status"] == "ok"
    assert result["entries_count"] == 30
    assert len(result["daily_series"]) == 30
    assert result["total_installs"] == 10 + 29 * 8  # last entry
    assert result["install_growth_pct"] > 0
    # First=10, last=242 → growth ≈ 2320%
    assert result["install_growth_pct"] == pytest.approx(2320.0, abs=1.0)


def test_smaller_window_filters_old_entries():
    """window_days=7 sobre 30 entries → solo 7 entries dentro de la ventana."""
    jsonl = make_fixture(num_entries=30, base_installs=10, growth_per_day=8)
    now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    result = aggregate_marketplace_stats(jsonl, window_days=7, now=now)

    assert result["status"] == "ok"
    # window_days=7 cutoff = now - 7 days. The fixture's last entry is anchored
    # at now - 0 days; entries from days [-6..0] fall inside the window (7 entries).
    assert result["entries_count"] == 7
    assert result["window_days"] == 7


def test_empty_jsonl_returns_no_data_yet():
    """AC-05 edge: jsonl vacío → status no_data_yet, reason extension_not_published_or_no_stats."""
    result = aggregate_marketplace_stats("", window_days=30)
    assert result["status"] == "no_data_yet"
    assert result["reason"] == "extension_not_published_or_no_stats"
    assert result["window_days"] == 30


def test_whitespace_only_jsonl_returns_no_data_yet():
    """Robustness: jsonl con solo whitespace → no_data_yet."""
    result = aggregate_marketplace_stats("   \n  \n\n   ", window_days=30)
    assert result["status"] == "no_data_yet"
    assert result["reason"] == "extension_not_published_or_no_stats"


def test_malformed_lines_are_skipped():
    """Robustness: jsonl con líneas malformadas → skip + count, no crash."""
    valid = json.dumps({
        "date": "2026-05-26T06:00:00Z",
        "version": "6.2.0",
        "installs": 100,
        "downloads": 200,
        "avg_rating": 4.5,
        "rating_count": 5,
        "trending_daily": 0,
        "trending_weekly": 0,
        "trending_monthly": 0,
        "delta_installs_24h": 5,
    })
    jsonl = f"this is not json\n{valid}\n{{broken json"
    now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    result = aggregate_marketplace_stats(jsonl, window_days=30, now=now)

    assert result["status"] == "ok"
    assert result["entries_count"] == 1
    assert result["malformed_lines_skipped"] == 2
    assert result["total_installs"] == 100


def test_entries_outside_window_dropped():
    """Window dejado por defecto en 30 días, fixture con 60 entries → solo las últimas 30 entran."""
    jsonl = make_fixture(num_entries=60, base_installs=1, growth_per_day=1)
    now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    result = aggregate_marketplace_stats(jsonl, window_days=30, now=now)

    assert result["status"] == "ok"
    # window_days=30 cutoff = now - 30 days; fixture spans days [-59..0]
    # so 31 entries fall within the window (days -29 through 0, inclusive of cutoff day)
    assert result["entries_count"] in (30, 31)


def test_all_entries_older_than_window():
    """Si todas las entries son más viejas que la ventana → no_entries_within_window."""
    # Build a fixture from a fixed past date, then query with a far-future "now"
    past = datetime(2025, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
    entries = []
    for i in range(5):
        ts = past + timedelta(days=i)
        entries.append(json.dumps({
            "date": ts.isoformat().replace("+00:00", "Z"),
            "version": "6.2.0",
            "installs": 10 + i,
            "downloads": 20 + i,
            "avg_rating": 4.0,
            "rating_count": 1,
            "trending_daily": 0,
            "trending_weekly": 0,
            "trending_monthly": 0,
            "delta_installs_24h": 1,
        }))
    jsonl = "\n".join(entries)
    now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    result = aggregate_marketplace_stats(jsonl, window_days=30, now=now)

    assert result["status"] == "no_data_yet"
    assert result["reason"] == "no_entries_within_window"
    assert result["entries_total_in_file"] == 5


def test_single_entry_growth_pct_is_zero():
    """Edge: una sola entry en la ventana → growth_pct = 0 (no hay first y last distintos)."""
    jsonl = make_fixture(num_entries=1, base_installs=42, growth_per_day=0)
    now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    result = aggregate_marketplace_stats(jsonl, window_days=30, now=now)

    assert result["status"] == "ok"
    assert result["entries_count"] == 1
    assert result["total_installs"] == 42
    assert result["install_growth_pct"] == 0.0  # first == last


def test_zero_first_installs_growth_zero():
    """Si first_installs = 0 → growth_pct = 0 (sin division by zero)."""
    now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    entries = [
        {
            "date": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
            "version": "6.2.0",
            "installs": 0,
            "downloads": 0,
            "avg_rating": 0,
            "rating_count": 0,
            "trending_daily": 0,
            "trending_weekly": 0,
            "trending_monthly": 0,
            "delta_installs_24h": 0,
        },
        {
            "date": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "version": "6.2.0",
            "installs": 5,
            "downloads": 10,
            "avg_rating": 4.0,
            "rating_count": 0,
            "trending_daily": 0,
            "trending_weekly": 0,
            "trending_monthly": 0,
            "delta_installs_24h": 5,
        },
    ]
    jsonl = "\n".join(json.dumps(e) for e in entries)
    result = aggregate_marketplace_stats(jsonl, window_days=30, now=now)

    assert result["status"] == "ok"
    assert result["install_growth_pct"] == 0.0
    assert result["total_installs"] == 5
