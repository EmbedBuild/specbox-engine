"""Discovery tools for v6.0 — Product Discovery integration.

Registers MCP tools that support the `/discovery` slash command flow.

**v6.0.1 — MCP Path Contract**

The three @mcp.tool functions are content-passing: they never touch the
filesystem of the MCP host. The client (skill) reads `doc/app/app_market.md`
and `doc/discovery/<feature>/icp_jtbd.md` locally, passes the content as
strings, and writes back any artifact returned by the tool.

This makes the tools host-agnostic — they behave identically whether the
MCP server runs locally (stdio) or remotely (HTTP/SSE on a VPS or in
claude.ai web).

Tools registered:

* `start_discovery(feature_name, app_market_content, existing_artifact_content, mode="auto")`
* `validate_discovery_completeness(feature_name, icp_jtbd_content)`
* `detect_v60_migration_case(app_prd_content, app_spec_content, app_market_content, settings_local_json_content, active_uc_present, pending_feedback_files, has_discovery_dir, has_app_dir)`

The Path-based private helpers below remain for backwards compatibility with
internal callers and unit tests; they are no longer reachable from the MCP
boundary.

US-D01 UC-D001 + UC-D002, plus part of US-D03 UC-D004 (the
v60_migration_case detector).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from server.app_docs.registry import CANONICAL_DOCS, get_doc
from server.app_docs.zones import parse_document


DISCOVERY_DIR = "doc/discovery"
APP_MARKET_PATH = "doc/app/app_market.md"


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_discovery_id() -> str:
    return f"disc-{uuid.uuid4().hex[:12]}"


def _feature_dir(project_path: Path, feature_name: str) -> Path:
    """Compute doc/discovery/<feature_name>/ — case-sensitive."""
    return project_path / DISCOVERY_DIR / feature_name


def _icp_jtbd_path(project_path: Path, feature_name: str) -> Path:
    return _feature_dir(project_path, feature_name) / "icp_jtbd.md"


def _app_market_is_pristine_or_missing(project_path: Path) -> bool:
    """True if app_market.md doesn't exist OR all manual zones are
    template-pristine. Used by start_discovery to detect bootstrap mode.

    Path-based variant kept for internal callers and tests. The MCP boundary
    uses :func:`_app_market_content_is_pristine_or_missing`.
    """
    market_path = project_path / APP_MARKET_PATH
    if not market_path.exists():
        return True
    try:
        parsed = parse_document(market_path)
    except Exception:
        return True
    if not parsed.is_well_formed:
        return True
    manual_zones = [z for z in parsed.zones if z.kind.value == "manual"]
    if not manual_zones:
        return False
    return all(z.status == "template-pristine" for z in manual_zones)


def _app_market_content_is_pristine_or_missing(
    app_market_content: str | None,
) -> bool:
    """Content-passing variant of :func:`_app_market_is_pristine_or_missing`.

    Returns True when:
      * content is None or empty (treated as missing), OR
      * content is malformed, OR
      * the document has no manual zones, OR
      * every manual zone is template-pristine.
    """
    if app_market_content is None or not app_market_content.strip():
        return True
    try:
        parsed = parse_document("app_market.md", content=app_market_content)
    except Exception:
        return True
    if not parsed.is_well_formed:
        return True
    manual_zones = [z for z in parsed.zones if z.kind.value == "manual"]
    if not manual_zones:
        return False
    return all(z.status == "template-pristine" for z in manual_zones)


# ─────────────────────────────────────────────────────────────────────
# Artifact rendering — initial icp_jtbd.md skeleton
# ─────────────────────────────────────────────────────────────────────


def _render_initial_icp_jtbd(
    feature_name: str,
    discovery_id: str,
    mode: str,
    app_market_signature: str | None,
) -> str:
    """Render the initial empty icp_jtbd.md.

    The skill (`.claude/skills/discovery/SKILL.md`) fills in the actual
    content during the 3-phase conversational flow. This tool only
    creates the skeleton with metadata.
    """
    inherit_line = (
        f"doc/app/app_market.md @ {app_market_signature}"
        if app_market_signature
        else "(bootstrap mode — app_market.md will be created during this flow)"
    )

    return f"""# Discovery: {feature_name}

