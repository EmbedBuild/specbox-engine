"""Data-migration rollback for the atomic backend switch (UC-812 / AC-07).

``apply_switch_transactional`` already rolls back the three config places
(registry / app_spec / settings). But an atomic switch into native ALSO writes
rows to Postgres before the config switch. If the config switch then fails, the
data write must be undone too, or the project lands in the limbo the refactor
exists to kill (data in the DB, config on the old backend).

This module is the data half of that rollback. It is deliberately narrow:

* For a target that was created fresh by this run (``created_fresh=True``) the
  rollback deletes the freshly-created project — restoring "empty", its
  pre-migration state.
* For a pre-existing target (``created_fresh=False``, i.e. ``on_collision=reuse``)
  there is no safe automatic undo of a merge, so the data rollback is a no-op
  and the caller is expected to have surfaced that limitation in the preview.

The actual DELETE is injected as a callable so the function stays I/O-free and
testable without a live database.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable


async def rollback_data_migration(
    *,
    created_fresh: bool,
    delete_project: Callable[[], Awaitable[None]] | None,
) -> dict[str, Any]:
    """Undo the data half of a failed atomic switch.

    Args:
        created_fresh: True when this run created the target project (so it can
            be safely deleted to restore the pre-migration "empty" state).
        delete_project: Async callable that deletes the freshly-created target
            project. Required when ``created_fresh`` is True; ignored otherwise.

    Returns:
        ``{"data_rolled_back": bool, "reason": str}`` describing what happened.
        Never raises on a best-effort delete failure — it reports it instead, so
        the caller can still surface the config rollback verdict.
    """
    if not created_fresh:
        return {
            "data_rolled_back": False,
            "reason": "target pre-existed (reuse) — no automatic data undo; "
            "config was rolled back",
        }

    if delete_project is None:
        return {
            "data_rolled_back": False,
            "reason": "created_fresh but no delete_project provided",
        }

    try:
        await delete_project()
    except Exception as exc:  # noqa: BLE001 - best-effort; report, don't mask
        return {
            "data_rolled_back": False,
            "reason": f"delete of fresh project failed: {exc}",
        }

    return {"data_rolled_back": True, "reason": "deleted freshly-created project"}
