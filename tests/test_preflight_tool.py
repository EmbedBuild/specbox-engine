"""Tests for the analyze_preflight_decisions MCP tool surface (US-06, UC-603).

The gate logic itself lives in ``server/implement_context/preflight_triage.py``
(tested in ``test_preflight_triage.py``). This file covers the tool wrapper:
the verdict contract the SKILL consumes, and the inline ``level_override`` path
that lets a remote MCP classify without reading the client filesystem.
"""

from __future__ import annotations

from server.app_docs.autopilot import evaluate_decision
from server.tools.preflight import analyze_preflight_decisions_impl

_PLAN_WITH_USER_DECISION = """
# Plan
## Decisiones
- Decisión: el contrato de API de /foo no está especificado.
"""

_PLAN_ALL_AUTONOMOUS = """
# Plan
- Elegir el tracking backend (freeform) para este proyecto.
"""

_PLAN_NO_DECISIONS = """
# Plan
- Implementar el endpoint.
- Escribir tests.
"""


def test_verdict_needs_user_input_when_user_dependent_present():
    """A plan with a user-dependent decision yields verdict needs_user_input
    and surfaces the decision for the gate to render (AC-06 support)."""
    out = analyze_preflight_decisions_impl(_PLAN_WITH_USER_DECISION, autopilot_level="equilibrado")
    assert out["verdict"] == "needs_user_input"
    assert out["user_dependent"] >= 1
    assert out["user_dependent_decisions"], "the gate needs the list to render"
    assert all("description" in d for d in out["user_dependent_decisions"])


def test_verdict_no_user_decisions_when_all_autonomous():
    """A plan whose only decision is autonomous yields no_user_decisions, so
    the gate proceeds without interrupting (AC-08)."""
    out = analyze_preflight_decisions_impl(_PLAN_ALL_AUTONOMOUS, autopilot_level="agresivo")
    assert out["verdict"] == "no_user_decisions"
    assert out["user_dependent"] == 0
    assert out["user_dependent_decisions"] == []


def test_verdict_no_user_decisions_when_no_decisions_at_all():
    """An empty inventory must not invent work — verdict no_user_decisions
    (AC-08): a clean task is not interrupted by the gate."""
    out = analyze_preflight_decisions_impl(_PLAN_NO_DECISIONS, autopilot_level="equilibrado")
    assert out["total"] == 0
    assert out["verdict"] == "no_user_decisions"


def test_level_override_changes_classification():
    """The inline level_override actually drives classification: backend_selection
    is ``ask`` at ``low`` (→ user_dependent) but ``auto`` at ``equilibrado``
    (→ autonomous). This is what lets a remote MCP classify without client FS."""
    low = analyze_preflight_decisions_impl(_PLAN_ALL_AUTONOMOUS, autopilot_level="low")
    bal = analyze_preflight_decisions_impl(_PLAN_ALL_AUTONOMOUS, autopilot_level="equilibrado")
    assert low["verdict"] == "needs_user_input"   # low asks everything
    assert bal["verdict"] == "no_user_decisions"  # equilibrado auto-confirms backend


def test_evaluate_decision_level_override_is_additive():
    """The level_override added to evaluate_decision is backwards-compatible:
    absent → unchanged; present → pins the level."""
    # backend_selection: low → ask, equilibrado → auto.
    assert evaluate_decision("backend_selection", {"level_override": "low"})["action"] == "ask"
    assert evaluate_decision("backend_selection", {"level_override": "equilibrado"})["action"] == "auto"
    # A bogus override is ignored (falls back to config/default).
    res = evaluate_decision("backend_selection", {"level_override": "not_a_tier"})
    assert res["action"] in ("ask", "auto")  # whatever config says, never crashes


def test_inviolable_still_user_dependent_through_the_tool():
    """End-to-end through the tool: an inviolable decision (destructive) is
    user_dependent even at the most aggressive level (AC-05 holds at the surface)."""
    plan = "- Decisión: drop table de la migración (destructive).\n"
    out = analyze_preflight_decisions_impl(plan, autopilot_level="agresivo")
    assert out["verdict"] == "needs_user_input"
    assert out["user_dependent"] >= 1
