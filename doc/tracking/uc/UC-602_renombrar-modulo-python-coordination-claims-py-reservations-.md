---
id: UC-602
title: Renombrar módulo Python coordination/claims.py → reservations.py y todas las APIs internas
parent_us: US-CLAIM-RENAME
status: review
actor: Engine
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-602 — Renombrar módulo Python coordination/claims.py → reservations.py y todas las APIs internas

> **US padre:** [US-CLAIM-RENAME](../us/US-CLAIM-RENAME_renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

**User Story:** US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
**Actor:** Engine
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [AC-01] `server/coordination/reservations.py` existe con `UCReservation`, `AlreadyReservedError`, `NotReservationOwnerError`, `reserve_uc`, `get_reservation`, `list_active_reservations`, `reserved_uc_ids_by_others`, `release_uc`, `start_uc_atomic`; `server/coordination/claims.py` ya no existe; `server/coordination/__init__.py` exporta los nuevos nombres y el docstring del paquete se actualiza (`claims` → `reservations`).
- AC-02: [AC-02] El dataclass de la reserva expone `reserved_at` (no `claimed_at`); `to_public()` devuelve `{"uc_id", "developer_id", "reserved_at", "branch"}`. El payload de `AlreadyReservedError.to_payload()` incluye `{"code": "ALREADY_RESERVED", "owner", "reserved_at", "branch"}`.
- AC-03: [AC-03] `grep -rn 'claim\|Claim\|claimed_at' server/ --include="*.py"` no devuelve ninguna línea fuera de `server/tools/coordination.py` (donde viven los alias deprecados del UC-604) — todas las apariciones legítimas son comentarios históricos en docstrings que aclaran la renombrada ("antes llamado claim").

## Contexto

## Acceptance Criteria

### AC-01

[AC-01] `server/coordination/reservations.py` existe con `UCReservation`, `AlreadyReservedError`, `NotReservationOwnerError`, `reserve_uc`, `get_reservation`, `list_active_reservations`, `reserved_uc_ids_by_others`, `release_uc`, `start_uc_atomic`; `server/coordination/claims.py` ya no existe; `server/coordination/__init__.py` exporta los nuevos nombres y el docstring del paquete se actualiza (`claims` → `reservations`).

- **Estado:** ✅ cumplido

### AC-02

[AC-02] El dataclass de la reserva expone `reserved_at` (no `claimed_at`); `to_public()` devuelve `{"uc_id", "developer_id", "reserved_at", "branch"}`. El payload de `AlreadyReservedError.to_payload()` incluye `{"code": "ALREADY_RESERVED", "owner", "reserved_at", "branch"}`.

- **Estado:** ✅ cumplido

### AC-03

[AC-03] `grep -rn 'claim\|Claim\|claimed_at' server/ --include="*.py"` no devuelve ninguna línea fuera de `server/tools/coordination.py` (donde viven los alias deprecados del UC-604) — todas las apariciones legítimas son comentarios históricos en docstrings que aclaran la renombrada ("antes llamado claim").

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
