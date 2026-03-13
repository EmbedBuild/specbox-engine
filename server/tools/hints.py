"""MCP tools for contextual onboarding hints.

UC-005: Hints contextuales en skills existentes.
Provides two tools:
  - get_skill_hint: returns hint text if it should be shown
  - record_skill_hint: records that a hint was displayed
"""

from fastmcp import FastMCP

from ..hint_manager import (
    get_hint_text,
    record_hint_shown,
    should_show_hint,
    get_available_hints,
)


def register_hint_tools(mcp: FastMCP):

    @mcp.tool
    def get_skill_hint(project_path: str, skill_name: str) -> dict:
        """Get a contextual onboarding hint for a skill, if one should be shown.

        Args:
            project_path: Absolute path to the project root directory.
            skill_name: Name of the skill (e.g. 'prd', 'implement', 'plan').

        Returns a dict with 'hint' (the text to display) and 'show' (bool).
        If show is False, hint is an empty string — the skill should proceed normally.
        Hints disappear after 3 displays or when the project has > 5 completed UCs.

        Use at the start of a skill execution to show contextual help to new users."""
        if should_show_hint(project_path, skill_name):
            text = get_hint_text(skill_name)
            return {"show": True, "hint": text, "skill": skill_name}
        return {"show": False, "hint": "", "skill": skill_name}

    @mcp.tool
    def record_skill_hint(project_path: str, skill_name: str) -> dict:
        """Record that a contextual hint was shown for a skill.

        Args:
            project_path: Absolute path to the project root directory.
            skill_name: Name of the skill that showed the hint.

        Increments the hint counter in .quality/hint_counters.json.
        Call this after displaying a hint to the user.

        Use after get_skill_hint returns show=True and the hint has been displayed."""
        record_hint_shown(project_path, skill_name)
        return {
            "recorded": True,
            "skill": skill_name,
            "project_path": project_path,
        }

    @mcp.tool
    def list_skill_hints() -> dict:
        """List all available skill hints and which skills have contextual hints defined.

        Returns the list of skill names that have onboarding hints.
        Use to discover which skills support contextual hints for new users."""
        hints = get_available_hints()
        return {
            "available_hints": hints,
            "total": len(hints),
        }
