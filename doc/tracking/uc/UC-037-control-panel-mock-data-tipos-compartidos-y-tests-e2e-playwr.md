---
id: UC-610
ordinal: UC-037
title: Control Panel — Mock data, tipos compartidos y tests E2E Playwright
parent_us: US-CLAIM-RENAME
status: review
actor: ControlPanel
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-610 — Control Panel — Mock data, tipos compartidos y tests E2E Playwright

> **US padre:** [US-CLAIM-RENAME](../us/US-05-renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

**User Story:** US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
**Actor:** ControlPanel
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [AC-01] `apps/web/src/lib/mockData.ts` exporta `mockReservations`, `reservationAgeHours`, y `mockProjects[i].active_reservations`; `grep -n 'claim\|Claim' apps/web/src/lib/mockData.ts` devuelve 0 hits.
- AC-02: [AC-02] El test E2E `apps/web/e2e/reservations-active.spec.ts` existe y pasa contra `pnpm dev` local (verificado con `pnpm --filter @specbox-panel/web test:e2e`).
- AC-03: [AC-03] Los tres UCs del tracking del panel (UC-005, UC-114, UC-125) tienen la nota "Renombrado v5.35.0" añadida al final de la descripción, pero el resto del contenido histórico se preserva intacto.

## Contexto

## Acceptance Criteria

### AC-01

[AC-01] `apps/web/src/lib/mockData.ts` exporta `mockReservations`, `reservationAgeHours`, y `mockProjects[i].active_reservations`; `grep -n 'claim\|Claim' apps/web/src/lib/mockData.ts` devuelve 0 hits.

- **Estado:** ⬜ pendiente

### AC-02

[AC-02] El test E2E `apps/web/e2e/reservations-active.spec.ts` existe y pasa contra `pnpm dev` local (verificado con `pnpm --filter @specbox-panel/web test:e2e`).

- **Estado:** ⬜ pendiente

### AC-03

[AC-03] Los tres UCs del tracking del panel (UC-005, UC-114, UC-125) tienen la nota "Renombrado v5.35.0" añadida al final de la descripción, pero el resto del contenido histórico se preserva intacto.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
