"""Tools para consultar estado y configuración del engine."""

import subprocess
from pathlib import Path

import yaml
from fastmcp import FastMCP


def register_engine_tools(mcp: FastMCP, engine_path: Path):

    def _read_local_version() -> dict:
        """Read local ENGINE_VERSION.yaml."""
        version_file = engine_path / "ENGINE_VERSION.yaml"
        if not version_file.exists():
            return {}
        try:
            with open(version_file) as f:
                return yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            return {}

    def _git_log_local(n: int = 1) -> str:
        """Get last N commit hashes from local engine clone."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{n}", "--format=%H %s"],
                cwd=str(engine_path),
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return ""

    @mcp.tool
    def get_engine_version() -> dict:
        """Get the current SDD-JPS Engine version, codename, and changelog.
        Use when you need to know which version of the engine is installed
        or what changed in the latest release."""
        version_file = engine_path / "ENGINE_VERSION.yaml"
        if not version_file.exists():
            return {"error": "ENGINE_VERSION.yaml not found", "path": str(version_file)}
        with open(version_file) as f:
            return yaml.safe_load(f)

    @mcp.tool
    def get_engine_status() -> dict:
        """Get a comprehensive status overview of the SDD-JPS Engine.
        Returns counts of: skills, plans, baselines, features in progress,
        hooks installed, supported stacks, engine version, and local git commit.
        Use when you need a quick health check of the entire engine."""
        status = {
            "engine_path": str(engine_path),
            "exists": engine_path.exists(),
            "engine_version": "unknown",
            "engine_codename": "unknown",
            "local_commit": "",
            "skills": [],
            "plans": [],
            "baselines": [],
            "features_in_progress": [],
            "hooks": [],
            "stacks": [],
        }

        if not engine_path.exists():
            return status

        local = _read_local_version()
        status["engine_version"] = str(local.get("version", "unknown"))
        status["engine_codename"] = local.get("codename", "unknown")
        status["local_commit"] = _git_log_local(1)

        skills_dir = engine_path / ".claude" / "skills"
        if skills_dir.exists():
            status["skills"] = [d.name for d in skills_dir.iterdir() if d.is_dir()]

        plans_dir = engine_path / "doc" / "plans"
        if plans_dir.exists():
            status["plans"] = [f.stem for f in plans_dir.glob("*.md")]

        baselines_dir = engine_path / ".quality" / "baselines"
        if baselines_dir.exists():
            status["baselines"] = [f.stem for f in baselines_dir.glob("*.json")]

        evidence_dir = engine_path / ".quality" / "evidence"
        if evidence_dir.exists():
            for feature_dir in evidence_dir.iterdir():
                if feature_dir.is_dir() and (feature_dir / "checkpoint.json").exists():
                    status["features_in_progress"].append(feature_dir.name)

        hooks_dir = engine_path / ".claude" / "hooks"
        if hooks_dir.exists():
            status["hooks"] = [f.name for f in hooks_dir.glob("*.sh")]

        arch_dir = engine_path / "architecture"
        if arch_dir.exists():
            status["stacks"] = [d.name for d in arch_dir.iterdir() if d.is_dir()]

        return status

    @mcp.tool
    def get_supported_stacks() -> list[dict]:
        """List all supported technology stacks with their architecture documentation.
        Returns stack name and available doc files (overview, patterns, testing, etc.).
        Use when planning a new project to know what stacks the engine supports."""
        arch_dir = engine_path / "architecture"
        if not arch_dir.exists():
            return []

        stacks = []
        for stack_dir in sorted(arch_dir.iterdir()):
            if stack_dir.is_dir():
                docs = [f.name for f in stack_dir.glob("*.md")]
                stacks.append({
                    "stack": stack_dir.name,
                    "docs": docs,
                    "path": str(stack_dir),
                })
        return stacks
