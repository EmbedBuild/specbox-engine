"""Atomic backend-switch orchestrator (UC-812).

"Change backend" used to be three public tools the caller chained by hand
(``migrate_backend`` → ``seed_native_identity`` → ``switch_backend``). Forgetting
a step, or an error between them, left the project in limbo: config says one
backend, the database holds another. This module makes the whole chain ONE
all-or-nothing operation: either everything lands, or nothing does.

The orchestrator is written against injected step callables so it is fully
testable without a live MCP session or Postgres. The MCP tool
(``switch_project_backend`` in ``server.tools.migration``) wires the real steps
in; the tests wire fakes.

Step order (execute path):
  1. count guard (verify_count) — refuse on 0-read or mismatch.
  2. (target native) require_dev_token — fail-fast before any write.
  3. snapshot whether the target was created fresh (for data rollback).
  4. write_target — copy US/UC/AC preserving states.
  5. (target native) seed developer identity.
  6. (source native) build the discarded-coordination exit report.
  7. apply_switch_transactional — the 3 config places, with its own rollback.
  8. on ANY failure in 4-7: roll back the data migration too (delete a
     freshly-created native project) and report rolled_back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .count_guard import CountGuardError, verify_count
from .rollback import rollback_data_migration


class SwitchOrchestrationError(RuntimeError):
    """A pre-write guard failed (count / dev_token / collision). Nothing written."""


@dataclass
class SwitchSteps:
    """Injected step callables for one switch run.

    Every callable is async. The orchestrator never does I/O itself.
    """

    # Returns the preview dict (must carry "read_counts"; may carry "collision",
    # "native_exit_report").
    preview: Callable[[], Awaitable[dict[str, Any]]]
    # Ensures/creates the target; returns (target_id, created_fresh).
    ensure_target: Callable[[], Awaitable[tuple[str, bool]]]
    # Copies US/UC/AC to the target. Returns a write-result dict.
    write_target: Callable[[str], Awaitable[dict[str, Any]]]
    # The 3-place config switch. Raises on failure (TransactionalSwitchError).
    apply_switch: Callable[[str], Awaitable[dict[str, Any]]]
    # Deletes a freshly-created native target (for data rollback). Optional.
    delete_fresh_target: Callable[[], Awaitable[None]] | None = None
    # (target native) raises if dev_token missing. Optional (non-native targets).
    require_dev_token: Callable[[], None] | None = None
    # (target native) seeds developer identity. Optional.
    seed_identity: Callable[[str], Awaitable[dict[str, Any]]] | None = None
    # (source native) builds the discarded-coordination report. Optional.
    build_exit_report: Callable[[], Awaitable[dict[str, Any]]] | None = None
    sub_steps_meta: dict[str, str] = field(default_factory=dict)


async def run_switch(
    *,
    steps: SwitchSteps,
    dry_run: bool,
    confirmed_count: dict[str, int] | None,
) -> dict[str, Any]:
    """Run the atomic switch (or a dry-run preview).

    Args:
        steps: The injected step callables.
        dry_run: When True, run only the preview and return it (no writes).
        confirmed_count: ``{us, uc}`` the client confirmed (execute only).

    Returns:
        For dry_run: the preview dict with ``dry_run=True``.
        For execute: a result dict with ``success`` plus the completed
        sub-steps, or ``rolled_back=True`` with ``failing_step`` on failure.

    Raises:
        SwitchOrchestrationError: a pre-write guard failed; nothing was written.
    """
    # Pre-write guard: dev_token fail-fast must happen before even reading the
    # source (AC-09), so it runs before the preview.
    if steps.require_dev_token is not None:
        steps.require_dev_token()

    preview = await steps.preview()

    if dry_run:
        return {**preview, "dry_run": True}

    # ── Execute path ──────────────────────────────────────────────────
    read_counts = preview.get("read_counts", {"us": 0, "uc": 0})
    try:
        verify_count(read_counts, confirmed_count)
    except CountGuardError as exc:
        raise SwitchOrchestrationError(str(exc)) from exc

    # Collision must be resolved before writing (AC-11). The caller encodes the
    # resolution by clearing/keeping "collision" in the preview.
    collision = preview.get("collision")
    if collision and collision.get("unresolved"):
        raise SwitchOrchestrationError(
            "project already exists in native — specify on_collision"
        )

    completed: list[str] = []
    target_id, created_fresh = await steps.ensure_target()
    completed.append("ensure_target")

    async def _rollback(failing_step: str, error: str) -> dict[str, Any]:
        data_rb = await rollback_data_migration(
            created_fresh=created_fresh,
            delete_project=steps.delete_fresh_target,
        )
        return {
            "success": False,
            "rolled_back": True,
            "failing_step": failing_step,
            "error": error,
            "completed_before_failure": completed,
            "data_rollback": data_rb,
        }

    try:
        write_result = await steps.write_target(target_id)
        completed.append("write_target")

        seed_result: dict[str, Any] | None = None
        if steps.seed_identity is not None:
            seed_result = await steps.seed_identity(target_id)
            completed.append("seed_identity")

        exit_report: dict[str, Any] | None = None
        if steps.build_exit_report is not None:
            exit_report = await steps.build_exit_report()
            completed.append("build_exit_report")

        switch_result = await steps.apply_switch(target_id)
        completed.append("apply_switch")
    except Exception as exc:  # noqa: BLE001 - turn any write failure into rollback
        failing = "apply_switch" if "switch" in type(exc).__name__.lower() else "write"
        return await _rollback(failing, str(exc))

    return {
        "success": True,
        "rolled_back": False,
        "target_id": target_id,
        "created_fresh": created_fresh,
        "completed_steps": completed,
        "write_result": write_result,
        "native_identity_seeded": seed_result,
        "native_exit_report": exit_report,
        "switch_result": switch_result,
    }
