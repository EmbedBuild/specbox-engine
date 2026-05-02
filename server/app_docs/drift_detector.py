"""Multi-source drift detector for `doc/app/app_*.md` (v5.29.0 PR-15).

Beyond the signature-based check from PR-11/PR-13 (which catches edits
that already happened to the docs themselves), this detector inspects
the project filesystem for drift between the canonical docs and the
actual project state. The signals are intentionally implicit — these
are things the engine cannot eventize because they happen outside
SpecBox tools (a developer adds a lockfile, a brand kit reference
becomes a dangling path, the user adds a feature in the code that the
roadmap never learned about).

Drift signals implemented in v5.29.0:

  S1. Stack change — new lockfile detected vs `app_spec.md` zone "stack".
  S2. Brand kit reference dangling — `app_spec.md` zone "brand_visual"
       points at a path that does not exist on disk.
  S3. Roadmap completed without backend evidence — `app_spec.md` zone
       "roadmap" claims a US is done but the tracking backend has no
       UC marked done for that US.
  S4. Canonical decision used but undocumented — a decision_key appears
       in `.quality/canonical_decisions.json` but is missing from
       `app_spec.md` zone "canonical_decisions".

Each detected drift entry is appended to `.quality/app_docs_drift.jsonl`
(same file the hook from PR-13 writes) and surfaced via the existing
heartbeat mechanism so it appears in Sala de Máquinas.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from .zones import parse_document, ZoneKind


KNOWN_LOCKFILES: dict[str, str] = {
    "pubspec.lock": "Flutter (pubspec.lock)",
    "package-lock.json": "Node.js (package-lock.json)",
    "yarn.lock": "Node.js (yarn.lock)",
    "pnpm-lock.yaml": "Node.js (pnpm-lock.yaml)",
    "bun.lockb": "Node.js (bun.lockb)",
    "uv.lock": "Python (uv.lock)",
    "poetry.lock": "Python (poetry.lock)",
    "Pipfile.lock": "Python (Pipfile.lock)",
    "go.sum": "Go (go.sum)",
    "Cargo.lock": "Rust (Cargo.lock)",
    "Gemfile.lock": "Ruby (Gemfile.lock)",
    "composer.lock": "PHP (composer.lock)",
}

DRIFT_LOG = ".quality/app_docs_drift.jsonl"
PRD_PATH = "doc/app/app_prd.md"
SPEC_PATH = "doc/app/app_spec.md"


@dataclass
class DriftSignal:
    code: str  # short identifier for the signal type (S1..S4)
    severity: str  # "info" | "warning" | "error"
    document: str  # "app_prd" | "app_spec" | "settings" | "tracking"
    zone_id: str | None
    message: str
    detected_at: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "document": self.document,
            "zone_id": self.zone_id,
            "message": self.message,
            "detected_at": self.detected_at,
            "details": self.details,
        }


# ── Detectors ────────────────────────────────────────────────────────


def _detect_stack_drift(project_path: Path) -> list[DriftSignal]:
    spec_path = project_path / SPEC_PATH
    if not spec_path.exists():
        return []
    doc = parse_document(spec_path)
    stack_zone = doc.zone_by_id("stack")
    if stack_zone is None:
        return []
    declared = stack_zone.body.lower()

    found_lockfiles: list[tuple[str, str]] = []
    for filename, label in KNOWN_LOCKFILES.items():
        if (project_path / filename).exists():
            found_lockfiles.append((filename, label))

    signals: list[DriftSignal] = []
    for filename, label in found_lockfiles:
        if filename.lower() in declared or label.lower() in declared:
            continue
        signals.append(
            DriftSignal(
                code="S1",
                severity="warning",
                document="app_spec",
                zone_id="stack",
                message=(
                    f"Lockfile {filename!r} present on disk but not mentioned in "
                    "app_spec.md zone 'stack'. Run `/app-sync --repair` to refresh."
                ),
                details={"lockfile": filename, "label": label},
            )
        )
    return signals


def _detect_brand_kit_drift(project_path: Path) -> list[DriftSignal]:
    spec_path = project_path / SPEC_PATH
    if not spec_path.exists():
        return []
    doc = parse_document(spec_path)
    zone = doc.zone_by_id("brand_visual")
    if zone is None:
        return []
    signals: list[DriftSignal] = []
    # Look for inline path references like `doc/design/brand_kit.md`.
    for match in re.finditer(r"`(?P<path>[^`\n]+\.md)`", zone.body):
        ref = match.group("path").strip()
        if ref.startswith("/"):
            continue  # absolute paths are out of scope
        full = project_path / ref
        if not full.exists():
            signals.append(
                DriftSignal(
                    code="S2",
                    severity="warning",
                    document="app_spec",
                    zone_id="brand_visual",
                    message=(
                        f"app_spec.md references {ref!r} which does not exist on disk."
                    ),
                    details={"missing_path": ref},
                )
            )
    return signals


def _detect_canonical_drift(project_path: Path) -> list[DriftSignal]:
    canonicals_path = project_path / ".quality" / "canonical_decisions.json"
    if not canonicals_path.exists():
        return []
    try:
        store = json.loads(canonicals_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    actives = [
        c for c in store.get("canonicals", []) if not c.get("invalidated_at")
    ]
    if not actives:
        return []

    spec_path = project_path / SPEC_PATH
    if not spec_path.exists():
        # Documenting decisions only matters if the user has the canonical doc.
        return []
    doc = parse_document(spec_path)
    zone = doc.zone_by_id("canonical_decisions")
    body = (zone.body if zone else "").lower()

    signals: list[DriftSignal] = []
    for entry in actives:
        key = entry.get("decision_key")
        if not key:
            continue
        if key.lower() in body:
            continue
        signals.append(
            DriftSignal(
                code="S4",
                severity="warning",
                document="app_spec",
                zone_id="canonical_decisions",
                message=(
                    f"Canonical decision {key!r} is active in "
                    ".quality/canonical_decisions.json but not documented in "
                    "app_spec.md zone 'canonical_decisions'."
                ),
                details={"decision_key": key, "value": entry.get("value")},
            )
        )
    return signals


def _detect_roadmap_drift(project_path: Path) -> list[DriftSignal]:
    """S3 — roadmap claims completed but no UC done in tracking.

    Implementation is intentionally narrow in v5.29.0: only checks
    the FreeForm backend (filesystem-readable). Trello/Plane variants
    require a live backend session and are deferred to v5.29.1.
    """
    prd_path = project_path / PRD_PATH
    items_path = project_path / "doc" / "tracking" / "items.json"
    if not prd_path.exists() or not items_path.exists():
        return []
    try:
        items = json.loads(items_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    completed_us = set()
    for item in items:
        if item.get("state") in ("done", "review"):
            us_id = (item.get("meta") or {}).get("us_id") or ""
            if us_id.startswith("US-"):
                completed_us.add(us_id)

    doc = parse_document(prd_path)
    zone = doc.zone_by_id("roadmap")
    if zone is None:
        return []
    signals: list[DriftSignal] = []
    # Look for "| US-XX | ... | done | ... |" rows in the markdown table.
    for row in re.finditer(r"\|\s*(?P<us>US-\d+)[^\n]*\|\s*(?P<state>done|completed)\s*\|", zone.body, re.IGNORECASE):
        us_id = row.group("us").upper()
        if us_id not in completed_us:
            signals.append(
                DriftSignal(
                    code="S3",
                    severity="warning",
                    document="app_prd",
                    zone_id="roadmap",
                    message=(
                        f"app_prd.md roadmap marks {us_id} as done but no UC for "
                        "that US is in state done/review in doc/tracking/items.json."
                    ),
                    details={"us_id": us_id},
                )
            )
    return signals


# ── Public API ───────────────────────────────────────────────────────


def run_drift_detection(project_path: str | Path = ".") -> dict[str, Any]:
    """Run every detector against the project and return a structured report."""
    root = Path(project_path).resolve()
    now = datetime.now(timezone.utc).isoformat()
    signals: list[DriftSignal] = []
    for detector in (
        _detect_stack_drift,
        _detect_brand_kit_drift,
        _detect_canonical_drift,
        _detect_roadmap_drift,
    ):
        for sig in detector(root):
            sig.detected_at = now
            signals.append(sig)

    if signals:
        log_path = root / DRIFT_LOG
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            for s in signals:
                f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")

    summary = {code: 0 for code in ("S1", "S2", "S3", "S4")}
    for s in signals:
        summary[s.code] = summary.get(s.code, 0) + 1

    return {
        "ok": True,
        "in_sync": not signals,
        "signal_count": len(signals),
        "summary_by_code": summary,
        "signals": [s.to_dict() for s in signals],
        "log_path": str(root / DRIFT_LOG) if signals else None,
        "detected_at": now,
    }


def heartbeat_payload(project_path: str | Path = ".") -> dict[str, Any]:
    """Compact summary suited for inclusion in heartbeat payloads."""
    report = run_drift_detection(project_path)
    return {
        "in_sync": report["in_sync"],
        "signal_count": report["signal_count"],
        "summary_by_code": report["summary_by_code"],
        "detected_at": report["detected_at"],
    }


# ── MCP registration ────────────────────────────────────────────────


def register_drift_tools(mcp: FastMCP, engine_path: Path) -> None:
    @mcp.tool
    def detect_app_docs_drift(project_path: str = ".") -> dict[str, Any]:
        """Run the multi-source drift detector against a project.

        Inspects the filesystem for signals that the canonical docs are
        out of sync with reality (S1 stack lockfiles, S2 dangling brand
        kit refs, S3 roadmap-vs-backend mismatch, S4 undocumented
        canonical decisions). Appends every detection to
        .quality/app_docs_drift.jsonl.

        Returns a structured report with summary counts and individual
        signals. Read-only with respect to the canonical docs themselves.
        """
        return run_drift_detection(project_path)

    @mcp.tool
    def app_docs_drift_for_heartbeat(project_path: str = ".") -> dict[str, Any]:
        """Compact drift summary suited for the heartbeat pipeline.

        Used by Sala de Máquinas to display per-project sync health
        across all onboarded projects.
        """
        return heartbeat_payload(project_path)
