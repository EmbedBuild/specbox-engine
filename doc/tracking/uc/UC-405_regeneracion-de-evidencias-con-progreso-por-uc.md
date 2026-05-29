---
id: UC-405
title: Regeneracion de evidencias con progreso por UC
parent_us: US-BACKEND-SWITCH
status: done
actor: Engine
hours: 6
owner: Jesús Pérez
created: 2026-05-22
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-405 — Regeneracion de evidencias con progreso por UC

> **US padre:** [US-BACKEND-SWITCH](../us/US-BACKEND-SWITCH_cambio-guiado-de-backend-entre-los-4-freeform-trello-plane-n.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

regenerate_evidence(project, ucs=None) identifica UCs con evidencia previa (escaneo de .quality/evidence/*/acceptance/results.json) y por cada uno reejecuta run_acceptance_check regenerando results.json + HTML; verificado: cada UC procesado tiene results.json con generated_at posterior al inicio.

- **Estado:** ⬜ pendiente

### AC-02

Reporta progreso por UC con formato [X/N] UC-XXX: {PASS|FAIL|SKIP} (n_acs ACs con evidencia) y resumen final con listas regenerados/fallidos/pendientes; verificado sobre proyecto con >=2 UCs.

- **Estado:** ⬜ pendiente

### AC-03

Resultado persistido en doc/migrations/evidence_regeneration_{timestamp}.md con detalle por UC y resumen; verificado: archivo existe con una entrada por UC procesado.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
