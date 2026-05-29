---
id: UC-609
ordinal: UC-036
title: "Control Panel — UI: ruta /claims → /reservations, ClaimsPage, sidebar, breadcrumbs, copy"
parent_us: US-CLAIM-RENAME
status: review
actor: ControlPanel
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-609 — Control Panel — UI: ruta /claims → /reservations, ClaimsPage, sidebar, breadcrumbs, copy

> **US padre:** [US-CLAIM-RENAME](../us/US-05-renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

**User Story:** US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
**Actor:** ControlPanel
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [AC-01] Navegar a `https://specbox-controlpanel.embed.build/reservations` (o `pnpm dev` local) renderiza la lista de reservas activas con título `"Reservas activas"`; navegar a `/claims` redirige a `/reservations` automáticamente (301 / Navigate replace).
- AC-02: [AC-02] El sidebar muestra el item `"Reservas"` con el icono renombrado; ningún texto visible en la UI muestra la palabra "claim" o "Claim" o "claims" (verificado con búsqueda manual y con un script `grep -rni 'claim' apps/web/src/` que devuelve 0 hits fuera de comentarios JSDoc que mencionan el rename histórico).
- AC-03: [AC-03] `pnpm --filter @specbox-panel/web test` termina en verde (los tests unitarios y de snapshot se actualizan a los nuevos nombres) y `tsc -b` no reporta errores de tipos.
- AC-04: [AC-04] El componente `<ActivityFeed>` renderiza las dos copias nuevas: "reservó" y "liberó la reserva de" — verificado con un test de snapshot.

## Contexto

## Acceptance Criteria

### AC-01

[AC-01] Navegar a `https://specbox-controlpanel.embed.build/reservations` (o `pnpm dev` local) renderiza la lista de reservas activas con título `"Reservas activas"`; navegar a `/claims` redirige a `/reservations` automáticamente (301 / Navigate replace).

- **Estado:** ⬜ pendiente

### AC-02

[AC-02] El sidebar muestra el item `"Reservas"` con el icono renombrado; ningún texto visible en la UI muestra la palabra "claim" o "Claim" o "claims" (verificado con búsqueda manual y con un script `grep -rni 'claim' apps/web/src/` que devuelve 0 hits fuera de comentarios JSDoc que mencionan el rename histórico).

- **Estado:** ⬜ pendiente

### AC-03

[AC-03] `pnpm --filter @specbox-panel/web test` termina en verde (los tests unitarios y de snapshot se actualizan a los nuevos nombres) y `tsc -b` no reporta errores de tipos.

- **Estado:** ⬜ pendiente

### AC-04

[AC-04] El componente `<ActivityFeed>` renderiza las dos copias nuevas: "reservó" y "liberó la reserva de" — verificado con un test de snapshot.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
