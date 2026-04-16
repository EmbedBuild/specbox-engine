"""Internal helpers shared by Tier 1-4 mutation tool modules.

Not registered as MCP tools. Imported by:
- server/tools/spec_mutations.py (Tier 1)
- server/tools/milestone_management.py (Tier 2, future)
- server/tools/board_operations.py (Tier 3, future)
- server/tools/acceptance_automation.py (Tier 4, future)

See doc/design/v5.23.0-full-mutations.md — section "Shared helpers".
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ..spec_backend import ChecklistItemDTO, ItemDTO, SpecBackend, parse_item_id

# ── Constants ────────────────────────────────────────────────────────

MILESTONES: tuple[str, ...] = ("H1", "H2", "H3", "H4")
LINK_TYPES: tuple[str, ...] = (
    "absorbs",
    "blocks",
    "depends_on",
    "supersedes",
    "related_to",
)
VERDICT_TYPES: tuple[str, ...] = ("ACCEPTED", "CONDITIONAL", "REJECTED")
DEFAULT_MILESTONE_TARGETS: dict[str, float] = {
    "H1": 0.30,
    "H2": 0.25,
    "H3": 0.25,
    "H4": 0.20,
}


def utc_now_iso() -> str:
    """ISO 8601 UTC timestamp with seconds precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── Validators ───────────────────────────────────────────────────────


def validate_milestone(value: str) -> tuple[bool, str | None]:
    """Check if value is a valid milestone key."""
    if value in MILESTONES:
        return True, None
    return False, f"Milestone must be one of {MILESTONES}, got {value!r}"


def validate_link_type(value: str) -> tuple[bool, str | None]:
    """Check if value is a valid UC link type."""
    if value in LINK_TYPES:
        return True, None
    return False, f"Link type must be one of {LINK_TYPES}, got {value!r}"


def validate_satellite(
    value: str, settings_path: Path | None
) -> tuple[bool, str | None]:
    """Check that `value` is a declared satellite key in orchestrator settings.

    If settings_path is None or does not exist, any non-empty string is
    accepted (freeform projects without a multirepo config).
    """
    if not value:
        return False, "Satellite key must be a non-empty string"

    if settings_path is None or not Path(settings_path).exists():
        return True, None

    try:
        data = json.loads(Path(settings_path).read_text())
    except (OSError, json.JSONDecodeError) as e:
        return False, f"Failed to read settings at {settings_path}: {e}"

    satellites = (
        data.get("multirepo", {}).get("satellites", {}) if isinstance(data, dict) else {}
    )
    if not isinstance(satellites, dict) or not satellites:
        # No satellites declared → accept (backwards-compatible)
        return True, None

    if value in satellites:
        return True, None
    declared = sorted(satellites.keys())
    return False, f"Satellite {value!r} not declared in settings; declared: {declared}"


def validate_ac_text(text: str) -> list[str]:
    """Return a list of issue tags for an AC text. Empty list = passes.

    Rules:
    - `too_short`: text < 10 chars
    - `vague`: text < 20 chars (but >= 10)
    - `not_testable`: missing both Gherkin (Dado/Cuando/Entonces) and any
       measurable assertion (comparators, "debe", "must")
    """
    issues: list[str] = []
    stripped = (text or "").strip()
    if len(stripped) < 10:
        issues.append("too_short")
    elif len(stripped) < 20:
        issues.append("vague")

    lower = stripped.lower()
    has_gherkin = any(kw in lower for kw in ("dado ", "cuando ", "entonces "))
    has_measurable = bool(
        re.search(r"[<>]=?\s*\d|\d\s*%|\bdebe\b|\bmust\b", lower)
    )
    if not has_gherkin and not has_measurable:
        issues.append("not_testable")

    return issues


# ── Item finders (thin wrappers over list_items) ─────────────────────


async def find_uc(
    backend: SpecBackend, board_id: str, uc_id: str
) -> ItemDTO | None:
    """Find a UC by its spec id (e.g. 'UC-001')."""
    return await backend.find_item_by_field(board_id, "uc_id", uc_id)


async def find_us(
    backend: SpecBackend, board_id: str, us_id: str
) -> ItemDTO | None:
    """Find a US by its spec id (e.g. 'US-01')."""
    return await backend.find_item_by_field(board_id, "us_id", us_id)


async def find_ac(
    backend: SpecBackend, board_id: str, uc_item_id: str, ac_id: str
) -> ChecklistItemDTO | None:
    """Find an AC on a UC by its spec id (e.g. 'AC-01')."""
    try:
        acs = await backend.get_acceptance_criteria(board_id, uc_item_id)
    except Exception:
        return None
    for ac in acs:
        if ac.id == ac_id:
            return ac
    return None


