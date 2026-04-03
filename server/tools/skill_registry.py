"""MCP tools for the Skill Registry — list, discover, and validate skills."""

from pathlib import Path
from fastmcp import FastMCP

from ..skill_registry import (
    check_dependencies,
    discover_skills_for_context,
    list_all_skills,
    validate_manifest,
)


def register_skill_registry_tools(mcp: FastMCP, engine_path: Path):

    @mcp.tool
    def list_skills_v2(project_path: str = "") -> list[dict]:
        """List all Agent Skills (core + external) with source and manifest info.

        Extends the original list_skills with:
        - source field: "core", "external", or "external-local"
        - version from manifest.yaml (if present)
        - shadow_warning if an external skill is shadowed by a core skill

        Args:
            project_path: Optional project path to include project-local skills.
        """
        return list_all_skills(
            engine_path,
            project_path if project_path else None,
        )

    @mcp.tool
    def discover_skills(
        project_path: str = "",
        stack: str = "",
        keywords: str = "",
    ) -> dict:
        """Auto-discover external skills matching a stack and keyword triggers.

        Used during /prd to activate domain-specific skills automatically.

        Args:
            project_path: Optional project path for project-local skills.
            stack: Target stack (e.g. "flutter", "react", "go", "python").
            keywords: Comma-separated keywords from PRD to match against triggers.

        Returns dict with "activated" (compatible) and "incompatible" lists.
        """
        if not stack:
            return {"error": "stack is required"}

        kw_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []

        results = discover_skills_for_context(
            engine_path,
            project_path if project_path else None,
            stack,
            kw_list,
        )

        activated = [s for s in results if s.get("activated")]
        incompatible = [s for s in results if s.get("incompatible")]

        return {
            "activated": activated,
            "incompatible": incompatible,
            "total_scanned": len(list_all_skills(
                engine_path,
                project_path if project_path else None,
            )),
        }

    @mcp.tool
    def validate_skill_manifest(skill_path: str) -> dict:
        """Validate a skill's manifest.yaml for required fields and format.

        Args:
            skill_path: Path to the skill directory containing manifest.yaml.

        Returns dict with "valid" boolean and "errors" list.
        """
        p = Path(skill_path)
        manifest_path = p / "manifest.yaml"

        valid, errors = validate_manifest(manifest_path)

        # Also check dependencies if valid
        dep_warnings: list[str] = []
        if valid:
            import yaml
            with open(manifest_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            available = [s["name"] for s in list_all_skills(engine_path)]
            missing = check_dependencies(data, available)
            if missing:
                dep_warnings = [f"missing dependency: {d}" for d in missing]

        return {
            "valid": valid,
            "errors": errors,
            "dependency_warnings": dep_warnings,
        }
