"""Transactional 3-place backend switch with rollback (UC-404, AC-12/AC-13).

When a project switches its active backend, three sources of truth must move
together or not at all:

1. **Registry** — ``$STATE_PATH/projects.json``: the ``spec_backend`` /
   ``board_id`` fields plus an appended ``backend_history`` entry.
2. **app_spec** — ``doc/app/app_spec.md`` auto-zone ``tracking_backend``,
   rewritten via :func:`server.app_docs.sync.sync_app_docs` with the
   ``set_auth_token`` event.
3. **settings** — ``.claude/settings.local.json`` key
   ``specbox.backend_type``.

:func:`apply_switch_transactional` snapshots the prior state of all three,
writes them in the order registry → app_spec → settings, and if **any** write
raises it restores the already-applied snapshots in reverse order and re-raises
a :class:`TransactionalSwitchError` naming the place that failed — leaving the
project on its original backend (AC-13).

The ``*_writer`` keyword arguments inject the write functions so tests can
simulate a mid-transaction failure; production callers omit them and get the
real implementations.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)

#: Stable place names used in the result and in rollback errors.
PLACE_REGISTRY = "registry"
PLACE_APP_SPEC = "app_spec"
PLACE_SETTINGS = "settings"

#: Order in which the three places are written. Rollback walks it in reverse.
WRITE_ORDER: tuple[str, ...] = (PLACE_REGISTRY, PLACE_APP_SPEC, PLACE_SETTINGS)


class TransactionalSwitchError(RuntimeError):
    """Raised when a place write fails after rollback of the applied ones.

    Carries the failing ``place`` so callers (switch_backend) can surface it.
    """

    def __init__(self, place: str, original: Exception, rolled_back: list[str]) -> None:
        self.place = place
        self.original = original
        self.rolled_back = rolled_back
        super().__init__(
            f"backend switch failed while writing {place!r}: {original}. "
            f"Rolled back: {rolled_back or 'nothing'}. Project left on original backend."
        )


# ── Registry (projects.json) ─────────────────────────────────────────


def _state_path(state_path: str | None) -> Path:
    return Path(state_path or os.getenv("STATE_PATH", "/data/state"))


def _registry_path(state_path: str | None) -> Path:
    return _state_path(state_path) / "projects.json"


def _read_registry_snapshot(project_slug: str, state_path: str | None) -> dict[str, Any]:
    """Return a deep-ish snapshot of the project's registry entry (or absent).

    ``file_present`` records whether ``projects.json`` existed at snapshot time so
    that rollback can DELETE a file a writer just created (mirror auto-init) instead
    of leaving an empty-but-present registry behind.
    """
    path = _registry_path(state_path)
    if not path.exists():
        return {"present": False, "entry": None, "file_present": False}
    registry = json.loads(path.read_text(encoding="utf-8"))
    entry = (registry.get("projects") or {}).get(project_slug)
    return {
        "present": entry is not None,
        "entry": json.loads(json.dumps(entry)) if entry is not None else None,
        "file_present": True,
    }


def _write_registry(
    project_slug: str,
    new_backend: str,
    new_board_id: str,
    state_path: str | None,
) -> None:
    """Update spec_backend / board_id + append backend_history in projects.json."""
    from datetime import datetime, timezone

    path = _registry_path(state_path)
    if not path.exists():
        raise FileNotFoundError(f"Project registry not found at {path}")
    registry = json.loads(path.read_text(encoding="utf-8"))
    projects = registry.get("projects") or {}
    if project_slug not in projects:
        raise KeyError(f"Project {project_slug!r} not found in registry")

    project = projects[project_slug]
    previous_backend = project.get("spec_backend", "")
    previous_board_id = project.get("board_id", "")
    project["spec_backend"] = new_backend
    project["board_id"] = new_board_id
    if previous_backend != new_backend:
        project.setdefault("backend_history", []).append(
            {
                "backend": previous_backend,
                "board_id": previous_board_id,
                "switched_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    registry["projects"][project_slug] = project
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")


def _restore_registry(project_slug: str, snapshot: dict[str, Any], state_path: str | None) -> None:
    """Restore the project's registry entry from a snapshot.

    If the registry file did not exist when snapshotted (``file_present`` False)
    a later writer created it — rollback deletes the whole file so the state dir
    returns byte-identical to before the transaction (mirror auto-init case).
    """
    path = _registry_path(state_path)
    if not path.exists():
        return
    if snapshot.get("file_present") is False:
        path.unlink()
        return
    registry = json.loads(path.read_text(encoding="utf-8"))
    registry.setdefault("projects", {})
    if snapshot.get("present") and snapshot.get("entry") is not None:
        registry["projects"][project_slug] = snapshot["entry"]
    else:
        registry["projects"].pop(project_slug, None)
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")


# ── settings.local.json ──────────────────────────────────────────────


def _settings_path(project_path: str) -> Path:
    return Path(project_path) / ".claude" / "settings.local.json"


def _read_settings_snapshot(project_path: str) -> dict[str, Any]:
    """Snapshot the entire settings.local.json (or mark absent)."""
    path = _settings_path(project_path)
    if not path.exists():
        return {"present": False, "content": None}
    return {"present": True, "content": path.read_text(encoding="utf-8")}


def _write_settings(project_path: str, new_backend: str) -> None:
    """Set specbox.backend_type in .claude/settings.local.json (create if absent)."""
    path = _settings_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            settings = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}
    settings.setdefault("specbox", {})
    settings["specbox"]["backend_type"] = new_backend
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def _restore_settings(project_path: str, snapshot: dict[str, Any]) -> None:
    """Restore settings.local.json from a snapshot (delete if it was absent)."""
    path = _settings_path(project_path)
    if snapshot.get("present"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(snapshot["content"], encoding="utf-8")
    elif path.exists():
        path.unlink()


# ── app_spec (doc/app/app_spec.md tracking_backend zone) ──────────────


def _read_app_spec_snapshot(project_path: str) -> dict[str, Any]:
    """Snapshot the full app_spec.md content (or mark absent)."""
    path = Path(project_path) / "doc" / "app" / "app_spec.md"
    if not path.exists():
        return {"present": False, "content": None}
    return {"present": True, "content": path.read_text(encoding="utf-8")}


def _build_app_spec_payload(
    new_backend: str,
    new_board_id: str,
    project_path: str,
    freeform_root_absolute: str | None,
) -> dict[str, Any]:
    """Build the set_auth_token payload for the tracking_backend renderer."""
    payload: dict[str, Any] = {"backend_type": new_backend}
    if new_backend == "freeform":
        payload["freeform_root_absolute"] = freeform_root_absolute or str(
            Path(project_path) / "doc" / "tracking"
        )
    elif new_backend == "trello":
        payload["trello_board_id"] = new_board_id
    elif new_backend == "plane":
        payload["plane_project_id"] = new_board_id
    elif new_backend == "native":
        payload["native_project_id"] = new_board_id
    return payload


def _write_app_spec(
    new_backend: str,
    new_board_id: str,
    project_path: str,
    freeform_root_absolute: str | None,
) -> None:
    """Rewrite the tracking_backend auto-zone via the app_docs sync orchestrator.

    Delegates to :func:`server.app_docs.sync.sync_app_docs` with the
    ``set_auth_token`` event. If app_spec.md is absent, the sync is a no-op
    (it reports the document as skipped) and this is treated as success — a
    project without canonical docs has nothing to keep in sync.
    """
    from ..app_docs.sync import sync_app_docs

    payload = _build_app_spec_payload(new_backend, new_board_id, project_path, freeform_root_absolute)
    result = sync_app_docs("set_auth_token", payload, project_path)
    if not result.get("ok", False):
        raise RuntimeError(f"app_spec sync failed: {result.get('error', result)}")


def _restore_app_spec(project_path: str, snapshot: dict[str, Any]) -> None:
    """Restore app_spec.md from a snapshot (delete if it was absent)."""
    path = Path(project_path) / "doc" / "app" / "app_spec.md"
    if snapshot.get("present"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(snapshot["content"], encoding="utf-8")
    elif path.exists():
        path.unlink()


# ── Orchestration ────────────────────────────────────────────────────


def apply_switch_transactional(
    project_slug: str,
    new_backend: str,
    new_board_id: str,
    project_path: str,
    state_path: str | None = None,
    *,
    freeform_root_absolute: str | None = None,
    settings_writer: Callable[[], None] | None = None,
    registry_writer: Callable[[], None] | None = None,
    app_spec_writer: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Atomically update registry + app_spec + settings, rolling back on failure.

    Snapshots the three places, writes them in order
    registry → app_spec → settings, and on any failure restores every
    already-written place in reverse order before raising
    :class:`TransactionalSwitchError` naming the failing place (AC-13).

    Args:
        project_slug: Project key in the engine registry.
        new_backend: Target backend type (one of the four).
        new_board_id: Board/project id in the target backend.
        project_path: Filesystem root of the project (for app_spec + settings).
        state_path: Override for ``$STATE_PATH`` (registry location).
        freeform_root_absolute: Absolute tracking path when target is freeform.
        settings_writer / registry_writer / app_spec_writer: Test seams to
            inject a write function (e.g. one that raises). Default: the real
            writers bound to the call's arguments.

    Returns:
        ``{"updated": ["registry", "app_spec", "settings"], "previous": {...}}``
        where ``previous`` holds the three snapshots taken before writing.
    """
    # Snapshots first — these are what we restore on rollback.
    snapshots: dict[str, dict[str, Any]] = {
        PLACE_REGISTRY: _read_registry_snapshot(project_slug, state_path),
        PLACE_APP_SPEC: _read_app_spec_snapshot(project_path),
        PLACE_SETTINGS: _read_settings_snapshot(project_path),
    }

    # Bind real writers unless a test seam overrides them.
    writers: dict[str, Callable[[], None]] = {
        PLACE_REGISTRY: registry_writer
        or (lambda: _write_registry(project_slug, new_backend, new_board_id, state_path)),
        PLACE_APP_SPEC: app_spec_writer
        or (lambda: _write_app_spec(new_backend, new_board_id, project_path, freeform_root_absolute)),
        PLACE_SETTINGS: settings_writer or (lambda: _write_settings(project_path, new_backend)),
    }

    restorers: dict[str, Callable[[], None]] = {
        PLACE_REGISTRY: lambda: _restore_registry(project_slug, snapshots[PLACE_REGISTRY], state_path),
        PLACE_APP_SPEC: lambda: _restore_app_spec(project_path, snapshots[PLACE_APP_SPEC]),
        PLACE_SETTINGS: lambda: _restore_settings(project_path, snapshots[PLACE_SETTINGS]),
    }

    applied: list[str] = []
    for place in WRITE_ORDER:
        try:
            writers[place]()
            applied.append(place)
        except Exception as exc:  # noqa: BLE001 - rollback then re-raise typed
            logger.error("switch_place_failed", place=place, error=str(exc))
            for done in reversed(applied):
                try:
                    restorers[done]()
                except Exception as rb_exc:  # noqa: BLE001 - best-effort rollback
                    logger.error("switch_rollback_failed", place=done, error=str(rb_exc))
            raise TransactionalSwitchError(place, exc, list(reversed(applied))) from exc

    logger.info(
        "switch_transactional_complete",
        project=project_slug,
        new_backend=new_backend,
        updated=applied,
    )
    return {"updated": applied, "previous": snapshots}


