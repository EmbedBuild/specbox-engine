---
id: UC-401
ordinal: UC-013
title: Conexion asyncpg al Supabase Pooler (transaction-mode)
parent_us: US-NATIVE-SUPABASE
status: done
actor:
hours: 8
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-401 — Conexion asyncpg al Supabase Pooler (transaction-mode)

> **US padre:** [US-NATIVE-SUPABASE](../us/US-02-migrar-el-native-backend-de-postgres-vps-a-supabase-gestiona.md)

## Objetivo / Descripción

Repuntar server/db/pool.py al Supabase Pooler en transaction-mode. El DSN sigue entrando SOLO por SPECBOX_NATIVE_DSN (Frontera 2 intacta). Resolver el gotcha de PgBouncer transaction-mode con asyncpg y forzar SSL.

## Acceptance Criteria

### AC-24

init_pool/create_pool pasa statement_cache_size=0 a asyncpg; un round-trip de escritura+lectura US/UC contra el Pooler (puerto 6543) no lanza 'prepared statement already exists' ni DuplicatePreparedStatementError tras 2 llamadas consecutivas con el mismo SQL.

- **Estado:** ✅ cumplido

### AC-25

La conexion exige TLS: el DSN incluye sslmode=require (o equivalente) y un intento sin SSL es rechazado; el handshake contra el host Supabase configurado por el operador (db.<PROJECT_REF>.supabase.co o pooler equivalente) se completa.

- **Estado:** ✅ cumplido

### AC-26

SPECBOX_NATIVE_DSN sigue siendo la UNICA fuente de la credencial: pool.py no acepta el DSN por argumento de tool ni por config de sesion (salvo el override de tests ya existente), y el DSN nunca aparece en logs ni en mensajes de error.

- **Estado:** ✅ cumplido

### AC-27

Los limites del pool (min/max_size) se ajustan al limite de conexiones del plan del Pooler; con max_size por encima del limite, el arranque o el primer acquire falla con un error claro que nombra el limite, no un timeout opaco.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
