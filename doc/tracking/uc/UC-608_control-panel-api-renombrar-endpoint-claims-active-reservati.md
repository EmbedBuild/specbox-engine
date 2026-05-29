---
id: UC-608
title: "Control Panel — API: renombrar endpoint /claims/active → /reservations/active y schemas"
parent_us: US-CLAIM-RENAME
status: review
actor: ControlPanel
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-608 — Control Panel — API: renombrar endpoint /claims/active → /reservations/active y schemas

> **US padre:** [US-CLAIM-RENAME](../us/US-CLAIM-RENAME_renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

**User Story:** US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
**Actor:** ControlPanel
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [AC-01] `GET /api/v1/reservations/active` responde 200 con array de objetos `{project_id, uc_id, developer_id, branch, reserved_at, claimed_at}` (ambas fechas idénticas durante la ventana de compatibilidad). `GET /api/v1/claims/active` ya no existe (404) o redirige 301 a `/reservations/active`.
- AC-02: [AC-02] En `packages/shared/src/`, el tipo `ReservationRow` está exportado con todos los campos en su forma nueva; el alias `ClaimRow` está marcado `@deprecated` y reexporta el mismo tipo (verificable con `tsc --noEmit` y assertion `expectType<ReservationRow>({} as ClaimRow)`).
- AC-03: [AC-03] La consulta SQL en el plugin pg de la API selecciona desde `uc_reservations` (verificado con un test de integración o un grep `'FROM uc_claims'` que devuelve 0 hits en `apps/api/src/`).

## Contexto

## Acceptance Criteria

### AC-01

[AC-01] `GET /api/v1/reservations/active` responde 200 con array de objetos `{project_id, uc_id, developer_id, branch, reserved_at, claimed_at}` (ambas fechas idénticas durante la ventana de compatibilidad). `GET /api/v1/claims/active` ya no existe (404) o redirige 301 a `/reservations/active`.

- **Estado:** ⬜ pendiente

### AC-02

[AC-02] En `packages/shared/src/`, el tipo `ReservationRow` está exportado con todos los campos en su forma nueva; el alias `ClaimRow` está marcado `@deprecated` y reexporta el mismo tipo (verificable con `tsc --noEmit` y assertion `expectType<ReservationRow>({} as ClaimRow)`).

- **Estado:** ⬜ pendiente

### AC-03

[AC-03] La consulta SQL en el plugin pg de la API selecciona desde `uc_reservations` (verificado con un test de integración o un grep `'FROM uc_claims'` que devuelve 0 hits en `apps/api/src/`).

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
