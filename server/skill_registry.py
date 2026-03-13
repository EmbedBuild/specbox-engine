"""
Skill Registry — validates manifests, lists skills, checks dependencies,
and auto-discovers skills matching stack + keyword triggers.

Supports both core skills (shipped with the engine) and external skills
(installed by users via install.sh --skill).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


REQUIRED_MANIFEST_FIELDS = {"name", "version", "author", "description", "compatibility"}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[\w.]+)?$")


# ---------------------------------------------------------------------------
# Frontmatter parser (reused from tools/skills.py style)
# ---------------------------------------------------------------------------

def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from a SKILL.md file."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    frontmatter: dict[str, Any] = {}
    current_key: str | None = None
    for line in parts[1].strip().splitlines():
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith("-") and not stripped.startswith(" "):
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            current_key = key
            if value and value != ">":
                frontmatter[key] = value
            elif value == ">":
                frontmatter[key] = ""
        elif current_key and stripped and current_key in frontmatter:
            frontmatter[current_key] = (frontmatter[current_key] + " " + stripped).strip()

    return frontmatter


# ---------------------------------------------------------------------------
# Manifest validation
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict[str, Any] | None:
    """Load a YAML file, return None on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return None


def validate_manifest(manifest_path: Path) -> tuple[bool, list[str]]:
    """Validate a skill manifest.yaml.

    Returns (valid, errors) where *valid* is True when no errors were found.
    """
    errors: list[str] = []

    if not manifest_path.exists():
        return False, ["manifest.yaml not found"]

    data = _load_yaml(manifest_path)
    if data is None:
        return False, ["manifest.yaml is not valid YAML"]

    # Required fields
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in data or data[field] is None or str(data[field]).strip() == "":
            errors.append(f"missing required field: {field}")

    # Semver check
    version = data.get("version")
    if version and not SEMVER_RE.match(str(version)):
        errors.append(f"version '{version}' is not valid semver (expected X.Y.Z)")

    # Compatibility must be a list
    compat = data.get("compatibility")
    if compat is not None and not isinstance(compat, list):
        errors.append("compatibility must be a list of stacks")

    # Optional field types
    triggers = data.get("triggers")
    if triggers is not None and not isinstance(triggers, list):
        errors.append("triggers must be a list of keywords")

    depends_on = data.get("depends_on")
    if depends_on is not None and not isinstance(depends_on, list):
        errors.append("depends_on must be a list of skill names")

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Skill listing
# ---------------------------------------------------------------------------

