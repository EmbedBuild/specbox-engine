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

- **Estado:** ⬜ pendiente

### AC-02

Cuando un Discovery contradice una decision canonica pero la declara explicitamente como documented_exception con justificacion, el gate la acepta. Test: con el artefacto de specbox_connectivity_ux devuelve READY_FOR_PRD.

- **Estado:** ⬜ pendiente

### AC-03

El reporte de drift distingue entre drift de mercado (app_market.md) y drift de decision canonica (app_spec.md), nombrando la decision concreta contradicha. Test: asserta el payload incluye canonical_decision_drift {decision, resolved, kind}.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
