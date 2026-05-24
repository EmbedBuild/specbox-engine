"""App-docs sync orchestrator (v5.29.0 PR-11; refactor v6.0.0 UC-D005).

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

**v6.0 (UC-D005)**: el sistema itera sobre `CANONICAL_DOCS` del módulo
`registry.py` en lugar de tener ramas hardcoded para `app_prd`/`app_spec`.
Añadir un doc canónico nuevo no requiere tocar este archivo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from .registry import CANONICAL_DOCS, build_event_zone_map, docs_for_version, get_doc
from .zones import (
    Zone,
    ZoneKind,
    compute_signature,
    parse_document,
    replace_zone_body,
)


SYNC_LOCK_PATH = ".quality/app_docs_sync.lock"


@dataclass
class DriftEntry:
    severity: str  # "info" | "warning" | "error"
    document: str  # canonical doc id (e.g. "app_prd", "app_spec", "app_market")
    zone_id: str | None
    message: str


@dataclass
class SyncResult:
    in_sync: bool
    # Backwards compat: explicit prd_signature/spec_signature fields preserved
    # so v5.29.x callers still work. New code should prefer `signatures` dict.
    prd_signature: str | None
    spec_signature: str | None
    signatures: dict[str, str] = field(default_factory=dict)  # {doc_id: signature}
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


def _read_engine_version_at_onboard(project_path: Path) -> str | None:
    """Read `engine_version_at_onboard` from project meta or settings.

    Order of resolution:
    1. `.specbox-meta.json` if present (v6.0+ projects).
    2. `.claude/settings.local.json` → `specbox.engine_version_at_onboard`.
    3. None → caller treats as "unknown" (conservative policy).

    Returns None when the field is missing, which signals the caller to
    use the conservative `docs_for_version(None)` fallback.
    """
    meta_path = project_path / ".specbox-meta.json"
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("engine_version_at_onboard"):
                return str(data["engine_version_at_onboard"])
        except (json.JSONDecodeError, OSError):
            pass

    settings_path = project_path / ".claude" / "settings.local.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            specbox = data.get("specbox") or {}
            v = specbox.get("engine_version_at_onboard")
            if v:
                return str(v)
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _doc_is_template_pristine(zones: list[Zone]) -> bool:
    """True if every MANUAL zone of the doc carries status='template-pristine'.

    A pristine doc is the empty plantilla created by `upgrade_project` for
    a canonical doc introduced after the project's `engine_version_at_onboard`.
    The hook and the verifier MUST NOT report drift on pristine docs — they
    haven't been initialized yet.

    /discovery and /app-init strip the `status="template-pristine"` attribute
    automatically when the user fills in the first zone, which flips this
    helper to False and re-engages the normal sync flow.
    """
    manual_zones = [z for z in zones if z.kind == ZoneKind.MANUAL]
    if not manual_zones:
        # No manual zones at all (rare, but possible for auto-only docs).
        # Treat as non-pristine to avoid silencing legitimate drift.
        return False
    return all(z.status == "template-pristine" for z in manual_zones)


# ── Verify ──────────────────────────────────────────────────────────


def verify_app_docs_in_sync(project_path: str | Path = ".") -> SyncResult:
    """Return a SyncResult describing whether the canonical docs are aligned.

    No filesystem changes. Caller decides what to do with drift entries
    (hook can BLOCKING, /app-sync can offer auto-fix, etc.).

    v6.0 (UC-D005) — itera sobre `CANONICAL_DOCS` filtrados por
    `engine_version_at_onboard`. Docs introducidos después de la versión
    de onboarding del proyecto se ignoran. Docs en estado template-pristine
    se ignoran (no warning hasta primera inicialización).
    """
    root = Path(project_path).resolve()
    drift: list[DriftEntry] = []
    signatures: dict[str, str] = {}

    engine_version = _read_engine_version_at_onboard(root)
    eligible_docs = docs_for_version(engine_version)

    for doc in eligible_docs:
        full_path = root / doc.path
        if not full_path.exists():
            # Missing doc with introduced_in <= engine_version_at_onboard is
            # NOT drift — the project may simply not have run /app-init yet.
            # /app-init or /app-sync --rebuild-from-tracking is the path to
            # create it; the hook stays silent until the file exists.
            continue

        parsed = parse_document(full_path)
        if not parsed.is_well_formed:
            for err in parsed.errors:
                drift.append(
                    DriftEntry(
                        severity="error", document=doc.id, zone_id=None, message=err
                    )
                )
            # Skip signature comparison when the doc is malformed.
            continue

        # Pristine plantilla = no drift. Caller (hook, /app-sync) sees the
        # doc as "present but not yet filled in" and prints info, not warning.
        if _doc_is_template_pristine(parsed.zones):
            continue

        sig = compute_signature(parsed)
        signatures[doc.id] = sig

    locked = _load_lock(root).get("signatures", {})
    for doc_id, sig in signatures.items():
        locked_sig = locked.get(doc_id)
        if locked_sig and locked_sig != sig:
            drift.append(
                DriftEntry(
                    severity="warning",
                    document=doc_id,
                    zone_id=None,
                    message=f"{doc_id}.md signature drifted since the last recorded sync.",
                )
            )

    return SyncResult(
        in_sync=not [d for d in drift if d.severity in ("warning", "error")],
        # Backwards compat fields:
        prd_signature=signatures.get("app_prd"),
        spec_signature=signatures.get("app_spec"),
        signatures=signatures,
        drift=drift,
        locked_signatures=locked,
    )


def record_sync_signature(project_path: str | Path = ".") -> dict[str, Any]:
    """Snapshot current signatures into `.quality/app_docs_sync.lock`.

    v6.0 (UC-D005) — itera sobre todos los docs canónicos elegibles para
    la versión del proyecto. Docs no presentes en disco se eliminan del
    lock state para mantenerlo limpio.
    """
    root = Path(project_path).resolve()
    state = _load_lock(root)
    sigs = state.setdefault("signatures", {})

    engine_version = _read_engine_version_at_onboard(root)
    eligible_docs = docs_for_version(engine_version)
    eligible_ids = {d.id for d in eligible_docs}

    for doc in eligible_docs:
        full_path = root / doc.path
        if full_path.exists():
            parsed = parse_document(full_path)
            if parsed.is_well_formed:
                sigs[doc.id] = compute_signature(parsed)
        elif doc.id in sigs:
            # Doc was tracked but is now gone — clean up the stale signature.
            del sigs[doc.id]

    # Also clean up signatures for docs that aren't eligible for this project
    # (e.g. app_market lingering in a v5.x meta.json reverted to v5.29).
    for stale_id in list(sigs.keys()):
        if stale_id not in eligible_ids:
            del sigs[stale_id]

    state["recorded_at"] = datetime.now(timezone.utc).isoformat()
    _save_lock(state, root)
    return state


# ── Sync (apply event) ──────────────────────────────────────────────


# Built once at import time from the registry. Same shape as the v5.29
# hardcoded dict (`{event: [(doc_id, zone_id), ...]}`), so legacy callers
# that introspect EVENT_ZONE_MAP still work. Refactor extension point:
# new events go in the corresponding CanonicalDoc.event_zone_map in
# registry.py — no edits to this file needed.
EVENT_ZONE_MAP: dict[str, list[tuple[str, str]]] = build_event_zone_map()


def sync_app_docs(
    event_type: str,
    payload: dict[str, Any] | None = None,
    project_path: str | Path = ".",
) -> dict[str, Any]:
    """Apply an event-driven update to the relevant auto-zones.

    The body for each zone is computed by `_render_zone_body(zone_id, payload, project_path)`.
    Idempotent: signature-stable rewrites do nothing.

    Returns a structured report describing which zones were touched.

    v6.0: el dispatcher resuelve `doc_id → path` via `get_doc()` del
    registro en lugar de mapear hardcoded a `PRD_PATH`/`SPEC_PATH`.
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
        doc = get_doc(document_name)
        if doc is None:
            skipped.append(
                {
                    "document": document_name,
                    "zone_id": zone_id,
                    "reason": "unknown_canonical_doc",
                }
            )
            continue

        full_path = root / doc.path
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
        if backend not in {"freeform", "trello", "plane", "native"}:
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
        if backend == "native" and payload.get("native_project_id"):
            lines.append(f"- **Native project id:** {payload['native_project_id']}")
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

    if zone_id == "exportable_copy":
        # Derived from app_market.md ICPs + JTBDs. Renderer added when
        # /discovery bootstrap mode (UC-D002) implements the LLM-driven
        # generation. Until then, this is a passthrough so the event
        # logs the trigger but doesn't rewrite the zone.
        return None

    return None


