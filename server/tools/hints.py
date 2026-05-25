"""MCP tools for contextual onboarding hints.

v6.0.1 — content-passing API. The client supplies the current hint
counters and the number of completed UCs; the tool returns whether the
hint should be shown and (for `record_skill_hint`) the new counter map
that the client writes back to ``.quality/hint_counters.json``.

UC-005: Hints contextuales en skills existentes.
"""

from typing import Any

from fastmcp import FastMCP

from ..hint_manager import (
    MAX_HINT_COUNT,
    COMPLETED_UC_THRESHOLD,
    get_hint_text,
    get_available_hints,
)


def register_hint_tools(mcp: FastMCP):

    @mcp.tool
    def get_skill_hint(
        skill_name: str,
        current_counter: int = 0,
        completed_uc_count: int = 0,
    ) -> dict:
        """Get a contextual onboarding hint for a skill, if one should be shown.

        **v6.0.1 — content-passing API**

        Args:
            skill_name: Name of the skill (e.g. 'prd', 'implement', 'plan').
            current_counter: How many times this hint has already been shown
                on the client (read from ``.quality/hint_counters.json``).
                Defaults to ``0`` for a fresh project.
            completed_uc_count: Number of UCs the project has completed.
                When ``> COMPLETED_UC_THRESHOLD`` (5), the hint is suppressed.

        Returns ``{"show": bool, "hint": str, "skill": str}``. When ``show``
        is ``False`` the caller skips the hint and proceeds normally.
        """
        text = get_hint_text(skill_name)
        if not text:
            return {"show": False, "hint": "", "skill": skill_name}
        if completed_uc_count > COMPLETED_UC_THRESHOLD:
            return {"show": False, "hint": "", "skill": skill_name}
        if current_counter >= MAX_HINT_COUNT:
            return {"show": False, "hint": "", "skill": skill_name}
        return {"show": True, "hint": text, "skill": skill_name}

    @mcp.tool
    def record_skill_hint(
        skill_name: str,
        counters: dict[str, int] | None = None,
    ) -> dict:
        """Record that a contextual hint was shown for a skill.

        **v6.0.1 — content-passing API**

        Args:
            skill_name: Name of the skill that showed the hint.
            counters: Current contents of ``.quality/hint_counters.json``
                (or ``{}`` / ``None`` for a fresh project). Returned with
                the counter for ``skill_name`` incremented.

        Returns ``{"recorded": True, "skill": skill_name, "updated_counters": ...}``.
        The client must write ``updated_counters`` back to
        ``.quality/hint_counters.json``.
        """
        current = dict(counters or {})
        current[skill_name] = int(current.get(skill_name, 0)) + 1
        return {
            "recorded": True,
            "skill": skill_name,
            "updated_counters": current,
        }

    @mcp.tool
    def list_skill_hints() -> dict:
        """List all available skill hints. (Pure data — no client I/O.)"""
        hints = get_available_hints()
        return {
            "available_hints": hints,
            "total": len(hints),
        }
