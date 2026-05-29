---
id: UC-303
ordinal: UC-009
title: find_next_uc excluye reclamados
parent_us: US-NATIVE-BACKEND
status: done
actor: Dev / skill implement
hours: 4
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-303 — find_next_uc excluye reclamados

> **US padre:** [US-NATIVE-BACKEND](../us/US-01-specbox-para-equipos-sobre-postgres-nativo.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-20

find_next_uc sobre backend Nativo no devuelve UCs con claim activo de otro dev; con dos devs y dos UCs disponibles, cada find_next_uc simultaneo devuelve UCs distintos.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
