"""Tools para consultar quality baselines, evidence, y métricas de proyectos."""

import json
from pathlib import Path
from fastmcp import FastMCP


def register_quality_tools(mcp: FastMCP, engine_path: Path):

    @mcp.tool
    def get_quality_baseline(project_name: str = "") -> dict | list[dict]:
        """Get quality baseline metrics for a project or list all baselines.
        Args:
            project_name: Project name (without .json). Empty = list all baselines.
        Returns lint errors/warnings, coverage percentage, test counts, and policies.
        Use before implementing to know the quality bar, or to check ratchet compliance."""
        baselines_dir = engine_path / ".quality" / "baselines"
        if not baselines_dir.exists():
            return {"error": "No baselines directory found"}

        if not project_name:
            baselines = []
            for f in baselines_dir.glob("*.json"):
                with open(f) as fh:
                    data = json.load(fh)
                    data["_filename"] = f.name
                    baselines.append(data)
            return baselines

        baseline_file = baselines_dir / f"{project_name}.json"
        if not baseline_file.exists():
            return {
                "error": f"No baseline for '{project_name}'",
                "available": [f.stem for f in baselines_dir.glob("*.json")],
            }

        with open(baseline_file) as f:
            return json.load(f)

    @mcp.tool
    def get_feature_evidence(feature_name: str) -> dict:
        """Get quality evidence, checkpoint, and healing data for a specific feature.
        Args:
            feature_name: Name of the feature directory in .quality/evidence/.
        Returns checkpoint state, evidence files, audit results, and self-healing events.
        Use to get the complete quality picture of a feature's implementation."""
        evidence_dir = engine_path / ".quality" / "evidence" / feature_name
        if not evidence_dir.exists():
            available = []
            parent = engine_path / ".quality" / "evidence"
            if parent.exists():
                available = [d.name for d in parent.iterdir() if d.is_dir()]
            return {
                "error": f"No evidence for feature '{feature_name}'",
                "available": available,
            }

        result: dict = {"feature": feature_name, "files": []}

        # Checkpoint
        checkpoint_file = evidence_dir / "checkpoint.json"
        if checkpoint_file.exists():
            with open(checkpoint_file) as f:
                result["checkpoint"] = json.load(f)

        # Audit report
        audit_file = evidence_dir / "audit.json"
        if audit_file.exists():
            with open(audit_file) as f:
                result["audit"] = json.load(f)

        # Healing summary
        healing_file = evidence_dir / "healing.jsonl"
        if healing_file.exists():
            events = []
            for line in healing_file.read_text().strip().splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            resolved = sum(1 for e in events if e.get("result") == "resolved")
            result["healing"] = {
                "total_events": len(events),
                "resolved": resolved,
                "failed": sum(1 for e in events if e.get("result") == "failed"),
                "max_level": max((e.get("level", 0) for e in events), default=0),
                "events": events,
            }

        # All files
        for f in evidence_dir.iterdir():
            if f.is_file():
                result["files"].append({
                    "name": f.name,
                    "size_bytes": f.stat().st_size,
                })

        return result

    @mcp.tool
    def list_features_in_progress() -> list[dict]:
        """List all features that have active checkpoints (currently in progress).
        Returns feature name, current phase number, phase name, branch, and timestamp.
        Use to see what's being worked on or find features to resume."""
        evidence_dir = engine_path / ".quality" / "evidence"
        if not evidence_dir.exists():
            return []

        features = []
        for feature_dir in sorted(evidence_dir.iterdir()):
            if feature_dir.is_dir():
                checkpoint = feature_dir / "checkpoint.json"
                if checkpoint.exists():
                    with open(checkpoint) as f:
                        data = json.load(f)
                        data["feature"] = feature_dir.name
                        features.append(data)
        return features

    @mcp.tool
    def get_quality_logs(date: str = "") -> dict:
        """Get session telemetry logs, optionally filtered by date.
        Args:
            date: Date in YYYY-MM-DD format. Empty = list available log files.
        Returns log entries or list of available log files.
        Use to analyze development session patterns and identify bottlenecks."""
        logs_dir = engine_path / ".quality" / "logs"
        if not logs_dir.exists():
            return {"error": "No logs directory found"}

        if not date:
            log_files = [f.name for f in sorted(logs_dir.glob("*.jsonl"))]
            return {"available_logs": log_files, "count": len(log_files)}

        log_file = logs_dir / f"sessions_{date}.jsonl"
        if not log_file.exists():
            return {"error": f"No log for date '{date}'"}

        entries = []
        for line in log_file.read_text().strip().splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        return {"date": date, "entries": entries, "count": len(entries)}
