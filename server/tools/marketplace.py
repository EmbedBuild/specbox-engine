"""MCP tool for the adoption signals seen from outside: Marketplace, npm and GitHub.

v6.2.0 — UC-643 (US-VSCODE-MARKETPLACE) introduced ``get_marketplace_stats``
over a ``.quality/marketplace-stats.jsonl`` written by a GitHub Actions
workflow. That file was ignored by git, so nothing was ever kept.

v6.34.0 — UC-11903 (US-119, EP-19): the figures come from the database. A
daily task on the SpecBox VPS (``ops/external-signals/`` of specbox-manager,
UC-11902) stores one row per UTC day, source and metric in
``public.external_signal_daily`` (migration of specbox_cloud, UC-11901). This
tool reads that table with the server's pool: the same figures as the daily
snapshot.

**Privacy**: zero PII. Only public figures leave this tool — Marketplace
installs and updates, npm downloads, GitHub stars and forks. The GitHub
traffic (clones and visits) that the snapshot also keeps is visible on GitHub
only to repository admins, so it stays in the SuperAdmin «Adopción» page and
is never returned here.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import asyncpg
from fastmcp import FastMCP

from server.db.pool import get_pool

logger = logging.getLogger(__name__)

#: Longest look-back a caller can ask for (days).
MAX_WINDOW_DAYS = 400

# Public figures only (see the module docstring): no GitHub traffic.
_ROWS_SQL = """
SELECT day, source, metric, value, captured_at
FROM public.external_signal_daily
WHERE day BETWEEN $1 AND $2
  AND (source IN ('marketplace', 'npm') OR (source = 'github' AND metric IN ('stars', 'forks')))
ORDER BY day
"""


def _clamp_window(window_days: Any) -> int:
    try:
        days = int(window_days)
    except (TypeError, ValueError):
        days = 30
    return max(1, min(days, MAX_WINDOW_DAYS))


def summarize_external_signals(
    rows: Iterable[dict[str, Any]],
    window_days: int,
    today: date,
) -> dict[str, Any]:
    """Pure summary of the snapshot rows of a window — testable without a database.

    Args:
        rows: ``{day, source, metric, value, captured_at}`` rows of
            ``external_signal_daily`` inside ``[today - window_days, today]``.
        window_days: Look-back window in days.
        today: The last day of the window (UTC).

    Returns:
        ``status: "ok"`` with the Marketplace installs and updates (latest,
        growth and daily series), npm downloads in the window with their daily
        series and the latest GitHub stars and forks; or ``status:
        "no_data_yet"`` when the window has no Marketplace snapshot.
        ``total_installs`` and ``daily_series`` keep the v6.2.0 shape.
    """
    start = today - timedelta(days=window_days)
    series: dict[tuple[str, str], dict[date, int]] = {}
    last_captured: datetime | None = None
    for r in rows:
        day = r["day"]
        if not (start <= day <= today):
            continue
        series.setdefault((r["source"], r["metric"]), {})[day] = int(r["value"])
        cap = r.get("captured_at")
        if cap is not None and (last_captured is None or cap > last_captured):
            last_captured = cap

    installs = series.get(("marketplace", "installs"), {})
    if not installs:
        return {
            "status": "no_data_yet",
            "reason": "no_snapshot_in_window",
            "source": "external_signal_daily",
            "window_days": window_days,
        }

    def latest(key: tuple[str, str]) -> int | None:
        s = series.get(key)
        return s[max(s)] if s else None

    days = sorted(installs)
    first, last = installs[days[0]], installs[days[-1]]
    growth = round((last - first) / first * 100.0, 2) if first > 0 else 0.0
    updates = series.get(("marketplace", "updates"), {})
    daily_series = []
    previous: int | None = None
    for d in days:
        daily_series.append({
            "date": d.isoformat(),
            "installs": installs[d],
            "updates": updates.get(d),
            "delta": installs[d] - previous if previous is not None else 0,
        })
        previous = installs[d]

    npm = series.get(("npm", "downloads"), {})
    return {
        "status": "ok",
        "source": "external_signal_daily",
        "window_days": window_days,
        "from": start.isoformat(),
        "to": today.isoformat(),
        "last_captured_at": last_captured.isoformat() if last_captured else None,
        "total_installs": last,
        "total_updates": latest(("marketplace", "updates")),
        "install_growth_pct": growth,
        "daily_series": daily_series,
        "npm": {
            "downloads_in_window": sum(npm.values()),
            "daily_series": [{"date": d.isoformat(), "downloads": npm[d]} for d in sorted(npm)],
        },
        "github": {
            "stars": latest(("github", "stars")),
            "forks": latest(("github", "forks")),
        },
        "entries_count": len(days),
    }


async def fetch_marketplace_stats(
    window_days: int = 30,
    *,
    pool: Any = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Read the window from ``external_signal_daily`` and summarise it.

    Never raises: without a database, or before the snapshot table exists,
    the answer is ``no_data_yet`` with the reason, and no internal detail.
    """
    window_days = _clamp_window(window_days)
    today = today or datetime.now(timezone.utc).date()
    start = today - timedelta(days=window_days)
    try:
        pool = pool or await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(_ROWS_SQL, start, today)
    except asyncpg.UndefinedTableError:
        return {"status": "no_data_yet", "reason": "snapshot_table_missing",
                "source": "external_signal_daily", "window_days": window_days}
    except Exception as exc:  # no DSN, network, permissions: same answer, detail only in the log
        logger.warning("get_marketplace_stats: database unavailable (%s)", type(exc).__name__)
        return {"status": "no_data_yet", "reason": "database_unavailable",
                "source": "external_signal_daily", "window_days": window_days}
    return summarize_external_signals([dict(r) for r in rows], window_days, today)


def register_marketplace_tools(mcp: FastMCP, engine_path: Path | None = None) -> None:
    """Register ``get_marketplace_stats``.

    ``engine_path`` is accepted for compatibility and no longer used: the
    figures come from the database, never from the server's filesystem.
    """

    @mcp.tool
    async def get_marketplace_stats(
        window_days: int = 30,
        jsonl_content: str = "",
    ) -> dict[str, Any]:
        """Adoption seen from outside, from the daily snapshot in the database.

        Returns the VS Code Marketplace installs and updates of the extension
        (latest, growth over the window and daily series), the npm downloads
        of the ``specbox`` CLI in the window and the latest GitHub stars and
        forks of the engine repository. Public figures only: downloads and
        installs, not people. Zero PII.

        Args:
            window_days: Look-back window in days (default 30, 1–400).
            jsonl_content: Deprecated since v6.34.0 and ignored. The figures
                no longer come from a local file.

        Returns:
            ``status: "ok"`` with ``total_installs``, ``total_updates``,
            ``install_growth_pct``, ``daily_series``, ``npm`` and ``github``;
            or ``status: "no_data_yet"`` with a ``reason``.
        """
        return await fetch_marketplace_stats(window_days)
