---
id: UC-607
ordinal: UC-034
title: "Coordinación cross-repo: ventana de release v5.35.0 + heads-up Control Panel"
parent_us: US-CLAIM-RENAME
status: review
actor: Owner
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-607 — Coordinación cross-repo: ventana de release v5.35.0 + heads-up Control Panel

> **US padre:** [US-CLAIM-RENAME](../us/US-05-renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

**User Story:** US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
**Actor:** Owner
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [AC-01] Tag git `v5.35.0` existe en `specbox-engine`, su changelog menciona el rename y los alias deprecados, y la imagen Docker desplegada en el VPS responde a `get_engine_version` con `5.35.0`.
- AC-02: [AC-02] La migración `0007` está aplicada en la Supabase `SpecBox-DataBase`: `mcp__supabase__execute_sql` con `SELECT to_regclass('uc_reservations'), to_regclass('uc_claims')` devuelve `('uc_reservations', NULL)`.
- AC-03: [AC-03] Un issue de coordinación en GitHub (repo `specbox-engine`) titulado "v5.35.0 — claim→reservation rename: cross-repo coordination" enumera los pasos del Control Panel pendientes (UC-608..UC-612), está cerrado, y referenciado desde el último commit de la US.

## Contexto

## Acceptance Criteria

### AC-01

[AC-01] Tag git `v5.35.0` existe en `specbox-engine`, su changelog menciona el rename y los alias deprecados, y la imagen Docker desplegada en el VPS responde a `get_engine_version` con `5.35.0`.

- **Estado:** ⬜ pendiente

### AC-02

[AC-02] La migración `0007` está aplicada en la Supabase `SpecBox-DataBase`: `mcp__supabase__execute_sql` con `SELECT to_regclass('uc_reservations'), to_regclass('uc_claims')` devuelve `('uc_reservations', NULL)`.

- **Estado:** ⬜ pendiente

### AC-03

[AC-03] Un issue de coordinación en GitHub (repo `specbox-engine`) titulado "v5.35.0 — claim→reservation rename: cross-repo coordination" enumera los pasos del Control Panel pendientes (UC-608..UC-612), está cerrado, y referenciado desde el último commit de la US.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
