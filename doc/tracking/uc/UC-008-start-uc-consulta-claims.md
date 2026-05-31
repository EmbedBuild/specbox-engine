---
id: UC-302
ordinal: UC-008
title: start_uc consulta claims
parent_us: US-NATIVE-BACKEND
status: done
actor: Dev / skill implement
hours: 6
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-302 — start_uc consulta claims

> **US padre:** [US-NATIVE-BACKEND](../us/US-01-specbox-para-equipos-sobre-postgres-nativo.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-18

start_uc sobre UC sin claim crea el claim a nombre del dev y pasa el UC a in_progress en la misma transaccion (sin claim huerfano si falla el cambio de estado).

- **Estado:** ✅ cumplido

### AC-19

start_uc sobre UC ya reclamado por otro dev devuelve conflicto con owner, claimed_at y branch.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
