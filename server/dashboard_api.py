"""REST API bridge for La Sala de Máquinas dashboard.

Registers custom HTTP routes on the FastMCP server that call the same
underlying logic as the MCP tools, serving JSON to the React frontend.
"""

import json
import os
from pathlib import Path

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse, Response
from starlette.staticfiles import StaticFiles

from .tools.state import (
    _read_registry,
    _read_jsonl,
    _read_meta,
    _filter_by_days,
    _available_projects,
    _compute_e2e_trend,
)


_CORS_ORIGIN = os.getenv("DASHBOARD_CORS_ORIGIN", "")


def _json(data: dict | list, status: int = 200) -> JSONResponse:
    cors = _CORS_ORIGIN if _CORS_ORIGIN else None
    headers = {"Access-Control-Allow-Origin": cors} if cors else {}
    return JSONResponse(data, status_code=status, headers=headers)


def register_dashboard_routes(mcp: FastMCP, engine_path: Path, state_path: Path) -> None:
    """Register REST API routes and static file serving for the dashboard."""

    # ------------------------------------------------------------------
    # Auth middleware (optional)
    # ------------------------------------------------------------------
    api_token = os.getenv("SPECBOX_SYNC_TOKEN", "")

    def _check_auth(request: Request) -> bool:
        if not api_token:
            return True
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            token = request.query_params.get("token", "")
        return token == api_token

    # ------------------------------------------------------------------
    # GET /health — Container healthcheck (no auth)
    # ------------------------------------------------------------------
    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return _json({"status": "ok", "version": "5.22.1"})

    # ------------------------------------------------------------------
    # GET /api/sala — Global dashboard
    # ------------------------------------------------------------------
    @mcp.custom_route("/api/sala", methods=["GET"])
    async def api_sala(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return _json({"error": "Unauthorized"}, 401)

        days = int(request.query_params.get("days", "7"))
        import time
        from datetime import datetime, timezone, timedelta

        # Check cache
        cache_file = state_path / "dashboard_cache.json"
        if cache_file.exists():
            try:
                cache = json.loads(cache_file.read_text(encoding="utf-8"))
                cache_age = time.time() - cache.get("generated_at_epoch", 0)
                if cache_age < 300 and cache.get("period_days") == days:
                    return _json(cache["data"])
            except (json.JSONDecodeError, OSError):
                pass

        registry = _read_registry(state_path)
        projects_data: list[dict] = []
        total_sessions = total_tokens = 0
        most_active_project = ""
        most_active_sessions = 0
        total_merged = total_blocked = total_accepted = total_validations = 0
        total_feedback_open = total_feedback_tickets = 0
        total_e2e_tests = total_e2e_passing = total_e2e_failing = total_e2e_runs = 0

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
            health = "healthy" if healing_rate >= 80 else "degraded" if healing_rate >= 50 else "critical"

            total_sessions += session_count
            total_tokens += tokens
            if session_count > most_active_sessions:
                most_active_sessions = session_count
                most_active_project = proj_name

            proj_accepted = sum(1 for v in validations if v.get("verdict") == "ACCEPTED")
            proj_merged = sum(1 for m in merges if m.get("merge_status") == "merged")
            proj_blocked = sum(1 for m in merges if m.get("merge_status") == "blocked")

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
            e2e_records = _filter_by_days(_read_jsonl(project_dir / "e2e_results.jsonl"), days)
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
                "last_verdict": meta.get("last_verdict", ""),
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

        # Cache
        try:
            cache_data = {
                "generated_at_epoch": time.time(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "period_days": days,
                "data": result,
            }
            cache_file.write_text(json.dumps(cache_data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

        return _json(result)

    # ------------------------------------------------------------------
    # GET /api/projects — List all projects
    # ------------------------------------------------------------------
    @mcp.custom_route("/api/projects", methods=["GET"])
    async def api_projects(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return _json({"error": "Unauthorized"}, 401)

        registry = _read_registry(state_path)
        projects: list[dict] = []
        for name, info in sorted(registry.get("projects", {}).items()):
            projects.append({
                "name": name,
                "stack": info.get("stack", "unknown"),
                "infra": info.get("infra", []),
                "repo_url": info.get("repo_url", ""),
                "description": info.get("description", ""),
                "registered_at": info.get("registered_at", ""),
                "engine_version": info.get("engine_version", "unknown"),
            })
        return _json(projects)

    # ------------------------------------------------------------------
    # GET /api/project/:name — Project detail
    # ------------------------------------------------------------------
    @mcp.custom_route("/api/project/{name}", methods=["GET"])
    async def api_project_detail(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return _json({"error": "Unauthorized"}, 401)

        name = request.path_params["name"]
        days = int(request.query_params.get("days", "7"))

        registry = _read_registry(state_path)
        if name not in registry.get("projects", {}):
            return _json({"error": "Project not registered", "available": _available_projects(state_path)}, 404)

        project_dir = state_path / "projects" / name
        sessions = _filter_by_days(_read_jsonl(project_dir / "sessions.jsonl"), days)
        checkpoints = _filter_by_days(_read_jsonl(project_dir / "checkpoints.jsonl"), days)
        healing = _filter_by_days(_read_jsonl(project_dir / "healing.jsonl"), days)
        validations = _filter_by_days(_read_jsonl(project_dir / "acceptance_validations.jsonl"), days)
        merges = _filter_by_days(_read_jsonl(project_dir / "merge_events.jsonl"), days)
        feedback = _filter_by_days(_read_jsonl(project_dir / "feedback.jsonl"), days)
        meta = _read_meta(project_dir)

        total_tokens = sum(s.get("context_tokens_est", 0) for s in sessions)
        total_files = sum(s.get("files_modified", 0) for s in sessions)
        active_features = sorted({c.get("feature", "") for c in checkpoints if c.get("feature")})
        healing_resolved = sum(1 for h in healing if h.get("result") == "resolved")

        accepted = sum(1 for v in validations if v.get("verdict") == "ACCEPTED")
        conditional = sum(1 for v in validations if v.get("verdict") == "CONDITIONAL")
        rejected = sum(1 for v in validations if v.get("verdict") == "REJECTED")

        merged = sum(1 for m in merges if m.get("merge_status") == "merged")
        blocked = sum(1 for m in merges if m.get("merge_status") == "blocked")
        blocked_by_feedback = sum(1 for m in merges if m.get("blocked_by") == "feedback")

        fb_tickets = [f for f in feedback if f.get("event_subtype") != "resolution"]
        fb_resolutions = [f for f in feedback if f.get("event_subtype") == "resolution"]
        fb_open = sum(1 for f in fb_tickets if f.get("status") == "open")
        fb_critical = sum(1 for f in fb_tickets if f.get("severity") == "critical")
        fb_major = sum(1 for f in fb_tickets if f.get("severity") == "major")
        fb_invalidating = sum(1 for f in fb_tickets if f.get("invalidates_acceptance"))

        e2e_records = _filter_by_days(_read_jsonl(project_dir / "e2e_results.jsonl"), days)
        latest_e2e = e2e_records[-1] if e2e_records else None

        return _json({
            "project": name,
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
                "acceptance_rate": round(accepted / len(validations) * 100, 1) if validations else 0.0,
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
        })

    # ------------------------------------------------------------------
    # GET /api/project/:name/timeline — Project timeline
    # ------------------------------------------------------------------
    @mcp.custom_route("/api/project/{name}/timeline", methods=["GET"])
    async def api_project_timeline(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return _json({"error": "Unauthorized"}, 401)

        name = request.path_params["name"]
        limit = int(request.query_params.get("limit", "50"))

        registry = _read_registry(state_path)
        if name not in registry.get("projects", {}):
            return _json({"error": "Project not registered"}, 404)

        project_dir = state_path / "projects" / name
        events: list[dict] = []

        file_type_map = {
            "sessions.jsonl": "session",
            "checkpoints.jsonl": "checkpoint",
            "healing.jsonl": "healing",
            "acceptance_tests.jsonl": "acceptance_test",
            "acceptance_validations.jsonl": "acceptance_validation",
            "merge_events.jsonl": "merge",
            "e2e_results.jsonl": "e2e_run",
        }

        for filename, event_type in file_type_map.items():
            for record in _read_jsonl(project_dir / filename):
                record["event_type"] = event_type
                events.append(record)

        for record in _read_jsonl(project_dir / "feedback.jsonl"):
            record["event_type"] = "feedback_resolution" if record.get("event_subtype") == "resolution" else "feedback"
            events.append(record)

        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

        return _json({
            "project": name,
            "total_events": len(events),
            "showing": min(limit, len(events)),
            "timeline": events[:limit],
        })

    # ------------------------------------------------------------------
    # GET /api/project/:name/quality — Quality baseline
    # ------------------------------------------------------------------
    @mcp.custom_route("/api/project/{name}/quality", methods=["GET"])
    async def api_project_quality(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return _json({"error": "Unauthorized"}, 401)

        name = request.path_params["name"]
        baselines_dir = engine_path / ".quality" / "baselines"

        if not baselines_dir.exists():
            return _json({"error": "No baselines directory"}, 404)

        baseline_file = baselines_dir / f"{name}.json"
        if not baseline_file.exists():
            return _json({"error": f"No baseline for '{name}'"}, 404)

        return _json(json.loads(baseline_file.read_text(encoding="utf-8")))

    # ------------------------------------------------------------------
    # GET /api/healing — Self-healing summary
    # ------------------------------------------------------------------
    @mcp.custom_route("/api/healing", methods=["GET"])
    async def api_healing(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return _json({"error": "Unauthorized"}, 401)

        evidence_dir = engine_path / ".quality" / "evidence"
        if not evidence_dir.exists():
            return _json({"total_events": 0, "message": "No evidence directory"})

        all_events: list[dict] = []
        feature_stats: list[dict] = []

        for feature_dir in evidence_dir.iterdir():
            if not feature_dir.is_dir():
                continue
            healing_file = feature_dir / "healing.jsonl"
            if not healing_file.exists():
                continue

            events = []
            for line in healing_file.read_text().strip().splitlines():
                try:
                    event = json.loads(line)
                    event["_feature"] = feature_dir.name
                    events.append(event)
                except json.JSONDecodeError:
                    continue

            resolved = sum(1 for e in events if e.get("result") == "resolved")
            failed = sum(1 for e in events if e.get("result") == "failed")
            max_level = max((e.get("level", 0) for e in events), default=0)

            feature_stats.append({
                "feature": feature_dir.name,
                "events": len(events),
                "resolved": resolved,
                "failed": failed,
                "max_level": max_level,
            })
            all_events.extend(events)

        if not all_events:
            return _json({"healing_events": 0, "message": "No healing events"})

        total_resolved = sum(1 for e in all_events if e.get("result") == "resolved")
        total_failed = sum(1 for e in all_events if e.get("result") == "failed")
        levels: dict[str, int] = {}
        for e in all_events:
            lvl = str(e.get("level", "?"))
            levels[lvl] = levels.get(lvl, 0) + 1

        feature_stats.sort(key=lambda x: x["failed"], reverse=True)

        return _json({
            "total_events": len(all_events),
            "total_resolved": total_resolved,
            "total_failed": total_failed,
            "resolution_rate": f"{round(total_resolved / len(all_events) * 100)}%" if all_events else "N/A",
            "by_level": levels,
            "features": feature_stats,
            "overall_health": "healthy" if total_failed == 0 else "degraded" if total_failed <= 3 else "unhealthy",
        })

    # ------------------------------------------------------------------
    # GET /api/e2e — E2E testing summary
    # ------------------------------------------------------------------
    @mcp.custom_route("/api/e2e", methods=["GET"])
    async def api_e2e(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return _json({"error": "Unauthorized"}, 401)

        registry = _read_registry(state_path)
        projects: list[dict] = []
        total_tests = 0
        total_passing = 0
        total_failing = 0

        for name in sorted(registry.get("projects", {})):
            proj_dir = state_path / "projects" / name
            e2e_file = proj_dir / "e2e_results.jsonl"
            if not e2e_file.exists():
                continue
            records = _read_jsonl(e2e_file)
            if not records:
                continue
            latest = records[-1]
            projects.append({
                "project": name,
                "total": latest["total"],
                "passing": latest["passing"],
                "failing": latest["failing"],
                "pass_rate": latest["pass_rate"],
                "viewports": latest.get("viewports", []),
                "runs": len(records),
                "last_run": latest["timestamp"],
                "trend": _compute_e2e_trend(records),
            })
            total_tests += latest["total"]
            total_passing += latest["passing"]
            total_failing += latest["failing"]

        return _json({
            "total_projects_with_e2e": len(projects),
            "total_tests": total_tests,
            "total_passing": total_passing,
            "total_failing": total_failing,
            "global_pass_rate": (
                round(total_passing / total_tests * 100, 1)
                if total_tests > 0 else None
            ),
            "projects": projects,
        })

    # ------------------------------------------------------------------
    # GET /api/upgrades — Version matrix
    # ------------------------------------------------------------------
    @mcp.custom_route("/api/upgrades", methods=["GET"])
    async def api_upgrades(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return _json({"error": "Unauthorized"}, 401)

        import yaml
        from . import __version__ as mcp_version

        version_file = engine_path / "ENGINE_VERSION.yaml"
        current_engine = "unknown"
        if version_file.exists():
            try:
                with open(version_file) as f:
                    data = yaml.safe_load(f)
                    current_engine = data.get("version", "unknown")
            except Exception:
                pass

        registry = _read_registry(state_path)
        projects: list[dict] = []
        needs_upgrade_count = 0

        for proj_name in sorted(registry.get("projects", {}).keys()):
            project_dir = state_path / "projects" / proj_name
            meta = _read_meta(project_dir)
            proj_engine = meta.get("engine_version", "unknown")
            proj_mcp = meta.get("mcp_version", "unknown")
            needs_upgrade = proj_engine != current_engine or proj_mcp != mcp_version

            if needs_upgrade:
                needs_upgrade_count += 1

            projects.append({
                "project": proj_name,
                "engine_version": proj_engine,
                "mcp_version": proj_mcp,
                "last_upgraded_at": meta.get("last_upgraded_at", "never"),
                "stack": meta.get("stack", "unknown"),
                "needs_upgrade": needs_upgrade,
            })

        return _json({
            "current_engine_version": current_engine,
            "current_mcp_version": mcp_version,
            "total_projects": len(projects),
            "needs_upgrade": needs_upgrade_count,
            "up_to_date": len(projects) - needs_upgrade_count,
            "projects": projects,
        })

    # ------------------------------------------------------------------
    # GET /api/spec-driven — Spec-driven (Trello/Plane) board status
    # ------------------------------------------------------------------
    @mcp.custom_route("/api/spec-driven", methods=["GET"])
    async def api_spec_driven(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return _json({"error": "Unauthorized"}, 401)

        registry = _read_registry(state_path)
        projects: list[dict] = []
        total_us = total_uc = total_ac = 0
        progress_sum = 0

        for proj_name, proj_info in sorted(registry.get("projects", {}).items()):
            board_id = proj_info.get("board_id", "") or proj_info.get("boardId", "")
            if not board_id:
                continue

            project_dir = state_path / "projects" / proj_name
            meta = _read_meta(project_dir)

            # Read spec-driven counts from meta (populated by /prd and /plan)
            us_count = meta.get("us_count", 0)
            uc_count = meta.get("uc_count", 0)
            ac_count = meta.get("ac_count", 0)
            progress = meta.get("spec_progress", 0)
            last_sync = meta.get("last_board_sync", meta.get("last_activity", "never"))

            total_us += us_count
            total_uc += uc_count
            total_ac += ac_count
            progress_sum += progress

            projects.append({
                "project": proj_name,
                "board_id": board_id,
                "stack": proj_info.get("stack", "unknown"),
                "us_count": us_count,
                "uc_count": uc_count,
                "ac_count": ac_count,
                "progress": progress,
                "last_sync": last_sync,
            })

        avg_progress = round(progress_sum / len(projects), 1) if projects else 0

        return _json({
            "total_projects": len(projects),
            "total_us": total_us,
            "total_uc": total_uc,
            "total_ac": total_ac,
            "avg_progress": avg_progress,
            "projects": projects,
        })

    # ------------------------------------------------------------------
    # GET /api/benchmark/public — Public benchmark metrics (UC-014)
    # No auth required (AC-64). Rate limiting is handled at infra level.
    # ------------------------------------------------------------------
    @mcp.custom_route("/api/benchmark/public", methods=["GET"])
    async def api_benchmark_public(request: Request) -> JSONResponse:
        # AC-63: Returns JSON with same metrics as snapshot
        # AC-64: No auth required
        # AC-66: Returns 404 if no snapshot exists
        from .benchmark_generator import generate_benchmark

        import yaml

        engine_version = "unknown"
        version_file = engine_path / "ENGINE_VERSION.yaml"
        if version_file.exists():
            try:
                with open(version_file) as f:
                    data = yaml.safe_load(f)
                    engine_version = data.get("version", "unknown")
            except Exception:
                pass

        metrics = generate_benchmark(state_path, engine_version)

        if metrics["total_projects"] == 0:
            return _json({"error": "No benchmark data available", "detail": "No projects found in state."}, 404)

        # AC-65: Include generated_at and engine_version
        return _json(metrics)

    # ------------------------------------------------------------------
    # POST /api/heartbeat — Receive consolidated project state
    # ------------------------------------------------------------------
    def _check_sync_auth(request: Request) -> bool:
        return _check_auth(request)

    @mcp.custom_route("/api/heartbeat", methods=["POST"])
    async def api_heartbeat(request: Request) -> JSONResponse:
        if not _check_sync_auth(request):
            return _json({"error": "Unauthorized"}, 401)

        try:
            body = await request.json()
        except Exception:
            return _json({"error": "Invalid JSON body"}, 400)

        project = body.get("project", "").strip()
        if not project:
            return _json({"error": "Missing required field: project"}, 400)

        timestamp = body.get("timestamp", "")
        if not timestamp:
            from datetime import datetime as dt, timezone as tz
            timestamp = dt.now(tz.utc).isoformat()

        from .tools.state import (
            _ensure_project_dir,
            _auto_register,
            _write_project_state,
            _read_meta,
            _write_meta,
            _invalidate_cache,
        )

        project_dir = _ensure_project_dir(state_path, project)
        _auto_register(state_path, project)

        from datetime import datetime as dt, timezone as tz

        state_data = {
            "project": project,
            "timestamp": timestamp,
            "received_at": dt.now(tz.utc).isoformat(),
            "source": "heartbeat",
            "session_active": body.get("session_active", True),
            "current_phase": body.get("current_phase") or None,
            "current_feature": body.get("current_feature") or None,
            "current_branch": body.get("current_branch") or None,
            "plan_progress": {
                "total_ucs": body.get("plan_total_ucs", 0),
                "completed_ucs": body.get("plan_completed_ucs", 0),
                "current_uc": body.get("plan_current_uc") or None,
            },
            "last_verdict": body.get("last_verdict") or None,
            "coverage_pct": body.get("coverage_pct"),
            "tests_passing": body.get("tests_passing", 0),
            "tests_failing": body.get("tests_failing", 0),
            "open_feedback": body.get("open_feedback", 0),
            "blocking_feedback": body.get("blocking_feedback", 0),
            "healing_health": body.get("healing_health", "healthy"),
            "self_healing_events": body.get("self_healing_events", 0),
            "last_operation": body.get("last_operation", "idle"),
            "last_commit": body.get("last_commit") or None,
            "last_commit_at": body.get("last_commit_at") or None,
        }

        _write_project_state(project_dir, state_data)

        meta = _read_meta(project_dir)
        meta["last_activity"] = timestamp
        if state_data["current_feature"]:
            meta["active_feature"] = state_data["current_feature"]
        _write_meta(project_dir, meta)

        _invalidate_cache(state_path)

        # AC-10: Log heartbeat to heartbeats.jsonl
        from .tools.heartbeat_stats import append_heartbeat_log
        source_ip = request.client.host if request.client else "unknown"
        append_heartbeat_log(state_path, project, source_ip, "ok")

        return _json({"status": "ok", "project": project})

    # ------------------------------------------------------------------
    # GET /api/heartbeats/stats — Heartbeat observability (AC-09)
    # ------------------------------------------------------------------
    @mcp.custom_route("/api/heartbeats/stats", methods=["GET"])
    async def api_heartbeat_stats(request: Request) -> JSONResponse:
        if not _check_auth(request):
            return _json({"error": "Unauthorized"}, 401)

        from .tools.heartbeat_stats import compute_heartbeat_stats
        stats = compute_heartbeat_stats(state_path)
        return _json(stats)

    # ------------------------------------------------------------------
    # POST /api/sync/github — Sync state from GitHub repos
    # ------------------------------------------------------------------
    @mcp.custom_route("/api/sync/github", methods=["POST"])
    async def api_sync_github(request: Request) -> JSONResponse:
        if not _check_sync_auth(request):
            return _json({"error": "Unauthorized"}, 401)

        try:
            body = await request.json()
        except Exception:
            body = {}

        force = body.get("force", False)

        from .github_sync import sync_all, sync_project, parse_repo_url

        # If specific repos provided, sync only those
        repos = body.get("repos", [])
        if repos:
            results = []
            for repo_info in repos:
                owner = repo_info.get("owner", "")
                repo = repo_info.get("repo", "")
                branch = repo_info.get("branch", "main")
                slug = repo_info.get("slug", repo)
                if owner and repo:
                    result = sync_project(
                        owner=owner,
                        repo=repo,
                        state_path=state_path,
                        project_slug=slug,
                        branch=branch,
                        force=force,
                    )
                    results.append(result)
        else:
            results = sync_all(state_path, force=force)

        summary = {
            "total": len(results),
            "updated": sum(1 for r in results if r.get("status") == "updated"),
            "skipped": sum(1 for r in results if r.get("status") == "skipped"),
            "failed": sum(1 for r in results if r.get("status") == "failed"),
        }

        return _json({"summary": summary, "results": results})

    # ------------------------------------------------------------------
    # Static files — serve React build from /dashboard/dist
    # ------------------------------------------------------------------
    # In Docker: /app/server/dashboard/dist (monorepo layout)
    dashboard_dist = Path(__file__).parent / "dashboard" / "dist"
    if not dashboard_dist.exists():
        # Fallback: check absolute path
        dashboard_dist = Path("/app/server/dashboard/dist")

    if dashboard_dist.exists():
        @mcp.custom_route("/assets/{path:path}", methods=["GET"])
        async def serve_assets(request: Request) -> Response:
            file_path = dashboard_dist / "assets" / request.path_params["path"]
            if file_path.exists() and file_path.is_file():
                content_type = "application/javascript"
                if file_path.suffix == ".css":
                    content_type = "text/css"
                elif file_path.suffix == ".svg":
                    content_type = "image/svg+xml"
                elif file_path.suffix == ".png":
                    content_type = "image/png"
                elif file_path.suffix == ".woff2":
                    content_type = "font/woff2"
                return Response(
                    content=file_path.read_bytes(),
                    media_type=content_type,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"},
                )
            return Response(status_code=404)

        @mcp.custom_route("/favicon.ico", methods=["GET"])
        async def serve_favicon(request: Request) -> Response:
            favicon = dashboard_dist / "favicon.ico"
            if favicon.exists():
                return Response(content=favicon.read_bytes(), media_type="image/x-icon")
            return Response(status_code=404)

        # SPA fallback — serve index.html for all non-API, non-asset routes
        @mcp.custom_route("/{path:path}", methods=["GET"])
        async def serve_spa(request: Request) -> Response:
            path = request.path_params.get("path", "")
            # Don't intercept API or MCP routes
            if path.startswith("api/") or path.startswith("mcp"):
                return Response(status_code=404)

            # Try to serve the exact file first
            file_path = dashboard_dist / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))

            # SPA fallback to index.html
            index = dashboard_dist / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return Response(status_code=404)

        @mcp.custom_route("/", methods=["GET"])
        async def serve_index(request: Request) -> Response:
            index = dashboard_dist / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return _json({"message": "La Sala de Máquinas — Dashboard not built yet. Run: cd dashboard && npm run build"})
