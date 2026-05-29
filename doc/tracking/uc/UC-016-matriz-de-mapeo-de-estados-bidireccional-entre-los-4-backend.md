---
id: UC-402
ordinal: UC-016
title: Matriz de mapeo de estados bidireccional entre los 4 backends
parent_us: US-BACKEND-SWITCH
status: done
actor: Engine
hours: 8
owner: Jesús Pérez
created: 2026-05-22
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-402 — Matriz de mapeo de estados bidireccional entre los 4 backends

> **US padre:** [US-BACKEND-SWITCH](../us/US-03-cambio-guiado-de-backend-entre-los-4-freeform-trello-plane-n.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

Tabla traduce los 5 estados canonicos del ABC (user_stories, backlog, in_progress, review, done) al estado nativo de cada uno de los 4 backends y viceversa; test verifica que un UC in_progress migrado de cualquier origen a cualquier destino re-lee a in_progress.

- **Estado:** ⬜ pendiente

### AC-02

Estado sin equivalente exacto aplica fallback documentado (done->done, intermedio desconocido->backlog) y registra warning en el reporte nombrando UC y estado degradado, verificado con caso sin equivalente.

- **Estado:** ⬜ pendiente

### AC-03

La migracion preserva AC marcados done (ChecklistItemDTO.done) entre los 4 backends; test migra UC con 3 de 5 AC done y verifica exactamente esos 3 done en destino.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
