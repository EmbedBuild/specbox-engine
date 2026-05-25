"""Tools for session telemetry, self-healing analysis, and activity dashboards."""

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastmcp import FastMCP


def _find_engine_path() -> str | None:
    """Find the jps_dev_engine root by checking common locations."""
    candidates = [
        os.environ.get("JPS_ENGINE_PATH", ""),
        os.path.expanduser("~/jps_dev_engine"),
        os.path.expanduser("~/Desktop/Proyectos/jpsdeveloper/jps_dev_engine"),
    ]
    for path in candidates:
        if path and os.path.isfile(os.path.join(path, "ENGINE_VERSION.yaml")):
            return path
    return None


def register_telemetry_tools(mcp: FastMCP, engine_path: Path):

    @mcp.tool
    def get_session_summary(days: int = 7) -> dict:
        """Get a summary of development sessions from the last N days.
        Args:
            days: Number of days to look back (default 7).
        Returns session count per day, total events, most active days.
        Use to understand development patterns, frequency, and workload."""
        logs_dir = engine_path / ".quality" / "logs"
        if not logs_dir.exists():
            return {"error": "No logs directory", "hint": "Sessions are logged by the on-session-end hook"}

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        daily_stats: dict[str, int] = {}
        daily_context_tokens: dict[str, int] = {}
        daily_files_modified: dict[str, int] = {}
        total_events = 0

        for logfile in sorted(logs_dir.glob("sessions_*.jsonl")):
            date_str = logfile.stem.replace("sessions_", "")
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if file_date < cutoff:
                    continue
            except ValueError:
                continue

            count = 0
            day_tokens = 0
            day_files = 0
            for line in logfile.read_text().strip().splitlines():
                if not line.strip():
                    continue
                count += 1
                try:
                    event = json.loads(line)
                    day_tokens += event.get("context_tokens_est", 0)
                    day_files += event.get("files_modified", 0)
                except json.JSONDecodeError:
                    continue
            daily_stats[date_str] = count
            daily_context_tokens[date_str] = day_tokens
            daily_files_modified[date_str] = day_files
            total_events += count

        if not daily_stats:
            return {"days_searched": days, "sessions_found": 0, "message": "No sessions in this period"}

        sorted_days = sorted(daily_stats.items(), key=lambda x: x[1], reverse=True)
        total_tokens = sum(daily_context_tokens.values())
        avg_tokens_per_session = total_tokens // max(total_events, 1)

        if avg_tokens_per_session < 30000:
            context_health = "green"
        elif avg_tokens_per_session < 60000:
            context_health = "yellow"
        else:
            context_health = "red"

        return {
            "period": f"last {days} days",
            "total_events": total_events,
            "active_days": len(daily_stats),
            "daily_breakdown": dict(sorted(daily_stats.items())),
            "daily_context_tokens": dict(sorted(daily_context_tokens.items())),
            "daily_files_modified": dict(sorted(daily_files_modified.items())),
            "most_active_day": sorted_days[0] if sorted_days else None,
            "avg_events_per_active_day": round(total_events / len(daily_stats), 1) if daily_stats else 0,
            "avg_tokens_per_session": avg_tokens_per_session,
            "context_health": context_health,
        }

    @mcp.tool
    def get_session_events(date: str = "") -> dict:
        """Get raw session events for a specific date.
        Args:
            date: Date in YYYY-MM-DD format. Empty = today.
        Returns individual session events with timestamps and working directories.
        Use to inspect what happened in a specific development day."""
        logs_dir = engine_path / ".quality" / "logs"
        if not logs_dir.exists():
            return {"error": "No logs directory found"}

        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        logfile = logs_dir / f"sessions_{date}.jsonl"
        if not logfile.exists():
            available = sorted([f.stem.replace("sessions_", "") for f in logs_dir.glob("sessions_*.jsonl")])
            return {"error": f"No log for {date}", "available_dates": available[-10:]}

        events = []
        for line in logfile.read_text().strip().splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        return {"date": date, "events": events, "count": len(events)}

    @mcp.tool
    def get_healing_log(feature_name: str) -> dict:
        """Get self-healing events for a specific feature implementation.
        Args:
            feature_name: Name of the feature (directory in .quality/evidence/).
        Returns healing events: what failed, what level of recovery was used,
        whether it was resolved. Use to audit implementation reliability.
        Self-healing levels: 1=auto-fix, 2=diagnose+fix, 3=rollback+retry, 4=human needed."""
        evidence_dir = engine_path / ".quality" / "evidence" / feature_name
        healing_file = evidence_dir / "healing.jsonl"

        if not healing_file.exists():
            available = []
            parent = engine_path / ".quality" / "evidence"
            if parent.exists():
                for d in parent.iterdir():
                    if d.is_dir() and (d / "healing.jsonl").exists():
                        available.append(d.name)
            if not available:
                return {"feature": feature_name, "events": [], "message": "No healing events (clean implementation)"}
            return {"error": f"No healing log for '{feature_name}'", "features_with_healing": available}

        events = []
        for line in healing_file.read_text().strip().splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        # Aggregate stats
        levels: dict[str, int] = {}
        resolved = 0
        failed = 0
        for e in events:
            lvl = str(e.get("level", "?"))
            levels[lvl] = levels.get(lvl, 0) + 1
            if e.get("result") == "resolved":
                resolved += 1
            elif e.get("result") == "failed":
                failed += 1

        return {
            "feature": feature_name,
            "total_events": len(events),
            "resolved": resolved,
            "failed": failed,
            "by_level": levels,
            "events": events,
            "health": "healthy" if failed == 0 else "degraded" if failed <= 2 else "unhealthy",
        }

    @mcp.tool
    def get_healing_summary() -> dict:
        """Get aggregated self-healing statistics across ALL features.
        Returns total events, resolution rate, most problematic features,
        level distribution. Use to assess overall engine reliability and
        identify patterns in implementation failures."""
        evidence_dir = engine_path / ".quality" / "evidence"
        if not evidence_dir.exists():
            return {"total_features": 0, "features_with_healing": 0, "message": "No evidence directory"}

        all_events = []
        feature_stats = []

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
            return {"total_features_scanned": len(list(evidence_dir.iterdir())), "healing_events": 0, "message": "No healing events found (all clean implementations)"}

        total_resolved = sum(1 for e in all_events if e.get("result") == "resolved")
        total_failed = sum(1 for e in all_events if e.get("result") == "failed")
        levels: dict[str, int] = {}
        for e in all_events:
            lvl = str(e.get("level", "?"))
            levels[lvl] = levels.get(lvl, 0) + 1

        # Sort by most problematic
        feature_stats.sort(key=lambda x: x["failed"], reverse=True)

        return {
            "total_events": len(all_events),
            "total_resolved": total_resolved,
            "total_failed": total_failed,
            "resolution_rate": f"{round(total_resolved / len(all_events) * 100)}%" if all_events else "N/A",
            "by_level": levels,
            "features": feature_stats,
            "overall_health": "healthy" if total_failed == 0 else "degraded" if total_failed <= 3 else "unhealthy",
        }

    @mcp.tool
    def get_activity_dashboard(days: int = 14) -> dict:
        """Get a comprehensive activity dashboard combining sessions, features,
        checkpoints, and healing data for the last N days.
        Args:
            days: Number of days to look back (default 14).
        Returns unified view of: session activity, active features with status,
        healing health, quality baseline status, and recent commits.
        Use for a quick overview of the entire engine's state and recent activity."""
        dashboard: dict = {
            "period": f"last {days} days",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sessions": {"total": 0, "active_days": 0},
            "features": {"in_progress": [], "completed": [], "failed": []},
            "healing": {"total_events": 0, "resolution_rate": "N/A", "health": "unknown"},
            "baselines": [],
            "engine_version": "unknown",
        }

        # Engine version
        version_file = engine_path / "ENGINE_VERSION.yaml"
        if version_file.exists():
            import yaml
            with open(version_file) as f:
                v = yaml.safe_load(f)
                dashboard["engine_version"] = v.get("version", "unknown")

        # Sessions
        logs_dir = engine_path / ".quality" / "logs"
        if logs_dir.exists():
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            total = 0
            active = 0
            for logfile in logs_dir.glob("sessions_*.jsonl"):
                date_str = logfile.stem.replace("sessions_", "")
                try:
                    file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    if file_date < cutoff:
                        continue
                except ValueError:
                    continue
                count = sum(1 for line in logfile.read_text().strip().splitlines() if line.strip())
                total += count
                active += 1
            dashboard["sessions"] = {"total": total, "active_days": active}

        # Features (from checkpoints)
        evidence_dir = engine_path / ".quality" / "evidence"
        if evidence_dir.exists():
            for feature_dir in evidence_dir.iterdir():
                if not feature_dir.is_dir():
                    continue
                cp_file = feature_dir / "checkpoint.json"
                if cp_file.exists():
                    try:
                        with open(cp_file) as f:
                            cp = json.load(f)
                        entry = {
                            "feature": feature_dir.name,
                            "phase": cp.get("phase"),
                            "phase_name": cp.get("phase_name"),
                            "branch": cp.get("branch"),
                            "status": cp.get("status"),
                            "timestamp": cp.get("timestamp"),
                        }
                        status = cp.get("status", "unknown")
                        if status == "complete":
                            dashboard["features"]["completed"].append(entry)
                        elif status in ("failed", "needs_human"):
                            dashboard["features"]["failed"].append(entry)
                        else:
                            dashboard["features"]["in_progress"].append(entry)
                    except (json.JSONDecodeError, KeyError):
                        continue

        # Healing summary (inline, lightweight)
        if evidence_dir and evidence_dir.exists():
            total_healing = 0
            total_resolved = 0
            for hf in evidence_dir.rglob("healing.jsonl"):
                for line in hf.read_text().strip().splitlines():
                    try:
                        event = json.loads(line)
                        total_healing += 1
                        if event.get("result") == "resolved":
                            total_resolved += 1
                    except json.JSONDecodeError:
                        continue
            if total_healing > 0:
                rate = round(total_resolved / total_healing * 100)
                dashboard["healing"] = {
                    "total_events": total_healing,
                    "resolution_rate": f"{rate}%",
                    "health": "healthy" if rate >= 90 else "degraded" if rate >= 70 else "unhealthy",
                }
            else:
                dashboard["healing"] = {"total_events": 0, "resolution_rate": "100%", "health": "healthy"}

        # Context health
        if logs_dir.exists():
            total_context_tokens = 0
            total_session_count = 0
            for logfile in logs_dir.glob("sessions_*.jsonl"):
                date_str = logfile.stem.replace("sessions_", "")
                try:
                    file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    if file_date < cutoff:
                        continue
                except ValueError:
                    continue
                for line in logfile.read_text().strip().splitlines():
                    if not line.strip():
                        continue
                    total_session_count += 1
                    try:
                        event = json.loads(line)
                        total_context_tokens += event.get("context_tokens_est", 0)
                    except json.JSONDecodeError:
                        continue
            avg_tokens = total_context_tokens // max(total_session_count, 1)
            if avg_tokens < 30000:
                context_health = {"status": "healthy", "indicator": "🟢", "avg_tokens": avg_tokens}
            elif avg_tokens < 60000:
                context_health = {"status": "moderate", "indicator": "🟡", "avg_tokens": avg_tokens}
            else:
                context_health = {"status": "high", "indicator": "🔴", "avg_tokens": avg_tokens, "recommendation": "Review Task Isolation, consider splitting tasks"}
            dashboard["context_health"] = context_health

        # Baselines
        baselines_dir = engine_path / ".quality" / "baselines"
        if baselines_dir.exists():
            for bf in baselines_dir.glob("*.json"):
                try:
                    with open(bf) as f:
                        data = json.load(f)
                    dashboard["baselines"].append({
                        "project": data.get("project", bf.stem),
                        "stack": data.get("stack"),
                        "lint_errors": data.get("metrics", {}).get("lint_errors"),
                        "coverage": data.get("metrics", {}).get("test_coverage_pct"),
                        "timestamp": data.get("timestamp"),
                    })
                except (json.JSONDecodeError, KeyError):
                    continue

        return dashboard

    @mcp.tool
    async def get_context_budget(
        file_inventory: dict[str, int] | None = None,
        context_window_tokens: int = 1_000_000,
    ) -> str:
        """Estimate token cost of a file inventory for context budget planning.

        **v6.0.1 — content-passing API**

        The client (skill or hook) walks the filesystem and supplies
        ``file_inventory`` as ``{relative_path: byte_count}``. The token
        estimate uses the conventional chars/4 heuristic (1 byte ≈ 1 char
        for ASCII-dominant code).

        Args:
            file_inventory: ``{relative_path: byte_count}`` mapping. ``None``
                or empty returns a zero estimate.
            context_window_tokens: Size of the target context window in
                tokens. Defaults to 1M (Opus 4.7 1M-context tier).

        Returns JSON with estimated tokens, context window percentage,
        health flag (green / yellow / red) and a recommendation.
        Thresholds: Green < 15%, Yellow 15-30%, Red > 30%.
        """
        inventory = file_inventory or {}
        total_bytes = 0
        per_file: list[dict] = []
        for rel_path, byte_count in inventory.items():
            if not isinstance(byte_count, int):
                continue
            total_bytes += max(0, byte_count)
            per_file.append({
                "path": rel_path,
                "bytes": byte_count,
                "estimated_tokens": max(0, byte_count) // 4,
            })

        estimated_tokens = total_bytes // 4
        context_pct = (
            round(estimated_tokens / context_window_tokens * 100, 2)
            if context_window_tokens > 0 else 0
        )

        if context_pct < 15:
            health = "green"
            recommendation = "Safe for single task"
        elif context_pct < 30:
            health = "yellow"
            recommendation = "Consider splitting into subtasks"
        else:
            health = "red"
            recommendation = "Must split into subtasks"

        response = {
            "total_files": len(per_file),
            "total_bytes": total_bytes,
            "estimated_tokens": estimated_tokens,
            "context_window_tokens": context_window_tokens,
            "context_window_pct": context_pct,
            "health": health,
            "recommendation": recommendation,
            "files": per_file,
        }
        return json.dumps(response, indent=2)
