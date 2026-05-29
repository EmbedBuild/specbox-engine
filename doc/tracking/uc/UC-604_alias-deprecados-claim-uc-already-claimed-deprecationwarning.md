---
id: UC-604
title: Alias deprecados claim_uc/ALREADY_CLAIMED + DeprecationWarning para v5.35-v5.36
parent_us: US-CLAIM-RENAME
status: review
actor: Engine
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-604 — Alias deprecados claim_uc/ALREADY_CLAIMED + DeprecationWarning para v5.35-v5.36

> **US padre:** [US-CLAIM-RENAME](../us/US-CLAIM-RENAME_renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

**User Story:** US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
**Actor:** Engine
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [AC-01] La tool MCP `claim_uc` sigue registrada y funcional (llamarla con un UC libre lo reserva correctamente) y su `description` empieza con la cadena literal `[DEPRECATED desde v5.35.0 — usa reserve_uc. Se elimina en v5.37.0]`.
- AC-02: [AC-02] El payload de respuesta de `claim_uc` durante el periodo deprecado contiene **simultáneamente** las claves nuevas (`reserved_at`, `code: "RESERVED"` o `"ALREADY_RESERVED"`) Y los aliases viejos (`claimed_at` con el mismo valor que `reserved_at`, `legacy_code: "CLAIMED"` o `"ALREADY_CLAIMED"`). Verificado por test que asserta presencia de ambos juegos de claves.
- AC-03: [AC-03] Una llamada a `claim_uc` emite exactamente un `DeprecationWarning` (capturable con `pytest.warns(DeprecationWarning)`) y registra una línea estructurada en el logger del MCP con `event="deprecated_tool_called"`, `tool="claim_uc"`, `since_version="v5.35.0"`, `remove_in_version="v5.37.0"`.
- AC-04: [AC-04] `reserve_uc` (tool nueva) NO emite DeprecationWarning ni añade los aliases viejos al payload — el campo `claimed_at` no aparece en su respuesta.

## Contexto

## Acceptance Criteria

### AC-01

[AC-01] La tool MCP `claim_uc` sigue registrada y funcional (llamarla con un UC libre lo reserva correctamente) y su `description` empieza con la cadena literal `[DEPRECATED desde v5.35.0 — usa reserve_uc. Se elimina en v5.37.0]`.

- **Estado:** ✅ cumplido

### AC-02

[AC-02] El payload de respuesta de `claim_uc` durante el periodo deprecado contiene **simultáneamente** las claves nuevas (`reserved_at`, `code: "RESERVED"` o `"ALREADY_RESERVED"`) Y los aliases viejos (`claimed_at` con el mismo valor que `reserved_at`, `legacy_code: "CLAIMED"` o `"ALREADY_CLAIMED"`). Verificado por test que asserta presencia de ambos juegos de claves.

- **Estado:** ✅ cumplido

### AC-03

[AC-03] Una llamada a `claim_uc` emite exactamente un `DeprecationWarning` (capturable con `pytest.warns(DeprecationWarning)`) y registra una línea estructurada en el logger del MCP con `event="deprecated_tool_called"`, `tool="claim_uc"`, `since_version="v5.35.0"`, `remove_in_version="v5.37.0"`.

- **Estado:** ✅ cumplido

### AC-04

[AC-04] `reserve_uc` (tool nueva) NO emite DeprecationWarning ni añade los aliases viejos al payload — el campo `claimed_at` no aparece en su respuesta.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
