"""UC-667 — drift gate aware of canonical decisions (US-CONN-GATE).

The market drift gate (v6.0) only checked app_market.md. UC-667 extends the
Discovery validation to also validate against app_spec.md § canonical_decisions:
a Discovery that contradicts a registered canonical decision without declaring
a resolution must NOT be READY_FOR_PRD (the PR #82 hole).

Tests target the MODULE-LEVEL `_validate_icp_jtbd` (the MCP tool itself is
nested inside register_product_discovery_tools and not importable; the tool is
a thin wrapper that forwards app_spec_content to this function).

AC-19: undeclared contradiction → DISCOVERY_INCOMPLETE with a specific missing.
AC-20: a documented_exception (as this feature's own Discovery does) → READY.
AC-21: payload distinguishes market drift from canonical drift, naming the decision.
"""
from __future__ import annotations

from pathlib import Path

from server.tools.discovery import (
    _validate_icp_jtbd,
    _parse_canonical_decisions,
    _extract_canonical_zone,
)

REPO = Path(__file__).resolve().parents[1]

_APP_SPEC = """\
# app_spec.md

<!-- @specbox:zone start kind="hybrid" id="canonical_decisions" merge="append_only" -->
## Decisiones canónicas

- **FreeForm requiere MCP local** — el backend FreeForm necesita un MCP local
  para tocar el filesystem del cliente.
- **VEG DISABLED para el engine** — el engine no tiene UI de producto propia.
<!-- @specbox:zone end -->
"""

# A complete icp_jtbd with all 4 required sections filled. The "## Drift from
# app_market" section is what the canonical gate inspects.
_COMPLETE_BODY = """\
# Discovery — demo

## ICPs involucrados
ICP-1 owner-operator. ICP-2 dev solo con FreeForm. Texto suficiente para superar el gate.

## JTBDs racionales
JR-1: cuando trabajo solo, quiero trazabilidad, para no perder el hilo. Más texto real aquí.

## JTBDs emocionales
JE-1: quiero sentirme en control de mi tracking sin fricción. Texto emocional real aquí.

## Validation evidence
Conversación con 3 usuarios ICP-2 (semana 2026-05-28) + traza git del incidente.
"""


def _with_drift(drift_section: str) -> str:
    return _COMPLETE_BODY + "\n## Drift from app_market\n" + drift_section + "\n"


# ── parsing helpers ──────────────────────────────────────────────────


def test_parse_canonical_decisions_reads_bold_titles():
    titles = _parse_canonical_decisions(_APP_SPEC)
    assert "FreeForm requiere MCP local" in titles
    assert "VEG DISABLED para el engine" in titles


def test_extract_canonical_zone_returns_none_without_markers():
    assert _extract_canonical_zone("# app_spec\nno zone here") is None


# ── AC-19: undeclared contradiction blocks the gate ──────────────────


def test_ac19_undeclared_canonical_contradiction_blocks():
    artifact = _with_drift(
        '- **Decisión canónica afectada**: "FreeForm requiere MCP local" '
        "(sin resolución declarada todavía)."
    )
    res = _validate_icp_jtbd(artifact, app_spec_content=_APP_SPEC)
    assert res["verdict"] != "READY_FOR_PRD"
    assert "canonical_decision_resolution" in res["missing"]
    cd = res["canonical_decision_drift"]
    assert cd["kind"] == "undeclared"
    assert cd["decision"] == "FreeForm requiere MCP local"


def test_ac19_no_canonical_mention_is_clean():
    artifact = _with_drift("- Nuevos ICPs: ninguno.\n- Resolución: no_drift.")
    res = _validate_icp_jtbd(artifact, app_spec_content=_APP_SPEC)
    assert res["verdict"] == "READY_FOR_PRD"
    assert res["canonical_decision_drift"]["kind"] == "no_canonical_drift"
    assert "canonical_decision_resolution" not in res["missing"]


# ── AC-20: documented_exception clears the gate ──────────────────────


def test_ac20_documented_exception_passes():
    artifact = _with_drift(
        '- **Decisión canónica afectada**: "FreeForm requiere MCP local" → sustituida.\n'
        "- Resolución: documented_exception con justificación arquitectural."
    )
    res = _validate_icp_jtbd(artifact, app_spec_content=_APP_SPEC)
    assert res["verdict"] == "READY_FOR_PRD"
    cd = res["canonical_decision_drift"]
    assert cd["kind"] == "documented_exception"
    assert cd["resolved"] is True
    assert cd["decision"] == "FreeForm requiere MCP local"


def test_ac20_real_feature_discovery_is_ready():
    """The feature's own icp_jtbd.md declares a documented_exception against
    'FreeForm requiere MCP local' → READY_FOR_PRD (living fixture)."""
    icp = (REPO / "doc/discovery/specbox_connectivity_ux/icp_jtbd.md").read_text()
    res = _validate_icp_jtbd(icp, app_spec_content=_APP_SPEC)
    assert res["verdict"] == "READY_FOR_PRD", res
    cd = res["canonical_decision_drift"]
    assert cd["kind"] == "documented_exception"
    assert cd["decision"] == "FreeForm requiere MCP local"


# ── AC-21: payload distinguishes market vs canonical drift ───────────


def test_ac21_payload_separates_market_and_canonical_drift():
    artifact = _with_drift(
        '- **Decisión canónica afectada**: "FreeForm requiere MCP local"\n'
        "- Resolución: documented_exception aplicada."
    )
    res = _validate_icp_jtbd(artifact, app_spec_content=_APP_SPEC)
    assert "drift" in res and "canonical_decision_drift" in res
    cd = res["canonical_decision_drift"]
    assert set(cd.keys()) == {"decision", "resolved", "kind"}
    assert cd["decision"] == "FreeForm requiere MCP local"


# ── backwards compat: no app_spec_content → no canonical gate ────────


def test_no_app_spec_keeps_legacy_behaviour():
    artifact = _with_drift(
        '- **Decisión canónica afectada**: "FreeForm requiere MCP local"'
    )
    res = _validate_icp_jtbd(artifact)  # no app_spec_content
    assert res["verdict"] == "READY_FOR_PRD"
    assert res["canonical_decision_drift"]["kind"] == "no_canonical_drift"
