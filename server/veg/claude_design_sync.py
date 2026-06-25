"""Design-system sync engine for Claude Design (US-29 · UC-2905).

The engine does NOT reimplement the repo→bundle conversion. That pipeline
(``package-build.mjs`` / ``resync.mjs``, the ``_ds_bundle.js`` contract) lives
in the harness ``/design-sync`` skill. This module only:

1. **Prepares** ``.design-sync/config.json`` at the resolved site with the
   anchored ``projectId`` (AC-01), so ``/design-sync`` knows which Claude
   Design project to sync against.
2. **Decides idempotency** via the ``_ds_sync.json`` anchor: if the anchor
   reflects the current ``dist/`` state, a second sync emits no writes
   (AC-02).
3. **Targets the gate's site**: the ``localDir`` synced is the ``dist/`` of the
   site resolved by the topology gate (orchestrator in multirepo, the repo
   itself in monorepo) (AC-03).

The actual sync is then driven by the ``/design-sync`` skill — this module
returns a structured directive, never shelling out to a reimplemented build.

Trazabilidad: Discovery ``disc-52cbe4033fae`` · US-29 · UC-2905.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .design_system_gate import SiteResolution, evaluate_gate

_CONFIG_DIR = ".design-sync"
_CONFIG_FILE = "config.json"
_SYNC_ANCHOR = "_ds_sync.json"
_DIST_DIRNAME = "dist"


@dataclass(frozen=True)
class SyncDecision:
    """Outcome of a sync evaluation.

    - ``action`` ∈ {"sync", "skip", "pending"}.
    - ``reason`` explains a skip/pending.
    - ``config_path`` is the prepared ``.design-sync/config.json``.
    - ``local_dir`` is the ``dist/`` that ``/design-sync`` will upload.
    - ``project_id`` is the anchored Claude Design project.
    """

    action: str
    reason: str
    config_path: str | None
    local_dir: str | None
    project_id: str | None


def prepare_config(site: SiteResolution, project_id: str | None) -> Path:
    """Write ``.design-sync/config.json`` at the resolved site (AC-01).

    The config anchors the ``projectId`` and the ``localDir`` (the site's
    ``dist/``). It is written at the site that owns the design-system — the
    orchestrator in multirepo, the repo itself in monorepo. Merges with any
    existing config (never clobbers unrelated keys).
    """
    cfg_dir = site.site_path / _CONFIG_DIR
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / _CONFIG_FILE

    existing: dict[str, Any] = {}
    if cfg_file.exists():
        try:
            existing = json.loads(cfg_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    if not isinstance(existing, dict):
        existing = {}

    existing["projectId"] = project_id
    existing["localDir"] = str(site.site_path / _DIST_DIRNAME)
    existing["role"] = site.role
    existing["consumes_from_orchestrator"] = site.consumes_from_orchestrator

    cfg_file.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return cfg_file


def _fingerprint_dist(dist_dir: Path) -> str:
    """Compute a deterministic fingerprint of the dist/ contents.

    Hashes the sorted list of (relative_path, size, mtime_ns) of every file
    under ``dist/``. Used to detect whether anything changed since the last
    sync without re-reading file bodies.
    """
    if not dist_dir.is_dir():
        return ""
    entries: list[str] = []
    for p in sorted(dist_dir.rglob("*")):
        if p.is_file():
            st = p.stat()
            rel = p.relative_to(dist_dir).as_posix()
            entries.append(f"{rel}:{st.st_size}:{st.st_mtime_ns}")
    blob = "\n".join(entries).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _read_anchor(site: Path) -> dict[str, Any]:
    anchor = site / _SYNC_ANCHOR
    if not anchor.exists():
        return {}
    try:
        data = json.loads(anchor.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_anchor(site: Path, fingerprint: str, project_id: str | None) -> Path:
    """Persist the ``_ds_sync.json`` anchor after a successful sync."""
    anchor = site / _SYNC_ANCHOR
    anchor.write_text(
        json.dumps(
            {"fingerprint": fingerprint, "projectId": project_id},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return anchor


def is_up_to_date(site: Path, project_id: str | None) -> bool:
    """Return True if the ``dist/`` is unchanged since the last sync (AC-02).

    Compares the current dist/ fingerprint against the one stored in
    ``_ds_sync.json``. A match (for the same projectId) means a second sync
    would emit no writes, so the caller can skip.
    """
    anchor = _read_anchor(site)
    if not anchor or anchor.get("projectId") != project_id:
        return False
    current = _fingerprint_dist(site / _DIST_DIRNAME)
    return bool(current) and anchor.get("fingerprint") == current


def evaluate_sync(
    project_root: str | Path, project_id: str | None
) -> SyncDecision:
    """Decide whether a sync is needed and prepare its config (AC-01..03).

    - If the gate is not ready → ``pending`` with the gate reason.
    - If the ``_ds_sync.json`` anchor matches the current dist/ → ``skip``
      (idempotent: no writes).
    - Otherwise → ``sync``, with ``.design-sync/config.json`` prepared at the
      gate's site and ``local_dir`` pointing to that site's ``dist/`` (AC-03).
    """
    gate, site = evaluate_gate(project_root)
    if not gate.ready:
        return SyncDecision(
            action="pending",
            reason=gate.reason,
            config_path=None,
            local_dir=None,
            project_id=project_id,
        )

    local_dir = site.site_path / _DIST_DIRNAME

    if is_up_to_date(site.site_path, project_id):
        return SyncDecision(
            action="skip",
            reason="dist/ unchanged since last sync (_ds_sync.json matches)",
            config_path=str(site.site_path / _CONFIG_DIR / _CONFIG_FILE),
            local_dir=str(local_dir),
            project_id=project_id,
        )

    cfg = prepare_config(site, project_id)
    return SyncDecision(
        action="sync",
        reason="delegating repo→bundle to the /design-sync skill",
        config_path=str(cfg),
        local_dir=str(local_dir),
        project_id=project_id,
    )
