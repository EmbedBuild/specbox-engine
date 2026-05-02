"""Pure aggregation of stitch_usage.jsonl entries.

Stitch advertises two quotas: Standard (Flash, 350/mo) and Experimental
(Pro, 200/mo). We count only ``status=ok`` entries that performed actual
generations (``stitch_generate_screen*``, ``stitch_edit_screen*``,
``stitch_generate_variants``, ``stitch_build_site*``). Read-only tools
(``list_projects``, ``get_screen``, ...) and metadata operations
(``set_api_key``, ``generate_design_md``, ``validate_stitch_prompt``)
do not count against quota.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_LIMIT_STANDARD = 350
DEFAULT_LIMIT_EXPERIMENTAL = 200

# Tool names that consume Stitch generation quota. Anything outside
# this set (telemetry, validation, list/read tools) is free.
_GENERATION_TOOLS = frozenset(
    {
        "stitch_generate_screen",
        "stitch_generate_screen_v2",
        "stitch_edit_screen",
        "stitch_edit_screens",
        "stitch_generate_variants",
        "stitch_build_site",
        "stitch_build_site_batched_v2",
        # Internal strategy events from the fallback chain still need
        # to count individually in our books because each one was a
        # generation call. The orchestration layer logs final attempt
        # counts in the parent entry, so we don't double-count.
    }
)


@dataclass
class QuotaSnapshot:
    """Computed quota state for one month."""

    month: str  # YYYY-MM
    standard_used: int
    standard_limit: int
    experimental_used: int
    experimental_limit: int

    @property
    def standard_pct(self) -> float:
        return (self.standard_used / self.standard_limit) * 100 if self.standard_limit else 0.0

    @property
    def experimental_pct(self) -> float:
        return (
            (self.experimental_used / self.experimental_limit) * 100
            if self.experimental_limit
            else 0.0
        )


@dataclass
class QuotaPayload:
    """Snapshot + flags ready for MCP/heartbeat surfacing."""

    snapshot: QuotaSnapshot
    warning: str | None = None
    summary: str = ""
    reset_at: str = ""


# ── Classification ─────────────────────────────────────────────────────


def classify_model(model_id: str | None) -> str:
    """Return ``standard`` for Flash variants, ``experimental`` for Pro,
    ``unknown`` otherwise. Defaults to ``experimental`` when ``model_id``
    is falsy because PRO is SpecBox's current default."""

    if not model_id:
        return "experimental"
    m = model_id.upper()
    if "FLASH" in m:
        return "standard"
    if "PRO" in m:
        return "experimental"
    return "unknown"


# ── Aggregation ────────────────────────────────────────────────────────


def compute_quota(
    entries: Iterable[dict],
    *,
    month: str | None = None,
    standard_limit: int = DEFAULT_LIMIT_STANDARD,
    experimental_limit: int = DEFAULT_LIMIT_EXPERIMENTAL,
) -> QuotaSnapshot:
    """Tally generation calls in the chosen month.

    ``month`` defaults to the current UTC month (YYYY-MM). Entries with
    invalid timestamps or missing ``tool`` are skipped. Entries with
    ``status`` other than ``ok`` are skipped — they didn't consume.
    """

    if month is None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

    standard = 0
    experimental = 0

    for raw in entries:
        if not isinstance(raw, dict):
            continue
        tool = raw.get("tool")
        if tool not in _GENERATION_TOOLS:
            continue
        if raw.get("status", "ok") != "ok":
            continue
        ts = raw.get("ts") or raw.get("timestamp")
        if not isinstance(ts, str) or not ts.startswith(month):
            continue
        klass = classify_model(raw.get("model_id") or raw.get("model"))
        if klass == "standard":
            standard += 1
        elif klass == "experimental":
            experimental += 1
        # unknown is intentionally not counted — better undercount than
        # overcount; surfaces in telemetry but doesn't block work.

    return QuotaSnapshot(
        month=month,
        standard_used=standard,
        standard_limit=standard_limit,
        experimental_used=experimental,
        experimental_limit=experimental_limit,
    )


def compute_quota_payload(
    entries: Iterable[dict],
    *,
    month: str | None = None,
    warn_pct: float = 80.0,
    standard_limit: int = DEFAULT_LIMIT_STANDARD,
    experimental_limit: int = DEFAULT_LIMIT_EXPERIMENTAL,
) -> QuotaPayload:
    """Snapshot + derived warning + summary string."""

    snap = compute_quota(
        entries,
        month=month,
        standard_limit=standard_limit,
        experimental_limit=experimental_limit,
    )

    warning: str | None = None
    if snap.experimental_pct >= 100.0:
        warning = (
            "PRO quota exhausted this month. Enable flash_safety_net or "
            "wait until reset."
        )
    elif snap.experimental_pct >= warn_pct:
        warning = (
            f"PRO quota at {snap.experimental_pct:.0f}% — only "
            f"{snap.experimental_limit - snap.experimental_used} generations left."
        )
    elif snap.standard_pct >= warn_pct:
        warning = (
            f"Flash quota at {snap.standard_pct:.0f}% — "
            "consider deferring trivial generations."
        )

    summary = (
        f"PRO {snap.experimental_used}/{snap.experimental_limit} "
        f"({snap.experimental_pct:.0f}%) · Flash "
        f"{snap.standard_used}/{snap.standard_limit} "
        f"({snap.standard_pct:.0f}%)"
    )

    return QuotaPayload(
        snapshot=snap,
        warning=warning,
        summary=summary,
        reset_at=_next_month_first_day(snap.month),
    )


def _next_month_first_day(month: str) -> str:
    """Given ``YYYY-MM``, return the ISO-8601 timestamp of the first
    day of the *next* month (UTC, 00:00:00)."""

    year, mon = (int(p) for p in month.split("-"))
    if mon == 12:
        return f"{year + 1}-01-01T00:00:00Z"
    return f"{year}-{mon + 1:02d}-01T00:00:00Z"


# ── File loader (used by the MCP tool) ─────────────────────────────────


def load_entries(jsonl_path: Path) -> list[dict]:
    """Read a JSONL file, returning a list of dicts. Bad lines are skipped."""

    if not jsonl_path.exists():
        return []
    out: list[dict] = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    out.append(obj)
            except json.JSONDecodeError:
                continue
    return out
