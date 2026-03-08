"""Tools para consultar Agent Skills disponibles en el engine."""

from pathlib import Path
from fastmcp import FastMCP


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from a SKILL.md file."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    frontmatter = {}
    current_key = None
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
            # Continuation of multi-line value
            frontmatter[current_key] = (frontmatter[current_key] + " " + stripped).strip()

    return frontmatter


def register_skill_tools(mcp: FastMCP, engine_path: Path):

    @mcp.tool
    def list_skills() -> list[dict]:
        """List all Agent Skills available in the engine with their metadata.
        Returns skill name, description, context mode (fork/direct), agent type,
        allowed tools, and supporting files count.
        Use to discover what capabilities the engine provides."""
        skills_dir = engine_path / ".claude" / "skills"
        if not skills_dir.exists():
            return []

        skills = []
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            content = skill_md.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)

            supporting_files = [f.name for f in skill_dir.iterdir() if f.name != "SKILL.md"]

            skills.append({
                "name": fm.get("name", skill_dir.name),
                "description": fm.get("description", "No description")[:200],
                "context": fm.get("context", "direct"),
                "agent": fm.get("agent", "none"),
                "allowed_tools": fm.get("allowed-tools", "all"),
                "disable_model_invocation": fm.get("disable-model-invocation", "false"),
                "supporting_files": supporting_files,
                "path": str(skill_dir),
            })
        return skills

    @mcp.tool
    def read_skill(skill_name: str) -> dict:
        """Read the full content and metadata of a specific Agent Skill.
        Args:
            skill_name: Name of the skill (directory name or name from frontmatter).
        Returns frontmatter fields, full SKILL.md content, and supporting file previews.
        Use when you need the detailed instructions of how a skill works."""
        skills_dir = engine_path / ".claude" / "skills"
        skill_dir = skills_dir / skill_name

        if not skill_dir.exists():
            matches = [d for d in skills_dir.iterdir() if d.is_dir() and skill_name.lower() in d.name.lower()]
            if matches:
                skill_dir = matches[0]
            else:
                available = [d.name for d in skills_dir.iterdir() if d.is_dir()]
                return {"error": f"Skill '{skill_name}' not found", "available": available}

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return {"error": f"SKILL.md not found in {skill_dir.name}"}

        content = skill_md.read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)

        supporting = {}
        for f in skill_dir.iterdir():
            if f.name != "SKILL.md" and f.is_file() and f.suffix in (".md", ".json", ".yaml", ".yml"):
                try:
                    supporting[f.name] = f.read_text(encoding="utf-8")[:2000]
                except Exception:
                    supporting[f.name] = "(could not read)"

        return {
            "name": fm.get("name", skill_dir.name),
            "frontmatter": fm,
            "content": content,
            "supporting_files": supporting,
        }
