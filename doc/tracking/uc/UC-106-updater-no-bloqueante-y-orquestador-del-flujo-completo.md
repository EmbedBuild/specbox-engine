---
id: UC-666
ordinal: UC-106
title: Updater no bloqueante y orquestador del flujo completo
parent_us: US-CONN-UPGRADE
status: draft
actor: Client
hours: 4
owner: Jesús Pérez
created: 2026-05-31
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-666 — Updater no bloqueante y orquestador del flujo completo

> **US padre:** [US-CONN-UPGRADE](../us/US-20-actualizacion-robusta-y-pedagogica-consciente-de-la-configur.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

El flujo de actualizacion (binario -> skills/hooks -> deteccion de config -> migracion -> resumen) se ejecuta sin bloquear la activacion (patron fire-and-forget de v6.6.2), con try/catch por fase que impide que un fallo cuelgue la extension. Test: simula un fallo en la fase de migracion y asserta que la activacion completa igualmente.

- **Estado:** ⬜ pendiente

### AC-02

Tras una actualizacion exitosa sin config obsoleta (ej. Trello/Plane), el usuario ve un mensaje minimo 'Actualizado a vX - sin cambios para tu configuracion', sin ruido innecesario. Test: para el caso 'sin cambios' asserta el copy breve y la ausencia de prompts de migracion.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