async def find_max_uc_number(backend: SpecBackend, board_id: str) -> int:
    """Scan all items and return the max UC numeric suffix (e.g. 27 for UC-027).

    Returns 0 if no UCs exist.
    """
    items = await backend.list_items(board_id)
    max_num = 0
    for item in items:
        uc_id = item.meta.get("uc_id") or parse_item_id(item.name, "UC")[0]
        if not uc_id or not uc_id.startswith("UC-"):
            continue
        try:
            num = int(uc_id.split("-")[1])
        except (IndexError, ValueError):
            continue
        if num > max_num:
            max_num = num
    return max_num


def next_ac_id(existing: list[ChecklistItemDTO]) -> str:
    """Compute the next AC-NN id from a list of existing ACs."""
    max_num = 0
    for ac in existing:
        if not ac.id or not ac.id.startswith("AC-"):
            continue
        try:
            num = int(ac.id.split("-")[1])
        except (IndexError, ValueError):
            continue
        if num > max_num:
            max_num = num
    return f"AC-{max_num + 1:02d}"


def format_uc_id(number: int) -> str:
    """Format a UC number as 'UC-NNN' (zero-padded to 3 digits)."""
    return f"UC-{number:03d}"


# ── Meta merge (only-non-None semantics) ─────────────────────────────


def merge_meta(
    existing: dict[str, Any] | None, updates: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Merge `updates` into `existing`, returning (merged, changed_fields).

    Only keys with non-None values in `updates` are applied. A key is
    listed in `changed_fields` only if the new value differs from the
    existing value (list/dict equality is deep via `==`).
    """
    merged: dict[str, Any] = dict(existing or {})
    changed: list[str] = []
    for key, new_val in updates.items():
        if new_val is None:
            continue
        old_val = merged.get(key)
        if old_val != new_val:
            merged[key] = new_val
            changed.append(key)
    return merged, changed


# ── AC classification (for estimate_from_ac, validate_ac_quality) ────


_SIMPLE_KEYWORDS = ("valida", "muestra", "lista", "abre", "renderiza", "visualiza")
_INTEGRATION_KEYWORDS = ("integra", "api", "sync", "llama a", "webhook", "endpoint")
_E2E_KEYWORDS = (
    "load test",
    "<200ms",
    "e2e",
    "end-to-end",
    "rendimiento",
    "performance",
    "stress",
)


def classify_ac(text: str) -> Literal["simple", "integration", "e2e"]:
    """Classify an AC by its text.

    Order of checks: e2e → integration → simple (most specific first).
    Default: simple.
    """
    lower = (text or "").lower()
    for kw in _E2E_KEYWORDS:
        if kw in lower:
            return "e2e"
    for kw in _INTEGRATION_KEYWORDS:
        if kw in lower:
            return "integration"
    for kw in _SIMPLE_KEYWORDS:
        if kw in lower:
            return "simple"
    return "simple"


# ── Milestone distribution math ──────────────────────────────────────


def compute_distribution(
    items: list[ItemDTO], ac_counts: dict[str, int]
) -> dict[str, dict[str, Any]]:
    """Compute per-milestone distribution from a list of UCs.

    Args:
        items: list of UC ItemDTOs with optional meta["milestone"]
        ac_counts: mapping uc_id -> number of ACs

    Returns:
        {
            "H1": {"ucs": [uc_id, ...], "ac_count": int, "pct_acs": float},
            ...
        }
    """
    distribution: dict[str, dict[str, Any]] = {
        m: {"ucs": [], "ac_count": 0, "pct_acs": 0.0} for m in MILESTONES
    }
    total_acs = 0
    for item in items:
        milestone = item.meta.get("milestone")
        if milestone not in MILESTONES:
            continue
        uc_id = item.meta.get("uc_id") or parse_item_id(item.name, "UC")[0]
        if not uc_id:
            continue
        ac_count = int(ac_counts.get(uc_id, 0))
        bucket = distribution[milestone]
        bucket["ucs"].append(uc_id)
        bucket["ac_count"] = int(bucket["ac_count"]) + ac_count
        total_acs += ac_count

    if total_acs > 0:
        for bucket in distribution.values():
            bucket["pct_acs"] = round(
                int(bucket["ac_count"]) / total_acs, 4
            )

    return distribution


# ── Settings path resolution ─────────────────────────────────────────


def settings_path_from_env() -> Path | None:
    """Resolve the orchestrator settings.local.json path from the environment.

    Looks at `SPECBOX_PROJECT_ROOT` first, then the current working dir.
    Returns None if no settings.local.json is found.
    """
    import os

    candidates: list[Path] = []
    root = os.getenv("SPECBOX_PROJECT_ROOT")
    if root:
        candidates.append(Path(root) / ".claude" / "settings.local.json")
    candidates.append(Path.cwd() / ".claude" / "settings.local.json")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
