"""App-docs sync orchestrator (v5.29.0 PR-11).

Sits on top of the zone parser from PR-3 and the read tool from PR-4.
Responsibilities:

* `verify_app_docs_in_sync(project_path)` — Compute fresh signatures
  from the actual project state and compare against the stored sync
  state. Returns drift entries the caller (hook, skill, CI) can act on.
* `sync_app_docs(event_type, payload, project_path)` — Apply an
  event-driven update to the relevant auto-zones. Idempotent: rewriting
  the same content twice is a no-op.
* `record_sync_signature(project_path)` — After a successful sync,
  store the new signature in `.quality/app_docs_sync.lock` so the next
  drift check has a baseline.

The decorators in PR-12 wrap spec-mutation tools with these helpers so
every state change immediately flows into the canonical docs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from .zones import (
    ZoneKind,
    compute_signature,
    parse_document,
    replace_zone_body,
)


SYNC_LOCK_PATH = ".quality/app_docs_sync.lock"
PRD_PATH = "doc/app/app_prd.md"
SPEC_PATH = "doc/app/app_spec.md"


@dataclass
class DriftEntry:
    severity: str  # "info" | "warning" | "error"
    document: str  # "app_prd" | "app_spec"
    zone_id: str | None
    message: str


@dataclass
class SyncResult:
    in_sync: bool
    prd_signature: str | None
    spec_signature: str | None
    drift: list[DriftEntry] = field(default_factory=list)
    locked_signatures: dict[str, str] = field(default_factory=dict)


def _lock_path(project_path: Path | str) -> Path:
    return Path(project_path) / SYNC_LOCK_PATH


def _load_lock(project_path: Path | str) -> dict[str, Any]:
    p = _lock_path(project_path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_lock(state: dict[str, Any], project_path: Path | str) -> None:
    p = _lock_path(project_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ── Verify ──────────────────────────────────────────────────────────


def verify_app_docs_in_sync(project_path: str | Path = ".") -> SyncResult:
    """Return a SyncResult describing whether the canonical docs are aligned.

    No filesystem changes. Caller decides what to do with drift entries
    (hook can BLOCKING, /app-sync can offer auto-fix, etc.).
    """
    root = Path(project_path).resolve()
    prd_path = root / PRD_PATH
    spec_path = root / SPEC_PATH
    drift: list[DriftEntry] = []

    prd_sig: str | None = None
    spec_sig: str | None = None
    if prd_path.exists():
        prd_doc = parse_document(prd_path)
        if not prd_doc.is_well_formed:
            for err in prd_doc.errors:
                drift.append(
                    DriftEntry(severity="error", document="app_prd", zone_id=None, message=err)
                )
        prd_sig = compute_signature(prd_doc)
    if spec_path.exists():
        spec_doc = parse_document(spec_path)
        if not spec_doc.is_well_formed:
            for err in spec_doc.errors:
                drift.append(
                    DriftEntry(severity="error", document="app_spec", zone_id=None, message=err)
                )
        spec_sig = compute_signature(spec_doc)

    locked = _load_lock(root).get("signatures", {})
    if prd_sig is not None and locked.get("app_prd") and locked["app_prd"] != prd_sig:
        drift.append(
            DriftEntry(
                severity="warning",
                document="app_prd",
                zone_id=None,
                message="app_prd.md signature drifted since the last recorded sync.",
            )
        )
    if spec_sig is not None and locked.get("app_spec") and locked["app_spec"] != spec_sig:
        drift.append(
            DriftEntry(
                severity="warning",
                document="app_spec",
                zone_id=None,
                message="app_spec.md signature drifted since the last recorded sync.",
            )
        )

    return SyncResult(
        in_sync=not [d for d in drift if d.severity in ("warning", "error")],
        prd_signature=prd_sig,
        spec_signature=spec_sig,
        drift=drift,
        locked_signatures=locked,
    )


def record_sync_signature(project_path: str | Path = ".") -> dict[str, Any]:
    """Snapshot current signatures into `.quality/app_docs_sync.lock`."""
    root = Path(project_path).resolve()
    state = _load_lock(root)
    sigs = state.setdefault("signatures", {})
    prd_path = root / PRD_PATH
    spec_path = root / SPEC_PATH
    if prd_path.exists():
        sigs["app_prd"] = compute_signature(parse_document(prd_path))
    elif "app_prd" in sigs:
        del sigs["app_prd"]
    if spec_path.exists():
        sigs["app_spec"] = compute_signature(parse_document(spec_path))
    elif "app_spec" in sigs:
        del sigs["app_spec"]
    state["recorded_at"] = datetime.now(timezone.utc).isoformat()
    _save_lock(state, root)
    return state


# ── Sync (apply event) ──────────────────────────────────────────────


# Map of pipeline events → (document, zone_id) tuples that must rewrite
# their auto-zone body when the event fires.
EVENT_ZONE_MAP: dict[str, list[tuple[str, str]]] = {
    "complete_uc": [("app_prd", "roadmap")],
    "move_uc": [("app_prd", "roadmap")],
    "add_uc": [("app_prd", "roadmap")],
    "delete_uc": [("app_prd", "roadmap")],
    "mark_ac_batch": [("app_prd", "roadmap"), ("app_prd", "success_metrics")],
    "set_auth_token": [("app_spec", "tracking_backend")],
    "lockfile_change": [("app_spec", "stack")],
    "framework_detected": [("app_spec", "stack")],
    "release_version_bump": [("app_spec", "stack")],
    "autopilot_config_change": [("app_spec", "autopilot")],
    "canonical_decision_created": [("app_spec", "canonical_decisions")],
    "canonical_decision_revoked": [("app_spec", "canonical_decisions")],
}


def sync_app_docs(
    event_type: str,
    payload: dict[str, Any] | None = None,
    project_path: str | Path = ".",
) -> dict[str, Any]:
    """Apply an event-driven update to the relevant auto-zones.

    The body for each zone is computed by `_render_zone_body(zone_id, payload, project_path)`.
    Idempotent: signature-stable rewrites do nothing.

    Returns a structured report describing which zones were touched.
    """
    root = Path(project_path).resolve()
    targets = EVENT_ZONE_MAP.get(event_type, [])
    if not targets:
        return {
            "ok": False,
            "error": "unknown_event_type",
            "event_type": event_type,
            "supported": sorted(EVENT_ZONE_MAP.keys()),
        }

    payload = payload or {}
    touched: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for document_name, zone_id in targets:
        rel_path = PRD_PATH if document_name == "app_prd" else SPEC_PATH
        full_path = root / rel_path
        if not full_path.exists():
            skipped.append(
                {
                    "document": document_name,
                    "zone_id": zone_id,
                    "reason": "document_not_present",
                }
            )
            continue
        content = full_path.read_text(encoding="utf-8")
        try:
            new_body = _render_zone_body(zone_id, payload, root)
            if new_body is None:
                skipped.append(
                    {
                        "document": document_name,
                        "zone_id": zone_id,
                        "reason": "no_renderer_for_zone",
                    }
                )
                continue
            new_content = replace_zone_body(content, zone_id, new_body)
            if new_content == content:
                skipped.append(
                    {
                        "document": document_name,
                        "zone_id": zone_id,
                        "reason": "no_change",
                    }
                )
                continue
            full_path.write_text(new_content, encoding="utf-8")
            touched.append({"document": document_name, "zone_id": zone_id})
        except KeyError:
            skipped.append(
                {
                    "document": document_name,
                    "zone_id": zone_id,
                    "reason": "zone_not_found_in_document",
                }
            )

    if touched:
        record_sync_signature(root)

    return {
        "ok": True,
        "event_type": event_type,
        "touched": touched,
        "skipped": skipped,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Zone renderers ──────────────────────────────────────────────────


def _render_zone_body(zone_id: str, payload: dict[str, Any], project_path: Path) -> str | None:
    """Render the new body for an auto-zone given the event payload.

    Renderers are intentionally narrow: each one consumes only the
    payload fields it needs and returns the full Markdown body. When a
    renderer cannot produce content (insufficient payload, missing
    inputs), it returns the existing body unchanged so the sync becomes
    a no-op.
    """
    if zone_id == "tracking_backend":
        backend = payload.get("backend_type")
        root_abs = payload.get("freeform_root_absolute")
        external_reporting = payload.get("external_reporting", "no")
        if backend not in {"freeform", "trello", "plane"}:
            return None
        lines = [
            "## 2. Tracking backend",
            "",
            f"- **Tipo:** {backend}",
        ]
        if backend == "freeform":
            lines.append(f"- **Path absoluto:** {root_abs or '(no resuelto)'}")
        if backend == "trello" and payload.get("trello_board_id"):
            lines.append(f"- **Trello board id:** {payload['trello_board_id']}")
        if backend == "plane" and payload.get("plane_project_id"):
            lines.append(f"- **Plane project id:** {payload['plane_project_id']}")
        lines.append(f"- **Reporting externo:** {external_reporting}")
        lines.extend(
            [
                "",
                "> Esta zona la mantiene el engine. Para forzar un refresh, ejecuta `/app-sync --refresh`.",
            ]
        )
        return "\n".join(lines)

    if zone_id == "autopilot":
        level = payload.get("level", "low")
        budget = payload.get("image_budget_eur_per_feature", 5)
        auto_overrides = payload.get("auto_confirm_overrides") or []
        ask_overrides = payload.get("always_ask_overrides") or []
        queue = payload.get("queue_enabled", False)
        return "\n".join(
            [
                "## 5. Autopilot",
                "",
                f"- **Level:** {level}",
                f"- **Image budget €/feature:** {budget}",
                f"- **Auto-confirm overrides:** {auto_overrides}",
                f"- **Always-ask overrides:** {ask_overrides}",
                f"- **Queue enabled:** {str(queue).lower()}",
                "",
                "> Esta zona se sincroniza automáticamente desde `.claude/settings.local.json`.",
            ]
        )

    if zone_id == "stack":
        rows = payload.get("rows") or []
        if not rows:
            return None
        out = ["## 1. Stack", "", "| Capa | Tecnología | Versión | Detectado de |", "|------|-----------|---------|--------------|"]
        for r in rows:
            out.append(
                f"| {r.get('layer','')} | {r.get('tech','')} | {r.get('version','')} | {r.get('source','')} |"
            )
        return "\n".join(out)

    if zone_id == "roadmap":
        rows = payload.get("rows") or []
        out = [
            "## 5. Roadmap de US",
            "",
            "| US | Título | Estado | UCs | Última actualización |",
            "|----|--------|--------|-----|----------------------|",
        ]
        if not rows:
            out.append("| (sin datos) | | | | |")
        else:
            for r in rows:
                out.append(
                    f"| {r.get('us_id','')} | {r.get('title','')} | {r.get('state','')} "
                    f"| {r.get('uc_count','')} | {r.get('updated_at','')} |"
                )
        return "\n".join(out)

    if zone_id == "canonical_decisions":
        entries = payload.get("entries") or []
        out = [
            "## 6. Decisiones canónicas",
            "",
            "_(Tu zona arriba; el engine añade entradas debajo del marcador)_",
            "",
            "<!-- engine-entries-below -->",
        ]
        for entry in entries:
            out.append(
                f"- **{entry.get('decision_key','')}** = "
                f"`{entry.get('value','')}` "
                f"(promovida {entry.get('promoted_at','')}, "
                f"{entry.get('confirmations','')} confirmaciones)"
            )
        if not entries:
            out.append("- _(no hay decisiones canónicas activas)_")
        return "\n".join(out)

    if zone_id == "success_metrics":
        # No deterministic source for metrics yet; sync is a passthrough.
        return None

    return None


# ── MCP registration ────────────────────────────────────────────────


def register_sync_tools(mcp: FastMCP, engine_path: Path) -> None:
    @mcp.tool
    def verify_app_docs(project_path: str = ".") -> dict[str, Any]:
        """Check whether `doc/app/app_prd.md` and `doc/app/app_spec.md` are in sync.

        Returns {in_sync, prd_signature, spec_signature, drift[], locked_signatures}.
        Read-only: never modifies the project.
        """
        result = verify_app_docs_in_sync(project_path)
        return {
            "in_sync": result.in_sync,
            "prd_signature": result.prd_signature,
            "spec_signature": result.spec_signature,
            "drift": [
                {"severity": d.severity, "document": d.document, "zone_id": d.zone_id, "message": d.message}
                for d in result.drift
            ],
            "locked_signatures": result.locked_signatures,
        }

    @mcp.tool
    def apply_app_docs_sync(
        event_type: str,
        payload: dict[str, Any] | None = None,
        project_path: str = ".",
    ) -> dict[str, Any]:
        """Apply an event-driven sync to the relevant auto-zones.

        Supported event_types: complete_uc, move_uc, add_uc, delete_uc,
        mark_ac_batch, set_auth_token, lockfile_change, framework_detected,
        release_version_bump, autopilot_config_change,
        canonical_decision_created, canonical_decision_revoked.

        Idempotent: re-running with identical payload writes nothing.
        """
        return sync_app_docs(event_type, payload or {}, project_path)

    @mcp.tool
    def record_app_docs_signature(project_path: str = ".") -> dict[str, Any]:
        """Snapshot current app_*.md signatures for future drift detection."""
        return record_sync_signature(project_path)
