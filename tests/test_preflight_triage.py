"""Tests for the pre-flight autonomy triage (US-06).

UC-601 (this file, Phase 1): the decision inventory.
- AC-01: the inventory includes user-dependent decisions with id/description/source.
- AC-02: catalogued decisions carry their exact ``decision_key``; non-catalogued
  ones are marked ``ad_hoc``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.app_docs.autopilot import DECISION_KEYS, evaluate_decision
from server.implement_context.preflight_triage import (
    AD_HOC,
    AUTONOMOUS,
    USER_DEPENDENT,
    DecisionEntry,
    build_decision_inventory,
    classify_decision,
    classify_inventory,
    inventory_to_dict,
    log_preflight_inventory,
)


def _project_with_level(tmp_path: Path, level: str) -> str:
    """Write a minimal settings.local.json pinning the autopilot level and
    return the project path string for ``evaluate_decision``'s ``projectPath``."""
    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(
        json.dumps({"specbox": {"autopilot": {"level": level}}}),
        encoding="utf-8",
    )
    return str(tmp_path)

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


# ── UC-602: classification ──────────────────────────────────────────────────


def test_ac03_catalogued_auto_becomes_autonomous_with_verbatim_reason(tmp_path):
    """AC-03: a catalogued decision whose policy is ``auto`` at the current
    level is classified ``autonomous`` and carries the policy engine's
    ``reason`` byte-for-byte."""
    project = _project_with_level(tmp_path, "equilibrado")
    # backend_selection in equilibrado → auto_freeform_default → action "auto".
    entry = DecisionEntry(
        id="D1",
        description="elegir backend",
        source="elegir backend",
        decision_key="backend_selection",
        family=DECISION_KEYS["backend_selection"]["family"],
    )
    classify_decision(entry, context={"projectPath": project})

    expected = evaluate_decision("backend_selection", {"projectPath": project})
    assert expected["action"] == "auto"  # precondition for this fixture
    assert entry.meta["classification"] == AUTONOMOUS
    assert entry.meta["reason"] == expected["reason"]  # byte-for-byte


def test_ac04_ad_hoc_without_inheritable_is_user_dependent():
    """AC-04: an ad_hoc decision with no inheritable backing it is
    ``user_dependent`` by conservative default."""
    entry = DecisionEntry(id="D1", description="choose lib", source="choose lib", decision_key=AD_HOC)
    classify_decision(entry, context={})  # no ad_hoc_inheritable, no app_spec
    assert entry.meta["classification"] == USER_DEPENDENT
    assert entry.meta["reason"] == "ad_hoc_conservative_default"


def test_ad_hoc_with_explicit_inheritable_is_autonomous():
    """The conservative ad_hoc default can be overridden only by an explicit
    inheritable — the escape hatch a caller sets when app_spec resolves it."""
    entry = DecisionEntry(id="D1", description="x", source="x", decision_key=AD_HOC)
    classify_decision(entry, context={"ad_hoc_inheritable": True})
    assert entry.meta["classification"] == AUTONOMOUS


@pytest.mark.parametrize(
    "decision_key",
    ["destructive_action", "image_cost_over_budget", "branch_to_main_push"],
)
@pytest.mark.parametrize("level", ["low", "conservador", "equilibrado", "agresivo"])
def test_ac05_inviolables_never_autonomous_at_any_level(tmp_path, decision_key, level):
    """AC-05: the three inviolable keys are never ``autonomous`` at any of the
    four autopilot levels — more autonomy never means less safety."""
    project = _project_with_level(tmp_path, level)
    entry = DecisionEntry(
        id="D1",
        description=decision_key,
        source=decision_key,
        decision_key=decision_key,
        family=DECISION_KEYS[decision_key]["family"],
    )
    classify_decision(entry, context={"projectPath": project})
    assert entry.meta["classification"] == USER_DEPENDENT
    assert entry.meta["reason"] == "inviolable_never_autonomous"


