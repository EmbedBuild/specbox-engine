---
id: UC-601
ordinal: UC-028
title: "Migración SQL: renombrar uc_claims → uc_reservations en specbox-engine"
parent_us: US-CLAIM-RENAME
status: review
actor: Engine
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-601 — Migración SQL: renombrar uc_claims → uc_reservations en specbox-engine

> **US padre:** [US-CLAIM-RENAME](../us/US-05-renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

**User Story:** US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
**Actor:** Engine
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [AC-01] La migración `0007_rename_claims_to_reservations.sql` existe, es idempotente (re-aplicarla dos veces no falla), y al aplicarse renombra `uc_claims` → `uc_reservations`, `claimed_at` → `reserved_at`, y el índice de developer_id; las filas pre-existentes se conservan (verificado insertando una fila antes, aplicando la migración, y haciendo SELECT que la recupere con los nuevos nombres).
- AC-02: [AC-02] Tras aplicar la migración, `psql \d uc_reservations` muestra la tabla con la PK `(project_id, uc_id)`, FKs ON DELETE CASCADE hacia `projects(project_id)` y `developers(developer_id)`, y la columna `reserved_at TIMESTAMPTZ NOT NULL DEFAULT now()`. La tabla `uc_claims` ya no existe (`SELECT to_regclass('uc_claims')` devuelve NULL).
- AC-03: [AC-03] La migración puede aplicarse a un Postgres dev local levantado desde cero (sin filas previas) y a un Postgres con datos pre-migración sin warnings ni errores.

## Contexto

## Acceptance Criteria

### AC-01

[AC-01] La migración `0007_rename_claims_to_reservations.sql` existe, es idempotente (re-aplicarla dos veces no falla), y al aplicarse renombra `uc_claims` → `uc_reservations`, `claimed_at` → `reserved_at`, y el índice de developer_id; las filas pre-existentes se conservan (verificado insertando una fila antes, aplicando la migración, y haciendo SELECT que la recupere con los nuevos nombres).

- **Estado:** ✅ cumplido

### AC-02

[AC-02] Tras aplicar la migración, `psql \d uc_reservations` muestra la tabla con la PK `(project_id, uc_id)`, FKs ON DELETE CASCADE hacia `projects(project_id)` y `developers(developer_id)`, y la columna `reserved_at TIMESTAMPTZ NOT NULL DEFAULT now()`. La tabla `uc_claims` ya no existe (`SELECT to_regclass('uc_claims')` devuelve NULL).

- **Estado:** ✅ cumplido

### AC-03

[AC-03] La migración puede aplicarse a un Postgres dev local levantado desde cero (sin filas previas) y a un Postgres con datos pre-migración sin warnings ni errores.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
