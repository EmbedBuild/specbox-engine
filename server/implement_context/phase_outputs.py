"""Append-only structured deltas per Task to phase_outputs.jsonl (v5.32.0).

Each Task delegated by /implement writes one line to
``.quality/evidence/{feature}/phase_outputs.jsonl`` capturing what
files it touched, how long it ran, and any healing attempts. The
orchestrator no longer needs to read ``git diff`` from its own session
to know what each phase did — it reads this JSONL.

Spec-Code Sync (Paso 5.1.1b / 8.5.1a) consumes ``aggregate_for_spec_sync``
which collapses the per-phase entries into the shape that
``write_implementation_status`` expects.

Format contract: ``doc/specs/phase-outputs-spec.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

PHASE_OUTPUTS_FILENAME = "phase_outputs.jsonl"
EVIDENCE_DIR = Path(".quality/evidence")
SCHEMA_VERSION = 1


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


# ── Model ──────────────────────────────────────────────────────────────


class PhaseOutput(BaseModel):
    """One Task's structured report. Validated by Pydantic so a
    malformed line is loud rather than silent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    ts: str = Field(default_factory=_now)
    phase: str  # e.g. "feature", "db", "design-to-code"
    phase_index: int  # 1-indexed; matches the SKILL.md phase order
    agent: str  # e.g. "AG-01"
    task_id: str | None = None  # uuid; optional for legacy entries
    duration_s: float | None = None
    status: str  # ok | error | partial
    files_created: list[str] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    files_deleted: list[str] = Field(default_factory=list)
    summary: str = ""  # human-readable 1-3 sentence summary
    tokens_used_prompt: int | None = None
    tokens_used_response: int | None = None
    healing_attempts: int = 0
    error: str | None = None


# ── Path resolution ────────────────────────────────────────────────────


def phase_outputs_path(
    feature_slug: str, project_root: Path | str | None = None
) -> Path:
    base = Path(project_root).expanduser().resolve() if project_root else Path.cwd()
    return base / EVIDENCE_DIR / feature_slug / PHASE_OUTPUTS_FILENAME


# ── Public API ─────────────────────────────────────────────────────────


def append_phase_output(
    feature_slug: str,
    payload: dict[str, Any] | PhaseOutput,
    project_root: Path | str | None = None,
) -> Path:
    """Append a validated PhaseOutput line to the JSONL file.

    ``payload`` may be either a dict or a PhaseOutput instance.
    Validation happens here — invalid payloads raise ValidationError
    rather than silently writing garbage.
    """

    if isinstance(payload, PhaseOutput):
        entry = payload
    else:
        entry = PhaseOutput.model_validate(payload)

    path = phase_outputs_path(feature_slug, project_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(entry.model_dump(exclude_none=True), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return path


def read_phase_outputs(
    feature_slug: str,
    project_root: Path | str | None = None,
) -> list[PhaseOutput]:
    """Load all entries. Skip and ignore corrupt lines (loud only when
    the entire file is unreadable)."""

    path = phase_outputs_path(feature_slug, project_root)
    if not path.exists():
        return []

    out: list[PhaseOutput] = []
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                out.append(PhaseOutput.model_validate(obj))
            except (json.JSONDecodeError, ValueError):
                # Skip malformed lines; the validator script catches
                # them in CI when contracts matter.
                continue
    return out


# ── Aggregation for Spec-Code Sync ─────────────────────────────────────


@dataclass
class SpecSyncAggregate:
    """The shape that ``write_implementation_status`` expects.

    Mirrors the structure used in v5.0 Spec-Code Sync but built from
    phase_outputs.jsonl rather than from the orchestrator's git diff.
    """

    feature_slug: str
    overall_status: str  # ok | partial | error
    delta_count: int
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    phases: list[dict] = field(default_factory=list)
    total_duration_s: float = 0.0
    total_healing_attempts: int = 0


def aggregate_for_spec_sync(
    feature_slug: str,
    project_root: Path | str | None = None,
) -> SpecSyncAggregate:
    """Collapse phase_outputs.jsonl into a single aggregate.

    Files lists are deduped while preserving first-seen order across
    phases. ``overall_status`` is "error" if any phase errored,
    "partial" if any was partial, else "ok".
    """

    entries = read_phase_outputs(feature_slug, project_root)

    seen_created: set[str] = set()
    seen_modified: set[str] = set()
    seen_deleted: set[str] = set()
    files_created: list[str] = []
    files_modified: list[str] = []
    files_deleted: list[str] = []
    total_duration = 0.0
    total_healing = 0
    statuses: set[str] = set()
    phases: list[dict] = []

    for e in entries:
        statuses.add(e.status)
        total_duration += e.duration_s or 0.0
        total_healing += e.healing_attempts
        for p in e.files_created:
            if p not in seen_created:
                seen_created.add(p)
                files_created.append(p)
        for p in e.files_modified:
            if p not in seen_modified:
                seen_modified.add(p)
                files_modified.append(p)
        for p in e.files_deleted:
            if p not in seen_deleted:
                seen_deleted.add(p)
                files_deleted.append(p)
        phases.append(
            {
                "phase": e.phase,
                "phase_index": e.phase_index,
                "agent": e.agent,
                "status": e.status,
                "summary": e.summary,
                "duration_s": e.duration_s,
                "files_touched": (
                    len(e.files_created)
                    + len(e.files_modified)
                    + len(e.files_deleted)
                ),
                "healing_attempts": e.healing_attempts,
            }
        )

    if "error" in statuses:
        overall = "error"
    elif "partial" in statuses:
        overall = "partial"
    else:
        overall = "ok" if entries else "empty"

    delta_count = (
        len(files_created) + len(files_modified) + len(files_deleted)
    )

    return SpecSyncAggregate(
        feature_slug=feature_slug,
        overall_status=overall,
        delta_count=delta_count,
        files_created=files_created,
        files_modified=files_modified,
        files_deleted=files_deleted,
        phases=phases,
        total_duration_s=round(total_duration, 2),
        total_healing_attempts=total_healing,
    )
