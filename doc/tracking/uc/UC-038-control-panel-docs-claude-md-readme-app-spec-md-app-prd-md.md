---
id: UC-611
ordinal: UC-038
title: Control Panel — Docs (CLAUDE.md, README, app_spec.md, app_prd.md)
parent_us: US-CLAIM-RENAME
status: review
actor: ControlPanel
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-611 — Control Panel — Docs (CLAUDE.md, README, app_spec.md, app_prd.md)

> **US padre:** [US-CLAIM-RENAME](../us/US-05-renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

**User Story:** US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
**Actor:** ControlPanel
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [AC-01] `grep -rn 'claim\|Claim' README.md CLAUDE.md doc/app/app_spec.md` (en el repo del Control Panel) devuelve 0 hits, excepto la nota explícita del rename histórico que menciona el término entre comillas.
- AC-02: [AC-02] `doc/app/app_spec.md` del Control Panel tiene en `canonical_decisions` el append del rename con fecha exacta y referencia a v5.35.0 del engine.
- AC-03: [AC-03] El item de tracking del Control Panel para esta US del engine se crea como `US-CLAIM-RENAME-PANEL-MIRROR` (espejo no autoritativo) con un solo UC `UC-PANEL-MIRROR-RENAME` que apunta a los UCs reales 608-611 de este tracking, para que el dashboard del panel los muestre cuando alguien filtra por 'todo lo del panel'.

## Contexto

## Acceptance Criteria

### AC-01

[AC-01] `grep -rn 'claim\|Claim' README.md CLAUDE.md doc/app/app_spec.md` (en el repo del Control Panel) devuelve 0 hits, excepto la nota explícita del rename histórico que menciona el término entre comillas.

- **Estado:** ⬜ pendiente

### AC-02

[AC-02] `doc/app/app_spec.md` del Control Panel tiene en `canonical_decisions` el append del rename con fecha exacta y referencia a v5.35.0 del engine.

- **Estado:** ⬜ pendiente

### AC-03

[AC-03] El item de tracking del Control Panel para esta US del engine se crea como `US-CLAIM-RENAME-PANEL-MIRROR` (espejo no autoritativo) con un solo UC `UC-PANEL-MIRROR-RENAME` que apunta a los UCs reales 608-611 de este tracking, para que el dashboard del panel los muestre cuando alguien filtra por 'todo lo del panel'.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
