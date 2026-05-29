---
id: UC-404
ordinal: UC-017
title: Tool migrate_backend N×N + switch_backend generalizado + update transaccional
parent_us: US-BACKEND-SWITCH
status: done
actor: Engine
hours: 12
owner: Jesús Pérez
created: 2026-05-22
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-404 — Tool migrate_backend N×N + switch_backend generalizado + update transaccional

> **US padre:** [US-BACKEND-SWITCH](../us/US-03-cambio-guiado-de-backend-entre-los-4-freeform-trello-plane-n.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

migrate_backend(source_type, source_id, target_type, target_id?, dry_run=True) con dry_run=True devuelve preview con counts US/UC/AC/comments y mapeo de estados sin escribir; verificado: destino sigue vacio tras dry-run.

- **Estado:** ⬜ pendiente

### AC-02

dry_run=False ejecuta migracion aditiva (origen intacto y legible) y devuelve id_map origen->destino + counts migrados/skipped/errores; verificado: list_items(source) igual antes y despues.

- **Estado:** ⬜ pendiente

### AC-03

switch_backend acepta los 4 backend_types y actualiza atomicamente los 3 lugares (projects.json spec_backend+board_id, zona auto tracking_backend de app_spec.md, specbox.backend_type en settings.local.json); detect_project_backend tras el switch devuelve el nuevo backend.

- **Estado:** ⬜ pendiente

### AC-04

Si la actualizacion de cualquiera de los 3 lugares falla, switch_backend revierte los ya escritos (rollback) y devuelve error que nombra el lugar fallido, dejando el proyecto en su backend original; verificado simulando fallo en settings.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