# ── Mirror block (US-DUAL-BACKEND) ───────────────────────────────────
#
# The dual-backend "mirror" sub-config lives in the SAME three places as the
# primary backend and moves with the same all-or-nothing semantics. Only the
# native project_id is persisted — the mirror dev_token stays session-only
# (Frontier 2), exactly like the primary's.


def _write_registry_mirror(
    project_slug: str,
    mirror_project_id: str | None,
    state_path: str | None,
    primary_backend: str = "",
    primary_board_id: str = "",
) -> None:
    """Set (or remove, when None) the project's ``mirror`` registry block.

    The mirror is opt-in best-effort over an already-live primary, and on a cloud
    MCP the ``projects.json`` registry may never have been materialised for the
    project (no local onboarding ran there). So enabling a mirror auto-bootstraps
    what it needs instead of failing:

    - **File missing** → create the ``{"projects": {}}`` skeleton (rollback deletes
      it; see :func:`_restore_registry`).
    - **Entry missing** (only when SETTING a mirror) → seed it from the PRIMARY
      (``spec_backend``/``board_id`` come from the session + tool args). The
      primary is the source of truth; the mirror block is purely additive.
    - **Entry present** → its ``spec_backend``/``board_id`` are NEVER overwritten;
      only the ``mirror`` sub-block is added or removed.
    - **Disable** (``mirror_project_id is None``) with a missing file/entry → no-op:
      we don't fabricate an entry just to remove something that isn't there.
    """
    path = _registry_path(state_path)
    if path.exists():
        registry = json.loads(path.read_text(encoding="utf-8"))
    elif mirror_project_id is None:
        return  # disable on a non-existent registry — nothing to remove
    else:
        registry = {"projects": {}}
        path.parent.mkdir(parents=True, exist_ok=True)

    projects = registry.setdefault("projects", {})
    if project_slug not in projects:
        if mirror_project_id is None:
            return  # disable with no entry — no-op
        # Auto-seed from the primary (never invents a primary it wasn't given).
        projects[project_slug] = {
            "spec_backend": primary_backend,
            "board_id": primary_board_id,
        }

    project = projects[project_slug]
    if mirror_project_id is None:
        project.pop("mirror", None)
    else:
        project["mirror"] = {"backend": "native", "project_id": mirror_project_id}
    registry["projects"][project_slug] = project
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_settings_mirror(project_path: str, mirror_project_id: str | None) -> None:
    """Set (or remove) ``specbox.mirror`` in .claude/settings.local.json."""
    path = _settings_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            settings = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}
    settings.setdefault("specbox", {})
    if mirror_project_id is None:
        settings["specbox"].pop("mirror", None)
    else:
        settings["specbox"]["mirror"] = {
            "backend": "native",
            "project_id": mirror_project_id,
        }
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_app_spec_mirror(
    project_slug: str,
    mirror_project_id: str | None,
    project_path: str,
    state_path: str | None,
) -> None:
    """Re-render the tracking_backend zone keeping the primary, ± mirror line.

    The primary's data is read from the registry entry (it does not change in
    a mirror operation); the freeform absolute path, when applicable, is read
    from settings so an enable/disable does not degrade the rendered zone.
    """
    from ..app_docs.sync import sync_app_docs

    snapshot = _read_registry_snapshot(project_slug, state_path)
    entry = snapshot.get("entry") or {}
    backend = entry.get("spec_backend", "")
    board_id = entry.get("board_id", "")
    freeform_root: str | None = None
    settings_path = _settings_path(project_path)
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            freeform_root = (settings.get("specbox") or {}).get("freeform_root_absolute")
        except json.JSONDecodeError:
            pass
    payload = _build_app_spec_payload(backend, board_id, project_path, freeform_root)
    if mirror_project_id is not None:
        payload["mirror_native_project_id"] = mirror_project_id
    result = sync_app_docs("set_auth_token", payload, project_path)
    if not result.get("ok", False):
        raise RuntimeError(f"app_spec sync failed: {result.get('error', result)}")


