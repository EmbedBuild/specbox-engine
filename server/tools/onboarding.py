"""Tools for onboarding and upgrading projects in the SpecBox Engine ecosystem.

v2.2: upgrade_project, upgrade_all_projects, get_version_matrix.
      Engine/MCP version tracking in meta.json and registry.json.

v2.0: onboard_project no longer requires a project path — it generates
file contents in the response for the user to copy. Project registration
goes to the central state registry (/data/state/registry.json).

detect_project_stack and get_onboarding_status remain for local (stdio) use.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastmcp import Context, FastMCP

from .. import __version__ as MCP_VERSION

logger = logging.getLogger(__name__)


# Stack detection rules: filename → stack name
_STACK_MARKERS: dict[str, str] = {
    "pubspec.yaml": "flutter",
    "package.json": "react",
    "go.mod": "go",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    ".clasp.json": "google-apps-script",
}

# Infra detection: keyword in dependency files → infra name
_INFRA_KEYWORDS: dict[str, str] = {
    "supabase": "supabase",
    "neon": "neon",
    "stripe": "stripe",
    "firebase": "firebase",
    "n8n": "n8n",
    "stitch": "stitch",
}

# Dependency files to scan for infra keywords
_DEP_FILES: list[str] = [
    "pubspec.yaml",
    "package.json",
    "go.mod",
    "pyproject.toml",
    "requirements.txt",
    ".clasp.json",
    ".env",
    ".env.example",
    "docker-compose.yml",
    "docker-compose.yaml",
]

# Default roles per stack
_STACK_ROLES: dict[str, list[str]] = {
    "flutter": ["lead-agent", "flutter-specialist", "qa-reviewer"],
    "react": ["lead-agent", "react-specialist", "qa-reviewer"],
    "go": ["lead-agent", "go-specialist", "qa-reviewer"],
    "python": ["lead-agent", "python-specialist", "qa-reviewer"],
    "google-apps-script": ["lead-agent", "gas-specialist", "qa-reviewer"],
}

# Quality directory structure
_QUALITY_DIRS: list[str] = [
    "baselines",
    "evidence",
    "logs",
    "scripts",
]


def _read_engine_version(engine_path: Path) -> str:
    """Read the engine version string from ENGINE_VERSION.yaml."""
    version_file = engine_path / "ENGINE_VERSION.yaml"
    if not version_file.exists():
        return "unknown"
    try:
        with open(version_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return str(data.get("version", "unknown"))
    except (yaml.YAMLError, OSError):
        return "unknown"


def _generate_onboarding_files(
    engine_path: Path,
    project: str,
    stack: str,
    infra_list: list[str],
    developer_name: str,
) -> tuple[dict[str, str], list[str], list[str]]:
    """Generate all onboarding file contents from engine templates.

    Returns (files_dict, quality_dirs, warnings).
    """
    roles = _STACK_ROLES.get(stack, _STACK_ROLES.get("python", []))
    template_vars = {
        "project_name": project,
        "stack": stack,
        "stacks": stack,
        "infra": ", ".join(infra_list) if infra_list else "none",
        "developer_name": developer_name,
    }

    files: dict[str, str] = {}
    warnings: list[str] = []
    templates_dir = engine_path / "templates"

    # CLAUDE.md
    template_file = templates_dir / "CLAUDE.md.template"
    if template_file.exists():
        files["CLAUDE.md"] = _render_template(template_file, template_vars)
    else:
        warnings.append("CLAUDE.md template not found — generate manually")

    # .claude/settings.json
    template_file = templates_dir / "settings.json.template"
    if template_file.exists():
        files[".claude/settings.json"] = _render_template(template_file, template_vars)
    else:
        warnings.append("settings.json template not found — generate manually")

    # team-config.json
    template_file = templates_dir / "team-config.json.template"
    if template_file.exists():
        files["team-config.json"] = _render_template(template_file, template_vars)
    else:
        team_config = {
            "project": project,
            "stack": stack,
            "roles": roles,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        files["team-config.json"] = json.dumps(team_config, indent=2, ensure_ascii=False)
        warnings.append("team-config.json generated from defaults (no template found)")

    # quality-baseline.json
    baseline_template = templates_dir / "quality-baseline.json.template"
    if baseline_template.exists():
        content = _render_template(baseline_template, template_vars)
        try:
            baseline = json.loads(content)
        except json.JSONDecodeError:
            baseline = _create_initial_baseline(project, stack)
    else:
        baseline = _create_initial_baseline(project, stack)
    files[f".quality/baselines/{project}.json"] = json.dumps(
        baseline, indent=2, ensure_ascii=False
    )

    quality_dirs = [f".quality/{d}/" for d in _QUALITY_DIRS]

    return files, quality_dirs, warnings


def _detect_stack(project_path: Path) -> dict:
    """Detect project stack by looking for marker files.

    Returns dict with stack, files_found, and architecture_pattern.
    """
    files_found: list[str] = []
    detected_stack = ""

    for marker, stack in _STACK_MARKERS.items():
        if (project_path / marker).exists():
            files_found.append(marker)
            if not detected_stack:
                detected_stack = stack

    # Determine architecture pattern
    pattern = "unknown"
    if detected_stack == "flutter":
        if (project_path / "lib" / "features").exists():
            pattern = "feature-first"
        elif (project_path / "lib" / "screens").exists():
            pattern = "screen-based"
        else:
            pattern = "default-flutter"
    elif detected_stack == "react":
        if (project_path / "src" / "app").exists():
            pattern = "next-app-router"
        elif (project_path / "src" / "pages").exists():
            pattern = "pages-router"
        elif (project_path / "src" / "components").exists():
            pattern = "component-based"
        else:
            pattern = "default-react"
    elif detected_stack == "python":
        if (project_path / "src").exists():
            pattern = "src-layout"
        elif (project_path / "app").exists():
            pattern = "app-layout"
        else:
            pattern = "flat-layout"
    elif detected_stack == "go":
        if (project_path / "cmd").exists() and (project_path / "internal").exists():
            pattern = "clean-architecture"
        elif (project_path / "cmd").exists():
            pattern = "cmd-structure"
        elif (project_path / "internal").exists():
            pattern = "internal-structure"
        else:
            pattern = "flat-layout"
    elif detected_stack == "google-apps-script":
        pattern = "clasp-project"

    return {
        "stack": detected_stack or "unknown",
        "files_found": files_found,
        "architecture_pattern": pattern,
    }


def _detect_infra(project_path: Path) -> list[str]:
    """Detect infrastructure services by scanning dependency files."""
    infra: set[str] = set()

    for dep_file in _DEP_FILES:
        dep_path = project_path / dep_file
        if dep_path.exists():
            try:
                content = dep_path.read_text(encoding="utf-8").lower()
                for keyword, service in _INFRA_KEYWORDS.items():
                    if keyword in content:
                        infra.add(service)
            except (OSError, UnicodeDecodeError):
                continue

    return sorted(infra)


def _render_template(template_path: Path, variables: dict[str, str]) -> str:
    """Render a template file by substituting {variable} placeholders."""
    if not template_path.exists():
        return ""

    content = template_path.read_text(encoding="utf-8")
    for key, value in variables.items():
        content = content.replace(f"{{{key}}}", value)
    return content


def _create_initial_baseline(project_name: str, stack: str) -> dict:
    """Create an initial quality-baseline.json with zeroed metrics."""
    return {
        "project": project_name,
        "stack": stack,
        "created": datetime.now(timezone.utc).isoformat(),
        "updated": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "lint_errors": 0,
            "lint_warnings": 0,
            "coverage_percent": 0.0,
            "tests_total": 0,
            "tests_passed": 0,
            "tests_failed": 0,
        },
        "policies": {
            "lint": "zero-tolerance",
            "coverage": "ratchet",
            "tests": "no-regression",
        },
    }


def register_onboarding_tools(
    mcp: FastMCP,
    engine_path: Path,
    state_path: Path | None = None,
):

    @mcp.tool
    def detect_project_stack(project_path: str) -> dict:
        """Detect the technology stack and infrastructure of a project without modifying anything.
        Args:
            project_path: Absolute path to the project root directory.
        Returns stack name, infra services found, marker files detected, and architecture pattern.
        Use when you need to understand a project's tech stack before onboarding or planning."""
        pp = Path(project_path)
        if not pp.exists():
            return {"error": f"Path does not exist: {project_path}"}
        if not pp.is_dir():
            return {"error": f"Path is not a directory: {project_path}"}

        stack_info = _detect_stack(pp)
        infra = _detect_infra(pp)

        return {
            "project_path": project_path,
            "project_name": pp.name,
            "stack": stack_info["stack"],
            "infra": infra,
            "files_found": stack_info["files_found"],
            "architecture_pattern": stack_info["architecture_pattern"],
        }

    @mcp.tool
    def get_onboarding_status(project_path: str) -> dict:
        """Check whether a project is already onboarded into the SpecBox Engine.
        Args:
            project_path: Absolute path to the project root directory.
        Returns which onboarding artifacts exist and which are missing.
        Use before running onboard_project to see what's already configured."""
        pp = Path(project_path)
        if not pp.exists():
            return {"error": f"Path does not exist: {project_path}"}

        checks = {
            "CLAUDE.md": (pp / "CLAUDE.md").exists(),
            ".claude/settings.json": (pp / ".claude" / "settings.json").exists(),
            "team-config.json": (pp / "team-config.json").exists(),
            ".quality/": (pp / ".quality").is_dir(),
            ".quality/baselines/": (pp / ".quality" / "baselines").is_dir(),
            ".quality/evidence/": (pp / ".quality" / "evidence").is_dir(),
            ".quality/logs/": (pp / ".quality" / "logs").is_dir(),
            ".quality/scripts/": (pp / ".quality" / "scripts").is_dir(),
        }

        present = [k for k, v in checks.items() if v]
        missing = [k for k, v in checks.items() if not v]

        # Check both registries: engine (legacy) and state (new)
        registered = False

        # Legacy engine registry
        engine_registry_file = engine_path / ".quality" / "registry.json"
        if engine_registry_file.exists():
            try:
                registry = json.loads(engine_registry_file.read_text(encoding="utf-8"))
                registered = any(
                    p.get("path") == project_path or p.get("name") == pp.name
                    for p in registry.get("projects", [])
                )
            except (json.JSONDecodeError, OSError):
                pass

        # State registry (new)
        if not registered and state_path:
            state_registry_file = state_path / "registry.json"
            if state_registry_file.exists():
                try:
                    registry = json.loads(state_registry_file.read_text(encoding="utf-8"))
                    registered = pp.name in registry.get("projects", {})
                except (json.JSONDecodeError, OSError):
                    pass

        fully_onboarded = len(missing) == 0 and registered

        return {
            "project_path": project_path,
            "project_name": pp.name,
            "fully_onboarded": fully_onboarded,
            "registered_in_engine": registered,
            "present": present,
            "missing": missing,
        }

    @mcp.tool
    def list_onboarded_projects() -> list[dict]:
        """List all projects registered in the SpecBox Engine ecosystem.
        Merges entries from the legacy engine registry and the central state registry.
        Returns project name, stack, infra, onboarding date, and status.
        Use to see which projects have been onboarded and their configuration."""
        projects: dict[str, dict] = {}

        # 1. Legacy engine registry (list format)
        engine_registry_file = engine_path / ".quality" / "registry.json"
        if engine_registry_file.exists():
            try:
                registry = json.loads(engine_registry_file.read_text(encoding="utf-8"))
                for p in registry.get("projects", []):
                    name = p.get("name", "")
                    if name:
                        pp = Path(p.get("path", ""))
                        projects[name] = {
                            "name": name,
                            "path": p.get("path", ""),
                            "stack": p.get("stack", "unknown"),
                            "infra": p.get("infra", []),
                            "roles": p.get("roles", []),
                            "onboarded_at": p.get("onboarded_at", ""),
                            "developer": p.get("developer", ""),
                            "source": "engine",
                            "path_exists": pp.exists() if p.get("path") else False,
                        }
            except (json.JSONDecodeError, OSError):
                pass

        # 2. State registry (dict format) — overrides engine entries
        if state_path:
            state_registry_file = state_path / "registry.json"
            if state_registry_file.exists():
                try:
                    registry = json.loads(state_registry_file.read_text(encoding="utf-8"))
                    for name, info in registry.get("projects", {}).items():
                        projects[name] = {
                            "name": name,
                            "stack": info.get("stack", "unknown"),
                            "infra": info.get("infra", []),
                            "repo_url": info.get("repo_url", ""),
                            "description": info.get("description", ""),
                            "registered_at": info.get("registered_at", ""),
                            "engine_version": info.get("engine_version", "unknown"),
                            "source": "state",
                        }
                except (json.JSONDecodeError, OSError):
                    pass

        return sorted(projects.values(), key=lambda p: p.get("name", ""))

    @mcp.tool
    async def onboard_project(
        project: str,
        stack: str = "",
        infra: str = "",
        repo_url: str = "",
        developer_name: str = "Jesús Pérez",
        trello_board_name: str = "",
        ctx: Context | None = None,
    ) -> dict:
        """Generate onboarding files for a new project and register it in the central index.

        Args:
            project: Project name (e.g. 'escandallo-app').
            stack: Technology stack (flutter, react, go, python, google-apps-script). Leave empty if unknown.
            infra: Comma-separated infra services (supabase, neon, stripe, etc.).
            repo_url: Git repository URL for reference.
            developer_name: Developer name for templates. Defaults to 'Jesús Pérez'.
            trello_board_name: Optional Trello board name. If provided, creates a SpecBox Engine board with workflow lists, custom fields, and labels via the Trello API.
            ctx: MCP context (injected automatically). Required when trello_board_name is provided.

        Returns the CONTENT of each file that should be created in the project repo
        (CLAUDE.md, settings.json, team-config.json, quality-baseline.json).
        The user copies these files to their local project.
        Also registers the project in the central state registry.
        If trello_board_name is given, includes the board_id in the generated settings.

        Use to onboard a new project into the SpecBox Engine ecosystem with quality gates and agent teams."""
        detected_stack = stack or "unknown"
        infra_list = [s.strip() for s in infra.split(",") if s.strip()] if infra else []
        roles = _STACK_ROLES.get(detected_stack, _STACK_ROLES.get("python", []))

        # Generate files from templates
        files, quality_dirs, warnings = _generate_onboarding_files(
            engine_path, project, detected_stack, infra_list, developer_name,
        )

        # Trello board setup (optional)
        board_id = ""
        board_url = ""
        if trello_board_name:
            if ctx is None:
                warnings.append(
                    "trello_board_name provided but no MCP context available — "
                    "board not created. Call setup_board separately."
                )
            else:
                try:
                    from .spec_driven import setup_board

                    board_result = await setup_board(trello_board_name, ctx)
                    if "error" in board_result:
                        warnings.append(f"Trello board creation failed: {board_result['error']}")
                    else:
                        board_id = board_result.get("board_id", "")
                        board_url = board_result.get("board_url", "")
                        logger.info(
                            "trello_board_created_during_onboarding",
                            project=project,
                            board_id=board_id,
                        )
                except Exception as e:
                    warnings.append(f"Trello board creation failed: {e}")

        # Inject board_id into settings if we got one
        if board_id and ".claude/settings.json" in files:
            try:
                settings = json.loads(files[".claude/settings.json"])
                settings.setdefault("trello", {})["board_id"] = board_id
                if board_url:
                    settings["trello"]["board_url"] = board_url
                files[".claude/settings.json"] = json.dumps(
                    settings, indent=2, ensure_ascii=False
                )
            except json.JSONDecodeError:
                warnings.append(
                    "Could not inject board_id into settings.json — "
                    f"add trello.board_id = {board_id!r} manually"
                )

        # Register in state registry
        registered = False
        current_engine_version = _read_engine_version(engine_path)
        if state_path:
            try:
                from .state import (
                    _ensure_project_dir,
                    _read_registry,
                    _write_registry,
                    _write_meta,
                    _invalidate_cache,
                )

                _ensure_project_dir(state_path, project)
                registry = _read_registry(state_path)
                registry_entry: dict = {
                    "stack": detected_stack,
                    "infra": infra_list,
                    "repo_url": repo_url,
                    "description": "",
                    "registered_at": datetime.now(timezone.utc).isoformat(),
                    "engine_version": current_engine_version,
                }
                if board_id:
                    registry_entry["trello_board_id"] = board_id
                registry.setdefault("projects", {})[project] = registry_entry
                _write_registry(state_path, registry)

                project_dir = state_path / "projects" / project
                meta: dict = {
                    "stack": detected_stack,
                    "infra": infra_list,
                    "repo_url": repo_url,
                    "registered_at": registry["projects"][project]["registered_at"],
                    "onboarded_by": developer_name,
                    "engine_version": current_engine_version,
                    "mcp_version": MCP_VERSION,
                }
                if board_id:
                    meta["trello_board_id"] = board_id
                _write_meta(project_dir, meta)
                _invalidate_cache(state_path)
                registered = True
            except Exception as e:
                warnings.append(f"State registration failed: {e}")

        result = {
            "project": project,
            "stack": detected_stack,
            "infra": infra_list,
            "roles": roles,
            "files": files,
            "quality_dirs_to_create": quality_dirs,
            "engine_version": current_engine_version,
            "mcp_version": MCP_VERSION,
            "registered_in_state": registered,
            "warnings": warnings if warnings else None,
            "instructions": (
                "Copy the files above to your project repo. "
                "Create the .quality/ directories listed in quality_dirs_to_create. "
                "The project has been registered in the central state index."
            ),
        }
        if board_id:
            result["trello_board_id"] = board_id
            result["trello_board_url"] = board_url
        return result

    @mcp.tool
    def upgrade_project(project: str) -> dict:
        """Regenerate onboarding files for an existing project using current engine templates.

        Args:
            project: Project name (must be already registered).

        Reads existing meta (stack, infra, repo_url, developer_name) from
        the state registry, then regenerates all onboarding files (CLAUDE.md,
        settings.json, team-config.json, quality-baseline.json) with the
        current engine templates. Records the engine and MCP version used.
        Does NOT re-register the project.

        Use when the engine has been updated with new templates and you need
        to refresh a project's configuration files."""
        if not state_path:
            return {"error": "State path not configured — cannot upgrade."}

        from .state import (
            _read_registry,
            _read_meta,
            _write_meta,
            _write_registry,
            _invalidate_cache,
            _available_projects,
        )

        registry = _read_registry(state_path)
        if project not in registry.get("projects", {}):
            return {
                "error": f"Project '{project}' not registered.",
                "available": _available_projects(state_path),
            }

        # Read existing meta to preserve project config
        project_dir = state_path / "projects" / project
        meta = _read_meta(project_dir)
        proj_info = registry["projects"][project]
        detected_stack = meta.get("stack", proj_info.get("stack", "unknown"))
        infra_list = meta.get("infra", proj_info.get("infra", []))
        repo_url = meta.get("repo_url", proj_info.get("repo_url", ""))
        developer_name = meta.get("onboarded_by", "Jesús Pérez")
        roles = _STACK_ROLES.get(detected_stack, _STACK_ROLES.get("python", []))

        # Regenerate files from current templates
        files, quality_dirs, warnings = _generate_onboarding_files(
            engine_path, project, detected_stack, infra_list, developer_name,
        )

        # Record version info (do NOT re-register)
        current_engine_version = _read_engine_version(engine_path)
        now = datetime.now(timezone.utc).isoformat()

        meta["engine_version"] = current_engine_version
        meta["mcp_version"] = MCP_VERSION
        meta["last_upgraded_at"] = now
        _write_meta(project_dir, meta)

        # Update engine_version in registry
        registry["projects"][project]["engine_version"] = current_engine_version
        _write_registry(state_path, registry)
        _invalidate_cache(state_path)

        # E2E gap detection hint
        e2e_alignment = {
            "action": "run get_e2e_gap_report with the project path to detect E2E gaps",
            "reason": (
                "v5.12.0+ requires HTML Evidence Reports for all stacks. "
                "UCs in Review/Done without E2E evidence need backfill."
            ),
            "tool": "get_e2e_gap_report",
            "args": {"project_path": "<project repo path>", "project": project},
        }

        # Visual identity alignment hint
        visual_alignment = {
            "action": "run get_visual_gap_report with the project path to detect visual identity gaps",
            "reason": (
                "v5.14.0+ supports /visual-setup for brand kit + Stitch Design System + VEG base. "
                "Projects using Stitch without a brand kit get inconsistent designs."
            ),
            "tool": "get_visual_gap_report",
            "args": {"project_path": "<project repo path>"},
        }

        return {
            "project": project,
            "stack": detected_stack,
            "infra": infra_list,
            "roles": roles,
            "files": files,
            "quality_dirs_to_create": quality_dirs,
            "engine_version": current_engine_version,
            "mcp_version": MCP_VERSION,
            "upgraded_at": now,
            "warnings": warnings if warnings else None,
            "e2e_alignment": e2e_alignment,
            "visual_alignment": visual_alignment,
            "instructions": (
                "Copy the files above to your project repo, replacing the existing ones. "
                "Then run get_e2e_gap_report and get_visual_gap_report on the project to detect "
                "E2E evidence gaps and visual identity gaps respectively."
            ),
        }

    @mcp.tool
    def upgrade_all_projects() -> dict:
        """Upgrade all registered projects to the current engine templates in one call.

        Regenerates onboarding files for every project in the central registry
        using current engine templates. Records engine and MCP version for each.
        Returns per-project results so the user can copy files for each project.

        Use when the engine has been updated and you want to refresh ALL projects at once."""
        if not state_path:
            return {"error": "State path not configured — cannot upgrade."}

        from .state import _read_registry

        registry = _read_registry(state_path)
        project_names = sorted(registry.get("projects", {}).keys())

        if not project_names:
            return {"error": "No projects registered.", "projects": []}

        results: list[dict] = []
        succeeded = 0
        failed = 0

        for proj in project_names:
            result = upgrade_project(proj)
            if "error" in result:
                failed += 1
            else:
                succeeded += 1
            results.append(result)

        return {
            "total": len(project_names),
            "succeeded": succeeded,
            "failed": failed,
            "engine_version": _read_engine_version(engine_path),
            "mcp_version": MCP_VERSION,
            "results": results,
        }

    @mcp.tool
    def get_version_matrix() -> dict:
        """Show all projects vs current engine version to identify which need upgrading.

        Returns a matrix of project name, current engine_version, current mcp_version,
        last_upgraded_at, and whether the project needs an upgrade (its recorded version
        differs from the running engine version).

        Use to quickly see which projects are outdated and need upgrade_project."""
        if not state_path:
            return {"error": "State path not configured."}

        from .state import _read_registry, _read_meta

        registry = _read_registry(state_path)
        current_engine = _read_engine_version(engine_path)
        current_mcp = MCP_VERSION

        projects: list[dict] = []
        needs_upgrade_count = 0

        for proj_name in sorted(registry.get("projects", {}).keys()):
            project_dir = state_path / "projects" / proj_name
            meta = _read_meta(project_dir)

            proj_engine = meta.get("engine_version", "unknown")
            proj_mcp = meta.get("mcp_version", "unknown")
            needs_upgrade = proj_engine != current_engine or proj_mcp != current_mcp

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

        return {
            "current_engine_version": current_engine,
            "current_mcp_version": current_mcp,
            "total_projects": len(projects),
            "needs_upgrade": needs_upgrade_count,
            "up_to_date": len(projects) - needs_upgrade_count,
            "projects": projects,
            "e2e_gap_hint": (
                "After upgrading, run get_e2e_gap_report on each project to detect "
                "UCs without E2E evidence and generate a backfill testing plan. "
                "v5.12.0+ requires HTML Evidence Reports for all active stacks."
            ),
            "visual_gap_hint": (
                "After upgrading, run get_visual_gap_report on each project to detect "
                "missing brand kit, Stitch Design System, or VEG base configuration. "
                "v5.14.0+ supports /visual-setup for consistent design identity."
            ),
        }

    @mcp.tool
    def get_onboarding_wizard() -> dict:
        """Get the interactive onboarding wizard questions when onboard_project is called without params.

        Returns a structured list of questions, each with an explanation, field name,
        type, and default value. The client/skill uses these to guide the user through
        onboarding step by step.

        When the user provides all params directly to onboard_project, this wizard
        is skipped (retrocompatibility). If the user answers "no" to all optional
        questions, a minimal config is generated.

        Use when starting onboard_project without knowing the project details upfront."""
        return {
            "wizard": True,
            "title": "Wizard de Onboarding — SpecBox Engine",
            "description": (
                "Vamos a configurar tu proyecto paso a paso. "
                "Cada pregunta incluye una explicacion de para que sirve."
            ),
            "questions": [
                {
                    "field": "project",
                    "question": "Nombre del proyecto (ej: 'mi-app', 'escandallo-app')",
                    "explanation": "Identificador unico del proyecto en el Engine. Se usa para registry, baselines y evidencia.",
                    "type": "string",
                    "required": True,
                    "default": "",
                },
                {
                    "field": "stack",
                    "question": "Stack tecnologico (flutter, react, go, python, google-apps-script)",
                    "explanation": "Define que patrones de arquitectura, agentes especializados y quality gates se aplican.",
                    "type": "choice",
                    "required": False,
                    "options": ["flutter", "react", "go", "python", "google-apps-script"],
                    "default": "unknown",
                },
                {
                    "field": "infra",
                    "question": "Servicios de infraestructura (supabase, neon, stripe, firebase, n8n) separados por coma",
                    "explanation": "Habilita patrones especificos de infra y configura integraciones en el CLAUDE.md generado.",
                    "type": "string",
                    "required": False,
                    "default": "",
                },
                {
                    "field": "repo_url",
                    "question": "URL del repositorio Git (ej: https://github.com/user/repo)",
                    "explanation": "Se registra como referencia. Usado por /implement para crear PRs y por el dashboard.",
                    "type": "string",
                    "required": False,
                    "default": "",
                },
                {
                    "field": "developer_name",
                    "question": "Nombre del desarrollador principal",
                    "explanation": "Se incluye en templates y evidencia generada. Identifica quien onboardeo el proyecto.",
                    "type": "string",
                    "required": False,
                    "default": "Jesus Perez",
                },
                {
                    "field": "trello_board_name",
                    "question": "Nombre del board Trello/Plane (dejar vacio si no usas spec-driven)",
                    "explanation": "Si se proporciona, crea un board con listas de workflow (Backlog, In Progress, Done, etc.) y custom fields.",
                    "type": "string",
                    "required": False,
                    "default": "",
                },
            ],
            "minimal_config_note": (
                "Si no sabes las respuestas, puedes dejar todo en blanco excepto el nombre. "
                "Se generara una config minima que puedes enriquecer despues con upgrade_project."
            ),
        }

    @mcp.tool
    def get_visual_gap_report(project_path: str) -> dict:
        """Scan a project for missing visual identity artifacts and report gaps.

        Args:
            project_path: Absolute path to the project repository root.

        Checks for:
        - Brand Kit (doc/brand/brand_kit/SKILL.md, variables.css, tailwind.config.js, light.md, dark.md)
        - Stitch config (stitch.projectId, stitch.designSystemAssetId in settings.local.json)
        - VEG base (doc/veg/base/*.md)
        - Prompt template (doc/design/stitch-prompt-template.md)
        - Multi-form-factor config (stitch.multiFormFactor in settings.local.json)

        Returns a structured report with coverage percentage, missing artifacts,
        and recommended actions. Projects not using Stitch at all get a clean skip.

        Use after upgrade_project to detect which projects need /visual-setup,
        or before /plan to verify visual identity is configured."""
        import json as json_mod
        from pathlib import Path as P

        repo = P(project_path)
        if not repo.is_dir():
            return {"error": f"Directory not found: {project_path}"}

        # --- Detect if project uses Stitch at all ---
        settings_path = repo / ".claude" / "settings.local.json"
        settings: dict = {}
        if settings_path.exists():
            try:
                settings = json_mod.loads(settings_path.read_text())
            except Exception:
                pass

        stitch_cfg = settings.get("stitch", {})
        has_any_stitch = bool(stitch_cfg.get("projectId"))

        # Check for any design HTML files (even without settings)
        design_dir = repo / "doc" / "design"
        has_design_htmls = False
        if design_dir.is_dir():
            has_design_htmls = any(design_dir.rglob("*.html"))

        uses_stitch = has_any_stitch or has_design_htmls

        # --- Check each artifact ---
        brand_kit_dir = repo / "doc" / "brand" / "brand_kit"
        artifacts = {
            "brand_kit_skill": {
                "path": "doc/brand/brand_kit/SKILL.md",
                "exists": (brand_kit_dir / "SKILL.md").is_file(),
                "category": "brand_kit",
                "description": "Brand summary for sub-agents (~600 tokens)",
            },
            "brand_kit_variables": {
                "path": "doc/brand/brand_kit/variables.css",
                "exists": (brand_kit_dir / "variables.css").is_file(),
                "category": "brand_kit",
                "description": "CSS custom properties (light + dark tokens)",
            },
            "brand_kit_tailwind": {
                "path": "doc/brand/brand_kit/tailwind.config.js",
                "exists": (brand_kit_dir / "tailwind.config.js").is_file(),
                "category": "brand_kit",
                "description": "Tailwind config using CSS variables",
            },
            "brand_kit_light": {
                "path": "doc/brand/brand_kit/light.md",
                "exists": (brand_kit_dir / "light.md").is_file(),
                "category": "brand_kit",
                "description": "Light theme specifications",
            },
            "brand_kit_dark": {
                "path": "doc/brand/brand_kit/dark.md",
                "exists": (brand_kit_dir / "dark.md").is_file(),
                "category": "brand_kit",
                "description": "Dark theme specifications",
            },
            "stitch_project_id": {
                "path": ".claude/settings.local.json → stitch.projectId",
                "exists": bool(stitch_cfg.get("projectId")),
                "category": "stitch",
                "description": "Stitch project created and configured",
            },
            "stitch_design_system": {
                "path": ".claude/settings.local.json → stitch.designSystemAssetId",
                "exists": bool(stitch_cfg.get("designSystemAssetId")),
                "category": "stitch",
                "description": "Stitch Design System with brand tokens applied",
            },
            "veg_base": {
                "path": "doc/veg/base/*.md",
                "exists": any((repo / "doc" / "veg" / "base").rglob("*.md"))
                if (repo / "doc" / "veg" / "base").is_dir()
                else False,
                "category": "veg",
                "description": "VEG base with visual directives for all features",
            },
            "prompt_template": {
                "path": "doc/design/stitch-prompt-template.md",
                "exists": (repo / "doc" / "design" / "stitch-prompt-template.md").is_file(),
                "category": "prompt",
                "description": "Reusable prompt structure for Stitch generation",
            },
            "multi_form_factor": {
                "path": ".claude/settings.local.json → stitch.multiFormFactor",
                "exists": bool(stitch_cfg.get("multiFormFactor")),
                "category": "config",
                "description": "Multi-form-factor enabled (DESKTOP + TABLET + MOBILE)",
            },
        }

        total = len(artifacts)
        present = sum(1 for a in artifacts.values() if a["exists"])
        missing = [
            {"artifact": k, "path": v["path"], "description": v["description"]}
            for k, v in artifacts.items()
            if not v["exists"]
        ]

        coverage_pct = round((present / total) * 100) if total > 0 else 0

        # --- Category summaries ---
        categories = {}
        for a in artifacts.values():
            cat = a["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "present": 0}
            categories[cat]["total"] += 1
            if a["exists"]:
                categories[cat]["present"] += 1

        # --- Determine status ---
        if coverage_pct == 100:
            status = "complete"
            action = "No action needed — visual identity is fully configured."
        elif coverage_pct == 0 and not uses_stitch:
            status = "not_applicable"
            action = (
                "Project does not use Stitch. Run /visual-setup if you want to "
                "add design system capabilities."
            )
        elif coverage_pct == 0 and uses_stitch:
            status = "missing"
            action = (
                "Project uses Stitch but has NO visual identity configured. "
                "Run /visual-setup to create brand kit, Design System, VEG base, "
                "and prompt template from scratch."
            )
        else:
            status = "partial"
            missing_cats = [
                cat for cat, info in categories.items()
                if info["present"] < info["total"]
            ]
            action = (
                f"Visual identity partially configured ({coverage_pct}%). "
                f"Missing in: {', '.join(missing_cats)}. "
                "Run /visual-setup — it will detect existing artifacts and complete "
                "only what's missing."
            )

        # --- Human-friendly summary ---
        summary_lines = [
            f"Visual Identity: {coverage_pct}% ({present}/{total} artifacts)",
            f"Status: {status.upper()}",
        ]
        if uses_stitch:
            summary_lines.append(f"Stitch: {'configured' if has_any_stitch else 'HTML designs found but no project config'}")
        if missing:
            summary_lines.append(f"Missing: {', '.join(m['artifact'] for m in missing[:5])}")
            if len(missing) > 5:
                summary_lines.append(f"  ...and {len(missing) - 5} more")
        summary_lines.append(f"Action: {action}")

        return {
            "project_path": project_path,
            "uses_stitch": uses_stitch,
            "status": status,
            "coverage": {
                "total": total,
                "present": present,
                "missing_count": len(missing),
                "coverage_pct": coverage_pct,
            },
            "categories": {
                cat: f"{info['present']}/{info['total']}"
                for cat, info in categories.items()
            },
            "artifacts": {
                k: {"exists": v["exists"], "path": v["path"]}
                for k, v in artifacts.items()
            },
            "missing": missing if missing else None,
            "action": action,
            "summary": "\n".join(summary_lines),
        }

    @mcp.tool
    def archive_project(project: str) -> dict:
        """Archive a project by setting its status to 'archived' in the state registry.

        Args:
            project: Project name (must be already registered).

        Reads the project meta, sets status to 'archived' and records
        the archived_at timestamp. The project remains in the registry
        but is marked as inactive.

        Use when a project is no longer actively developed and should
        be excluded from upgrade sweeps and dashboards."""
        if not state_path:
            return {"error": "State path not configured — cannot archive."}

        from .state import (
            _read_registry,
            _write_registry,
            _read_meta,
            _write_meta,
            _invalidate_cache,
            _available_projects,
        )

        registry = _read_registry(state_path)
        if project not in registry.get("projects", {}):
            return {
                "error": f"Project '{project}' not registered.",
                "available": _available_projects(state_path),
            }

        now = datetime.now(timezone.utc).isoformat()

        # Update project meta
        project_dir = state_path / "projects" / project
        meta = _read_meta(project_dir)
        meta["status"] = "archived"
        meta["archived_at"] = now
        _write_meta(project_dir, meta)

        # Update registry entry
        registry["projects"][project]["status"] = "archived"
        registry["projects"][project]["archived_at"] = now
        _write_registry(state_path, registry)
        _invalidate_cache(state_path)

        logger.info("project_archived", project=project, archived_at=now)

        return {
            "project": project,
            "status": "archived",
        }
