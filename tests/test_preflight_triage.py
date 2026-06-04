"""Tests for the pre-flight autonomy triage (US-06).

UC-601 (this file, Phase 1): the decision inventory.
- AC-01: the inventory includes user-dependent decisions with id/description/source.
- AC-02: catalogued decisions carry their exact ``decision_key``; non-catalogued
  ones are marked ``ad_hoc``.
"""

from __future__ import annotations

from server.app_docs.autopilot import DECISION_KEYS
from server.implement_context.preflight_triage import (
    AD_HOC,
    DecisionEntry,
    build_decision_inventory,
    inventory_to_dict,
)

# A plan fragment that contains exactly two decisions: one that maps to the
# catalogue (the tracking backend selection) and one that is task-specific
# (an undocumented API contract — the canonical "autopilot guessed it" case).
_PLAN_ONE_CATALOGUED_ONE_AD_HOC = """
# Plan: some feature

## Fase 1
- Implementar el endpoint sin más.

## Decisiones
- Decisión: el contrato de API del nuevo endpoint /foo no está especificado.
- Elegir el tracking backend (freeform vs native) para este proyecto.
"""


def test_ac01_inventory_includes_user_dependent_decision_with_id_description_source():
    """AC-01: a plan with a user-dependent decision yields an inventory entry
    carrying id, description and source (the plan line that originated it)."""
    entries = build_decision_inventory(_PLAN_ONE_CATALOGUED_ONE_AD_HOC)

    assert entries, "inventory must not be empty for a plan with decisions"
    api = next((e for e in entries if "contrato de api" in e.description.lower()), None)
    assert api is not None, "the undocumented API contract decision must be inventoried"
    assert api.id == "D1" or api.id.startswith("D")  # deterministic id assigned
    assert api.description
    assert "contrato de api" in api.source.lower()  # source references the plan line

    # Inventory is JSON-serializable and verifiable (AC-01).
    payload = inventory_to_dict(entries)
    assert payload["total"] == len(entries)
    assert all({"id", "description", "source", "decision_key"} <= set(d) for d in payload["decisions"])


def test_ac02_distinguishes_catalogued_from_ad_hoc():
    """AC-02: a fixture with 1 catalogued + 1 ad-hoc produces exactly those
    two kinds — the catalogued entry carries a real ``decision_key`` from the
    catalogue, the other is marked ``ad_hoc``."""
    entries = build_decision_inventory(_PLAN_ONE_CATALOGUED_ONE_AD_HOC)

    catalogued = [e for e in entries if e.decision_key != AD_HOC]
    ad_hoc = [e for e in entries if e.decision_key == AD_HOC]

    assert len(catalogued) >= 1, "the backend-selection line must map to the catalogue"
    assert len(ad_hoc) >= 1, "the API-contract line must fall to ad_hoc"

    # Every catalogued decision_key must really exist in the policy catalogue —
    # the inventory can never invent a key the policy engine would reject.
    for e in catalogued:
        assert e.decision_key in DECISION_KEYS
        assert e.family == DECISION_KEYS[e.decision_key]["family"]

    backend = next((e for e in catalogued if e.decision_key == "backend_selection"), None)
    assert backend is not None, "the tracking-backend line must map to backend_selection"


def test_empty_plan_yields_empty_inventory():
    """A plan with no decision cues (or no plan at all) yields an empty
    inventory — the gate must not invent work (supports AC-08 downstream)."""
    assert build_decision_inventory(None) == []
    assert build_decision_inventory("") == []
    assert build_decision_inventory("# Plan\n- just run the build\n- write some tests") == []


def test_inventory_is_deterministic_and_deduped():
    """Same plan → same inventory (stable ids); a decision mentioned twice is
    inventoried once (so the gate count is honest)."""
    plan = "- Decisión: nombrar la nueva tabla.\n- Decisión: nombrar la nueva tabla.\n"
    first = build_decision_inventory(plan)
    second = build_decision_inventory(plan)

    assert [e.to_dict() for e in first] == [e.to_dict() for e in second]
    assert len(first) == 1, "a duplicate decision line must be deduped"
    assert first[0].id == "D1"


def test_extra_decisions_injected_default_to_ad_hoc():
    """Decisions surfaced outside the plan text are inventoried; an unknown
    decision_key falls to ad_hoc (conservative)."""
    entries = build_decision_inventory(
        None,
        extra_decisions=[
            {"description": "choose the websocket library", "decision_key": "not_a_real_key"},
            {"description": "use freeform backend", "decision_key": "backend_selection"},
        ],
    )
    assert len(entries) == 2
    bogus = next(e for e in entries if "websocket" in e.description)
    assert bogus.decision_key == AD_HOC  # unknown key never leaks through
    real = next(e for e in entries if "freeform" in e.description)
    assert real.decision_key == "backend_selection"


def test_decision_entry_to_dict_shape():
    """A DecisionEntry serializes to the documented shape."""
    e = DecisionEntry(id="D1", description="x", source="x", decision_key=AD_HOC)
    d = e.to_dict()
    assert d == {"id": "D1", "description": "x", "source": "x", "decision_key": AD_HOC, "family": "ad_hoc"}
