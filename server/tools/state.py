"""Tools for universal state management — ingestion and query.

Hooks from SpecBox Engine send telemetry via HTTP (report_session,
report_checkpoint, report_healing, report_acceptance_tests,
report_acceptance_validation, report_merge_status, report_feedback,
report_feedback_resolution, report_e2e_results). Query tools expose the
aggregated state as the "Sala de Máquinas" dashboard.

State layout on disk:
    /data/state/
    ├── registry.json
    ├── projects/
    │   └── {project}/
    │       ├── sessions.jsonl
    │       ├── checkpoints.jsonl
    │       ├── healing.jsonl
    │       ├── acceptance_tests.jsonl
    │       ├── acceptance_validations.jsonl
    │       ├── merge_events.jsonl
    │       ├── feedback.jsonl
    │       ├── e2e_results.jsonl
    │       └── meta.json
    └── dashboard_cache.json
"""

import json
import shutil
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastmcp import FastMCP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_project_dir(state_path: Path, project: str) -> Path:
    """Create the project directory under state/projects/ if needed."""
    project_dir = state_path / "projects" / project
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def _read_registry(state_path: Path) -> dict:
    """Read state/registry.json, returning empty structure if missing."""
    registry_file = state_path / "registry.json"
    if registry_file.exists():
        try:
            return json.loads(registry_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"projects": {}}


def _write_registry(state_path: Path, registry: dict) -> None:
    """Persist registry.json."""
    registry_file = state_path / "registry.json"
    registry_file.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _read_meta(project_dir: Path) -> dict:
    """Read meta.json for a project."""
    meta_file = project_dir / "meta.json"
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _write_meta(project_dir: Path, meta: dict) -> None:
    """Persist meta.json for a project."""
    meta_file = project_dir / "meta.json"
    meta_file.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _append_jsonl(file_path: Path, record: dict) -> None:
    """Append a single JSON record as a line to a JSONL file."""
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_jsonl(file_path: Path) -> list[dict]:
    """Read all records from a JSONL file."""
    records: list[dict] = []
    if not file_path.exists():
        return records
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def _invalidate_cache(state_path: Path) -> None:
    """Remove dashboard_cache.json to force regeneration."""
    cache_file = state_path / "dashboard_cache.json"
    if cache_file.exists():
        cache_file.unlink()


