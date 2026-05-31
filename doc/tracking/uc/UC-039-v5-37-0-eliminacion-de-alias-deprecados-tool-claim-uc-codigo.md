---
id: UC-612
ordinal: UC-039
title: "v5.37.0: eliminación de alias deprecados (tool claim_uc, código ALREADY_CLAIMED, campo claimed_at)"
parent_us: US-CLAIM-RENAME
status: ready
actor: Engine
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-612 — v5.37.0: eliminación de alias deprecados (tool claim_uc, código ALREADY_CLAIMED, campo claimed_at)

> **US padre:** [US-CLAIM-RENAME](../us/US-05-renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

**User Story:** US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
**Actor:** Engine
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [AC-01] Llamar la tool MCP `claim_uc` desde un cliente devuelve error de tool no registrada (`UnknownToolError` o equivalente del transporte MCP). Solo `reserve_uc` y `release_uc` están en el `list_tools`.
- AC-02: [AC-02] El payload de `reserve_uc` NO contiene las claves `claimed_at` ni `legacy_code` — verificado con assertion `assert "claimed_at" not in payload`.
- AC-03: [AC-03] `grep -rn 'claim\|Claim' server/ apps/web/src/ packages/shared/src/ apps/api/src/` (ambos repos) devuelve 0 hits excepto comentarios históricos explícitos que mencionan el término entre comillas como referencia.
- AC-04: [AC-04] El tag v5.37.0 del engine existe y su changelog menciona "Eliminación de alias `claim_uc`, código `ALREADY_CLAIMED` y campo `claimed_at` deprecados desde v5.35.0".

## Contexto

## Acceptance Criteria

### AC-01

[AC-01] Llamar la tool MCP `claim_uc` desde un cliente devuelve error de tool no registrada (`UnknownToolError` o equivalente del transporte MCP). Solo `reserve_uc` y `release_uc` están en el `list_tools`.

- **Estado:** ⬜ pendiente

### AC-02

[AC-02] El payload de `reserve_uc` NO contiene las claves `claimed_at` ni `legacy_code` — verificado con assertion `assert "claimed_at" not in payload`.

- **Estado:** ⬜ pendiente

### AC-03

[AC-03] `grep -rn 'claim\|Claim' server/ apps/web/src/ packages/shared/src/ apps/api/src/` (ambos repos) devuelve 0 hits excepto comentarios históricos explícitos que mencionan el término entre comillas como referencia.

- **Estado:** ⬜ pendiente

### AC-04

[AC-04] El tag v5.37.0 del engine existe y su changelog menciona "Eliminación de alias `claim_uc`, código `ALREADY_CLAIMED` y campo `claimed_at` deprecados desde v5.35.0".

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
