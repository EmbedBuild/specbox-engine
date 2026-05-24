"""Discovery tools for v6.0 — Product Discovery integration.

Registers MCP tools that support the `/discovery` slash command flow:

* `start_discovery(feature_name, project_path, mode="auto")` — initialize
  or resume a discovery session for a feature. Returns the artifact
  path + mode resolution (auto detects bootstrap vs standard).

* `validate_discovery_completeness(feature_name, project_path)` —
  check whether `doc/discovery/<feature>/icp_jtbd.md` is complete enough
  to proceed to `/prd`. Returns READY_FOR_PRD or DISCOVERY_INCOMPLETE
  with specific missing items.

* `detect_v60_migration_case(project_path)` — classify a project into
  one of the 8 v6.0 migration cases (PRD §4.8). Analogous to the v5.29
  `detect_v529_migration_case` precedent.

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
    """
    market_path = project_path / APP_MARKET_PATH
    if not market_path.exists():
        return True
    try:
        parsed = parse_document(market_path)
    except Exception:
        return True
    if not parsed.is_well_formed:
        # Malformed doc — treat as needing initialization
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
    # If the body consists exclusively of pending placeholders, not real content.
    stripped = body.strip()
    is_pending = any(re.search(p, stripped) for p in PENDING_MARKERS)
    if is_pending and len(stripped) < 200:
        # Heuristic: short bodies that match a pending pattern are placeholders.
        # Longer bodies likely have real content even if they mention "pendiente".
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

    # 1. ICPs involucrados
    ok, _ = _section_has_real_content(
        content,
        r"## ICPs involucrados\s*\n(.+?)(?=\n## |\Z)",
    )
    if not ok:
        missing.append("icps_involucrados")

    # 2. JTBDs racionales (al menos uno)
    ok, _ = _section_has_real_content(
        content,
        r"## JTBDs racionales\s*\n(.+?)(?=\n## |\Z)",
    )
    if not ok:
        missing.append("jtbds_racionales")

    # 3. JTBDs emocionales (al menos uno)
    ok, _ = _section_has_real_content(
        content,
        r"## JTBDs emocionales\s*\n(.+?)(?=\n## |\Z)",
    )
    if not ok:
        missing.append("jtbds_emocionales")

    # 4. Validation evidence
    ok, _ = _section_has_real_content(
        content,
        r"## Validation evidence\s*\n(.+?)(?=\n## |\Z)",
    )
    if not ok:
        missing.append("validation_evidence")

    # 5. Drift from app_market — resolución registrada
    drift_match = re.search(
        r"## Drift from app_market\s*\n(.+?)(?=\n## |\Z)",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    drift_info: dict[str, Any] = {"section_present": bool(drift_match)}
    if drift_match:
        drift_body = drift_match.group(1)
        # Check for resolution keyword
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

    # Verdict
    verdict = "READY_FOR_PRD" if not missing else "DISCOVERY_INCOMPLETE"

    return {
        "verdict": verdict,
        "missing": missing,
        "drift": drift_info,
    }


# ─────────────────────────────────────────────────────────────────────
# Migration case detector (v6.0)
# ─────────────────────────────────────────────────────────────────────


def _detect_v60_case(project_path: Path) -> dict[str, Any]:
    """Classify a project into one of the 8 v6.0 migration cases.

    PRD §4.8:
      1. Pre-v5.29 (sin doc/app/)
      2. v5.29-v5.35 con app_prd+app_spec, sin app_market.md
      3. Active UC en curso
      4. Pending feedback bloqueante
      5. Multirepo orchestrator
      6. Multirepo satellite
      7. Fresh-clone post-v6.0
      8. Proyecto con doc/discovery/ manual pre-existente
    """
    notes: list[str] = []

    # Settings
    settings_path = project_path / ".claude" / "settings.local.json"
    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}
    specbox_block = settings.get("specbox") or {}
    multirepo_block = settings.get("multirepo") or {}

    # Active UC check (case 3 takes priority — never disrupt in-progress work)
    active_uc_path = project_path / ".quality" / "active_uc.json"
    if active_uc_path.exists():
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

    # Pending feedback check (case 4)
    feedback_dir = project_path / ".quality" / "evidence" / "feedback"
    if feedback_dir.exists():
        for fb in feedback_dir.glob("*.json"):
            try:
                data = json.loads(fb.read_text(encoding="utf-8"))
                if data.get("severity") in {"critical", "major"} and not data.get(
                    "resolved_at"
                ):
                    return {
                        "case_id": "case_4_pending_feedback",
                        "case_description": "Pending critical/major feedback blocks migration",
                        "steps": [
                            "Resolve feedback via /feedback or commit feedback resolution",
                            "Re-run detect_v60_migration_case after resolution",
                        ],
                        "backup_required": False,
                        "notes": [f"Blocking feedback: {fb.name}"],
                    }
            except Exception:
                continue

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

    # Pre-v5.29 case (1) — no doc/app/ at all
    app_dir = project_path / "doc" / "app"
    if not app_dir.exists():
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

    # Case 8: manual doc/discovery/ pre-existing
    discovery_dir = project_path / DISCOVERY_DIR
    has_app_market = (project_path / APP_MARKET_PATH).exists()
    if discovery_dir.exists() and not has_app_market:
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

    # Case 7: fresh-clone post-v6.0
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

    # Case 2 (default): v5.29-v5.35 with app_prd+app_spec, no app_market
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

    # Fallback: project already has app_market.md but engine_version_at_onboard
    # missing/<v6 — uncommon but possible after manual edits.
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


