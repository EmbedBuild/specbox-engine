"""Persistent execution context for /implement Tasks (v5.32.0).

Each invocation of `/implement` writes a single ``execution_context.json``
under ``.quality/evidence/{feature_slug}/`` containing the values that
isolated Tasks need (branch, feature, stack, project paths). This is
what lets a Task delegated to a sub-agent know "where am I" without
the orchestrator embedding those values verbatim into every prompt
(which is what causes the orchestrator's context to grow unbounded).

The companion module ``phase_outputs`` (added in Phase 4) handles the
return path: each Task writes a structured delta to
``phase_outputs.jsonl`` so Spec-Code Sync (Paso 5.1.1b / 8.5.1a) no
longer needs to read ``git diff`` from the orchestrator's session.
"""

from __future__ import annotations

from .execution_context import (
    SCHEMA_VERSION,
    ExecutionContext,
    compute_plan_hash,
    context_path,
    read_execution_context,
    update_last_updated,
    write_execution_context,
)

__all__ = [
    "SCHEMA_VERSION",
    "ExecutionContext",
    "compute_plan_hash",
    "context_path",
    "read_execution_context",
    "update_last_updated",
    "write_execution_context",
]
