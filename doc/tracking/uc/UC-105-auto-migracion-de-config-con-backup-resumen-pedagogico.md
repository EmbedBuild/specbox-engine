---
id: UC-665
ordinal: UC-105
title: Auto-migracion de config con backup + resumen pedagogico
parent_us: US-CONN-UPGRADE
status: draft
actor: Client
hours: 7
owner: Jesús Pérez
created: 2026-05-31
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-665 — Auto-migracion de config con backup + resumen pedagogico

> **US padre:** [US-CONN-UPGRADE](../us/US-20-actualizacion-robusta-y-pedagogica-consciente-de-la-configur.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

Cuando el caso es config obsoleta (ej. modo Local), la extension hace backup de settings.local.json (a settings.local.json.bak-<ts>) ANTES de tocar nada, y luego aplica la migracion (Local->Remoto+bridge). Test: asserta que el .bak existe con el contenido original y que el settings.local.json migrado apunta al remoto.

- **Estado:** ⬜ pendiente

### AC-02

Tras migrar, la extension muestra un resumen pedagogico no bloqueante con: que cambio, que se migro automaticamente, donde esta el backup, y que -si algo- debe hacer el usuario, con copy especifico por caso de ICP. Test: para cada caso asserta el copy contiene las 4 secciones (cambio/migrado/backup/accion).

- **Estado:** ⬜ pendiente

### AC-03

La migracion de settings.json es reversible: un comando 'SpecBox: Revert last migration' restaura desde el .bak mas reciente. Test: migra, revierte y asserta que el settings.local.json vuelve al estado original byte-a-byte.

- **Estado:** ⬜ pendiente

### AC-04

La auto-migracion respeta el gate de acciones destructivas inviolables: mover/transformar datos de tracking (no solo reconfigurar transporte) NO se auto-ejecuta; se propone con confirmacion explicita. Test: un plan que incluye movimiento de datos exige confirmacion, mientras que uno que solo reconfigura transporte no.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