# ─────────────────────────────────────────────────────────────────────
# MCP tool registration
# ─────────────────────────────────────────────────────────────────────


def register_product_discovery_tools(mcp: FastMCP, engine_path: Path) -> None:
    """Register the v6.0 Product Discovery tools.

    Distinct from `server/app_docs/discovery.py:register_discovery_tools`
    which exposes the backend auto-detector (v5.29). This function registers
    the v6.0 product-discovery flow (start_discovery,
    validate_discovery_completeness, detect_v60_migration_case).
    """
    @mcp.tool
    def start_discovery(
        feature_name: str,
        project_path: str = ".",
        mode: str = "auto",
    ) -> dict[str, Any]:
        """Initialize or resume a /discovery session for a feature.

        v6.0 (UC-D001 + UC-D002). Creates doc/discovery/<feature_name>/icp_jtbd.md
        with a UUID + initial skeleton. Idempotent — a second call with the
        same feature_name detects the existing artifact and returns
        status="resumable".

        Args:
            feature_name: Slug-friendly feature identifier (e.g. "user_export").
            project_path: Absolute or relative path to the project repo.
            mode: "auto" (default — detects bootstrap vs standard based on
                whether app_market.md exists and is non-pristine),
                "standard" (force standard mode), "bootstrap" (force
                bootstrap regardless of app_market.md state).

        Returns:
            {
              "discovery_id": "disc-...",
              "status": "created" | "resumable",
              "artifact_path": "doc/discovery/<feature>/icp_jtbd.md",
              "mode_used": "standard" | "bootstrap",
              "app_market_present": bool,
              "next_step": str,
            }
        """
        if not feature_name or not feature_name.strip():
            return {
                "error": "feature_name is required and cannot be empty",
                "code": "INVALID_FEATURE_NAME",
            }
        feature_name = feature_name.strip()
        # Sanity check — feature names should be slug-friendly
        if not re.match(r"^[a-zA-Z0-9_-]+$", feature_name):
            return {
                "error": (
                    f"feature_name {feature_name!r} contains invalid characters. "
                    "Use only letters, numbers, underscore, hyphen."
                ),
                "code": "INVALID_FEATURE_NAME",
            }

        root = Path(project_path).resolve()
        feature_dir = _feature_dir(root, feature_name)
        artifact = _icp_jtbd_path(root, feature_name)

        # Idempotency: if the artifact exists, return resumable status
        if artifact.exists():
            try:
                content = artifact.read_text(encoding="utf-8")
                disc_id_match = re.search(r"\*\*Discovery ID\*\*:\s*(disc-\w+)", content)
                disc_id = disc_id_match.group(1) if disc_id_match else "unknown"
                # Detect the mode previously used
                mode_match = re.search(r"\*\*Mode\*\*:\s*(standard|bootstrap)", content)
                prev_mode = mode_match.group(1) if mode_match else "unknown"
            except OSError:
                disc_id = "unknown"
                prev_mode = "unknown"

            validation = _validate_icp_jtbd(content) if artifact.exists() else {
                "verdict": "DISCOVERY_INCOMPLETE",
                "missing": [],
            }
            return {
                "discovery_id": disc_id,
                "status": "resumable",
                "artifact_path": str(artifact.relative_to(root))
                if artifact.is_relative_to(root)
                else str(artifact),
                "mode_used": prev_mode,
                "app_market_present": (root / APP_MARKET_PATH).exists(),
                "current_verdict": validation["verdict"],
                "missing": validation.get("missing", []),
                "next_step": (
                    "/discovery is resumable — re-invoke the skill to continue "
                    "filling in the remaining sections, or start fresh by "
                    "deleting the existing artifact."
                ),
            }

        # Resolve mode
        if mode not in {"auto", "standard", "bootstrap"}:
            return {
                "error": f"mode must be auto|standard|bootstrap, got {mode!r}",
                "code": "INVALID_MODE",
            }
        if mode == "auto":
            mode_used = (
                "bootstrap"
                if _app_market_is_pristine_or_missing(root)
                else "standard"
            )
        else:
            mode_used = mode

        # Create directory structure
        feature_dir.mkdir(parents=True, exist_ok=True)

        # Compute app_market signature if present and non-pristine
        app_market_sig: str | None = None
        if mode_used == "standard":
            try:
                from server.app_docs.zones import compute_signature

                parsed = parse_document(root / APP_MARKET_PATH)
                if parsed.is_well_formed:
                    app_market_sig = compute_signature(parsed)[:16]
            except Exception:
                app_market_sig = None

        # Write initial artifact
        discovery_id = _new_discovery_id()
        skeleton = _render_initial_icp_jtbd(
            feature_name=feature_name,
            discovery_id=discovery_id,
            mode=mode_used,
            app_market_signature=app_market_sig,
        )
        artifact.write_text(skeleton, encoding="utf-8")

        return {
            "discovery_id": discovery_id,
            "status": "created",
            "artifact_path": str(artifact.relative_to(root))
            if artifact.is_relative_to(root)
            else str(artifact),
            "mode_used": mode_used,
            "app_market_present": (root / APP_MARKET_PATH).exists(),
            "app_market_signature": app_market_sig,
            "next_step": (
                "Invoke the /discovery skill to walk through the 3 phases "
                "(ICP identification, JTBD extraction, validation gate). "
                "The skill will fill in this artifact interactively."
                if mode_used == "standard"
                else (
                    "Bootstrap mode active: the skill will first fill in "
                    "doc/app/app_market.md (project-level), then descend "
                    "to the feature-level icp_jtbd.md."
                )
            ),
        }

    @mcp.tool
    def validate_discovery_completeness(
        feature_name: str,
        project_path: str = ".",
    ) -> dict[str, Any]:
        """Check whether icp_jtbd.md is complete enough to proceed to /prd.

        v6.0 (UC-D001 AC-10). Reads doc/discovery/<feature_name>/icp_jtbd.md
        and verifies all required sections are filled in. Returns READY_FOR_PRD
        or DISCOVERY_INCOMPLETE with a specific list of missing items.

        Called by:
          - The /discovery skill at the end of phase 3.
          - The /pre-prd-discovery-check hook before /prd invocation.
          - Directly as /discovery --status.

        Returns:
            {
              "verdict": "READY_FOR_PRD" | "DISCOVERY_INCOMPLETE",
              "missing": ["icps_involucrados", "jtbds_emocionales", ...],
              "drift": { "section_present": bool, "resolved": bool },
              "artifact_path": str,
            }
        """
        root = Path(project_path).resolve()
        artifact = _icp_jtbd_path(root, feature_name)

        if not artifact.exists():
            return {
                "verdict": "DISCOVERY_INCOMPLETE",
                "missing": ["artifact_not_found"],
                "drift": {"section_present": False, "resolved": False},
                "artifact_path": str(artifact.relative_to(root))
                if artifact.is_relative_to(root)
                else str(artifact),
                "error": (
                    f"doc/discovery/{feature_name}/icp_jtbd.md does not exist. "
                    f"Run start_discovery({feature_name!r}) first."
                ),
            }

        content = artifact.read_text(encoding="utf-8")
        result = _validate_icp_jtbd(content)
        result["artifact_path"] = (
            str(artifact.relative_to(root))
            if artifact.is_relative_to(root)
            else str(artifact)
        )
        return result

    @mcp.tool
    def detect_v60_migration_case(project_path: str = ".") -> dict[str, Any]:
        """Classify a project into one of 8 v6.0 migration cases.

        v6.0 (UC-D005 §4.8). Analogous to detect_v529_migration_case but
        for the v5.x → v6.0 transition. Returns a plan with steps the
        caller (CLI tool or skill) can execute or surface to the user.

        Cases priority-ordered: case 3 (active UC) and case 4 (pending
        feedback) check first since they can co-exist with any backend
        state and demand deferral.

        Returns:
            {
              "case_id": "case_2_v529_v535",
              "case_description": "...",
              "steps": [...],
              "backup_required": bool,
              "notes": [...],
            }
        """
        root = Path(project_path).resolve()
        return _detect_v60_case(root)
