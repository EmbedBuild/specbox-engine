"""MCP Resources — read-only data exposed to LLM context."""

from pathlib import Path
from fastmcp import FastMCP


def register_resources(mcp: FastMCP, engine_path: Path):

    @mcp.resource("engine://version")
    def engine_version() -> str:
        """Current engine version info from ENGINE_VERSION.yaml."""
        version_file = engine_path / "ENGINE_VERSION.yaml"
        if version_file.exists():
            return version_file.read_text(encoding="utf-8")
        return "Engine version file not found"

    @mcp.resource("engine://claude-md")
    def engine_claude_md() -> str:
        """The engine's CLAUDE.md configuration and conventions."""
        claude_md = engine_path / "CLAUDE.md"
        if claude_md.exists():
            return claude_md.read_text(encoding="utf-8")
        return "CLAUDE.md not found"

    @mcp.resource("engine://readme")
    def engine_readme() -> str:
        """The engine's full README documentation."""
        readme = engine_path / "README.md"
        if readme.exists():
            return readme.read_text(encoding="utf-8")
        return "README.md not found"

    @mcp.resource("engine://skills-summary")
    def skills_summary() -> str:
        """Quick summary of all available skills (name + description)."""
        skills_dir = engine_path / ".claude" / "skills"
        if not skills_dir.exists():
            return "No skills directory found"

        lines = ["# Available Skills\n"]
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding="utf-8")
                name = skill_dir.name
                desc = "No description"
                if "description:" in content:
                    for line in content.splitlines():
                        if line.strip().startswith("description:"):
                            desc = line.split(":", 1)[1].strip().strip('"').strip("'")[:100]
                            break
                lines.append(f"- **{name}**: {desc}")

        return "\n".join(lines)

    @mcp.resource("engine://hooks-config")
    def hooks_config() -> str:
        """Hook configuration from .claude/settings.json."""
        settings = engine_path / ".claude" / "settings.json"
        if settings.exists():
            return settings.read_text(encoding="utf-8")
        return "No settings.json found"

    @mcp.resource("engine://global-rules")
    def global_rules() -> str:
        """Global rules that apply to all projects (GLOBAL_RULES.md)."""
        rules = engine_path / "rules" / "GLOBAL_RULES.md"
        if rules.exists():
            return rules.read_text(encoding="utf-8")
        return "GLOBAL_RULES.md not found"

    @mcp.resource("engine://quality-readme")
    def quality_readme() -> str:
        """Documentation of the quality system (.quality/README.md)."""
        readme = engine_path / ".quality" / "README.md"
        if readme.exists():
            return readme.read_text(encoding="utf-8")
        return "No .quality/README.md found"

    @mcp.resource("engine://file-ownership")
    def file_ownership() -> str:
        """File ownership rules per agent (which agent can modify which paths)."""
        ownership = engine_path / ".claude" / "skills" / "implement" / "file-ownership.md"
        if ownership.exists():
            return ownership.read_text(encoding="utf-8")
        return "No file-ownership.md found"
