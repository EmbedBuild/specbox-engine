---
id: UC-304
title: active_uc.json como cache + branch_registry
parent_us: US-NATIVE-BACKEND
status: done
actor: Dev / hooks
hours: 8
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-304 — active_uc.json como cache + branch_registry

> **US padre:** [US-NATIVE-BACKEND](../us/US-NATIVE-BACKEND_specbox-para-equipos-sobre-postgres-nativo.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-21

Tras start_uc, .quality/active_uc.json se escribe local con referencia al claim remoto (uc_id, developer_id, claimed_at); se trata como cache y spec-guard.mjs lo acepta offline.

- **Estado:** ✅ cumplido

### AC-22

Con red, spec-guard.mjs revalida el claim contra el MCP antes de permitir escribir codigo; si el claim ya no es del dev, bloquea con mensaje que indica el conflicto.

- **Estado:** ✅ cumplido

### AC-23

branch_registry registra (project_id, uc_id, branch, dev); registrar un branch con nombre ya usado por otro dev para otro UC es rechazado, y el naming sugerido incluye el uc_id (feature/{uc_id}-{slug}).

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
