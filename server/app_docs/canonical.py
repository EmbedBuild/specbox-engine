"""Canonical decisions store (v5.29.0 PR-7).

When the user confirms the same decision N consecutive times for the
same `decision_key` in a project, the engine offers to convert it to a
**canonical decision** — a value reused on subsequent runs without
asking. Canonicals are cleared automatically when project context
shifts (e.g. stack change invalidates VEG-related decisions).

Storage: `.quality/canonical_decisions.json` is the source of truth.
A human-friendly mirror appears in `doc/app/app_spec.md` zone
`canonical_decisions` (kind=hybrid append-only) for visibility — the
sync layer (PR-11+) will keep them aligned.

Engram is not required: SpecBox projects without the Engram MCP still
get the same behavior locally. If Engram is available, callers can
also `mem_save` with topic_key="autopilot/{project}/{decision_key}"
for cross-session memory beyond the project repo.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP


CANONICAL_FILE = ".quality/canonical_decisions.json"
DEFAULT_PROMOTION_THRESHOLD = 3  # consecutive identical confirmations


@dataclass
class CanonicalDecision:
    decision_key: str
    value: str
    promoted_at: str  # ISO 8601 UTC
    confirmations: int  # how many identical user confirmations were observed
    last_seen: str  # ISO 8601 UTC of the last time the engine applied this
    invalidated_at: str | None = None
    invalidation_reason: str | None = None


@dataclass
class _Counter:
    """Tracks consecutive identical confirmations for a not-yet-canonical key."""

    decision_key: str
    last_value: str
    streak: int
    updated_at: str


def _store_path(project_path: Path | str = ".") -> Path:
    return Path(project_path) / CANONICAL_FILE


def _load_store(project_path: Path | str = ".") -> dict[str, Any]:
    path = _store_path(project_path)
    if not path.exists():
        return {"canonicals": [], "counters": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"canonicals": [], "counters": []}


def _save_store(store: dict[str, Any], project_path: Path | str = ".") -> None:
    path = _store_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Public API ───────────────────────────────────────────────────────


def get_canonical(decision_key: str, project_path: str | Path = ".") -> CanonicalDecision | None:
    """Return the active canonical decision for ``decision_key`` or None."""
    store = _load_store(project_path)
    for entry in store.get("canonicals", []):
        if entry["decision_key"] != decision_key:
            continue
        if entry.get("invalidated_at"):
            continue
        return CanonicalDecision(**entry)
    return None


def list_canonicals(project_path: str | Path = ".") -> list[dict[str, Any]]:
    """List all canonicals (including invalidated, for audit)."""
    store = _load_store(project_path)
    return list(store.get("canonicals", []))


def record_confirmation(
    decision_key: str,
    value: str,
    *,
    project_path: str | Path = ".",
    promotion_threshold: int = DEFAULT_PROMOTION_THRESHOLD,
) -> dict[str, Any]:
    """Record a user confirmation. Promote to canonical if streak hits threshold.

    Returns:
        {
          "promoted": bool,         # whether this confirmation triggered promotion
          "canonical": dict | None, # the canonical entry if promoted or already existed
          "streak": int,            # current consecutive streak for this value
          "threshold": int,
        }
    """
    store = _load_store(project_path)
    canonicals = store.setdefault("canonicals", [])
    counters = store.setdefault("counters", [])

    # If a canonical already exists for this key, just bump last_seen and return.
    for entry in canonicals:
        if entry["decision_key"] != decision_key or entry.get("invalidated_at"):
            continue
        if entry["value"] != value:
            # User picked a different value than the canonical — invalidate
            # the existing one and start a fresh counter.
            entry["invalidated_at"] = _now()
            entry["invalidation_reason"] = "user_chose_different_value"
            counters = [c for c in counters if c["decision_key"] != decision_key]
            store["counters"] = counters
            break  # fall through to counter logic below
        entry["last_seen"] = _now()
        entry["confirmations"] += 1
        _save_store(store, project_path)
        return {
            "promoted": False,
            "canonical": dict(entry),
            "streak": entry["confirmations"],
            "threshold": promotion_threshold,
        }

    # No active canonical — work the counters.
    counter: dict[str, Any] | None = None
    for c in counters:
        if c["decision_key"] == decision_key:
            counter = c
            break

    if counter is None:
        counter = {"decision_key": decision_key, "last_value": value, "streak": 1, "updated_at": _now()}
        counters.append(counter)
    elif counter["last_value"] == value:
        counter["streak"] += 1
        counter["updated_at"] = _now()
    else:
        counter["last_value"] = value
        counter["streak"] = 1
        counter["updated_at"] = _now()

    promoted = False
    canonical_entry: dict[str, Any] | None = None
    if counter["streak"] >= promotion_threshold:
        canonical_entry = {
            "decision_key": decision_key,
            "value": value,
            "promoted_at": _now(),
            "confirmations": counter["streak"],
            "last_seen": _now(),
            "invalidated_at": None,
            "invalidation_reason": None,
        }
        canonicals.append(canonical_entry)
        store["counters"] = [c for c in counters if c["decision_key"] != decision_key]
        promoted = True

    _save_store(store, project_path)
    return {
        "promoted": promoted,
        "canonical": dict(canonical_entry) if canonical_entry else None,
        "streak": counter["streak"],
        "threshold": promotion_threshold,
    }


def invalidate_canonical(
    decision_key: str,
    *,
    reason: str,
    project_path: str | Path = ".",
) -> dict[str, Any]:
    """Mark a canonical as invalidated. Subsequent get_canonical returns None."""
    store = _load_store(project_path)
    for entry in store.get("canonicals", []):
        if entry["decision_key"] != decision_key or entry.get("invalidated_at"):
            continue
        entry["invalidated_at"] = _now()
        entry["invalidation_reason"] = reason
        _save_store(store, project_path)
        return {"ok": True, "entry": dict(entry)}
    return {"ok": False, "error": "no_active_canonical_for_key", "decision_key": decision_key}


def revoke_canonical(decision_key: str, project_path: str | Path = ".") -> dict[str, Any]:
    """User-facing: hard-revoke a canonical (clears the entry entirely)."""
    store = _load_store(project_path)
    before = len(store.get("canonicals", []))
    store["canonicals"] = [
        e
        for e in store.get("canonicals", [])
        if e["decision_key"] != decision_key or e.get("invalidated_at")
    ]
    after = len(store["canonicals"])
    if before == after:
        return {"ok": False, "error": "no_active_canonical_for_key", "decision_key": decision_key}
    _save_store(store, project_path)
    return {"ok": True, "removed": before - after}


# ── MCP registration ─────────────────────────────────────────────────


def register_canonical_tools(mcp: FastMCP, engine_path: Path) -> None:
    """Expose canonical-decisions store as MCP tools."""

    @mcp.tool
    def get_canonical_decision(
        decision_key: str, project_path: str = "."
    ) -> dict[str, Any] | None:
        """Return the active canonical decision for a decision_key, or None.

        Skills consult this before asking the user. If a canonical exists,
        the skill applies its value silently and skips the question.
        """
        canonical = get_canonical(decision_key, project_path)
        return asdict(canonical) if canonical else None

    @mcp.tool
    def record_canonical_confirmation(
        decision_key: str,
        value: str,
        project_path: str = ".",
        promotion_threshold: int = DEFAULT_PROMOTION_THRESHOLD,
    ) -> dict[str, Any]:
        """Record that the user confirmed a particular value for a decision_key.

        After ``promotion_threshold`` consecutive identical confirmations
        (default 3), the value is promoted to a canonical decision and
        will be reused without asking on subsequent runs.

        If the user picks a different value than the existing canonical,
        the canonical is auto-invalidated and a fresh counter starts.
        """
        return record_confirmation(
            decision_key,
            value,
            project_path=project_path,
            promotion_threshold=promotion_threshold,
        )

    @mcp.tool
    def list_canonical_decisions(project_path: str = ".") -> list[dict[str, Any]]:
        """List all canonical decisions for a project (active + invalidated)."""
        return list_canonicals(project_path)

    @mcp.tool
    def revoke_canonical_decision(
        decision_key: str, project_path: str = "."
    ) -> dict[str, Any]:
        """Hard-revoke a canonical decision (user-driven). Returns ok status."""
        return revoke_canonical(decision_key, project_path)
