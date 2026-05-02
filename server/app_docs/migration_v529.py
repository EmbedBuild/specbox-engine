"""v5.28 → v5.29 migration tooling (PR-9).

Detects which of the 10 hypothetical project states from the v5.29.0
plan a project is in and runs the appropriate idempotent migration.
The 10 cases live in `doc/plans/v5.29.0_cognitive_load_reduction_plan.md`
sección 7. Summary:

  Case 1  — empty / no onboarding
  Case 2  — v5.28 FreeForm + local MCP
  Case 3  — v5.28 FreeForm + remote MCP (BLOCKER reproduction)
  Case 4  — v5.28 Trello onboarded
  Case 5  — v5.28 Plane onboarded
  Case 6  — multirepo orchestrator+satellites
  Case 7  — feature in progress (active UC, open branch, pending healing)
  Case 8  — pending feedback blocking merge
  Case 9  — manually-created app_*.md without zone markers
  Case 10 — fresh clone, no .quality/

The detector returns the case_id and a recommended migration plan; the
runner executes a dry-run by default and only writes when ``apply=True``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastmcp import FastMCP


CaseId = Literal[
    "case_1_empty",
    "case_2_freeform_local",
    "case_3_freeform_vps",
    "case_4_trello",
    "case_5_plane",
    "case_6_multirepo",
    "case_7_feature_in_progress",
    "case_8_pending_feedback",
    "case_9_manual_app_md",
    "case_10_fresh_clone",
]

Severity = Literal["info", "warning", "blocker"]


@dataclass
class MigrationStep:
    name: str
    description: str
    severity: Severity = "info"
    blocked_by: list[str] = field(default_factory=list)


@dataclass
class MigrationPlan:
    case_id: CaseId
    project_path: str
    steps: list[MigrationStep] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    backup_required: bool = False


# ── Detector ─────────────────────────────────────────────────────────


def detect_case(project_path: str | Path = ".") -> MigrationPlan:
    """Walk the project filesystem and return the dominant migration case.

    Cases are evaluated in priority order so projects with multiple
    signals get the most-specific plan. Case 7 (feature in progress)
    and case 8 (pending feedback) are checked early because they can
    co-exist with any backend-related case and demand additional care.
    """
    root = Path(project_path).resolve()
    plan = MigrationPlan(case_id="case_1_empty", project_path=str(root))

    has_app_dir = (root / "doc" / "app").exists()
    has_app_prd = (root / "doc" / "app" / "app_prd.md").exists()
    has_tracking = (root / "doc" / "tracking").exists()
    has_quality = (root / ".quality").exists()
    settings_path = root / ".claude" / "settings.local.json"
    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}

    backend_specbox = (settings.get("specbox") or {}).get("backend_type")
    legacy_trello = bool((settings.get("trello") or {}).get("boardId"))
    legacy_plane = bool((settings.get("plane") or {}).get("projectId"))
    legacy_freeform_relative = backend_specbox == "freeform" and not (
        settings.get("specbox", {}).get("freeform_root_absolute", "").startswith("/")
    )
    multirepo = (settings.get("multirepo") or {}).get("enabled")

    # Active feature signals.
    active_uc = (root / ".quality" / "active_uc.json").exists()
    feedback_dir = root / ".quality" / "evidence" / "feedback"
    pending_feedback = False
    if feedback_dir.exists():
        for fb in feedback_dir.glob("*.json"):
            try:
                data = json.loads(fb.read_text(encoding="utf-8"))
                if data.get("severity") in {"critical", "major"} and not data.get("resolved_at"):
                    pending_feedback = True
                    break
            except Exception:
                continue

    is_remote_mcp = bool(os.environ.get("SPECBOX_ENGINE_MCP_URL", "").strip())

    # ── Case dispatch ──
    # Case 10: fresh clone — no .quality/ at all means hooks not installed yet.
    if not has_quality and not settings_path.exists() and not has_tracking:
        plan.case_id = "case_10_fresh_clone"
        plan.steps = [
            MigrationStep(
                "run_install_sh",
                "Run `./install.sh` to install hooks, skills, and MCP wiring before anything else.",
                severity="warning",
            ),
            MigrationStep(
                "then_app_init",
                "After install, run `/app-init` to create doc/app/ + doc/tracking/.",
            ),
        ]
        return plan

    # Case 7: active UC takes priority — never disrupt in-progress work.
    if active_uc:
        plan.case_id = "case_7_feature_in_progress"
        plan.steps = [
            MigrationStep(
                "defer_migration",
                "Active UC detected (.quality/active_uc.json). Defer v5.29 migration "
                "until current UC completes or is explicitly abandoned.",
                severity="warning",
            ),
            MigrationStep(
                "post_completion_run_app_init",
                "Once the active UC closes, run `/app-init` (no other v5.29 changes "
                "are applied automatically while a feature is open).",
            ),
        ]
        plan.notes.append(
            "v5.29 hooks (sync-guard etc.) deliberately stay in warning-only mode "
            "until the in-progress UC reaches done — see PR-13."
        )
        return plan

    # Case 8: pending feedback blocking merge.
    # Only stops here if the project does NOT also have a backend signal —
    # in which case the backend case wins and we just append a note.
    has_backend_signal = (
        backend_specbox in {"freeform", "trello", "plane"}
        or has_tracking
        or legacy_trello
        or legacy_plane
        or multirepo
    )
    if pending_feedback and not has_backend_signal:
        plan.case_id = "case_8_pending_feedback"
        plan.steps = [
            MigrationStep(
                "feedback_unaffected",
                "Pending feedback detected — v5.29 migration is non-destructive for "
                "feedback evidence. Continuing.",
                severity="info",
            ),
            MigrationStep(
                "run_app_init",
                "Run `/app-init` to add doc/app/. Existing feedback flow is preserved.",
            ),
        ]
        return plan
    if pending_feedback:
        plan.notes.append(
            "Pending feedback found — v5.29 migration leaves feedback evidence untouched."
        )

    # Case 6: multirepo.
    if multirepo:
        plan.case_id = "case_6_multirepo"
        plan.steps = [
            MigrationStep(
                "orchestrator_owns_app_md",
                "In multirepo, only the orchestrator stores doc/app/. Satellites "
                "inherit via the multirepo.orchestrator path.",
                severity="info",
            ),
            MigrationStep(
                "run_app_init_in_orchestrator",
                "If this is the orchestrator, run `/app-init`. Satellites pick up "
                "the canonical docs automatically through detect_backend.",
            ),
        ]
        return plan

    # Case 3: FreeForm + remote MCP with relative path = the BLOCKER reproduction.
    if backend_specbox == "freeform" and is_remote_mcp and legacy_freeform_relative:
        plan.case_id = "case_3_freeform_vps"
        plan.backup_required = True
        plan.steps = [
            MigrationStep(
                "backup_remote_data",
                "BACKUP REQUIRED — remote MCP may have written items.json on the VPS "
                "filesystem. Capture a snapshot before migrating.",
                severity="blocker",
            ),
            MigrationStep(
                "rewrite_settings_with_absolute",
                f"Rewrite settings.local.json: specbox.freeform_root_absolute = "
                f"\"{root / 'doc' / 'tracking'}\".",
                severity="warning",
            ),
            MigrationStep(
                "verify_local_data_consistent",
                "Compare local doc/tracking/items.json against the VPS snapshot. "
                "Resolve diffs manually before proceeding.",
                severity="blocker",
            ),
            MigrationStep(
                "run_app_init",
                "Run `/app-init` once data is reconciled.",
            ),
        ]
        return plan

    # Case 2: FreeForm + local MCP (relative path is fine locally, but warn).
    if backend_specbox == "freeform" or has_tracking:
        plan.case_id = "case_2_freeform_local"
        plan.steps = [
            MigrationStep(
                "consider_absolute_path",
                "FreeForm + local MCP: relative paths still work but switching to "
                "absolute future-proofs the project for VPS deployments.",
                severity="info",
            ),
            MigrationStep(
                "rewrite_settings_with_absolute",
                f"Update specbox.freeform_root_absolute = \"{root / 'doc' / 'tracking'}\".",
            ),
            MigrationStep(
                "run_app_init",
                "Run `/app-init` to add doc/app/ canonical docs.",
            ),
        ]
        return plan

    # Case 4 & 5: Trello / Plane onboarded.
    if legacy_trello:
        plan.case_id = "case_4_trello"
        plan.steps = [
            MigrationStep(
                "trello_unaffected",
                "Trello backend continues working unchanged. v5.29 only adds optional doc/app/.",
                severity="info",
            ),
            MigrationStep(
                "run_app_init_optional",
                "Run `/app-init` if you want doc/app/. If not, skill behaviour falls "
                "back to v5.28 (ask everything).",
            ),
            MigrationStep(
                "consider_migrate_to_freeform",
                "If external client reporting is no longer needed, "
                "`migrate_to_freeform_tool` exports the board to local files.",
            ),
        ]
        return plan

    if legacy_plane:
        plan.case_id = "case_5_plane"
        plan.steps = [
            MigrationStep(
                "plane_unaffected",
                "Plane backend continues working unchanged.",
                severity="info",
            ),
            MigrationStep(
                "run_app_init_optional",
                "Run `/app-init` to add doc/app/. Optional.",
            ),
        ]
        return plan

    # Case 9: app_*.md present manually without zone markers.
    if has_app_prd:
        try:
            content = (root / "doc" / "app" / "app_prd.md").read_text(encoding="utf-8")
        except OSError:
            content = ""
        if "@specbox:zone" not in content:
            plan.case_id = "case_9_manual_app_md"
            plan.steps = [
                MigrationStep(
                    "preserve_user_content",
                    "doc/app/app_prd.md exists but has no zone markers. /app-init "
                    "will run in upgrade-zones mode: it proposes a mapping with "
                    "diff and waits for confirmation before rewriting.",
                    severity="warning",
                ),
                MigrationStep(
                    "backup_before_apply",
                    "Backup of the original is written to .quality/edits_backup/ "
                    "before any change is applied.",
                ),
            ]
            plan.backup_required = True
            return plan

    # Default fallthrough: empty project.
    plan.case_id = "case_1_empty"
    plan.steps = [
        MigrationStep(
            "run_app_init",
            "Run `/app-init` to onboard. Defaults: backend=freeform, autopilot=equilibrado.",
        ),
    ]
    return plan


# ── Idempotent runner ────────────────────────────────────────────────


def apply_settings_specbox_block(
    project_path: Path,
    *,
    backend_type: str = "freeform",
    autopilot_level: str = "equilibrado",
    freeform_root_absolute: str | None = None,
) -> dict[str, Any]:
    """Idempotently merge a `specbox.*` block into settings.local.json.

    Returns a small report describing what changed (or nothing).
    """
    settings_path = project_path / ".claude" / "settings.local.json"
    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    before = json.dumps(settings, sort_keys=True)
    specbox = settings.setdefault("specbox", {})
    specbox.setdefault("backend_type", backend_type)
    autopilot = specbox.setdefault("autopilot", {})
    autopilot.setdefault("level", autopilot_level)
    autopilot.setdefault("image_budget_eur_per_feature", 5)
    if freeform_root_absolute and backend_type == "freeform":
        specbox.setdefault("freeform_root_absolute", freeform_root_absolute)
    after = json.dumps(settings, sort_keys=True)

    if before == after:
        return {"changed": False, "reason": "settings already include specbox block"}
    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"changed": True, "path": str(settings_path)}


def run_migration(
    project_path: str | Path = ".",
    *,
    apply: bool = False,
    backend_type: str = "freeform",
) -> dict[str, Any]:
    """Detect the case and (optionally) apply non-destructive automatic steps.

    The "automatic" subset is intentionally narrow: only settings.local.json
    is touched. Everything else (creating doc/app/, downloading remote data
    in case 3, walking the user through case 9) is delegated to the
    /app-init skill so the user always sees a confirmation prompt for
    write-heavy operations.
    """
    root = Path(project_path).resolve()
    plan = detect_case(root)
    report: dict[str, Any] = {
        "case_id": plan.case_id,
        "project_path": str(root),
        "apply": apply,
        "backup_required": plan.backup_required,
        "notes": list(plan.notes),
        "steps": [
            {"name": s.name, "description": s.description, "severity": s.severity}
            for s in plan.steps
        ],
        "automatic_actions": [],
    }

    if not apply:
        report["mode"] = "dry-run"
        return report

    # Cases that skip automatic settings updates entirely.
    if plan.case_id in {"case_3_freeform_vps", "case_7_feature_in_progress", "case_9_manual_app_md"}:
        report["mode"] = "deferred"
        report["reason"] = (
            "This case requires user-mediated steps (backup, manual reconciliation, or "
            "active-feature deferral). No filesystem changes applied."
        )
        return report

    freeform_root = (
        str(root / "doc" / "tracking") if backend_type == "freeform" else None
    )
    settings_change = apply_settings_specbox_block(
        root,
        backend_type=backend_type,
        autopilot_level="equilibrado",
        freeform_root_absolute=freeform_root,
    )
    report["automatic_actions"].append({"settings_local_json": settings_change})
    report["mode"] = "applied"
    report["next_steps"] = [
        "Run /app-init to create doc/app/app_prd.md and doc/app/app_spec.md.",
    ]
    return report


# ── MCP registration ─────────────────────────────────────────────────


def register_v529_migration_tools(mcp: FastMCP, engine_path: Path) -> None:
    """Expose the v5.28→v5.29 migration helpers."""

    @mcp.tool
    def detect_v529_migration_case(project_path: str = ".") -> dict[str, Any]:
        """Detect which of the 10 v5.28→v5.29 migration cases applies.

        Returns the case_id, recommended steps, and whether a backup is
        required. Read-only — does not modify the project.
        """
        plan = detect_case(project_path)
        return {
            "case_id": plan.case_id,
            "project_path": plan.project_path,
            "backup_required": plan.backup_required,
            "notes": plan.notes,
            "steps": [
                {"name": s.name, "description": s.description, "severity": s.severity}
                for s in plan.steps
            ],
        }

    @mcp.tool
    def run_v529_migration(
        project_path: str = ".",
        apply: bool = False,
        backend_type: str = "freeform",
    ) -> dict[str, Any]:
        """Run the safe automatic subset of the v5.28→v5.29 migration.

        Only updates `.claude/settings.local.json` to add the specbox.* block.
        Cases that need user-mediated steps (case 3 VPS migration, case 7
        active UC, case 9 manual app_*.md) are detected and skipped with a
        deferred-mode report explaining what to do.

        Default is dry-run (apply=False).
        """
        return run_migration(project_path, apply=apply, backend_type=backend_type)
