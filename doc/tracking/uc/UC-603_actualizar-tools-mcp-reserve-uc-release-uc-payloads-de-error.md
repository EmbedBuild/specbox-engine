---
id: UC-603
title: "Actualizar tools MCP: reserve_uc, release_uc, payloads de error y meta heredada"
parent_us: US-CLAIM-RENAME
status: review
actor: Engine
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-603 — Actualizar tools MCP: reserve_uc, release_uc, payloads de error y meta heredada

> **US padre:** [US-CLAIM-RENAME](../us/US-CLAIM-RENAME_renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

**User Story:** US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
**Actor:** Engine
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [AC-01] La tool MCP `reserve_uc` está registrada (verificable vía `list_tools` del MCP) con descripción que menciona "Reservar" y "NOT_RESERVATION_OWNER". Llamarla devuelve payload con claves `code in {RESERVED, ALREADY_RESERVED}`, `reserved_at` (no `claimed_at`), y `summary` que contiene la palabra "reservado".
- AC-02: [AC-02] Cuando `reserve_uc(UC-X)` colisiona con una reserva existente de otro dev, el payload devuelto tiene `code="ALREADY_RESERVED"` y campos `{owner, reserved_at, branch}`; el cliente NO recibe la palabra `claim` en ningún campo (verificado por test que hace assert sobre las claves del dict).
- AC-03: [AC-03] `release_uc(UC-X)` ejecutado por un dev que no es el dueño devuelve `code="NOT_RESERVATION_OWNER"`, no `NOT_CLAIM_OWNER`. El test `test_coordination_claims.py::test_release_by_non_owner_rejected` (renombrado por UC-605) verifica el nuevo código.

## Contexto

## Acceptance Criteria

### AC-01

[AC-01] La tool MCP `reserve_uc` está registrada (verificable vía `list_tools` del MCP) con descripción que menciona "Reservar" y "NOT_RESERVATION_OWNER". Llamarla devuelve payload con claves `code in {RESERVED, ALREADY_RESERVED}`, `reserved_at` (no `claimed_at`), y `summary` que contiene la palabra "reservado".

- **Estado:** ✅ cumplido

### AC-02

[AC-02] Cuando `reserve_uc(UC-X)` colisiona con una reserva existente de otro dev, el payload devuelto tiene `code="ALREADY_RESERVED"` y campos `{owner, reserved_at, branch}`; el cliente NO recibe la palabra `claim` en ningún campo (verificado por test que hace assert sobre las claves del dict).

- **Estado:** ✅ cumplido

### AC-03

[AC-03] `release_uc(UC-X)` ejecutado por un dev que no es el dueño devuelve `code="NOT_RESERVATION_OWNER"`, no `NOT_CLAIM_OWNER`. El test `test_coordination_claims.py::test_release_by_non_owner_rejected` (renombrado por UC-605) verifica el nuevo código.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
