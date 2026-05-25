"""MCP tools for the Skill Registry — list, discover, and validate skills.

v6.0.1 — the @mcp.tool wrappers are content-passing. The client supplies
the project-local skill manifests it already discovered (or ``None`` for
core-only listings). Core (engine) skills are still resolved from the MCP
host's installation.

UC-620 part of US-MCP-PATH-CONTRACT.
"""

from pathlib import Path

import yaml
from fastmcp import FastMCP

from ..skill_registry import (
    check_dependencies,
    list_all_skills,
    validate_manifest,
)


def register_skill_registry_tools(mcp: FastMCP, engine_path: Path):

    @mcp.tool
    def list_skills_v2(
        project_local_manifests: list[dict] | None = None,
    ) -> list[dict]:
        """List all Agent Skills (core + supplied project-local).

        **v6.0.1 — content-passing API**

        Args:
            project_local_manifests: Optional list of parsed ``manifest.yaml``
                dicts for the client's project-local ``.claude/skills/``.
                Each dict should mirror what ``yaml.safe_load`` returns
                (with at least ``name``, ``version``, ``description``,
                ``triggers``, ``stacks``, optionally ``depends_on``).
                When omitted, only core engine skills are returned.

        Returns the merged list with ``source`` ∈ {core, external, external-local}.
        """
        core = list_all_skills(engine_path, None)
        if not project_local_manifests:
            return core

        local: list[dict] = []
        core_names = {s.get("name") for s in core}
        for m in project_local_manifests:
            if not isinstance(m, dict):
                continue
            name = m.get("name")
            if not name:
                continue
            entry = {
                "name": name,
                "version": m.get("version", "unknown"),
                "description": m.get("description", ""),
                "source": "external-local",
                "triggers": m.get("triggers", []),
                "stacks": m.get("stacks", []),
                "depends_on": m.get("depends_on", []),
            }
            if name in core_names:
                entry["shadow_warning"] = (
                    f"Project-local skill {name!r} shadows a core engine skill"
                )
            local.append(entry)

        return core + local

    @mcp.tool
    def discover_skills(
        stack: str,
        keywords: str = "",
        project_local_manifests: list[dict] | None = None,
    ) -> dict:
        """Auto-discover external skills matching a stack and keyword triggers.

        **v6.0.1 — content-passing API**

        Args:
            stack: Target stack (e.g. ``"flutter"``, ``"react"``, ``"go"``,
                ``"python"``).
            keywords: Comma-separated keywords from PRD to match against triggers.
            project_local_manifests: Optional list of project-local manifest
                dicts (see :func:`list_skills_v2`).

        Returns ``{"activated": [...], "incompatible": [...], "total_scanned": int}``.
        """
        if not stack:
            return {"error": "stack is required"}

        kw_list = [k.strip().lower() for k in keywords.split(",") if k.strip()] if keywords else []
        candidates = list_skills_v2.fn(project_local_manifests) if hasattr(list_skills_v2, "fn") else list_skills_v2(project_local_manifests)  # type: ignore[arg-type]
        # When called as plain Python, list_skills_v2 is the registered tool's
        # underlying callable; both paths return the merged list.

        activated: list[dict] = []
        incompatible: list[dict] = []
        for skill in candidates:
            stacks = [s.lower() for s in skill.get("stacks", [])]
            triggers = [t.lower() for t in skill.get("triggers", [])]
            stack_ok = (not stacks) or stack.lower() in stacks
            kw_ok = (not kw_list) or any(any(kw in t for t in triggers) for kw in kw_list)
            entry = {**skill, "stack_match": stack_ok, "keyword_match": kw_ok}
            if stack_ok and kw_ok:
                entry["activated"] = True
                activated.append(entry)
            elif not stack_ok:
                entry["incompatible"] = True
                entry["reason"] = f"stack {stack!r} not in {skill.get('stacks')}"
                incompatible.append(entry)
            # If stack_ok but kw_ok=False, the skill is compatible but not
            # triggered → omitted from both lists (matches prior behavior).

        return {
            "activated": activated,
            "incompatible": incompatible,
            "total_scanned": len(candidates),
        }

    @mcp.tool
    def validate_skill_manifest(
        manifest_yaml_content: str,
    ) -> dict:
        """Validate a skill's manifest.yaml content.

        **v6.0.1 — content-passing API**

        Args:
            manifest_yaml_content: Raw text of the skill's ``manifest.yaml``
                (read on the client). The tool parses it and reports
                required-field validity + missing dependencies against
                the core engine skill list.
        """
        if not manifest_yaml_content or not manifest_yaml_content.strip():
            return {
                "valid": False,
                "errors": ["manifest_yaml_content is empty"],
                "dependency_warnings": [],
            }
        try:
            data = yaml.safe_load(manifest_yaml_content) or {}
        except yaml.YAMLError as exc:
            return {
                "valid": False,
                "errors": [f"YAML parse error: {exc}"],
                "dependency_warnings": [],
            }

        errors: list[str] = []
        required_fields = ("name", "version", "description")
        for field in required_fields:
            if not data.get(field):
                errors.append(f"missing required field: {field}")

        valid = not errors

        dep_warnings: list[str] = []
        if valid:
            available = [s.get("name") for s in list_all_skills(engine_path, None)]
            missing = check_dependencies(data, available)
            if missing:
                dep_warnings = [f"missing dependency: {d}" for d in missing]

        return {
            "valid": valid,
            "errors": errors,
            "dependency_warnings": dep_warnings,
        }


# Keep validate_manifest importable for tests that need the path-based version.
__all__ = ["register_skill_registry_tools"]
