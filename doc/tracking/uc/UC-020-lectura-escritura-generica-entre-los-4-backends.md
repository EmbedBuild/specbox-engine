---
id: UC-801
ordinal: UC-020
title: Lectura/escritura generica entre los 4 backends
parent_us: US-BACKEND-SWITCH
status: done
actor: Engine
hours: 12
owner: Jesús Pérez
created: 2026-05-22
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-801 — Lectura/escritura generica entre los 4 backends

> **US padre:** [US-BACKEND-SWITCH](../us/US-03-cambio-guiado-de-backend-entre-los-4-freeform-trello-plane-n.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

_write_target(target_backend, target_id, source_data) crea US, UC y AC en cualquiera de los 4 backends a partir del dict de _read_source, preservando jerarquia padre->hijo (parent_id) y el uc_id/us_id/ac_id logico en meta; test de round-trip lee de A, escribe en B y verifica mismo numero de US/UC/AC e IDs logicos.

- **Estado:** ⬜ pendiente

### AC-02

El dispatch acepta los 4 valores (freeform, trello, plane, native) como origen y destino; backend_type invalido devuelve error que nombra los 4 validos, verificado por test parametrizado sobre los 4 tipos.

- **Estado:** ⬜ pendiente

### AC-03

Escritura idempotente via external_id (como migrate_project): reejecutar sobre destino ya poblado no duplica y reporta skipped, verificado con doble pasada y 0 duplicados.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
