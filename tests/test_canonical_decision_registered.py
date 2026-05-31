"""UC-668 — the new canonical decision is registered in app_spec.md (US-CONN-GATE).

AC-22: app_spec.md § canonical_decisions contains BOTH the new decision
("Transporte único MCP remoto + content-passing") AND the superseded one
("FreeForm requiere MCP local"), with the supersession relationship explicit,
append-only (the old one not deleted).

Also closes the plan's identified risk that UC-668 could auto-block on the
UC-667 gate: the real app_spec.md + the real feature Discovery must validate
as a documented_exception → READY_FOR_PRD (full loop, no self-block).
"""
from __future__ import annotations

from pathlib import Path

from server.app_docs.zones import parse_document
from server.tools.discovery import _validate_icp_jtbd, _parse_canonical_decisions

REPO = Path(__file__).resolve().parents[1]
APP_SPEC = REPO / "doc/app/app_spec.md"
FEATURE_DISCOVERY = REPO / "doc/discovery/specbox_connectivity_ux/icp_jtbd.md"


def _canonical_zone():
    parsed = parse_document(APP_SPEC)
    return next(z for z in parsed.zones if z.id == "canonical_decisions")


def test_app_spec_is_well_formed():
    assert parse_document(APP_SPEC).is_well_formed


def test_ac22_both_decisions_present_with_supersession():
    body = _canonical_zone().body
    # Superseded decision still present (append-only — not deleted).
    assert "FreeForm requiere MCP local" in body
    # New decision present.
    assert "Transporte único MCP remoto" in body
    assert "content-passing" in body
    # Supersession relationship explicit.
    low = body.lower()
    assert "sustitu" in low  # "sustituida" / "sustituye"
    assert "uc-668" in low or "specbox_connectivity_ux_prd.md" in body


def test_ac22_new_decision_is_an_active_canonical_title():
    # The new decision is registered as an ACTIVE bold canonical title (parseable).
    titles = _parse_canonical_decisions(APP_SPEC.read_text())
    assert any("Transporte único MCP remoto" in t for t in titles)
    # The superseded one is struck-through (~~...~~), so it is intentionally NOT
    # an active title — it lives in the zone body as history (asserted above),
    # not as a current decision. This is the append-only-with-supersession shape.
    assert not any(t.startswith("FreeForm requiere MCP local") for t in titles), (
        "the superseded decision must not be an active canonical title"
    )


# ── Full loop: real app_spec + real Discovery → gate accepts (no self-block) ──


def test_uc668_does_not_self_block_on_the_uc667_gate():
    """The feature's own Discovery declares a documented_exception against the
    decision now registered in app_spec.md. The UC-667 gate must therefore
    accept it (READY_FOR_PRD) — otherwise registering the decision would be
    impossible without tripping its own gate."""
    icp = FEATURE_DISCOVERY.read_text()
    app_spec = APP_SPEC.read_text()
    res = _validate_icp_jtbd(icp, app_spec_content=app_spec)
    assert res["verdict"] == "READY_FOR_PRD", res
    assert res["canonical_decision_drift"]["kind"] == "documented_exception"