def _read_skill_dir(skill_dir: Path, source: str) -> dict[str, Any] | None:
    """Read a single skill directory and return its metadata dict."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    content = skill_md.read_text(encoding="utf-8")
    fm = _parse_frontmatter(content)

    manifest_path = skill_dir / "manifest.yaml"
    manifest: dict[str, Any] | None = None
    if manifest_path.exists():
        manifest = _load_yaml(manifest_path)

    supporting_files = [f.name for f in skill_dir.iterdir() if f.name != "SKILL.md"]

    result: dict[str, Any] = {
        "name": fm.get("name", skill_dir.name),
        "description": fm.get("description", "No description")[:200],
        "context": fm.get("context", "direct"),
        "agent": fm.get("agent", "none"),
        "allowed_tools": fm.get("allowed-tools", "all"),
        "source": source,
        "supporting_files": supporting_files,
        "path": str(skill_dir),
    }

    if manifest:
        result["version"] = str(manifest.get("version", ""))
        result["author"] = manifest.get("author", "")
        result["compatibility"] = manifest.get("compatibility", [])
        result["triggers"] = manifest.get("triggers", [])
        result["depends_on"] = manifest.get("depends_on", [])

    return result


def list_all_skills(
    engine_path: Path,
    project_path: str | None = None,
    *,
    home_override: Path | None = None,
) -> list[dict[str, Any]]:
    """List all skills (core + external) with *source* field.

    Core skills live under ``engine_path/.claude/skills/``.
    External global skills live under ``~/.claude/skills/`` (that are NOT
    symlinks pointing into the engine).
    Project-local external skills live under ``project_path/.claude/skills/``.

    Core skills take priority: if a core and external skill share the same
    directory name, the external one is marked with ``"shadow_warning": True``.
    """
    skills: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    # 1. Core skills (from engine repo)
    core_dir = engine_path / ".claude" / "skills"
    if core_dir.is_dir():
        for d in sorted(core_dir.iterdir()):
            if not d.is_dir():
                continue
            info = _read_skill_dir(d, source="core")
            if info:
                skills.append(info)
                seen_names.add(d.name)

    # 2. Global external skills (~/.claude/skills/ minus engine symlinks)
    home = home_override or Path.home()
    global_dir = home / ".claude" / "skills"
    if global_dir.is_dir():
        for d in sorted(global_dir.iterdir()):
            if not d.is_dir():
                continue
            # Skip if this is a symlink pointing into the engine (= core)
            if d.is_symlink():
                target = d.resolve()
                if core_dir.is_dir() and str(target).startswith(str(core_dir.resolve())):
                    continue
            info = _read_skill_dir(d, source="external")
            if info:
                if d.name in seen_names:
                    info["shadow_warning"] = True
                skills.append(info)
                seen_names.add(d.name)

    # 3. Project-local external skills
    if project_path:
        proj_dir = Path(project_path) / ".claude" / "skills"
        if proj_dir.is_dir():
            for d in sorted(proj_dir.iterdir()):
                if not d.is_dir():
                    continue
                info = _read_skill_dir(d, source="external-local")
                if info:
                    if d.name in seen_names:
                        info["shadow_warning"] = True
                    skills.append(info)
                    seen_names.add(d.name)

    return skills


# ---------------------------------------------------------------------------
# Dependency checking
# ---------------------------------------------------------------------------

def check_dependencies(manifest: dict[str, Any], available_skills: list[str]) -> list[str]:
    """Check ``depends_on`` in *manifest* against *available_skills*.

    Returns a list of missing dependency names (empty if all satisfied).
    """
    depends_on = manifest.get("depends_on")
    if not depends_on or not isinstance(depends_on, list):
        return []
    return [dep for dep in depends_on if dep not in available_skills]


# ---------------------------------------------------------------------------
# Auto-discovery for pipeline
# ---------------------------------------------------------------------------

def discover_skills_for_context(
    engine_path: Path,
    project_path: str | None,
    stack: str,
    keywords: list[str],
    *,
    home_override: Path | None = None,
) -> list[dict[str, Any]]:
    """Auto-discovery: find skills matching *stack* + *keywords* from triggers.

    A skill is activated when:
    1. It has a manifest with a ``compatibility`` list containing *stack*
       (case-insensitive), AND
    2. At least one of its ``triggers`` matches a keyword (case-insensitive
       substring).

    Skills incompatible with the stack are returned separately under
    ``"incompatible": True`` for logging purposes.
    """
    all_skills = list_all_skills(engine_path, project_path, home_override=home_override)

    activated: list[dict[str, Any]] = []
    stack_lower = stack.lower()
    kw_lower = [k.lower() for k in keywords]

    for skill in all_skills:
        compat = skill.get("compatibility", [])
        triggers = skill.get("triggers", [])

        # Skip skills without manifest data (core skills without manifest)
        if not compat and not triggers:
            continue

        # Check stack compatibility
        compat_lower = [c.lower() for c in compat] if compat else []
        stack_ok = not compat_lower or stack_lower in compat_lower

        # Check trigger match
        trigger_match = False
        if triggers:
            for trigger in triggers:
                t_lower = trigger.lower()
                for kw in kw_lower:
                    if kw in t_lower or t_lower in kw:
                        trigger_match = True
                        break
                if trigger_match:
                    break

        if trigger_match:
            entry = {**skill, "activated": stack_ok, "incompatible": not stack_ok}
            activated.append(entry)

    return activated