**Discovery ID**: {discovery_id}
**Created**: {_now_iso()}
**Status**: DISCOVERY_INCOMPLETE
**Mode**: {mode}
**Source of inheritance**: {inherit_line}

## ICPs involucrados

_(Pendiente — fase 1 del flujo `/discovery` los rellena)_

## JTBDs racionales

_(Pendiente — fase 2 del flujo `/discovery`)_

## JTBDs emocionales

_(Pendiente — fase 2 del flujo `/discovery`)_

## Validation evidence

_(Pendiente — fase 3 del flujo `/discovery`)_

## Drift from app_market

- **Nuevos ICPs introducidos**: _(pendiente análisis)_
- **Nuevos JTBDs introducidos**: _(pendiente análisis)_
- **Resolución**: _(pendiente)_

## Verdict

**DISCOVERY_INCOMPLETE** because:
- Discovery flow has not yet been run.

---

> Este artefacto se completa interactivamente via el skill `/discovery`.
> Tras completarlo, `validate_discovery_completeness` actualizará el verdict
> a `READY_FOR_PRD` cuando todas las secciones estén llenas.
"""


# ─────────────────────────────────────────────────────────────────────
# Completeness validation
# ─────────────────────────────────────────────────────────────────────


# Regex patterns for each required section. Each pattern is "satisfied"
# when the content under the section header is NOT just a pending placeholder.
PENDING_MARKERS = (
    r"_\(Pendiente",
    r"_\(pendiente",
    r"_\(.*pendiente.*\)_",
)


def _section_has_real_content(content: str, section_re: str) -> tuple[bool, str]:
    """Return (satisfied, snippet). satisfied=True when the section body
    has content that is not a pending placeholder."""
    m = re.search(section_re, content, re.IGNORECASE | re.DOTALL)
    if not m:
        return (False, "section_not_found")
    body = m.group(1).strip()
    if not body:
        return (False, "empty_body")
    stripped = body.strip()
    is_pending = any(re.search(p, stripped) for p in PENDING_MARKERS)
    if is_pending and len(stripped) < 200:
        return (False, "still_placeholder")
    return (True, stripped[:120])


def _validate_icp_jtbd(content: str) -> dict[str, Any]:
    """Parse icp_jtbd.md and report missing sections.

    Returns:
        {
          "verdict": "READY_FOR_PRD" | "DISCOVERY_INCOMPLETE",
          "missing": [...],
          "drift": {...},
        }
    """
    missing: list[str] = []

    ok, _ = _section_has_real_content(
        content,
        r"## ICPs involucrados\s*\n(.+?)(?=\n## |\Z)",
    )
    if not ok:
        missing.append("icps_involucrados")

    ok, _ = _section_has_real_content(
        content,
        r"## JTBDs racionales\s*\n(.+?)(?=\n## |\Z)",
    )
    if not ok:
        missing.append("jtbds_racionales")

    ok, _ = _section_has_real_content(
        content,
        r"## JTBDs emocionales\s*\n(.+?)(?=\n## |\Z)",
    )
    if not ok:
        missing.append("jtbds_emocionales")

    ok, _ = _section_has_real_content(
        content,
        r"## Validation evidence\s*\n(.+?)(?=\n## |\Z)",
    )
    if not ok:
        missing.append("validation_evidence")

    drift_match = re.search(
        r"## Drift from app_market\s*\n(.+?)(?=\n## |\Z)",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    drift_info: dict[str, Any] = {"section_present": bool(drift_match)}
    if drift_match:
        drift_body = drift_match.group(1)
        has_resolution = bool(
            re.search(
                r"Resolución.*?(feature_creep_rejected|app_market_updated|"
                r"documented_exception|no drift detected)",
                drift_body,
                re.IGNORECASE,
            )
        )
        drift_info["resolved"] = has_resolution
        if not has_resolution and "pendiente" in drift_body.lower():
            missing.append("drift_resolution")

    verdict = "READY_FOR_PRD" if not missing else "DISCOVERY_INCOMPLETE"

    return {
        "verdict": verdict,
        "missing": missing,
        "drift": drift_info,
    }


# ─────────────────────────────────────────────────────────────────────
# Migration case detection — content-passing core
# ─────────────────────────────────────────────────────────────────────


def _detect_v60_case_from_content(
    *,
    app_prd_content: str | None,
    app_spec_content: str | None,
    app_market_content: str | None,
    settings_local_json_content: str | None,
    active_uc_present: bool,
    pending_critical_feedback: list[str],
    has_discovery_dir: bool,
    has_app_dir: bool,
) -> dict[str, Any]:
    """Classify a project into one of the 8 v6.0 migration cases using
    content + filesystem signals supplied by the client.

    The client is responsible for reading the local repository and packaging
    the signals into the parameters above.
    """
    notes: list[str] = []

    settings: dict[str, Any] = {}
    if settings_local_json_content:
        try:
            settings = json.loads(settings_local_json_content)
        except json.JSONDecodeError:
            settings = {}
    specbox_block = settings.get("specbox") or {}
    multirepo_block = settings.get("multirepo") or {}

    # Case 3: active UC takes priority — never disrupt in-progress work
    if active_uc_present:
        return {
            "case_id": "case_3_active_uc",
            "case_description": "Active UC in progress — defer v6.0 migration",
            "steps": [
                "Wait for the current UC to complete or be explicitly abandoned",
                "Once the active UC closes, return to /app-init or upgrade_project to apply v6.0 changes",
            ],
            "backup_required": False,
            "notes": ["Case 3 always takes priority over backend-related cases"],
        }

    # Case 4: pending critical/major feedback
    if pending_critical_feedback:
        return {
            "case_id": "case_4_pending_feedback",
            "case_description": "Pending critical/major feedback blocks migration",
            "steps": [
                "Resolve feedback via /feedback or commit feedback resolution",
                "Re-run detect_v60_migration_case after resolution",
            ],
            "backup_required": False,
            "notes": [f"Blocking feedback: {name}" for name in pending_critical_feedback],
        }

    # Multirepo cases (5, 6)
    if multirepo_block.get("enabled"):
        role = multirepo_block.get("role", "")
        if role == "satellite":
            return {
                "case_id": "case_6_multirepo_satellite",
                "case_description": "Multirepo satellite — inherits from orchestrator",
                "steps": [
                    "No direct migration action required",
                    "When the orchestrator applies v6.0, this satellite inherits automatically",
                ],
                "backup_required": False,
                "notes": [f"Orchestrator: {multirepo_block.get('orchestrator', 'unknown')}"],
            }
        if role == "orchestrator":
            return {
                "case_id": "case_5_multirepo_orchestrator",
                "case_description": "Multirepo orchestrator — apply v6.0 here; satellites inherit",
                "steps": [
                    "Apply v6.0 to this orchestrator project first",
                    "Run /app-init --refresh to detect missing canonical docs (e.g. app_market.md)",
                    "After this orchestrator is on v6.0, satellites pick up the change on their next read",
                ],
                "backup_required": False,
                "notes": [],
            }

    # Case 1: pre-v5.29 (no doc/app/)
    if not has_app_dir:
        return {
            "case_id": "case_1_pre_v529",
            "case_description": "Pre-v5.29 project — no doc/app/",
            "steps": [
                "Run v5.29 migration first: /app-init creates app_prd.md + app_spec.md",
                "Then apply v6.0: /app-init --refresh will offer app_market.md plantilla",
                "Run /discovery <feature> for the first feature → bootstrap mode fills app_market.md",
            ],
            "backup_required": False,
            "notes": ["v5.29 migration is a prerequisite for v6.0"],
        }

    has_app_market = bool(app_market_content)

    # Case 8: pre-existing doc/discovery/ without app_market
    if has_discovery_dir and not has_app_market:
        return {
            "case_id": "case_8_manual_discovery",
            "case_description": "Pre-existing doc/discovery/ without app_market.md",
            "steps": [
                "Review existing doc/discovery/*/icp_jtbd.md for content",
                "Run /app-init --upgrade-zones to insert canonical markers if needed",
                "Then /discovery in bootstrap mode to consolidate into app_market.md",
            ],
            "backup_required": True,
            "notes": ["Manual content detected — backup before applying canonical structure"],
        }

    engine_version_at_onboard = specbox_block.get("engine_version_at_onboard")
    if engine_version_at_onboard and engine_version_at_onboard.startswith("6."):
        if has_app_market:
            return {
                "case_id": "case_7_fresh_v6",
                "case_description": "Fresh-clone or new project on v6.0 — nothing to migrate",
                "steps": [
                    "Project already on v6.0 with app_market.md present",
                    "Run /discovery <feature> for any new feature",
                ],
                "backup_required": False,
                "notes": [],
            }

    # Case 2 default: v5.29-v5.35 with canonical docs but no app_market
    if not has_app_market:
        return {
            "case_id": "case_2_v529_v535",
            "case_description": "v5.29-v5.35 project with canonical docs but no app_market.md",
            "steps": [
                "Run upgrade_project to bump engine version and capture engine_version_at_onboard",
                "upgrade_project will offer app_market.md plantilla via canonical_docs_to_create",
                "Copy the plantilla content to doc/app/app_market.md (status='template-pristine')",
                "discovery.gate_mode defaults to 'off' — no behavior change unless user opts in",
                "Run /discovery <feature> when ready to fill in ICPs + JTBDs (bootstrap mode)",
            ],
            "backup_required": False,
            "notes": [
                f"engine_version_at_onboard={engine_version_at_onboard or 'unknown'}",
                "Plantillas pristine produce no drift warnings",
            ],
        }

    return {
        "case_id": "case_7_fresh_v6",
        "case_description": "Project has app_market.md present — assuming v6.0+ state",
        "steps": [
            "Verify engine_version_at_onboard is correctly set in .claude/settings.local.json",
            "Run /discovery <feature> as needed",
        ],
        "backup_required": False,
        "notes": notes or ["app_market.md detected without explicit v6.x version marker"],
    }


def _detect_v60_case(project_path: Path) -> dict[str, Any]:
    """Path-based variant kept for internal callers and tests.

    Reads filesystem signals from ``project_path`` and delegates to
    :func:`_detect_v60_case_from_content`.
    """
    settings_path = project_path / ".claude" / "settings.local.json"
    settings_text: str | None = None
    if settings_path.exists():
        try:
            settings_text = settings_path.read_text(encoding="utf-8")
        except OSError:
            settings_text = None

    active_uc_path = project_path / ".quality" / "active_uc.json"
    active_uc_present = active_uc_path.exists()

    feedback_dir = project_path / ".quality" / "evidence" / "feedback"
    pending_critical: list[str] = []
    if feedback_dir.exists():
        for fb in feedback_dir.glob("*.json"):
            try:
                data = json.loads(fb.read_text(encoding="utf-8"))
                if data.get("severity") in {"critical", "major"} and not data.get(
                    "resolved_at"
                ):
                    pending_critical.append(fb.name)
            except Exception:
                continue

    app_dir = project_path / "doc" / "app"
    has_app_dir = app_dir.exists()

    discovery_dir = project_path / DISCOVERY_DIR
    has_discovery_dir = discovery_dir.exists()

    market_path = project_path / APP_MARKET_PATH
    app_market_content: str | None = None
    if market_path.exists():
        try:
            app_market_content = market_path.read_text(encoding="utf-8")
        except OSError:
            app_market_content = None

    prd_path = project_path / "doc" / "app" / "app_prd.md"
    app_prd_content: str | None = None
    if prd_path.exists():
        try:
            app_prd_content = prd_path.read_text(encoding="utf-8")
        except OSError:
            app_prd_content = None

    spec_path = project_path / "doc" / "app" / "app_spec.md"
    app_spec_content: str | None = None
    if spec_path.exists():
        try:
            app_spec_content = spec_path.read_text(encoding="utf-8")
        except OSError:
            app_spec_content = None

    return _detect_v60_case_from_content(
        app_prd_content=app_prd_content,
        app_spec_content=app_spec_content,
        app_market_content=app_market_content,
        settings_local_json_content=settings_text,
        active_uc_present=active_uc_present,
        pending_critical_feedback=pending_critical,
        has_discovery_dir=has_discovery_dir,
        has_app_dir=has_app_dir,
    )


# ─────────────────────────────────────────────────────────────────────
# Signature helper (content-passing)
# ─────────────────────────────────────────────────────────────────────


def _compute_app_market_signature(app_market_content: str | None) -> str | None:
    """Compute a short signature for inheritance tracking."""
    if not app_market_content or not app_market_content.strip():
        return None
    try:
        from server.app_docs.zones import compute_signature

        parsed = parse_document("app_market.md", content=app_market_content)
        if parsed.is_well_formed:
            return compute_signature(parsed)[:16]
    except Exception:
        return None
    return None


def _parse_existing_artifact(content: str | None) -> dict[str, Any]:
    """Extract discovery_id and mode_used from an existing icp_jtbd.md.

    Returns dict with keys: discovery_id (str), mode_used (str).
    Falls back to "unknown" when fields can't be parsed.
    """
    if not content:
        return {"discovery_id": "unknown", "mode_used": "unknown"}
    disc_id_match = re.search(r"\*\*Discovery ID\*\*:\s*(disc-\w+)", content)
    mode_match = re.search(r"\*\*Mode\*\*:\s*(standard|bootstrap)", content)
    return {
        "discovery_id": disc_id_match.group(1) if disc_id_match else "unknown",
        "mode_used": mode_match.group(1) if mode_match else "unknown",
    }


# ─────────────────────────────────────────────────────────────────────
# MCP tool registration (content-passing API, v6.0.1)
# ─────────────────────────────────────────────────────────────────────


def register_product_discovery_tools(mcp: FastMCP, engine_path: Path) -> None:
    """Register the v6.0 Product Discovery tools (content-passing v6.0.1).

    The ``engine_path`` parameter is kept for API compatibility with
    pre-v6.0.1 callers but is unused — the tools no longer touch any
    filesystem.
    """
    @mcp.tool
    def start_discovery(
        feature_name: str,
        app_market_content: str | None = None,
        existing_artifact_content: str | None = None,
        mode: str = "auto",
    ) -> dict[str, Any]:
        """Initialize or resume a /discovery session for a feature.

        **v6.0.1 — content-passing API**

        The MCP tool no longer reads or writes the client filesystem. The
        caller is expected to:

        1. Read ``doc/app/app_market.md`` locally and pass the content via
           ``app_market_content`` (or ``None`` if the file does not exist).
        2. Read ``doc/discovery/<feature_name>/icp_jtbd.md`` locally if it
           exists and pass the content via ``existing_artifact_content``
           (``None`` for fresh sessions).
        3. Write the returned ``skeleton_content`` to
           ``doc/discovery/<feature_name>/icp_jtbd.md`` when ``status``
           is ``"created"``.

        Args:
            feature_name: Slug-friendly feature identifier
                (e.g. ``"user_export"``). Only ``[a-zA-Z0-9_-]+`` is allowed.
            app_market_content: Current content of ``doc/app/app_market.md``,
                or ``None`` if the file does not exist on the client.
            existing_artifact_content: Current content of the feature's
                ``icp_jtbd.md`` if one already exists; ``None`` for a
                fresh session.
            mode: ``"auto"`` (default — detects bootstrap vs standard based
                on whether ``app_market_content`` is non-pristine), ``"standard"``
                (force standard mode), ``"bootstrap"`` (force bootstrap
                regardless of ``app_market_content`` state).

        Returns:
            On creation::

                {
                  "discovery_id": "disc-...",
                  "status": "created",
                  "artifact_path": "doc/discovery/<feature>/icp_jtbd.md",
                  "mode_used": "standard" | "bootstrap",
                  "app_market_present": bool,
                  "app_market_signature": str | None,
                  "skeleton_content": "...",  # ← client writes this locally
                  "next_step": str,
                }

            On resume (``existing_artifact_content`` was provided)::

                {
                  "discovery_id": "disc-... or 'unknown'",
                  "status": "resumable",
                  "artifact_path": "doc/discovery/<feature>/icp_jtbd.md",
                  "mode_used": "standard" | "bootstrap" | "unknown",
                  "app_market_present": bool,
                  "current_verdict": "READY_FOR_PRD" | "DISCOVERY_INCOMPLETE",
                  "missing": [...],
                  "next_step": str,
                }
        """
        if not feature_name or not feature_name.strip():
            return {
                "error": "feature_name is required and cannot be empty",
                "code": "INVALID_FEATURE_NAME",
            }
        feature_name = feature_name.strip()
        if not re.match(r"^[a-zA-Z0-9_-]+$", feature_name):
            return {
                "error": (
                    f"feature_name {feature_name!r} contains invalid characters. "
                    "Use only letters, numbers, underscore, hyphen."
                ),
                "code": "INVALID_FEATURE_NAME",
            }

        relative_artifact = f"{DISCOVERY_DIR}/{feature_name}/icp_jtbd.md"
        app_market_present = bool(app_market_content and app_market_content.strip())

        if existing_artifact_content is not None and existing_artifact_content.strip():
            parsed_prev = _parse_existing_artifact(existing_artifact_content)
            validation = _validate_icp_jtbd(existing_artifact_content)
            return {
                "discovery_id": parsed_prev["discovery_id"],
                "status": "resumable",
                "artifact_path": relative_artifact,
                "mode_used": parsed_prev["mode_used"],
                "app_market_present": app_market_present,
                "current_verdict": validation["verdict"],
                "missing": validation.get("missing", []),
                "next_step": (
                    "/discovery is resumable — re-invoke the skill to continue "
                    "filling in the remaining sections, or start fresh by "
                    "deleting the existing artifact."
                ),
            }

        if mode not in {"auto", "standard", "bootstrap"}:
            return {
                "error": f"mode must be auto|standard|bootstrap, got {mode!r}",
                "code": "INVALID_MODE",
            }
        if mode == "auto":
            mode_used = (
                "bootstrap"
                if _app_market_content_is_pristine_or_missing(app_market_content)
                else "standard"
            )
        else:
            mode_used = mode

        app_market_sig: str | None = None
        if mode_used == "standard":
            app_market_sig = _compute_app_market_signature(app_market_content)

        discovery_id = _new_discovery_id()
        skeleton = _render_initial_icp_jtbd(
            feature_name=feature_name,
            discovery_id=discovery_id,
            mode=mode_used,
            app_market_signature=app_market_sig,
        )

        return {
            "discovery_id": discovery_id,
            "status": "created",
            "artifact_path": relative_artifact,
            "mode_used": mode_used,
            "app_market_present": app_market_present,
            "app_market_signature": app_market_sig,
            "skeleton_content": skeleton,
            "next_step": (
                "Write the returned `skeleton_content` to "
                f"`{relative_artifact}` and invoke the /discovery skill to walk "
                "through the 3 phases (ICP identification, JTBD extraction, "
                "validation gate). The skill will fill in this artifact "
                "interactively."
                if mode_used == "standard"
                else (
                    "Bootstrap mode active: write the returned "
                    f"`skeleton_content` to `{relative_artifact}`, then the "
                    "skill will first fill in `doc/app/app_market.md` "
                    "(project-level), then descend to the feature-level "
                    "icp_jtbd.md."
                )
            ),
        }

    @mcp.tool
    def validate_discovery_completeness(
        feature_name: str,
        icp_jtbd_content: str | None = None,
    ) -> dict[str, Any]:
        """Check whether icp_jtbd.md is complete enough to proceed to /prd.

        **v6.0.1 — content-passing API**

        The caller is expected to read
        ``doc/discovery/<feature_name>/icp_jtbd.md`` locally and pass its
        content via ``icp_jtbd_content``. When the file does not exist on
        the client, pass ``None``.

        Args:
            feature_name: Slug-friendly feature identifier. Only used to
                construct the diagnostic ``artifact_path`` in the response.
            icp_jtbd_content: Current content of
                ``doc/discovery/<feature_name>/icp_jtbd.md``, or ``None``
                when the file does not exist locally.

        Returns:
            {
              "verdict": "READY_FOR_PRD" | "DISCOVERY_INCOMPLETE",
              "missing": ["icps_involucrados", "jtbds_emocionales", ...],
              "drift": { "section_present": bool, "resolved": bool },
              "artifact_path": "doc/discovery/<feature>/icp_jtbd.md",
            }
        """
        relative_artifact = f"{DISCOVERY_DIR}/{feature_name}/icp_jtbd.md"

        if icp_jtbd_content is None or not icp_jtbd_content.strip():
            return {
                "verdict": "DISCOVERY_INCOMPLETE",
                "missing": ["artifact_not_found"],
                "drift": {"section_present": False, "resolved": False},
                "artifact_path": relative_artifact,
                "error": (
                    f"doc/discovery/{feature_name}/icp_jtbd.md was not provided. "
                    f"Run start_discovery({feature_name!r}) first and write the "
                    "returned skeleton_content to the artifact path."
                ),
            }

        result = _validate_icp_jtbd(icp_jtbd_content)
        result["artifact_path"] = relative_artifact
        return result

    @mcp.tool
    def detect_v60_migration_case(
        app_prd_content: str | None = None,
        app_spec_content: str | None = None,
        app_market_content: str | None = None,
        settings_local_json_content: str | None = None,
        active_uc_present: bool = False,
        pending_critical_feedback: list[str] | None = None,
        has_discovery_dir: bool = False,
        has_app_dir: bool = False,
    ) -> dict[str, Any]:
        """Classify a project into one of 8 v6.0 migration cases.

        **v6.0.1 — content-passing API**

        The caller is expected to read the relevant client filesystem
        signals and pass them as parameters. The recommended bundle:

        * ``doc/app/app_prd.md`` → ``app_prd_content``
        * ``doc/app/app_spec.md`` → ``app_spec_content``
        * ``doc/app/app_market.md`` → ``app_market_content``
        * ``.claude/settings.local.json`` → ``settings_local_json_content``
        * Existence of ``.quality/active_uc.json`` → ``active_uc_present``
        * List of unresolved critical/major feedback files in
          ``.quality/evidence/feedback/`` → ``pending_critical_feedback``
        * Existence of ``doc/discovery/`` → ``has_discovery_dir``
        * Existence of ``doc/app/`` → ``has_app_dir``

        Returns:
            {
              "case_id": "case_2_v529_v535",
              "case_description": "...",
              "steps": [...],
              "backup_required": bool,
              "notes": [...],
            }
        """
        return _detect_v60_case_from_content(
            app_prd_content=app_prd_content,
            app_spec_content=app_spec_content,
            app_market_content=app_market_content,
            settings_local_json_content=settings_local_json_content,
            active_uc_present=active_uc_present,
            pending_critical_feedback=pending_critical_feedback or [],
            has_discovery_dir=has_discovery_dir,
            has_app_dir=has_app_dir,
        )
