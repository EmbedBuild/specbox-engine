"""Tools para consultar planes de implementación y diseños Stitch."""

from pathlib import Path
from fastmcp import FastMCP

from ._safe_paths import child_within


def register_plan_tools(mcp: FastMCP, engine_path: Path):

    @mcp.tool
    def list_plans() -> list[dict]:
        """List all implementation plans in the engine.
        Returns plan name, file size, and last modified date for each.
        Use when you need to see what plans exist or find a specific plan."""
        plans_dir = engine_path / "doc" / "plans"
        if not plans_dir.exists():
            return []

        plans = []
        for f in sorted(plans_dir.glob("*.md")):
            stat = f.stat()
            plans.append({
                "name": f.stem,
                "filename": f.name,
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
                "path": str(f),
            })
        return plans

    @mcp.tool
    def read_plan(plan_name: str) -> dict:
        """Read the full content of a specific implementation plan.
        Args:
            plan_name: Name of the plan (with or without .md extension).
        Returns plan content, line count, and metadata.
        Use when you need to review plan details, phases, or agent assignments."""
        plans_dir = engine_path / "doc" / "plans"

        candidates = [child_within(plans_dir, plan_name), child_within(plans_dir, f"{plan_name}.md")]
        plan_file = next((p for p in candidates if p is not None and p.exists()), None)
        if plan_file is None:
            matches = list(plans_dir.glob(f"*{plan_name}*")) if candidates[0] is not None else []
            if matches:
                plan_file = matches[0]
            else:
                return {
                    "error": f"Plan '{plan_name}' not found",
                    "available": [f.stem for f in plans_dir.glob("*.md")],
                }

        content = plan_file.read_text(encoding="utf-8")
        return {
            "name": plan_file.stem,
            "filename": plan_file.name,
            "content": content,
            "lines": len(content.splitlines()),
        }

    @mcp.tool
    def list_designs(feature_name: str = "") -> list[dict]:
        """List Stitch design HTML files, optionally filtered by feature.
        Args:
            feature_name: Optional feature name to filter. Empty returns all designs.
        Returns feature, filename, path, and size for each design.
        Use to check what UI designs exist before implementing a feature."""
        design_dir = engine_path / "doc" / "design"
        if not design_dir.exists():
            return []

        designs = []
        search_path = child_within(design_dir, feature_name) if feature_name else design_dir
        if search_path is None:
            return []
        for f in search_path.rglob("*.html"):
            designs.append({
                "feature": f.parent.name,
                "filename": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
            })
        return designs
