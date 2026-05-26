"""MCP tools for VSCode Marketplace adoption telemetry.

v6.2.0 — UC-643 (US-VSCODE-MARKETPLACE). The client supplies the raw
``.quality/marketplace-stats.jsonl`` content (one JSON entry per day,
written by the ``marketplace-stats.yml`` GitHub Actions workflow). The
tool aggregates the entries inside the requested window and returns a
compact summary safe to render in a dashboard or chat reply.

**Privacy**: zero PII. The jsonl only contains public Marketplace stats
(installs, downloads, ratings, trending ranks) scraped from the
``extensionquery`` public REST endpoint. No data is collected from
end-user installs.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP


# Engine-side fallback location (only used when jsonl_content is empty
# and the MCP server happens to share the filesystem with the repo —
# typical for local stdio mode). Remote MCP callers MUST pass jsonl_content
# explicitly per the v6.0.1 Path Contract.
_FALLBACK_RELPATH = ".quality/marketplace-stats.jsonl"


def aggregate_marketplace_stats(
    jsonl_content: str,
    window_days: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Pure aggregation function — testable without an MCP instance.

    Args:
        jsonl_content: Raw jsonl text (one entry per line) from
            ``.quality/marketplace-stats.jsonl``.
        window_days: Look-back window in days.
        now: Override "current time" for deterministic tests. Defaults to
            ``datetime.now(timezone.utc)``.

    Returns:
        See ``get_marketplace_stats`` docstring.
    """
    now = now or datetime.now(timezone.utc)
    content = jsonl_content.strip()

    if not content:
        return {
            "status": "no_data_yet",
            "reason": "extension_not_published_or_no_stats",
            "window_days": window_days,
        }

    entries: list[dict[str, Any]] = []
    malformed = 0
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if isinstance(entry, dict) and "date" in entry:
                entries.append(entry)
            else:
                malformed += 1
        except json.JSONDecodeError:
            malformed += 1

    if not entries:
        return {
            "status": "no_data_yet",
            "reason": "jsonl_empty_or_malformed",
            "window_days": window_days,
            "malformed_lines": malformed,
        }

    cutoff = now - timedelta(days=window_days)
    in_window: list[dict[str, Any]] = []
    for e in entries:
        try:
            d = e["date"].replace("Z", "+00:00")
            ts = datetime.fromisoformat(d)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                in_window.append(e)
        except (KeyError, ValueError, TypeError):
            malformed += 1

    if not in_window:
        return {
            "status": "no_data_yet",
            "reason": "no_entries_within_window",
            "window_days": window_days,
            "entries_total_in_file": len(entries),
        }

    in_window.sort(key=lambda e: e["date"])
    first = in_window[0]
    last = in_window[-1]

    first_installs = int(first.get("installs", 0))
    last_installs = int(last.get("installs", 0))
    install_growth_pct = (
        ((last_installs - first_installs) / first_installs * 100.0)
        if first_installs > 0
        else 0.0
    )

    daily_series = [
        {
            "date": e["date"],
            "installs": int(e.get("installs", 0)),
            "delta": int(e.get("delta_installs_24h", 0)),
        }
        for e in in_window
    ]

    return {
        "status": "ok",
        "total_installs": last_installs,
        "total_downloads": int(last.get("downloads", 0)),
        "avg_rating": float(last.get("avg_rating", 0.0)),
        "rating_count": int(last.get("rating_count", 0)),
        "install_growth_pct": round(install_growth_pct, 2),
        "daily_series": daily_series,
        "current_trending_rank": {
            "daily": int(last.get("trending_daily", 0)),
            "weekly": int(last.get("trending_weekly", 0)),
            "monthly": int(last.get("trending_monthly", 0)),
        },
        "window_days": window_days,
        "entries_count": len(in_window),
        "malformed_lines_skipped": malformed,
    }


def register_marketplace_tools(mcp: FastMCP, engine_path: Path | None = None) -> None:
    """Register the marketplace stats tool with the MCP server.

    Args:
        mcp: FastMCP instance.
        engine_path: Optional engine repo root. When provided, used as a
            fallback to read the jsonl from disk if the caller did not
            supply ``jsonl_content``. In remote MCP deployments this path
            points to the *server's* filesystem (not the client's), so it
            is only useful for local stdio sessions.
    """

    @mcp.tool
    def get_marketplace_stats(
        window_days: int = 30,
        jsonl_content: str = "",
    ) -> dict[str, Any]:
        """Aggregate VSCode Marketplace adoption stats over a time window.

        **v6.0.1 content-passing API**: the client reads
        ``.quality/marketplace-stats.jsonl`` locally and passes its
        contents via ``jsonl_content``. The tool parses, filters by
        date window, and returns aggregated metrics. Zero PII.

        Args:
            window_days: Look-back window in days (default 30). Entries
                older than this are excluded from the aggregation.
            jsonl_content: Raw content of
                ``.quality/marketplace-stats.jsonl`` (one JSON object per
                line). Pass empty to attempt an engine-side fallback read
                (only works in local stdio MCP mode).

        Returns:
            See :func:`aggregate_marketplace_stats`.
        """
        content = jsonl_content.strip()
        if not content and engine_path is not None:
            fallback = engine_path / _FALLBACK_RELPATH
            if fallback.exists():
                content = fallback.read_text(encoding="utf-8").strip()

        return aggregate_marketplace_stats(content, window_days=window_days)
