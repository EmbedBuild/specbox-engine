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


def _collect_canonical_doc_templates(
    engine_path: Path,
    engine_version_at_onboard: str | None,
    project: str,
    now_iso: str,
) -> tuple[list[dict[str, str]], list[str]]:
    """Build the list of canonical doc plantillas to offer for creation.

    v6.0 (UC-D005 AC-10): for each CanonicalDoc with
    `introduced_in > engine_version_at_onboard`, the caller offers a
    plantilla pristine that the project may copy. Returns:

        (canonical_docs, warnings)

    where each `canonical_docs` entry is:
        {
          "id": "app_market",
          "path": "doc/app/app_market.md",
          "content": "<rendered template>",
          "reason": "introduced_in_6.0.0",
          "template_path": "templates/app_market.md.template",
        }

    The caller is responsible for NOT overwriting existing files in the
    project repo. The invariant "upgrade_project never overwrites existing
    content" is preserved — this function only OFFERS content to create.

    When `engine_version_at_onboard` is None ("unknown"), no docs are
    offered: the conservative policy assumes the project was onboarded
    pre-v6.0 and the user must explicitly bump the field to receive new
    canonical docs.
    """
    from server.app_docs.registry import CANONICAL_DOCS, _semver_tuple

    if engine_version_at_onboard is None or engine_version_at_onboard == "unknown":
        # Conservative: don't push new docs on a project whose onboard
        # version we can't determine. The user can bump the field via
        # /app-init --refresh to opt in later.
        return ([], [])

    project_v = _semver_tuple(engine_version_at_onboard)
    out: list[dict[str, str]] = []
    warnings: list[str] = []

    for doc in CANONICAL_DOCS:
        if _semver_tuple(doc.introduced_in) <= project_v:
            continue  # doc already existed at onboard time — skip
        template_file = engine_path / doc.template_path
        if not template_file.exists():
            warnings.append(
                f"canonical doc {doc.id!r} template missing: {doc.template_path} — "
                "skipping. Add the template to the engine repo."
            )
            continue
        try:
            content = template_file.read_text(encoding="utf-8")
        except OSError as e:
            warnings.append(f"canonical doc {doc.id!r} template unreadable: {e}")
            continue
        # Render minimal placeholders (project_name + date_iso). Other
        # zones stay as template-pristine until /discovery fills them.
        rendered = content.replace("{project_name}", project).replace(
            "{date_iso}", now_iso
        )
        out.append(
            {
                "id": doc.id,
                "path": doc.path,
                "content": rendered,
                "reason": f"introduced_in_{doc.introduced_in}",
                "template_path": doc.template_path,
            }
        )

    return (out, warnings)


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
    engine_version = _read_engine_version(engine_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    infra_joined = ", ".join(infra_list) if infra_list else "none"
    primary_service = infra_list[0] if infra_list else "none"

    # Placeholder map for _render_template. Keys are matched case-sensitively
    # against {KEY} tokens in the template files under templates/.
    # All placeholders that appear in any template MUST have an entry here —
    # otherwise the raw {TOKEN} leaks into the generated file.
    template_vars: dict[str, str] = {
        # Identity / metadata
        "PROJECT_NAME": project,
        "STACK": stack,
        "INFRA": infra_joined,
        "DEVELOPER_NAME": developer_name,
        "ENGINE_VERSION": engine_version,
        "DATE": now_iso,
        "ISO_TIMESTAMP": now_iso,

        # CLAUDE.md descriptive placeholders (neutral defaults — user edits later)
        "VERSION": "",
        "BACKEND": primary_service,
        "DATABASE": "",
        "ARCHITECTURE_DESCRIPTION": (
            f"Patrones estandar para stack {stack}. "
            "Editar esta seccion con la arquitectura especifica del proyecto."
        ),
        "PROJECT_SPECIFIC_RULE_1": "TODO: regla especifica del proyecto",
        "PROJECT_SPECIFIC_RULE_2": "TODO: regla especifica del proyecto",
        "UI_STYLE": "TBD",
        "UI_STYLE_ID": "TBD",
        "SERVICE_1": primary_service,
        "PROJECT_ID": "TBD",
        "STITCH_PROJECT_ID": "TBD",
        "PLANE_PROJECT": "TBD",
        "PLANE_PROJECT_ID": "TBD",
        "USER_ID": "TBD",
        "STACK_HOOKS": f"(hooks estandar para {stack})",

        # quality-baseline.json numeric/string defaults.
        # The template was updated so numeric placeholders have NO surrounding
        # quotes — substituting with "0" keeps the JSON syntactically valid.
        "LINT_COMMAND": "",
        "COVERAGE_PERCENT": "0",
        "COVERAGE_COMMAND": "",
        "TOTAL_TESTS": "0",
        "PASSING_TESTS": "0",
        "TEST_COMMAND": "",
        "VIOLATIONS_COUNT": "0",
        "DEAD_CODE_COUNT": "0",
        "OUTDATED_COUNT": "0",
        "E2E_COMMAND": "",
    }

    files: dict[str, str] = {}
    warnings: list[str] = []
    templates_dir = engine_path / "templates"

    def _render_and_track(rel_label: str, path: Path) -> str:
        """Render a template and append a warning for any unresolved placeholder."""
        rendered, unresolved = _render_template(path, template_vars)
        if unresolved:
            warnings.append(
                f"{rel_label}: unresolved placeholders {unresolved} — "
                "add defaults in _generate_onboarding_files.template_vars"
            )
        return rendered

    # CLAUDE.md
    template_file = templates_dir / "CLAUDE.md.template"
    if template_file.exists():
        files["CLAUDE.md"] = _render_and_track("CLAUDE.md", template_file)
    else:
        warnings.append("CLAUDE.md template not found — generate manually")

    # .claude/settings.json
    template_file = templates_dir / "settings.json.template"
    if template_file.exists():
        files[".claude/settings.json"] = _render_and_track(
            ".claude/settings.json", template_file,
        )
    else:
        warnings.append("settings.json template not found — generate manually")

    # team-config.json
    template_file = templates_dir / "team-config.json.template"
    if template_file.exists():
        files["team-config.json"] = _render_and_track(
            "team-config.json", template_file,
        )
    else:
        team_config = {
            "project": project,
            "stack": stack,
            "roles": roles,
            "created": now_iso,
        }
        files["team-config.json"] = json.dumps(team_config, indent=2, ensure_ascii=False)
        warnings.append("team-config.json generated from defaults (no template found)")

    # quality-baseline.json
    baseline_template = templates_dir / "quality-baseline.json.template"
    if baseline_template.exists():
        content = _render_and_track(
            f".quality/baselines/{project}.json", baseline_template,
        )
        try:
            baseline = json.loads(content)
        except json.JSONDecodeError as exc:
            warnings.append(
                f".quality/baselines/{project}.json: template JSON invalid after "
                f"render ({exc}) — falling back to _create_initial_baseline"
            )
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


import re as _re

# Matches UPPERCASE placeholder tokens like {PROJECT_NAME}, {ENGINE_VERSION}.
# Requires a non-$ preceding char (or start-of-string) to skip shell-style
# ${VAR} substitutions that also contain {VAR}. Tokens must start with an
# uppercase letter and contain only uppercase letters, digits, and underscores.
_PLACEHOLDER_RE = _re.compile(r"(?<!\$)\{([A-Z][A-Z0-9_]*)\}")


def _render_template(
    template_path: Path,
    variables: dict[str, str],
) -> tuple[str, list[str]]:
    """Render a template by substituting {KEY} placeholders.

    Returns (rendered_content, unresolved_placeholders).

    Matching is case-sensitive and only UPPERCASE tokens are considered.
    Lowercase braces like {feature} or {stack} inside example paths are
    left untouched (they are documentation, not placeholders). Shell-style
    ${VAR} substitutions are also preserved.

    If any UPPERCASE placeholder remains unresolved after substitution, it
    is reported in the second return value so callers can surface a warning
    instead of silently leaking raw tokens into generated files.
    """
    if not template_path.exists():
        return "", []

    content = template_path.read_text(encoding="utf-8")
    for key, value in variables.items():
        content = content.replace(f"{{{key}}}", value)

    unresolved = sorted({m.group(1) for m in _PLACEHOLDER_RE.finditer(content)})
    return content, unresolved


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


# v6.3.0 — canonical defaults exposed as module-level constants so tests
# and other modules can reference them without entering the closure of
# register_onboarding_tools.
DEFAULT_BACKEND_TYPE = "native"
VALID_BACKEND_TYPES = frozenset({"freeform", "trello", "plane", "native"})


def resolve_default_backend_type(
    backend_type: str | None,
    trello_board_name: str | None,
) -> str:
    """Pick the backend_type for onboard_project when the caller is implicit.

    Order:
      1. If the caller passed an explicit backend_type, return it verbatim.
      2. Else, if trello_board_name is set, infer "trello" (back-compat with
         pre-v5.29 onboards that only knew the Trello path).
      3. Else, return DEFAULT_BACKEND_TYPE ("native" since v6.3.0,
         "freeform" before v6.3.0).

    The caller is responsible for validating the result against
    VALID_BACKEND_TYPES before relying on it.
    """
    if backend_type:
        return backend_type
    if trello_board_name:
        return "trello"
    return DEFAULT_BACKEND_TYPE


def register_onboarding_tools(
    mcp: FastMCP,
    engine_path: Path,
    state_path: Path | None = None,
):

    @mcp.tool
    def detect_local_root_path() -> dict:
        """Declare the FreeForm path-resolution contract for the calling client.

        Returns the rules a Claude Code client must follow when configuring a
        FreeForm tracking backend. Because the MCP server may run remotely
        (on a VPS), it cannot observe the client's working directory: any
        relative path the client sends would be resolved against the server's
        own CWD and the tracking folder would land on the wrong filesystem.

        The contract surfaced here is the single source of truth used by:
          - the /app-init skill (Paso 1.5),
          - the freeform-path-guard PreToolUse hook (auto-rewrites relative
            paths to absolute via `git rev-parse --show-toplevel`),
          - the server-side FreeformBackend guard
            (rejects relative paths when SPECBOX_ENGINE_MCP_URL is set).

        Use this as a read-only handshake before calling set_auth_token or
        onboard_project with backend_type='freeform'. The tool does not
        write anywhere; it only reports the rules the caller must obey.

        Returns:
            dict with:
              is_remote_mcp: bool — whether SPECBOX_ENGINE_MCP_URL is set
                on the SERVER process. Note: the client must check the same
                env var on its own side; the two values can differ.
              requires_absolute_path: bool — always True when the server
                is remote. True is the safest default and is what the
                client should assume.
              default_relative_path: str — the conventional relative path
                ("doc/tracking") that should be resolved against the
                client's git toplevel.
              client_resolution_recipe: str — exact shell command the
                client should run to compute the absolute path.
              hook_helper: str — path to the JS helper that already
                implements this logic for Claude Code clients.
        """
        import os

        return {
            "is_remote_mcp": bool(os.environ.get("SPECBOX_ENGINE_MCP_URL", "").strip()),
            "requires_absolute_path": True,
            "default_relative_path": "doc/tracking",
            "client_resolution_recipe": (
                'ABS_TRACKING="$(git rev-parse --show-toplevel)/doc/tracking"'
            ),
            "hook_helper": ".claude/hooks/lib/freeform-path.mjs",
            "summary": (
                "FreeForm tracking paths must be absolute on the client "
                "filesystem. Resolve 'doc/tracking' against `git rev-parse "
                "--show-toplevel` before calling set_auth_token or "
                "onboard_project. The freeform-path-guard hook does this "
                "automatically when invoked from Claude Code."
            ),
        }

    @mcp.tool
    def detect_project_stack(
        project_name: str = "",
        marker_files_present: list[str] | None = None,
        dep_files: dict[str, str] | None = None,
        feature_dirs_present: list[str] | None = None,
    ) -> dict:
        """Detect the technology stack and infrastructure of a project.

        **v6.0.1 — content-passing API**

        Does no filesystem I/O. The caller (skill or hook) is expected to
        scan the local repo and pass:

        * ``marker_files_present`` — sorted list of marker files that exist
          at the repo root (subset of ``["pubspec.yaml", "package.json",
          "go.mod", "pyproject.toml", "requirements.txt", ".clasp.json"]``).
        * ``dep_files`` — mapping of dependency-file name (e.g. ``"package.json"``,
          ``"pubspec.yaml"``) to the file's UTF-8 content. Used to detect
          infra services. Pass ``{}`` if none exist.
        * ``feature_dirs_present`` — sorted list of architectural marker
          directories that exist (subset of ``["lib/features", "lib/screens",
          "src/app", "src/pages", "src/components", "src", "app", "cmd",
          "internal"]``). Used to determine architecture pattern.
        * ``project_name`` — optional; if omitted, returned ``project_name``
          is empty.

        Returns stack name, infra services found, marker files detected, and
        architecture pattern.
        """
        markers = list(marker_files_present or [])
        deps = dict(dep_files or {})
        feature_dirs = set(feature_dirs_present or [])

        files_found: list[str] = []
        detected_stack = ""
        for marker, stack in _STACK_MARKERS.items():
            if marker in markers:
                files_found.append(marker)
                if not detected_stack:
                    detected_stack = stack

        pattern = "unknown"
        if detected_stack == "flutter":
            if "lib/features" in feature_dirs:
                pattern = "feature-first"
            elif "lib/screens" in feature_dirs:
                pattern = "screen-based"
            else:
                pattern = "default-flutter"
        elif detected_stack == "react":
            if "src/app" in feature_dirs:
                pattern = "next-app-router"
            elif "src/pages" in feature_dirs:
                pattern = "pages-router"
            elif "src/components" in feature_dirs:
                pattern = "component-based"
            else:
                pattern = "default-react"
        elif detected_stack == "python":
            if "src" in feature_dirs:
                pattern = "src-layout"
            elif "app" in feature_dirs:
                pattern = "app-layout"
            else:
                pattern = "flat-layout"
        elif detected_stack == "go":
            if "cmd" in feature_dirs and "internal" in feature_dirs:
                pattern = "clean-architecture"
            elif "cmd" in feature_dirs:
                pattern = "cmd-structure"
            elif "internal" in feature_dirs:
                pattern = "internal-structure"
            else:
                pattern = "flat-layout"
        elif detected_stack == "google-apps-script":
            pattern = "clasp-project"

        infra: set[str] = set()
        for _name, content in deps.items():
            if not isinstance(content, str):
                continue
            haystack = content.lower()
            for keyword, service in _INFRA_KEYWORDS.items():
                if keyword in haystack:
                    infra.add(service)

        return {
            "project_name": project_name,
            "stack": detected_stack or "unknown",
            "infra": sorted(infra),
            "files_found": files_found,
            "architecture_pattern": pattern,
        }

    @mcp.tool
    def get_onboarding_status(
        project_name: str,
        artifact_presence: dict[str, bool] | None = None,
    ) -> dict:
        """Check whether a project is already onboarded into the SpecBox Engine.

        **v6.0.1 — content-passing API**

        Does no client filesystem I/O. The caller is expected to scan the
        local repo and pass:

        * ``project_name`` — the repo directory name (used to look up
          registry membership).
        * ``artifact_presence`` — mapping of each artifact to a bool. Keys
          checked: ``"CLAUDE.md"``, ``".claude/settings.json"``,
          ``"team-config.json"``, ``".quality/"``, ``".quality/baselines/"``,
          ``".quality/evidence/"``, ``".quality/logs/"``, ``".quality/scripts/"``.
          Missing keys default to ``False``.

        Returns which onboarding artifacts exist and which are missing,
        plus whether the project is registered in the engine's internal
        state registry (which is on the MCP host, not the client).
        """
        checks_keys = (
            "CLAUDE.md",
            ".claude/settings.json",
            "team-config.json",
            ".quality/",
            ".quality/baselines/",
            ".quality/evidence/",
            ".quality/logs/",
            ".quality/scripts/",
        )
        presence = dict(artifact_presence or {})
        present = [k for k in checks_keys if presence.get(k, False)]
        missing = [k for k in checks_keys if not presence.get(k, False)]

        # Registry lookups run on the MCP host — those paths are server-side.
        registered = False
        engine_registry_file = engine_path / ".quality" / "registry.json"
        if engine_registry_file.exists():
            try:
                registry = json.loads(engine_registry_file.read_text(encoding="utf-8"))
                registered = any(
                    p.get("name") == project_name
                    for p in registry.get("projects", [])
                )
            except (json.JSONDecodeError, OSError):
                pass

        if not registered and state_path:
            state_registry_file = state_path / "registry.json"
            if state_registry_file.exists():
                try:
                    registry = json.loads(state_registry_file.read_text(encoding="utf-8"))
                    registered = project_name in registry.get("projects", {})
                except (json.JSONDecodeError, OSError):
                    pass

        fully_onboarded = len(missing) == 0 and registered

        return {
            "project_name": project_name,
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
        backend_type: str = "",
        freeform_root_absolute: str = "",
        multirepo_role: str = "",
        orchestrator_project: str = "",
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
            backend_type: Tracking backend selection. One of "freeform", "trello", "plane", "native". Defaults to "native" since v6.3.0 ("Native Default OAuth") — multi-developer shared tracking via Supabase + GitHub OAuth, recommended for any project that ships through the VSCode extension's sign-in flow. If "trello" and trello_board_name is set, creates the board. If empty AND trello_board_name is provided, "trello" is inferred for backward compatibility. Use "freeform" explicitly for solo / air-gapped projects (still first-class — see doc/runbooks/freeform-only-mode.md).
            freeform_root_absolute: Absolute path to the FreeForm tracking directory when backend_type="freeform". When omitted, defaults to "<repo_root>/doc/tracking" — but the caller is responsible for resolving <repo_root> client-side because the MCP server may run remotely (see PR-1). The /app-init skill handles this automatically.
            multirepo_role: Optional multi-repo role: 'orchestrator' or 'satellite'. Leave empty for standard single-repo projects (default). When 'satellite', the project inherits the board from the orchestrator and generates a settings.local.json with the orchestrator reference.
            orchestrator_project: Required when multirepo_role='satellite'. Name of the orchestrator project in the registry. Used to inherit the board_id and set the orchestrator path.
            ctx: MCP context (injected automatically). Required when trello_board_name is provided.

        Returns the CONTENT of each file that should be created in the project repo
        (CLAUDE.md, settings.json, team-config.json, quality-baseline.json).
        The user copies these files to their local project.
        Also registers the project in the central state registry.
        If trello_board_name is given, includes the board_id in the generated settings.

        Use to onboard a new project into the SpecBox Engine ecosystem with quality gates and agent teams."""
        # v6.3.0: backend_type selection. Default = native (Native Default OAuth)
        # unless legacy trello_board_name is provided (back-compat).
        # Pre-v6.3.0 (v5.29.0..v6.2.x) the default was "freeform"; existing
        # projects are unaffected because detect_backend() still falls back to
        # "freeform" when no explicit signal is present — only NEW onboards via
        # onboard_project() without an explicit backend_type get "native" now.
        backend_type = resolve_default_backend_type(backend_type, trello_board_name)
        if backend_type not in VALID_BACKEND_TYPES:
            return {
                "error": f"Invalid backend_type {backend_type!r}. "
                         f"Must be one of: {', '.join(sorted(VALID_BACKEND_TYPES))}.",
                "code": "INVALID_BACKEND_TYPE",
            }
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

        # Multi-repo: inherit board_id from orchestrator and generate settings.local.json
        multirepo_board_id = ""
        if multirepo_role == "satellite" and orchestrator_project:
            if state_path:
                try:
                    from .state import _read_registry

                    registry = _read_registry(state_path)
                    orch_entry = registry.get("projects", {}).get(orchestrator_project, {})
                    multirepo_board_id = orch_entry.get("trello_board_id", "")
                    if not board_id and multirepo_board_id:
                        board_id = multirepo_board_id
                except Exception as e:
                    warnings.append(f"Could not read orchestrator registry: {e}")

            # Generate settings.local.json with multi-repo config
            settings_local = {
                "multirepo": {
                    "enabled": True,
                    "role": "satellite",
                    "orchestrator": f"../{orchestrator_project}",
                },
            }
            if board_id:
                settings_local["boardId"] = board_id
            files[".claude/settings.local.json"] = json.dumps(
                settings_local, indent=2, ensure_ascii=False
            )

        elif multirepo_role == "orchestrator":
            # For orchestrator, just note the role — satellites config is manual
            pass

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

        # v5.29.0: write the canonical specbox.* block into settings.local.json
        # so /prd, /plan, /implement etc. detect the backend without asking.
        # FreeForm requires an absolute path (BLOCKER fix from PR-1) — when the
        # caller did not provide one, leave it empty and surface a warning so
        # the /app-init skill can resolve it client-side.
        from pathlib import Path as _Path

        freeform_root = freeform_root_absolute.strip() if freeform_root_absolute else ""
        if backend_type == "freeform" and freeform_root and not _Path(freeform_root).is_absolute():
            warnings.append(
                f"freeform_root_absolute={freeform_root!r} is not absolute — "
                "ignored. Pass an absolute path or rely on /app-init to resolve it."
            )
            freeform_root = ""

        specbox_block: dict[str, object] = {
            "backend_type": backend_type,
            "autopilot": {
                "level": "equilibrado",
                "image_budget_eur_per_feature": 5,
            },
        }
        if backend_type == "freeform" and freeform_root:
            specbox_block["freeform_root_absolute"] = freeform_root
        if backend_type == "trello" and board_id:
            specbox_block["trello_board_id"] = board_id

        # Merge into settings.local.json if it already exists (multirepo case),
        # otherwise create a fresh one.
        existing_local = files.get(".claude/settings.local.json")
        try:
            local_data = json.loads(existing_local) if existing_local else {}
        except json.JSONDecodeError:
            local_data = {}
        local_data.setdefault("specbox", {})
        # Preserve user-provided values if any; only add what's missing.
        for k, v in specbox_block.items():
            local_data["specbox"].setdefault(k, v)
        files[".claude/settings.local.json"] = json.dumps(
            local_data, indent=2, ensure_ascii=False
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
                if multirepo_role:
                    registry_entry["multirepo_role"] = multirepo_role
                if orchestrator_project:
                    registry_entry["multirepo_group"] = orchestrator_project
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
                    # v6.0 (UC-D005 AC-05): capture the onboarding version for
                    # future upgrade_project calls to know which canonical docs
                    # are eligible for plantilla creation.
                    "engine_version_at_onboard": current_engine_version,
                    "mcp_version": MCP_VERSION,
                }
                if board_id:
                    meta["trello_board_id"] = board_id
                if multirepo_role:
                    meta["multirepo_role"] = multirepo_role
                if orchestrator_project:
                    meta["multirepo_group"] = orchestrator_project
                _write_meta(project_dir, meta)
                _invalidate_cache(state_path)
                registered = True
            except Exception as e:
                warnings.append(f"State registration failed: {e}")

        # v6.0 (UC-D005 AC-10): on a fresh onboard, every canonical doc with
        # introduced_in == current_engine_version (or earlier) becomes part
        # of the project. For onboard the relevant set is "all of them",
        # since engine_version_at_onboard == current. We still pass through
        # the helper for consistency with upgrade_project.
        now_iso = datetime.now(timezone.utc).isoformat()
        canonical_docs_to_create, canonical_warnings = _collect_canonical_doc_templates(
            engine_path,
            engine_version_at_onboard=None,  # at onboard nothing is "new" — caller decides
            project=project,
            now_iso=now_iso,
        )
        if canonical_warnings:
            warnings.extend(canonical_warnings)

        result = {
            "project": project,
            "stack": detected_stack,
            "infra": infra_list,
            "roles": roles,
            "files": files,
            "quality_dirs_to_create": quality_dirs,
            "engine_version": current_engine_version,
            "engine_version_at_onboard": current_engine_version,
            "mcp_version": MCP_VERSION,
            "registered_in_state": registered,
            "canonical_docs_to_create": canonical_docs_to_create,  # v6.0
            "warnings": warnings if warnings else None,
            "instructions": (
                "Copy the files above to your project repo. "
                "Create the .quality/ directories listed in quality_dirs_to_create. "
                "The project has been registered in the central state index. "
                "(v6.0: canonical_docs_to_create is empty on fresh onboard — "
                "/app-init creates app_prd.md and app_spec.md plantillas, and "
                "/discovery creates app_market.md when invoked in bootstrap mode.)"
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

        # v6.0 (UC-D005 AC-05): preserve engine_version_at_onboard if it was
        # captured at onboard time. Pre-v6.0 projects won't have this field —
        # mark them as "unknown" (D-11 conservative policy). The user can
        # manually bump the field via .specbox-meta.json or settings.local.json
        # if they want to opt in to receiving newer canonical docs.
        engine_version_at_onboard = meta.get("engine_version_at_onboard")
        if engine_version_at_onboard is None:
            engine_version_at_onboard = "unknown"
            meta["engine_version_at_onboard"] = engine_version_at_onboard

        meta["engine_version"] = current_engine_version
        meta["mcp_version"] = MCP_VERSION
        meta["last_upgraded_at"] = now
        _write_meta(project_dir, meta)

        # v6.0 (UC-D005 AC-10/11): offer plantillas for canonical docs
        # introduced after engine_version_at_onboard. Caller is responsible
        # for NOT overwriting existing files. The "upgrade_project never
        # overwrites existing content" invariant is preserved — this only
        # offers new files to create.
        canonical_docs_to_create, canonical_warnings = _collect_canonical_doc_templates(
            engine_path,
            engine_version_at_onboard=engine_version_at_onboard,
            project=project,
            now_iso=now,
        )

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

        # Settings matcher migration hint (v5.19+)
        settings_migration = {
            "action": "CRITICAL: replace .claude/settings.json — matcher format has changed",
            "reason": (
                "Pre-v5.19 settings used {tool_name: ...} objects for matcher. "
                "Claude Code expects matcher as a string. Old format causes: "
                "'Settings file failed to parse' — ALL hooks and permissions disabled."
            ),
            "fix": "The new settings.json in files above uses the correct string matcher format.",
        }

        # v6.0 (UC-D005 AC-10): hint for the caller about new canonical docs
        # that may need to be created in the project repo. The hint is
        # advisory — the caller (Claude Code agent invoking upgrade_project)
        # must verify the file doesn't already exist before writing the
        # plantilla content. This preserves the "never overwrite" invariant.
        discovery_alignment = {
            "action": (
                "v6.0 introduces canonical doc(s) not present at this project's "
                "onboard version. Copy each entry from canonical_docs_to_create "
                "ONLY IF the target path does not already exist in the project repo."
            ),
            "reason": (
                f"engine_version_at_onboard={engine_version_at_onboard!r}; "
                "any canonical doc introduced after this version is offered."
            ),
            "invariant": (
                "upgrade_project NEVER overwrites existing files. Plantillas "
                "are 'template-pristine' — the hook and /app-sync respect this "
                "marker until /discovery or /app-init fill in the first zone."
            ),
            "next_steps": (
                "After copying app_market.md plantilla (if offered), the user "
                "can run /discovery <feature> to enter bootstrap mode and fill "
                "in ICPs + JTBDs + NSM."
            ),
        }
        all_warnings = (warnings if warnings else []) + (canonical_warnings or [])

        return {
            "project": project,
            "stack": detected_stack,
            "infra": infra_list,
            "roles": roles,
            "files": files,
            "quality_dirs_to_create": quality_dirs,
            "engine_version": current_engine_version,
            "engine_version_at_onboard": engine_version_at_onboard,
            "mcp_version": MCP_VERSION,
            "upgraded_at": now,
            "canonical_docs_to_create": canonical_docs_to_create,  # v6.0
            "warnings": all_warnings if all_warnings else None,
            "e2e_alignment": e2e_alignment,
            "visual_alignment": visual_alignment,
            "settings_migration": settings_migration,
            "discovery_alignment": discovery_alignment,  # v6.0
            "instructions": (
                "IMPORTANT: Replace .claude/settings.json FIRST — the old matcher format "
                "was broken (object instead of string) and caused Claude Code to ignore all "
                "hooks and permissions. Copy all files above to your project repo. "
                "Then run get_e2e_gap_report and get_visual_gap_report on the project to detect "
                "E2E evidence gaps and visual identity gaps respectively. "
                "v6.0: review canonical_docs_to_create — for each entry, write the content "
                "to its path ONLY IF the file doesn't already exist (preserves the invariant). "
                "engine_version_at_onboard is now tracked in meta.json (UC-D005)."
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
    def get_visual_gap_report(
        settings_local_json_content: str | None = None,
        artifact_presence: dict[str, bool] | None = None,
        has_design_htmls: bool = False,
        has_veg_base_files: bool = False,
    ) -> dict:
        """Scan a project for missing visual identity artifacts and report gaps.

        **v6.0.1 — content-passing API**

        Does no filesystem I/O. The caller (skill or hook) is expected to:

        * Read ``.claude/settings.local.json`` and pass its raw content via
          ``settings_local_json_content`` (or ``None`` if missing).
        * Build ``artifact_presence`` from ``Path.is_file()`` checks for:
          ``"doc/brand/brand_kit/SKILL.md"``,
          ``"doc/brand/brand_kit/variables.css"``,
          ``"doc/brand/brand_kit/tailwind.config.js"``,
          ``"doc/brand/brand_kit/light.md"``,
          ``"doc/brand/brand_kit/dark.md"``,
          ``"doc/design/stitch-prompt-template.md"``.
        * Pass ``has_design_htmls=True`` if ``doc/design/**/*.html`` matches
          anything, ``has_veg_base_files=True`` if ``doc/veg/base/**/*.md``
          matches anything.

        Returns a structured report with coverage percentage, missing
        artifacts, and recommended actions. Projects not using Stitch at all
        get a clean ``status="not_applicable"``.
        """
        settings: dict = {}
        if settings_local_json_content and settings_local_json_content.strip():
            try:
                settings = json.loads(settings_local_json_content)
            except json.JSONDecodeError:
                settings = {}

        stitch_cfg = settings.get("stitch") or {}
        has_any_stitch = bool(stitch_cfg.get("projectId"))
        uses_stitch = has_any_stitch or bool(has_design_htmls)

        presence = dict(artifact_presence or {})

        def _is(path_key: str) -> bool:
            return bool(presence.get(path_key, False))

        artifacts = {
            "brand_kit_skill": {
                "path": "doc/brand/brand_kit/SKILL.md",
                "exists": _is("doc/brand/brand_kit/SKILL.md"),
                "category": "brand_kit",
                "description": "Brand summary for sub-agents (~600 tokens)",
            },
            "brand_kit_variables": {
                "path": "doc/brand/brand_kit/variables.css",
                "exists": _is("doc/brand/brand_kit/variables.css"),
                "category": "brand_kit",
                "description": "CSS custom properties (light + dark tokens)",
            },
            "brand_kit_tailwind": {
                "path": "doc/brand/brand_kit/tailwind.config.js",
                "exists": _is("doc/brand/brand_kit/tailwind.config.js"),
                "category": "brand_kit",
                "description": "Tailwind config using CSS variables",
            },
            "brand_kit_light": {
                "path": "doc/brand/brand_kit/light.md",
                "exists": _is("doc/brand/brand_kit/light.md"),
                "category": "brand_kit",
                "description": "Light theme specifications",
            },
            "brand_kit_dark": {
                "path": "doc/brand/brand_kit/dark.md",
                "exists": _is("doc/brand/brand_kit/dark.md"),
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
                "exists": bool(has_veg_base_files),
                "category": "veg",
                "description": "VEG base with visual directives for all features",
            },
            "prompt_template": {
                "path": "doc/design/stitch-prompt-template.md",
                "exists": _is("doc/design/stitch-prompt-template.md"),
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