# ── MCP registration ────────────────────────────────────────────────


def register_sync_tools(mcp: FastMCP, engine_path: Path) -> None:
    @mcp.tool
    def verify_app_docs(project_path: str = ".") -> dict[str, Any]:
        """Check whether canonical docs under `doc/app/` are in sync.

        Returns {in_sync, prd_signature, spec_signature, signatures, drift[], locked_signatures}.
        v6.0: `signatures` is the new dict {doc_id: signature} covering all
        canonical docs (including `app_market.md` when introduced_in <=
        project's engine_version_at_onboard). `prd_signature` and
        `spec_signature` preserved for backwards compat.
        Read-only: never modifies the project.
        """
        result = verify_app_docs_in_sync(project_path)
        return {
            "in_sync": result.in_sync,
            "prd_signature": result.prd_signature,
            "spec_signature": result.spec_signature,
            "signatures": result.signatures,
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

        Supported event_types (v6.0): complete_uc, move_uc, add_uc, delete_uc,
        mark_ac_batch, set_auth_token, lockfile_change, framework_detected,
        release_version_bump, autopilot_config_change,
        canonical_decision_created, canonical_decision_revoked,
        app_market_icp_added, app_market_jtbd_added, nsm_updated.

        Idempotent: re-running with identical payload writes nothing.
        """
        return sync_app_docs(event_type, payload or {}, project_path)

    @mcp.tool
    def record_app_docs_signature(project_path: str = ".") -> dict[str, Any]:
        """Snapshot current canonical doc signatures for future drift detection."""
        return record_sync_signature(project_path)