def test_classify_inventory_sets_verdict_needs_user_input(tmp_path):
    """A mixed inventory yields verdict ``needs_user_input`` when any decision
    is user-dependent (the gate must stop)."""
    project = _project_with_level(tmp_path, "equilibrado")
    entries = build_decision_inventory(_PLAN_ONE_CATALOGUED_ONE_AD_HOC)
    classify_inventory(entries, context={"projectPath": project})
    payload = inventory_to_dict(entries)
    assert payload["verdict"] == "needs_user_input"
    assert payload["user_dependent"] >= 1  # the ad_hoc API contract


def test_classify_inventory_verdict_no_user_decisions_when_all_autonomous(tmp_path):
    """When every decision is autonomous, the verdict is ``no_user_decisions``
    so a fully-autonomous task does not interrupt (AC-08 downstream)."""
    project = _project_with_level(tmp_path, "agresivo")
    # A single catalogued auto decision, nothing user-dependent.
    entries = [
        DecisionEntry(
            id="D1",
            description="elegir backend",
            source="elegir backend",
            decision_key="backend_selection",
            family=DECISION_KEYS["backend_selection"]["family"],
        )
    ]
    classify_inventory(entries, context={"projectPath": project})
    payload = inventory_to_dict(entries)
    assert payload["verdict"] == "no_user_decisions"
    assert payload["user_dependent"] == 0
    assert payload["autonomous"] == 1


def test_classification_surfaces_in_to_dict(tmp_path):
    """Once classified, to_dict surfaces classification/action/reason at the
    top level for the gate and the audit log."""
    project = _project_with_level(tmp_path, "equilibrado")
    entry = DecisionEntry(id="D1", description="x", source="x", decision_key=AD_HOC)
    classify_decision(entry, context={"projectPath": project})
    d = entry.to_dict()
    assert d["classification"] == USER_DEPENDENT
    assert d["action"] == "ask"
    assert "reason" in d


# ── UC-604: audit log ───────────────────────────────────────────────────────


def test_ac09_one_jsonl_line_per_decision(tmp_path):
    """AC-09: after the gate runs, .quality/autopilot_decisions.jsonl has one
    parseable line per decision of the inventory, with the documented fields."""
    project = _project_with_level(tmp_path, "equilibrado")
    entries = build_decision_inventory(_PLAN_ONE_CATALOGUED_ONE_AD_HOC)
    classify_inventory(entries, context={"projectPath": project})

    records = log_preflight_inventory(
        entries, project_path=project, feature="autopilot_autonomy_triage",
        now_fn=lambda: "2026-06-04T00:00:00+00:00",
    )

    log_file = tmp_path / ".quality" / "autopilot_decisions.jsonl"
    assert log_file.exists()
    lines = [ln for ln in log_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == len(entries), "exactly one JSONL line per inventory decision"

    parsed = [json.loads(ln) for ln in lines]  # every line is valid JSON
    for rec in parsed:
        assert {
            "id", "decision_key", "classification", "action",
            "reason", "resolved_by", "feature", "ts", "kind",
        } <= set(rec)
        assert rec["kind"] == "preflight"
        assert rec["resolved_by"] in ("auto", "user")
        assert rec["feature"] == "autopilot_autonomy_triage"
    assert len(records) == len(entries)


def test_resolved_by_follows_classification(tmp_path):
    """A user_dependent decision is logged resolved_by=user; an autonomous one
    resolved_by=auto (the auditable record of who decided)."""
    project = _project_with_level(tmp_path, "agresivo")
    autonomous = DecisionEntry(
        id="D1", description="elegir backend", source="elegir backend",
        decision_key="backend_selection",
        family=DECISION_KEYS["backend_selection"]["family"],
    )
    user_dep = DecisionEntry(id="D2", description="api contract", source="api contract", decision_key=AD_HOC)
    classify_inventory([autonomous, user_dep], context={"projectPath": project})

    records = log_preflight_inventory([autonomous, user_dep], project_path=project, now_fn=lambda: "t")
    by_id = {r["id"]: r for r in records}
    assert by_id["D1"]["resolved_by"] == "auto"
    assert by_id["D2"]["resolved_by"] == "user"
