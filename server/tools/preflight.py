"""MCP tool for the pre-flight autonomy triage (US-06, UC-603 surface).

Exposes the pure triage logic of
:mod:`server.implement_context.preflight_triage` (UC-601 inventory + UC-602
classification + UC-604 audit log) as a single MCP tool the ``/implement``
SKILL calls in its pre-flight step, **before** creating the branch.

Follows the v6.0.1 content-passing contract: the client reads the plan
locally and passes ``plan_content`` as a string; the tool never touches the
client filesystem. The autopilot level is passed explicitly (the SKILL reads
it from ``.claude/settings.local.json``) rather than resolved server-side,
because the MCP server is remote and cannot see the client's settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..implement_context.preflight_triage import (
    USER_DEPENDENT,
    build_decision_inventory,
    classify_inventory,
    inventory_to_dict,
)


def analyze_preflight_decisions_impl(
    plan_content: str | None,
    *,
    autopilot_level: str | None = None,
    extra_decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pure entry point: inventory → classify → package (testable in isolation).

    ``autopilot_level`` is woven into the classification context as a synthetic
    project so :func:`evaluate_decision` resolves tiers without reading the
    client filesystem. When ``None``, the policy engine falls back to its own
    default (``low`` — ask everything), which is the safe default for a remote
    call with no level provided.
    """
    entries = build_decision_inventory(plan_content, extra_decisions=extra_decisions)

    # The classifier delegates catalogued keys to evaluate_decision, which by
    # default reads the level from a settings file under ``projectPath``. On a
    # remote MCP there is no client FS, so we pin the level inline via
    # ``level_override`` (evaluate_decision honours it and falls back to the
    # config/``low`` default when absent — the safe default for a remote call).
    context: dict[str, Any] = {}
    if autopilot_level:
        context["level_override"] = autopilot_level

    classify_inventory(entries, context=context)
    payload = inventory_to_dict(entries)

    # Surface the user-dependent decisions explicitly so the SKILL can render
    # the gate without re-filtering.
    payload["user_dependent_decisions"] = [
        e.to_dict() for e in entries if e.meta.get("classification") == USER_DEPENDENT
    ]
    # ``verdict`` is set by inventory_to_dict when classified; default for the
    # empty inventory (no decisions at all) is no_user_decisions.
    payload.setdefault("verdict", "no_user_decisions")
    return payload


def register_preflight_tools(mcp, engine_path: Path) -> None:
    """Register the ``analyze_preflight_decisions`` MCP tool (UC-603)."""

    @mcp.tool
    def analyze_preflight_decisions(
        plan_content: str,
        autopilot_level: str | None = None,
    ) -> dict[str, Any]:
        """Analyze a plan and return its decisions classified for the gate.

        Pre-flight autonomy triage (US-06): given the plan of the UC about to
        be implemented, discover the decisions it contains, classify each one
        ``autonomous`` vs. ``user_dependent`` reusing the autopilot policy
        engine, and return a verdict the ``/implement`` gate consumes **before**
        creating the branch.

        v6.0.1 content-passing: the client reads ``doc/plans/<feature>_plan.md``
        locally and passes its content here; the tool never reads the client FS.

        Args:
            plan_content: The full plan markdown of the UC/feature.
            autopilot_level: Active autopilot level
                (``low``/``conservador``/``equilibrado``/``agresivo``). When
                omitted, the conservative default applies (ask).

        Returns:
            ``{decisions[], total, catalogued, ad_hoc, autonomous,
            user_dependent, user_dependent_decisions[], verdict}`` where
            ``verdict`` is ``needs_user_input`` (the gate must stop and ask) or
            ``no_user_decisions`` (the gate proceeds straight to start_uc).
        """
        return analyze_preflight_decisions_impl(
            plan_content, autopilot_level=autopilot_level
        )
