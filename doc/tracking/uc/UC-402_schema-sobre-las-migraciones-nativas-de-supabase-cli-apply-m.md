---
id: UC-402
title: Schema sobre las migraciones nativas de Supabase (CLI/apply_migration)
parent_us: US-NATIVE-SUPABASE
status: done
actor:
hours: 9
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-402 — Schema sobre las migraciones nativas de Supabase (CLI/apply_migration)

> **US padre:** [US-NATIVE-SUPABASE](../us/US-NATIVE-SUPABASE_migrar-el-native-backend-de-postgres-vps-a-supabase-gestiona.md)

## Objetivo / Descripción

Migrar el esquema 0001-0003 (projects, user_stories, use_cases, acceptance_criteria, developers, project_members, uc_claims, branch_registry) al sistema de migraciones de Supabase con ledger supabase_migrations, en lugar del runner casero migrate.py. Las migraciones quedan versionadas y rastreables en el dashboard.

## Acceptance Criteria

### AC-28

El esquema completo (0001-0003) se aplica al proyecto Supabase via apply_migration / supabase db push y queda registrado en el ledger supabase_migrations; list_migrations devuelve las 3 (o sus equivalentes) con su nombre versionado.

- **Estado:** ✅ cumplido

### AC-29

Re-aplicar las migraciones es idempotente: una segunda pasada no falla ni duplica tablas (CREATE ... IF NOT EXISTS se conserva) y el ledger no registra entradas duplicadas para la misma version.

- **Estado:** ✅ cumplido

### AC-30

Tras aplicar, list_tables('public') sobre el proyecto Supabase devuelve projects, user_stories, use_cases, acceptance_criteria, developers, project_members, uc_claims y branch_registry con las columnas y FKs definidas (incluida version INTEGER en US/UC/AC).

- **Estado:** ✅ cumplido

### AC-31

El runner casero migrate.py queda deprecado o restringido a entorno local/tests: la documentacion (CLAUDE.md / plan) indica explicitamente que produccion usa migraciones Supabase, evitando dos fuentes de verdad del schema.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