def apply_mirror_transactional(
    project_slug: str,
    mirror_project_id: str | None,
    project_path: str,
    state_path: str | None = None,
    *,
    primary_backend: str = "",
    primary_board_id: str = "",
    settings_writer: Callable[[], None] | None = None,
    registry_writer: Callable[[], None] | None = None,
    app_spec_writer: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Atomically persist (or remove) the ``mirror`` block in the 3 places.

    ``mirror_project_id`` is the native tenant id to mirror into;
    ``None`` removes the block (disable_mirror). Same snapshot → write
    (registry → app_spec → settings) → rollback-on-failure semantics as
    :func:`apply_switch_transactional`; the primary backend fields are
    never touched.

    ``primary_backend`` / ``primary_board_id`` are the live primary's identity,
    used ONLY to auto-seed a brand-new registry entry when the project was never
    materialised in ``projects.json`` on this MCP host (cloud case). When the
    entry already exists they are ignored — the on-disk primary always wins.

    Returns ``{"updated": [...], "previous": {...}, "mirror": ...}``.
    """
    snapshots: dict[str, dict[str, Any]] = {
        PLACE_REGISTRY: _read_registry_snapshot(project_slug, state_path),
        PLACE_APP_SPEC: _read_app_spec_snapshot(project_path),
        PLACE_SETTINGS: _read_settings_snapshot(project_path),
    }

    writers: dict[str, Callable[[], None]] = {
        PLACE_REGISTRY: registry_writer
        or (
            lambda: _write_registry_mirror(
                project_slug,
                mirror_project_id,
                state_path,
                primary_backend,
                primary_board_id,
            )
        ),
        PLACE_APP_SPEC: app_spec_writer
        or (
            lambda: _write_app_spec_mirror(
                project_slug, mirror_project_id, project_path, state_path
            )
        ),
        PLACE_SETTINGS: settings_writer
        or (lambda: _write_settings_mirror(project_path, mirror_project_id)),
    }

    restorers: dict[str, Callable[[], None]] = {
        PLACE_REGISTRY: lambda: _restore_registry(project_slug, snapshots[PLACE_REGISTRY], state_path),
        PLACE_APP_SPEC: lambda: _restore_app_spec(project_path, snapshots[PLACE_APP_SPEC]),
        PLACE_SETTINGS: lambda: _restore_settings(project_path, snapshots[PLACE_SETTINGS]),
    }

    applied: list[str] = []
    for place in WRITE_ORDER:
        try:
            writers[place]()
            applied.append(place)
        except Exception as exc:  # noqa: BLE001 - rollback then re-raise typed
            logger.error("mirror_place_failed", place=place, error=str(exc))
            for done in reversed(applied):
                try:
                    restorers[done]()
                except Exception as rb_exc:  # noqa: BLE001 - best-effort rollback
                    logger.error("mirror_rollback_failed", place=done, error=str(rb_exc))
            raise TransactionalSwitchError(place, exc, list(reversed(applied))) from exc

    logger.info(
        "mirror_transactional_complete",
        project=project_slug,
        mirror=mirror_project_id,
        updated=applied,
    )
    return {"updated": applied, "previous": snapshots, "mirror": mirror_project_id}
