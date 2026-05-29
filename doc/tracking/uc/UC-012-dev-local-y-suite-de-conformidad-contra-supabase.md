---
id: UC-405
ordinal: UC-012
title: Dev local y suite de conformidad contra Supabase
parent_us: US-NATIVE-SUPABASE
status: done
actor:
hours: 5
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-405 — Dev local y suite de conformidad contra Supabase

> **US padre:** [US-NATIVE-SUPABASE](../us/US-02-migrar-el-native-backend-de-postgres-vps-a-supabase-gestiona.md)

## Objetivo / Descripción

Adaptar el flujo de desarrollo y la suite de conformidad parametrizada (test_native_backend_conformance.py, test_native_schema.py, test_native_dispatch.py) para que corran contra Supabase (rama de base de datos efimera o stack local de Supabase) sin romper el path no-DB de CI que hoy skipea limpio.

## Acceptance Criteria

### AC-38

Con SPECBOX_NATIVE_DSN apuntando a una base Supabase (branch DB efimera o supabase start local), la suite test_native_backend_conformance.py corre el parametro 'native' (no skipea) y pasa en verde, incluido el round-trip optimistic-version (AC-03).

- **Estado:** ✅ cumplido

### AC-39

Sin SPECBOX_NATIVE_DSN alcanzable, los tests native siguen haciendo skip limpio (no error) — el path no-DB de CI se mantiene verde, preservando el comportamiento actual de skipif(not PG_OK).

- **Estado:** ✅ cumplido

### AC-40

La documentacion de dev (CLAUDE.md / architecture) describe como levantar el entorno Supabase para tests (branch DB o local) y como exportar SPECBOX_NATIVE_DSN, reemplazando la referencia a docker-compose.dev.yml o aclarando su rol residual solo-local.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
