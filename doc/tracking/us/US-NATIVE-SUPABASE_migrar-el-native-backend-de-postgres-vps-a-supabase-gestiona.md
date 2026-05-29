---
id: US-NATIVE-SUPABASE
title: Migrar el Native Backend de Postgres-VPS a Supabase gestionado
status: done
hours: 34
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# US-NATIVE-SUPABASE — Migrar el Native Backend de Postgres-VPS a Supabase gestionado

## Como… quiero… para…

> Como mantenedor de SpecBox, quiero que el Native Backend use una instancia Supabase gestionada (Postgres 17+, region a elegir por el operador) en lugar del Postgres self-hosted del VPS, para externalizar backups/parches/monitorizacion y ganar pooler + dashboard, sin reescribir la identidad de developers (UC-201) ni romper los demas backends (Trello/Plane/FreeForm). Decisiones: conexion via Supabase Pooler transaction-mode (6543, statement_cache_size=0); migraciones via Supabase CLI/apply_migration; identidad propia intacta. Cada operador del MCP gestiona su propia instancia Supabase; el repo es publico y no documenta refs concretos.

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-401 | [Conexion asyncpg al Supabase Pooler (transaction-mode)](../uc/UC-401_conexion-asyncpg-al-supabase-pooler-transaction-mode.md) | done |
| UC-402 | [Schema sobre las migraciones nativas de Supabase (CLI/apply_migration)](../uc/UC-402_schema-sobre-las-migraciones-nativas-de-supabase-cli-apply-m.md) | done |
| UC-403 | [RLS y policies sobre las tablas public (silenciar advisors)](../uc/UC-403_rls-y-policies-sobre-las-tablas-public-silenciar-advisors.md) | done |
| UC-404 | [Gestion y rotacion de la credencial Supabase (Frontera 2)](../uc/UC-404_gestion-y-rotacion-de-la-credencial-supabase-frontera-2.md) | done |
| UC-405 | [Dev local y suite de conformidad contra Supabase](../uc/UC-405_dev-local-y-suite-de-conformidad-contra-supabase.md) | done |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
