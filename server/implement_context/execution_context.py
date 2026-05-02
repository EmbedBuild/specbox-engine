"""Read/write helpers for ``.quality/evidence/{feature}/execution_context.json``.

Pure I/O on a tiny JSON document. Schema validated by Pydantic so the
file format errors are loud rather than silent. Writers are atomic
(``tempfile + os.replace``) so a crash mid-write never leaves a partial
file readable to a Task that's about to start.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1
CONTEXT_FILENAME = "execution_context.json"
EVIDENCE_DIR = Path(".quality/evidence")


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


# ── Model ──────────────────────────────────────────────────────────────


class ExecutionContext(BaseModel):
    """Frozen-by-convention context for one /implement run.

    Only ``last_updated_at`` is expected to mutate during execution;
    everything else is set at Paso 0.4b and never re-written. Tasks
    are expected to read this file rather than receive these values
    in their prompt body.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    feature_slug: str
    uc_id: str | None = None
    us_id: str | None = None
    branch: str
    base_branch: str = "main"
    stack: str  # flutter | react | python | go | google-apps-script | ...
    backend_type: str = "freeform"  # freeform | trello | plane
    board_id: str | None = None
    project_name: str
    project_root_absolute: str
    plan_path: str | None = None
    plan_hash: str | None = None
    started_at: str = Field(default_factory=_now)
    last_updated_at: str = Field(default_factory=_now)
    engine_version: str
    autopilot_level: str | None = None  # low | conservador | equilibrado | agresivo


# ── Path resolution ────────────────────────────────────────────────────


def context_path(feature_slug: str, project_root: Path | str | None = None) -> Path:
    """Resolve the path to ``execution_context.json`` for a feature.

    Defaults to the current working directory if ``project_root`` is
    not provided — useful from the orchestrator session where ``cwd``
    is the project root anyway. Tasks running in isolation should
    pass ``project_root`` explicitly to avoid surprises.
    """

    base = Path(project_root).expanduser().resolve() if project_root else Path.cwd()
    return base / EVIDENCE_DIR / feature_slug / CONTEXT_FILENAME


# ── Public API ─────────────────────────────────────────────────────────


def write_execution_context(
    feature_slug: str,
    *,
    branch: str,
    stack: str,
    project_name: str,
    project_root_absolute: str,
    engine_version: str,
    base_branch: str = "main",
    backend_type: str = "freeform",
    board_id: str | None = None,
    uc_id: str | None = None,
    us_id: str | None = None,
    plan_path: str | None = None,
    plan_hash: str | None = None,
    autopilot_level: str | None = None,
    project_root: Path | str | None = None,
) -> Path:
    """Atomically write the context file. Returns the resolved path.

    Idempotent: if the file already exists with the same content
    (modulo ``last_updated_at``), no write happens. This keeps
    re-runs of /implement from churning the file unnecessarily.
    """

    ctx = ExecutionContext(
        feature_slug=feature_slug,
        branch=branch,
        base_branch=base_branch,
        stack=stack,
        backend_type=backend_type,
        board_id=board_id,
        uc_id=uc_id,
        us_id=us_id,
        project_name=project_name,
        project_root_absolute=project_root_absolute,
        plan_path=plan_path,
        plan_hash=plan_hash,
        engine_version=engine_version,
        autopilot_level=autopilot_level,
    )

    path = context_path(feature_slug, project_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = ctx.model_dump(exclude_none=True)
    new_serialised = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)

    # Idempotency: skip the write if the only difference would be timestamps.
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            existing.pop("started_at", None)
            existing.pop("last_updated_at", None)
            stripped_new = {**payload}
            stripped_new.pop("started_at", None)
            stripped_new.pop("last_updated_at", None)
            if existing == stripped_new:
                return path
        except (OSError, json.JSONDecodeError):
            pass  # corrupt file → overwrite

    _atomic_write(path, new_serialised)
    return path


def read_execution_context(
    feature_slug: str, project_root: Path | str | None = None
) -> ExecutionContext | None:
    """Load and validate the context file. Returns ``None`` if absent.

    Raises ``pydantic.ValidationError`` if the file exists but is
    malformed — the caller should treat that as a hard failure.
    """

    path = context_path(feature_slug, project_root)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    return ExecutionContext.model_validate(data)


def update_last_updated(
    feature_slug: str, project_root: Path | str | None = None
) -> Path | None:
    """Bump ``last_updated_at`` to ``now``. No-op if the file is absent."""

    ctx = read_execution_context(feature_slug, project_root)
    if ctx is None:
        return None
    ctx.last_updated_at = _now()
    path = context_path(feature_slug, project_root)
    payload = ctx.model_dump(exclude_none=True)
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return path


def compute_plan_hash(plan_path: Path | str) -> str:
    """SHA-256 of the plan file content. Used to detect drift between
    the plan and the in-flight implementation."""

    p = Path(plan_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"plan file not found: {p}")
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ── Internals ──────────────────────────────────────────────────────────


def _atomic_write(path: Path, content: str) -> None:
    """Write via tempfile + os.replace so a crash never leaves a half
    file. ``Path.write_text`` is not atomic on POSIX."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