def _auto_register(state_path: Path, project: str) -> None:
    """Register a project in registry.json if not already present."""
    registry = _read_registry(state_path)
    if project not in registry.get("projects", {}):
        registry.setdefault("projects", {})[project] = {
            "stack": "unknown",
            "infra": [],
            "repo_url": "",
            "description": "",
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_registry(state_path, registry)


def _available_projects(state_path: Path) -> list[str]:
    """List all known project names from registry."""
    registry = _read_registry(state_path)
    return sorted(registry.get("projects", {}).keys())


def _filter_by_days(records: list[dict], days: int, ts_key: str = "timestamp") -> list[dict]:
    """Filter records to only include those within the last N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return [r for r in records if r.get(ts_key, "") >= cutoff]


def _read_project_state(project_dir: Path) -> dict:
    """Read project_state.json for a project (consolidated snapshot)."""
    state_file = project_dir / "project_state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _write_project_state(project_dir: Path, data: dict) -> None:
    """Persist project_state.json (overwrites — this is a snapshot, not a log)."""
    state_file = project_dir / "project_state.json"
    state_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _apply_session_decay(state: dict, decay_minutes: int = 30) -> dict:
    """Apply lazy session decay: if received_at > decay_minutes ago, set session_active=false.

    Returns a copy — does NOT modify the original dict or file."""
    if not state or not state.get("session_active"):
        return state
    received_at = state.get("received_at", "")
    if not received_at:
        return state
    try:
        received_dt = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - received_dt
        if age > timedelta(minutes=decay_minutes):
            result = dict(state)
            result["session_active"] = False
            return result
    except (ValueError, TypeError):
        pass
    return state


def _compute_e2e_trend(records: list[dict]) -> str:
    """Compute E2E test trend from historical runs."""
    if len(records) < 2:
        return "insufficient_data"
    recent = records[-1].get("pass_rate", 0)
    previous = records[-2].get("pass_rate", 0)
    if recent > previous:
        return "improving"
    elif recent < previous:
        return "degrading"
    return "stable"


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register_state_tools(mcp: FastMCP, engine_path: Path, state_path: Path):

    # ===================================================================
    # INGESTION TOOLS — hooks call these
    # ===================================================================

    @mcp.tool
    def report_session(
        project: str,
        timestamp: str,
        files_modified: int = 0,
        context_tokens_est: int = 0,
        healing_events: int = 0,
        active_feature: str = "",
    ) -> dict:
        """Report a development session from a hook (on-session-end).

        Args:
            project: Project name (e.g. 'escandallo-app').
            timestamp: ISO 8601 timestamp of the session end.
            files_modified: Number of files modified in the session.
            context_tokens_est: Estimated context tokens consumed.
            healing_events: Number of self-healing events triggered.
            active_feature: Feature being worked on (if any).

        Appends to sessions.jsonl, updates meta, auto-registers project.
        Called by engine hooks via HTTP — fire-and-forget."""
        project_dir = _ensure_project_dir(state_path, project)
        _auto_register(state_path, project)

        record = {
            "timestamp": timestamp,
            "files_modified": files_modified,
            "context_tokens_est": context_tokens_est,
            "healing_events": healing_events,
            "active_feature": active_feature,
        }
        _append_jsonl(project_dir / "sessions.jsonl", record)

        # Update meta
        meta = _read_meta(project_dir)
        meta["last_activity"] = timestamp
        if active_feature:
            meta["active_feature"] = active_feature
        _write_meta(project_dir, meta)

        _invalidate_cache(state_path)

        return {"status": "ok", "project": project, "event": "session"}

    @mcp.tool
    def report_checkpoint(
        project: str,
        feature: str,
        phase: int,
        phase_name: str,
        branch: str,
        timestamp: str,
    ) -> dict:
        """Report an /implement checkpoint from a hook.

        Args:
            project: Project name.
            feature: Feature being implemented.
            phase: Phase number (1-8).
            phase_name: Phase name (e.g. 'scaffold', 'implement', 'test').
            branch: Git branch name.
            timestamp: ISO 8601 timestamp.

        Appends to checkpoints.jsonl, updates meta with active feature/branch.
        Called by engine hooks — fire-and-forget."""
        project_dir = _ensure_project_dir(state_path, project)
        _auto_register(state_path, project)

        record = {
            "timestamp": timestamp,
            "feature": feature,
            "phase": phase,
            "phase_name": phase_name,
            "branch": branch,
        }
        _append_jsonl(project_dir / "checkpoints.jsonl", record)

        meta = _read_meta(project_dir)
        meta["last_activity"] = timestamp
        meta["active_feature"] = feature
        meta["active_branch"] = branch
        _write_meta(project_dir, meta)

        _invalidate_cache(state_path)

        return {"status": "ok", "project": project, "event": "checkpoint", "phase": phase}

    @mcp.tool
    def report_healing(
        project: str,
        feature: str,
        level: int,
        error_type: str,
        result: str,
        timestamp: str,
    ) -> dict:
        """Report a self-healing event from a hook.

        Args:
            project: Project name.
            feature: Feature where healing was triggered.
            level: Healing level (1=retry, 2=rollback, 3=escalate).
            error_type: Type of error (lint, test, build, runtime).
            result: Outcome (resolved, escalated, failed).
            timestamp: ISO 8601 timestamp.

        Appends to healing.jsonl, updates meta with healing stats.
        Called by engine hooks — fire-and-forget."""
        project_dir = _ensure_project_dir(state_path, project)
        _auto_register(state_path, project)

        record = {
            "timestamp": timestamp,
            "feature": feature,
            "level": level,
            "error_type": error_type,
            "result": result,
        }
        _append_jsonl(project_dir / "healing.jsonl", record)

        meta = _read_meta(project_dir)
        meta["last_healing"] = timestamp
        meta["healing_count"] = meta.get("healing_count", 0) + 1
        _write_meta(project_dir, meta)

        _invalidate_cache(state_path)

        return {"status": "ok", "project": project, "event": "healing", "level": level}

    @mcp.tool
    def report_acceptance_tests(
        project: str,
        feature: str,
        timestamp: str,
        stack: str,
        tests_total: int,
        tests_passed: int,
        tests_failed: int,
        results: list[dict],
    ) -> dict:
        """Report acceptance test results from AG-09a (Acceptance Tester).

        Args:
            project: Project name (e.g. 'tempo-zenon').
            feature: Feature name (e.g. 'staff_management').
            timestamp: ISO 8601 timestamp.
            stack: Technology stack (flutter, react, python, google-apps-script).
            tests_total: Total number of acceptance tests executed.
            tests_passed: Number of tests that passed.
            tests_failed: Number of tests that failed.
            results: List of per-criterion results. Each dict has:
                id (str): AC-XX identifier.
                description (str): Criterion description.
                status (str): "PASS" or "FAIL".
                duration_ms (int, optional): Test duration in milliseconds.
                error (str, optional): Error message if FAIL.
                screenshot (str, optional): Evidence file name.

        Appends to acceptance_tests.jsonl, updates meta with last test run.
        Called by engine hooks (AG-09a) — fire-and-forget."""
        project_dir = _ensure_project_dir(state_path, project)
        _auto_register(state_path, project)

        record = {
            "timestamp": timestamp,
            "feature": feature,
            "stack": stack,
            "tests_total": tests_total,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "results": results,
        }
        _append_jsonl(project_dir / "acceptance_tests.jsonl", record)

        meta = _read_meta(project_dir)
        meta["last_activity"] = timestamp
        meta["last_acceptance_test"] = timestamp
        meta["active_feature"] = feature
        _write_meta(project_dir, meta)

        _invalidate_cache(state_path)

        return {
            "status": "ok",
            "project": project,
            "event": "acceptance_tests",
            "tests_passed": tests_passed,
            "tests_total": tests_total,
        }

    @mcp.tool
    def report_acceptance_validation(
        project: str,
        feature: str,
        timestamp: str,
        prd_source: str,
        validator: str,
        criteria_total: int,
        criteria_passed: int,
        criteria_failed: int,
        criteria_partial: int,
        verdict: str,
        blocking_criteria: list[str],
        criteria: list[dict],
        healing_attempt: int = 0,
    ) -> dict:
        """Report acceptance validation verdict from AG-09b (Acceptance Validator).

        Args:
            project: Project name.
            feature: Feature name.
            timestamp: ISO 8601 timestamp.
            prd_source: Work item ID or path to PRD (e.g. 'TEMPO-42').
            validator: Validator agent ID (e.g. 'AG-09b').
            criteria_total: Total number of acceptance criteria evaluated.
            criteria_passed: Number of criteria that passed.
            criteria_failed: Number of criteria that failed.
            criteria_partial: Number of criteria partially met.
            verdict: Validation verdict — "ACCEPTED", "CONDITIONAL", or "REJECTED".
            blocking_criteria: List of AC-XX IDs that block acceptance.
            criteria: List of per-criterion evaluations. Each dict has:
                id (str): AC-XX identifier.
                status (str): "PASS", "FAIL", or "PARTIAL".
                has_code (bool): Implementation exists.
                has_unit_test (bool): Unit test exists.
                has_acceptance_test (bool): Acceptance test exists.
                has_evidence (bool): Visual/log evidence exists.
                missing (str, optional): What's missing if FAIL.
            healing_attempt: Attempt number (0 = first evaluation, 1-2 = post-healing).

        Appends to acceptance_validations.jsonl, updates meta with verdict.
        Called by engine hooks (AG-09b) — fire-and-forget."""
        project_dir = _ensure_project_dir(state_path, project)
        _auto_register(state_path, project)

        record = {
            "timestamp": timestamp,
            "feature": feature,
            "prd_source": prd_source,
            "validator": validator,
            "criteria_total": criteria_total,
            "criteria_passed": criteria_passed,
            "criteria_failed": criteria_failed,
            "criteria_partial": criteria_partial,
            "verdict": verdict,
            "blocking_criteria": blocking_criteria,
            "criteria": criteria,
            "healing_attempt": healing_attempt,
        }
        _append_jsonl(project_dir / "acceptance_validations.jsonl", record)

        meta = _read_meta(project_dir)
        meta["last_activity"] = timestamp
        meta["last_acceptance_validation"] = timestamp
        meta["last_verdict"] = verdict
        meta["active_feature"] = feature
        _write_meta(project_dir, meta)

        _invalidate_cache(state_path)

        return {
            "status": "ok",
            "project": project,
            "event": "acceptance_validation",
            "verdict": verdict,
            "healing_attempt": healing_attempt,
        }

    @mcp.tool
    def report_merge_status(
        project: str,
        feature: str,
        timestamp: str,
        pr_number: int,
        branch: str,
        merge_status: str,
        merge_method: str | None = None,
        ag08_verdict: str = "",
        ag09_verdict: str = "",
        blocked_by: str | None = None,
        feedback_blocking: dict | None = None,
        next_card: str | None = None,
    ) -> dict:
        """Report merge pipeline result (sequential merge from Paso 8.5 of /implement).

        Args:
            project: Project name.
            feature: Feature name.
            timestamp: ISO 8601 timestamp.
            pr_number: Pull request number.
            branch: Git branch name (e.g. 'feature/staff-management').
            merge_status: Result — "merged", "blocked", or "manual_review".
            merge_method: Merge strategy used — "squash", "merge", "rebase", or null.
            ag08_verdict: AG-08 quality verdict — "GO", "CONDITIONAL_GO", or "NO_GO".
            ag09_verdict: AG-09b acceptance verdict — "ACCEPTED", "CONDITIONAL", "REJECTED", "INVALIDATED", or "SKIPPED".
            blocked_by: What blocked the merge — "AG-08", "AG-09b", "feedback", "user", or null.
            feedback_blocking: Feedback blocking details (if blocked_by="feedback"). Dict with:
                total_open (int): Number of open feedback tickets.
                blocking_ids (list[str]): FB-NNN IDs blocking merge.
                invalidated_criteria (list[str]): AC-XX IDs invalidated by feedback.
            next_card: ID of the next card in pipeline (if sequential merge continues).

        Appends to merge_events.jsonl, updates meta with merge result.
        Called by engine hooks — fire-and-forget."""
        project_dir = _ensure_project_dir(state_path, project)
        _auto_register(state_path, project)

        record = {
            "timestamp": timestamp,
            "feature": feature,
            "pr_number": pr_number,
            "branch": branch,
            "merge_status": merge_status,
            "merge_method": merge_method,
            "ag08_verdict": ag08_verdict,
            "ag09_verdict": ag09_verdict,
            "blocked_by": blocked_by,
            "feedback_blocking": feedback_blocking,
            "next_card": next_card,
        }
        _append_jsonl(project_dir / "merge_events.jsonl", record)

        meta = _read_meta(project_dir)
        meta["last_activity"] = timestamp
        meta["last_merge"] = timestamp
        meta["last_merge_status"] = merge_status
        if merge_status == "merged":
            meta["merged_count"] = meta.get("merged_count", 0) + 1
        _write_meta(project_dir, meta)

        _invalidate_cache(state_path)

        return {
            "status": "ok",
            "project": project,
            "event": "merge_status",
            "merge_status": merge_status,
            "pr_number": pr_number,
        }

    @mcp.tool
    def report_feedback(
        project: str,
        feature: str,
        timestamp: str,
        feedback_id: str,
        severity: str,
        status: str,
        ac_ids: list[str],
        description: str,
        expected: str,
        actual: str,
        invalidates_acceptance: bool,
        reporter: str,
        github_issue_number: int | None = None,
        github_issue_url: str | None = None,
    ) -> dict:
        """Report a developer feedback ticket from manual testing via /feedback.

        Args:
            project: Project name (e.g. 'tempo-zenon').
            feature: Feature name (e.g. 'invoice-detail').
            timestamp: ISO 8601 timestamp.
            feedback_id: Feedback ticket ID (e.g. 'FB-001').
            severity: Severity level — "critical", "major", or "minor".
            status: Ticket status — "open" or "resolved".
            ac_ids: List of AC-XX acceptance criteria affected (can be empty).
            description: Description of the problem found.
            expected: Expected behavior.
            actual: Actual behavior observed.
            invalidates_acceptance: Whether this feedback invalidates a prior ACCEPTED verdict.
            reporter: Who reported the feedback (e.g. 'developer').
            github_issue_number: GitHub issue number created (null if none).
            github_issue_url: GitHub issue URL (null if none).

        Appends to feedback.jsonl, updates meta with feedback stats.
        Called by engine hooks (/feedback skill) — fire-and-forget."""
        project_dir = _ensure_project_dir(state_path, project)
        _auto_register(state_path, project)

        record = {
            "timestamp": timestamp,
            "feature": feature,
            "feedback_id": feedback_id,
            "severity": severity,
            "status": status,
            "ac_ids": ac_ids,
            "description": description,
            "expected": expected,
            "actual": actual,
            "invalidates_acceptance": invalidates_acceptance,
            "reporter": reporter,
            "github_issue_number": github_issue_number,
            "github_issue_url": github_issue_url,
        }
        _append_jsonl(project_dir / "feedback.jsonl", record)

        meta = _read_meta(project_dir)
        meta["last_activity"] = timestamp
        meta["last_feedback"] = timestamp
        meta["active_feature"] = feature
        meta["feedback_open"] = meta.get("feedback_open", 0) + (1 if status == "open" else 0)
        _write_meta(project_dir, meta)

        _invalidate_cache(state_path)

        return {
            "status": "ok",
            "project": project,
            "event": "feedback",
            "feedback_id": feedback_id,
            "severity": severity,
        }

    @mcp.tool
    def report_feedback_resolution(
        project: str,
        feature: str,
        timestamp: str,
        feedback_id: str,
        resolution: str,
        ac_ids_revalidation_needed: list[str],
        remaining_open_feedback: int,
        blocking_resolved: bool,
        github_issue_number: int | None = None,
        github_issue_closed: bool = False,
    ) -> dict:
        """Report resolution of a feedback ticket via /feedback resolve.

        Args:
            project: Project name.
            feature: Feature name.
            timestamp: ISO 8601 timestamp.
            feedback_id: Feedback ticket ID being resolved (e.g. 'FB-001').
            resolution: Description of the resolution applied.
            ac_ids_revalidation_needed: AC-XX IDs that need re-validation after fix.
            remaining_open_feedback: Number of open feedback tickets remaining for this feature.
            blocking_resolved: Whether the resolved feedback was blocking the merge pipeline.
            github_issue_number: GitHub issue number that was closed (null if none).
            github_issue_closed: Whether the GitHub issue was successfully closed.

        Appends resolution to feedback.jsonl, updates meta with resolution stats.
        Called by engine hooks (/feedback resolve) — fire-and-forget."""
        project_dir = _ensure_project_dir(state_path, project)
        _auto_register(state_path, project)

        record = {
            "timestamp": timestamp,
            "feature": feature,
            "feedback_id": feedback_id,
            "event_subtype": "resolution",
            "resolution": resolution,
            "ac_ids_revalidation_needed": ac_ids_revalidation_needed,
            "remaining_open_feedback": remaining_open_feedback,
            "blocking_resolved": blocking_resolved,
            "github_issue_number": github_issue_number,
            "github_issue_closed": github_issue_closed,
        }
        _append_jsonl(project_dir / "feedback.jsonl", record)

        meta = _read_meta(project_dir)
        meta["last_activity"] = timestamp
        meta["last_feedback_resolution"] = timestamp
        meta["active_feature"] = feature
        meta["feedback_open"] = max(0, remaining_open_feedback)
        meta["feedback_resolved"] = meta.get("feedback_resolved", 0) + 1
        _write_meta(project_dir, meta)

        _invalidate_cache(state_path)

        return {
            "status": "ok",
            "project": project,
            "event": "feedback_resolution",
            "feedback_id": feedback_id,
            "remaining_open": remaining_open_feedback,
            "blocking_resolved": blocking_resolved,
        }

    @mcp.tool
    def report_e2e_results(
        project: str,
        total: int,
        passing: int,
        failing: int,
        skipped: int,
        duration_ms: int,
        viewports: list[str],
        report_path: str = "",
        feature: str = "",
    ) -> dict:
        """Report E2E test run results for a project.

        Args:
            project: Project name (e.g. 'tempo-zenon').
            total: Total number of E2E tests executed.
            passing: Number of tests that passed.
            failing: Number of tests that failed.
            skipped: Number of tests skipped.
            duration_ms: Total run duration in milliseconds.
            viewports: List of viewports tested (e.g. ['desktop', 'mobile']).
            report_path: Path to the HTML report file (optional).
            feature: Feature being tested (optional).

        Appends to e2e_results.jsonl, updates meta with E2E stats.
        Called by hooks/e2e-report.sh after Playwright runs — fire-and-forget."""
        project_dir = _ensure_project_dir(state_path, project)
        _auto_register(state_path, project)

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": total,
            "passing": passing,
            "failing": failing,
            "skipped": skipped,
            "duration_ms": duration_ms,
            "pass_rate": round(passing / total * 100, 1) if total > 0 else 0,
            "viewports": viewports,
            "report_path": report_path,
            "feature": feature,
        }
        _append_jsonl(project_dir / "e2e_results.jsonl", record)

        meta = _read_meta(project_dir)
        meta["last_activity"] = record["timestamp"]
        meta["last_e2e_run"] = record["timestamp"]
        meta["e2e_pass_rate"] = record["pass_rate"]
        if feature:
            meta["active_feature"] = feature
        _write_meta(project_dir, meta)

        _invalidate_cache(state_path)

        return {
            "status": "ok",
            "project": project,
            "event": "e2e_results",
            "pass_rate": record["pass_rate"],
            "summary": f"{passing}/{total} passing ({record['pass_rate']}%)",
        }

    @mcp.tool
    def register_project(
        project: str,
        stack: str = "",
        infra: str = "",
        repo_url: str = "",
        description: str = "",
    ) -> dict:
        """Register a project in the central state registry.

        Args:
            project: Project name (e.g. 'escandallo-app').
            stack: Technology stack (flutter, react, python, google-apps-script).
            infra: Comma-separated infra services (supabase, stripe, etc.).
            repo_url: Git repository URL.
            description: Short project description.

        Creates the project entry in registry.json and initializes meta.json.
        This is NOT the same as onboard_project (which generates config files).
        Use this to register a project in the central index for tracking."""
        _ensure_project_dir(state_path, project)

        infra_list = [s.strip() for s in infra.split(",") if s.strip()] if infra else []

        registry = _read_registry(state_path)
        already_exists = project in registry.get("projects", {})

        registry.setdefault("projects", {})[project] = {
            "stack": stack or "unknown",
            "infra": infra_list,
            "repo_url": repo_url,
            "description": description,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_registry(state_path, registry)

        # Initialize meta.json
        project_dir = state_path / "projects" / project
        meta = _read_meta(project_dir)
        meta.update({
            "stack": stack or meta.get("stack", "unknown"),
            "infra": infra_list or meta.get("infra", []),
            "repo_url": repo_url or meta.get("repo_url", ""),
            "description": description or meta.get("description", ""),
            "registered_at": registry["projects"][project]["registered_at"],
        })
        _write_meta(project_dir, meta)

        _invalidate_cache(state_path)

        return {
            "status": "ok",
            "project": project,
            "action": "updated" if already_exists else "registered",
        }

    @mcp.tool
    def update_project_meta(
        project: str,
        stack: str = "",
        infra: str = "",
        repo_url: str = "",
        description: str = "",
    ) -> dict:
        """Update metadata for a registered project.

        Args:
            project: Project name.
            stack: New stack value (leave empty to keep current).
            infra: New comma-separated infra (leave empty to keep current).
            repo_url: New repo URL (leave empty to keep current).
            description: New description (leave empty to keep current).

        Updates both meta.json and registry.json. Only provided fields are changed."""
        registry = _read_registry(state_path)
        if project not in registry.get("projects", {}):
            return {
                "error": "Project not registered",
                "available": _available_projects(state_path),
            }

        project_dir = state_path / "projects" / project
        meta = _read_meta(project_dir)
        infra_list = [s.strip() for s in infra.split(",") if s.strip()] if infra else None

        # Update only provided fields
        if stack:
            meta["stack"] = stack
            registry["projects"][project]["stack"] = stack
        if infra_list is not None:
            meta["infra"] = infra_list
            registry["projects"][project]["infra"] = infra_list
        if repo_url:
            meta["repo_url"] = repo_url
            registry["projects"][project]["repo_url"] = repo_url
        if description:
            meta["description"] = description
            registry["projects"][project]["description"] = description

        _write_meta(project_dir, meta)
        _write_registry(state_path, registry)
        _invalidate_cache(state_path)

        return {"status": "ok", "project": project, "meta": meta}

    # ===================================================================
    # QUERY TOOLS — Sala de Máquinas
    # ===================================================================

    @mcp.tool
    def get_project_activity(project: str, days: int = 7) -> dict:
        """Get detailed activity report for a single project.

        Args:
            project: Project name.
            days: Number of days to look back (default 7).

        Returns session count, total tokens, total files, active features,
        healing stats, acceptance validation stats, merge pipeline stats,
        feedback loop stats, and last activity.
        Use for deep-diving into a project's recent development activity."""
        registry = _read_registry(state_path)
        if project not in registry.get("projects", {}):
            return {
                "error": "Project not registered",
                "available": _available_projects(state_path),
            }

        project_dir = state_path / "projects" / project
        sessions = _filter_by_days(_read_jsonl(project_dir / "sessions.jsonl"), days)
        checkpoints = _filter_by_days(_read_jsonl(project_dir / "checkpoints.jsonl"), days)
        healing = _filter_by_days(_read_jsonl(project_dir / "healing.jsonl"), days)
        validations = _filter_by_days(_read_jsonl(project_dir / "acceptance_validations.jsonl"), days)
        merges = _filter_by_days(_read_jsonl(project_dir / "merge_events.jsonl"), days)
        feedback = _filter_by_days(_read_jsonl(project_dir / "feedback.jsonl"), days)
        meta = _read_meta(project_dir)

        total_tokens = sum(s.get("context_tokens_est", 0) for s in sessions)
        total_files = sum(s.get("files_modified", 0) for s in sessions)
        active_features = sorted({
            c.get("feature", "") for c in checkpoints if c.get("feature")
        })
        healing_resolved = sum(1 for h in healing if h.get("result") == "resolved")

        # Acceptance metrics
        accepted = sum(1 for v in validations if v.get("verdict") == "ACCEPTED")
        conditional = sum(1 for v in validations if v.get("verdict") == "CONDITIONAL")
        rejected = sum(1 for v in validations if v.get("verdict") == "REJECTED")
        acceptance_rate = round(accepted / len(validations) * 100, 1) if validations else 0.0

        # Merge metrics
        merged = sum(1 for m in merges if m.get("merge_status") == "merged")
        blocked = sum(1 for m in merges if m.get("merge_status") == "blocked")
        blocked_by_feedback = sum(1 for m in merges if m.get("blocked_by") == "feedback")

        # Feedback metrics
        fb_tickets = [f for f in feedback if f.get("event_subtype") != "resolution"]
        fb_resolutions = [f for f in feedback if f.get("event_subtype") == "resolution"]
        fb_open = sum(1 for f in fb_tickets if f.get("status") == "open")
        fb_critical = sum(1 for f in fb_tickets if f.get("severity") == "critical")
        fb_major = sum(1 for f in fb_tickets if f.get("severity") == "major")
        fb_invalidating = sum(1 for f in fb_tickets if f.get("invalidates_acceptance"))

        # E2E metrics
        e2e_records = _filter_by_days(
            _read_jsonl(project_dir / "e2e_results.jsonl"), days
        )
        latest_e2e = e2e_records[-1] if e2e_records else None

        return {
            "project": project,
            "period_days": days,
            "sessions": {
                "count": len(sessions),
                "total_tokens": total_tokens,
                "total_files_modified": total_files,
                "avg_tokens_per_session": round(total_tokens / len(sessions)) if sessions else 0,
            },
            "features_active": active_features,
            "healing": {
                "count": len(healing),
                "resolved": healing_resolved,
                "resolution_rate": round(healing_resolved / len(healing) * 100, 1) if healing else 100.0,
            },
            "acceptance": {
                "validations": len(validations),
                "accepted": accepted,
                "conditional": conditional,
                "rejected": rejected,
                "acceptance_rate": acceptance_rate,
            },
            "merge_pipeline": {
                "total": len(merges),
                "merged": merged,
                "blocked": blocked,
                "blocked_by_feedback": blocked_by_feedback,
                "merge_rate": round(merged / len(merges) * 100, 1) if merges else 0.0,
            },
            "feedback": {
                "tickets": len(fb_tickets),
                "resolutions": len(fb_resolutions),
                "open": fb_open,
                "critical": fb_critical,
                "major": fb_major,
                "invalidating": fb_invalidating,
                "resolution_rate": round(len(fb_resolutions) / len(fb_tickets) * 100, 1) if fb_tickets else 0.0,
            },
            "e2e": {
                "runs": len(e2e_records),
                "latest_total": latest_e2e["total"] if latest_e2e else 0,
                "latest_passing": latest_e2e["passing"] if latest_e2e else 0,
                "latest_failing": latest_e2e["failing"] if latest_e2e else 0,
                "latest_skipped": latest_e2e["skipped"] if latest_e2e else 0,
                "latest_pass_rate": latest_e2e["pass_rate"] if latest_e2e else None,
                "latest_duration_ms": latest_e2e["duration_ms"] if latest_e2e else 0,
                "viewports": latest_e2e["viewports"] if latest_e2e else [],
                "trend": _compute_e2e_trend(e2e_records),
            },
            "last_activity": meta.get("last_activity", "never"),
            "stack": meta.get("stack", "unknown"),
        }

    @mcp.tool
    def get_sala_de_maquinas(days: int = 7) -> dict:
        """Global dashboard of ALL registered projects — the Sala de Máquinas.

        Args:
            days: Number of days to look back (default 7).

        Returns per-project summary (last activity, sessions, active feature,
        healing health, stack) plus global aggregates (total sessions, total
        tokens, most active project, overall health).
        Uses a 5-minute cache for performance. The cache is invalidated
        automatically on every write operation."""
        # Check cache
        cache_file = state_path / "dashboard_cache.json"
        if cache_file.exists():
            try:
                cache = json.loads(cache_file.read_text(encoding="utf-8"))
                cache_age = time.time() - cache.get("generated_at_epoch", 0)
                if cache_age < 300 and cache.get("period_days") == days:
                    return cache["data"]
            except (json.JSONDecodeError, OSError):
                pass

        registry = _read_registry(state_path)
        projects_data: list[dict] = []
        total_sessions = 0
        total_tokens = 0
        most_active_project = ""
        most_active_sessions = 0

        total_merged = 0
        total_blocked = 0
        total_accepted = 0
        total_validations = 0
        total_feedback_open = 0
        total_feedback_tickets = 0
        total_e2e_tests = 0
        total_e2e_passing = 0
        total_e2e_failing = 0
        total_e2e_runs = 0

        for proj_name, proj_info in registry.get("projects", {}).items():
            project_dir = state_path / "projects" / proj_name
            sessions = _filter_by_days(_read_jsonl(project_dir / "sessions.jsonl"), days)
            healing = _filter_by_days(_read_jsonl(project_dir / "healing.jsonl"), days)
            validations = _filter_by_days(_read_jsonl(project_dir / "acceptance_validations.jsonl"), days)
            merges = _filter_by_days(_read_jsonl(project_dir / "merge_events.jsonl"), days)
            feedback = _filter_by_days(_read_jsonl(project_dir / "feedback.jsonl"), days)
            meta = _read_meta(project_dir)

            session_count = len(sessions)
            tokens = sum(s.get("context_tokens_est", 0) for s in sessions)
            healing_resolved = sum(1 for h in healing if h.get("result") == "resolved")
            healing_rate = round(healing_resolved / len(healing) * 100, 1) if healing else 100.0

            if healing_rate >= 80:
                health = "healthy"
            elif healing_rate >= 50:
                health = "degraded"
            else:
                health = "critical"

            total_sessions += session_count
            total_tokens += tokens
            if session_count > most_active_sessions:
                most_active_sessions = session_count
                most_active_project = proj_name

            # Acceptance & merge metrics per project
            proj_accepted = sum(1 for v in validations if v.get("verdict") == "ACCEPTED")
            proj_merged = sum(1 for m in merges if m.get("merge_status") == "merged")
            proj_blocked = sum(1 for m in merges if m.get("merge_status") == "blocked")
            last_verdict = meta.get("last_verdict", "")

            # Feedback metrics per project
            fb_tickets = [f for f in feedback if f.get("event_subtype") != "resolution"]
            fb_open = sum(1 for f in fb_tickets if f.get("status") == "open")
            fb_blocking_ids = [
                f.get("feedback_id", "") for f in fb_tickets
                if f.get("status") == "open" and f.get("severity") in ("critical", "major")
            ]

            total_accepted += proj_accepted
            total_validations += len(validations)
            total_merged += proj_merged
            total_blocked += proj_blocked
            total_feedback_tickets += len(fb_tickets)
            total_feedback_open += fb_open

            # E2E metrics per project
            e2e_records = _filter_by_days(
                _read_jsonl(project_dir / "e2e_results.jsonl"), days
            )
            latest_e2e = e2e_records[-1] if e2e_records else None
            proj_e2e_total = latest_e2e["total"] if latest_e2e else 0
            proj_e2e_passing = latest_e2e["passing"] if latest_e2e else 0
            proj_e2e_failing = latest_e2e["failing"] if latest_e2e else 0

            total_e2e_tests += proj_e2e_total
            total_e2e_passing += proj_e2e_passing
            total_e2e_failing += proj_e2e_failing
            total_e2e_runs += len(e2e_records)

            projects_data.append({
                "project": proj_name,
                "stack": proj_info.get("stack", "unknown"),
                "last_activity": meta.get("last_activity", "never"),
                "sessions": session_count,
                "active_feature": meta.get("active_feature", ""),
                "healing_health": health,
                "healing_events": len(healing),
                "acceptance_validations": len(validations),
                "last_verdict": last_verdict,
                "merges": proj_merged,
                "blocked": proj_blocked,
                "feedback_open": fb_open,
                "feedback_blocking": fb_blocking_ids,
                "e2e_total": proj_e2e_total,
                "e2e_passing": proj_e2e_passing,
                "e2e_failing": proj_e2e_failing,
                "e2e_pass_rate": latest_e2e["pass_rate"] if latest_e2e else None,
                "e2e_runs": len(e2e_records),
            })

        # Sort by last activity descending
        projects_data.sort(key=lambda p: p.get("last_activity", ""), reverse=True)

        global_health = "healthy"
        unhealthy = sum(1 for p in projects_data if p["healing_health"] != "healthy")
        if unhealthy > len(projects_data) / 2:
            global_health = "critical"
        elif unhealthy > 0:
            global_health = "degraded"

        result = {
            "period_days": days,
            "projects": projects_data,
            "aggregates": {
                "total_projects": len(projects_data),
                "total_sessions": total_sessions,
                "total_tokens": total_tokens,
                "most_active_project": most_active_project,
                "global_health": global_health,
                "total_validations": total_validations,
                "total_accepted": total_accepted,
                "acceptance_rate": round(total_accepted / total_validations * 100, 1) if total_validations else 0.0,
                "total_merged": total_merged,
                "total_blocked": total_blocked,
                "total_feedback_tickets": total_feedback_tickets,
                "total_feedback_open": total_feedback_open,
                "total_e2e_runs": total_e2e_runs,
                "total_e2e_tests": total_e2e_tests,
                "total_e2e_passing": total_e2e_passing,
                "total_e2e_failing": total_e2e_failing,
                "e2e_global_pass_rate": (
                    round(total_e2e_passing / total_e2e_tests * 100, 1)
                    if total_e2e_tests > 0 else None
                ),
            },
        }

        # Write cache
        try:
            cache_data = {
                "generated_at_epoch": time.time(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "period_days": days,
                "data": result,
            }
            cache_file.write_text(
                json.dumps(cache_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

        return result

    @mcp.tool
    def get_project_timeline(project: str, limit: int = 50) -> dict:
        """Get a unified chronological timeline of all events for a project.

        Args:
            project: Project name.
            limit: Maximum number of events to return (default 50, most recent first).

        Merges sessions, checkpoints, healing, acceptance tests, acceptance
        validations, merge events, and feedback into a single timeline sorted
        by timestamp (newest first). Each event includes its type for filtering.
        Use for a complete chronological view of a project's development history."""
        registry = _read_registry(state_path)
        if project not in registry.get("projects", {}):
            return {
                "error": "Project not registered",
                "available": _available_projects(state_path),
            }

        project_dir = state_path / "projects" / project
        events: list[dict] = []

        for record in _read_jsonl(project_dir / "sessions.jsonl"):
            record["event_type"] = "session"
            events.append(record)

        for record in _read_jsonl(project_dir / "checkpoints.jsonl"):
            record["event_type"] = "checkpoint"
            events.append(record)

        for record in _read_jsonl(project_dir / "healing.jsonl"):
            record["event_type"] = "healing"
            events.append(record)

        for record in _read_jsonl(project_dir / "acceptance_tests.jsonl"):
            record["event_type"] = "acceptance_test"
            events.append(record)

        for record in _read_jsonl(project_dir / "acceptance_validations.jsonl"):
            record["event_type"] = "acceptance_validation"
            events.append(record)

        for record in _read_jsonl(project_dir / "merge_events.jsonl"):
            record["event_type"] = "merge"
            events.append(record)

        for record in _read_jsonl(project_dir / "feedback.jsonl"):
            if record.get("event_subtype") == "resolution":
                record["event_type"] = "feedback_resolution"
            else:
                record["event_type"] = "feedback"
            events.append(record)

        for record in _read_jsonl(project_dir / "e2e_results.jsonl"):
            record["event_type"] = "e2e_run"
            record["status"] = "green" if record.get("failing", 0) == 0 else "red"
            events.append(record)

        # Sort newest first
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

        return {
            "project": project,
            "total_events": len(events),
            "showing": min(limit, len(events)),
            "timeline": events[:limit],
        }

    # ===================================================================
    # MAINTENANCE TOOLS — state reset
    # ===================================================================

    @mcp.tool
    def reset_all_state(confirm: str) -> dict:
        """Reset ALL state data — registry, cache, and all project data.

        Args:
            confirm: Must be exactly "yes" to proceed (safety guard).

        Deletes registry.json, dashboard_cache.json, and the entire projects/
        directory. Recreates projects/ empty. USE WITH CAUTION — this is
        irreversible and removes all tracked sessions, checkpoints, and healing."""
        if confirm != "yes":
            return {
                "error": "Safety guard: pass confirm='yes' to proceed with full state reset.",
            }

        # Collect project names before deletion
        registry = _read_registry(state_path)
        deleted_projects = sorted(registry.get("projects", {}).keys())

        # Delete registry.json
        registry_file = state_path / "registry.json"
        if registry_file.exists():
            registry_file.unlink()

        # Delete dashboard_cache.json
        _invalidate_cache(state_path)

        # Delete and recreate projects/
        projects_dir = state_path / "projects"
        if projects_dir.exists():
            shutil.rmtree(projects_dir)
        projects_dir.mkdir(parents=True, exist_ok=True)

        return {
            "status": "ok",
            "action": "full_reset",
            "deleted_projects": deleted_projects,
        }

    @mcp.tool
    def reset_project(project: str, confirm: str) -> dict:
        """Reset state data for a single project.

        Args:
            project: Project name to reset.
            confirm: Must be exactly "yes" to proceed (safety guard).

        Deletes the project's directory (sessions, checkpoints, healing, meta)
        and removes its entry from registry.json. Invalidates dashboard cache.
        USE WITH CAUTION — this is irreversible for the target project."""
        if confirm != "yes":
            return {
                "error": "Safety guard: pass confirm='yes' to proceed with project reset.",
            }

        registry = _read_registry(state_path)
        if project not in registry.get("projects", {}):
            return {
                "error": f"Project '{project}' not found in registry.",
                "available": _available_projects(state_path),
            }

        # Count files before deletion
        project_dir = state_path / "projects" / project
        files_deleted = 0
        if project_dir.exists():
            files_deleted = sum(1 for _ in project_dir.rglob("*") if _.is_file())
            shutil.rmtree(project_dir)

        # Remove from registry
        del registry["projects"][project]
        _write_registry(state_path, registry)

        _invalidate_cache(state_path)

        return {
            "status": "ok",
            "action": "project_reset",
            "project": project,
            "files_deleted": files_deleted,
        }

    # ===================================================================
    # HEARTBEAT — consolidated project state snapshot
    # ===================================================================

    @mcp.tool
    def report_heartbeat(
        project: str,
        timestamp: str,
        session_active: bool = True,
        current_phase: str = "",
        current_feature: str = "",
        current_branch: str = "",
        plan_total_ucs: int = 0,
        plan_completed_ucs: int = 0,
        plan_current_uc: str = "",
        last_verdict: str = "",
        coverage_pct: float | None = None,
        tests_passing: int = 0,
        tests_failing: int = 0,
        open_feedback: int = 0,
        blocking_feedback: int = 0,
        healing_health: str = "healthy",
        self_healing_events: int = 0,
        last_operation: str = "idle",
        last_commit: str = "",
        last_commit_at: str = "",
    ) -> dict:
        """Report a consolidated project state snapshot (heartbeat).

        Overwrites project_state.json with the latest snapshot.  Called by
        engine hooks after each significant operation (/prd, /plan, /implement,
        /feedback) via HTTP POST to /api/heartbeat or via MCP tool call.

        Args:
            project: Project name (slug, e.g. 'mcprofit').
            timestamp: ISO 8601 timestamp from the client.
            session_active: Whether a Claude Code session is currently active.
            current_phase: Current pipeline phase (prd|plan|implement|validate|idle).
            current_feature: Feature being worked on.
            current_branch: Active git branch.
            plan_total_ucs: Total UCs in the current plan.
            plan_completed_ucs: Completed UCs so far.
            plan_current_uc: Current UC being implemented.
            last_verdict: Last AG-09b verdict (ACCEPTED|CONDITIONAL|REJECTED).
            coverage_pct: Test coverage percentage (null if unknown).
            tests_passing: Number of passing tests.
            tests_failing: Number of failing tests.
            open_feedback: Open feedback tickets count.
            blocking_feedback: Blocking (critical/major) feedback count.
            healing_health: Self-healing health (healthy|degraded|critical).
            self_healing_events: Count of self-healing events.
            last_operation: Last engine operation (prd|plan|implement|feedback|idle).
            last_commit: Last commit message.
            last_commit_at: Last commit timestamp (ISO 8601).
        """
        project_dir = _ensure_project_dir(state_path, project)
        _auto_register(state_path, project)

        state = {
            "project": project,
            "timestamp": timestamp,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "source": "heartbeat",
            "session_active": session_active,
            "current_phase": current_phase or None,
            "current_feature": current_feature or None,
            "current_branch": current_branch or None,
            "plan_progress": {
                "total_ucs": plan_total_ucs,
                "completed_ucs": plan_completed_ucs,
                "current_uc": plan_current_uc or None,
            },
            "last_verdict": last_verdict or None,
            "coverage_pct": coverage_pct,
            "tests_passing": tests_passing,
            "tests_failing": tests_failing,
            "open_feedback": open_feedback,
            "blocking_feedback": blocking_feedback,
            "healing_health": healing_health,
            "self_healing_events": self_healing_events,
            "last_operation": last_operation,
            "last_commit": last_commit or None,
            "last_commit_at": last_commit_at or None,
        }

        _write_project_state(project_dir, state)

        # Update meta
        meta = _read_meta(project_dir)
        meta["last_activity"] = timestamp
        if current_feature:
            meta["active_feature"] = current_feature
        _write_meta(project_dir, meta)

        _invalidate_cache(state_path)

        return {"status": "ok", "project": project, "event": "heartbeat"}
