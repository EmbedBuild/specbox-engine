---
id: UC-667
ordinal: UC-107
title: Validacion de drift contra decisiones canonicas
parent_us: US-CONN-GATE
status: draft
actor: Engine
hours: 5
owner: Jesús Pérez
created: 2026-05-31
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-667 — Validacion de drift contra decisiones canonicas

> **US padre:** [US-CONN-GATE](../us/US-21-drift-gate-consciente-de-las-decisiones-canonicas.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

validate_discovery_completeness acepta el contenido de app_spec.md canonical_decisions (content-passing) y detecta si el Discovery contradice alguna decision registrada. Test: con un artefacto que contradice una decision canonica SIN declararla en 'Drift from app_market' devuelve verdict != READY_FOR_PRD con un missing especifico.

- **Estado:** ✅ done — `_validate_icp_jtbd(content, app_spec_content)` + helpers `_detect_canonical_drift`/`_parse_canonical_decisions`/`_extract_canonical_zone` (nivel módulo, importables); la tool anidada `validate_discovery_completeness` reenvía `app_spec_content`. Contradicción no declarada → DISCOVERY_INCOMPLETE + `missing` incluye `canonical_decision_resolution`. Test `test_ac19_undeclared_canonical_contradiction_blocks`.

### AC-02

Cuando un Discovery contradice una decision canonica pero la declara explicitamente como documented_exception con justificacion, el gate la acepta. Test: con el artefacto de specbox_connectivity_ux devuelve READY_FOR_PRD.

- **Estado:** ✅ done — `documented_exception` → READY_FOR_PRD. Tests `test_ac20_documented_exception_passes` + `test_ac20_real_feature_discovery_is_ready` (icp_jtbd.md real de esta feature como fixture vivo).

### AC-03

El reporte de drift distingue entre drift de mercado (app_market.md) y drift de decision canonica (app_spec.md), nombrando la decision concreta contradicha. Test: asserta el payload incluye canonical_decision_drift {decision, resolved, kind}.

- **Estado:** ✅ done — payload separa `drift` (mercado) de `canonical_decision_drift: {decision, resolved, kind}`. Test `test_ac21_payload_separates_market_and_canonical_drift`. 8 tests en `tests/test_discovery_canonical_gate.py`; suite discovery+app_docs 60 passed (sin MCP_URL) / 48 (con), 0 failed.

## Nota de implementación

El gate solo validaba `app_market.md` (vía `_validate_icp_jtbd`, nivel módulo).
UC-667 añade el parámetro opcional `app_spec_content` (retrocompatible: sin él,
comportamiento idéntico). `_extract_canonical_zone` lee la zona
`canonical_decisions`; `_parse_canonical_decisions` extrae los títulos en
negrita; `_detect_canonical_drift` trabaja sobre la sección "## Drift from
app_market" del Discovery: si nombra una decisión canónica afectada sin declarar
resolución → `kind=undeclared` → bloquea; `documented_exception` → pasa. La tool
MCP `validate_discovery_completeness` (anidada en `register_product_discovery_tools`)
reenvía el nuevo parámetro.

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
