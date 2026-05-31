---
id: UC-102
ordinal: UC-002
title: Esquema Postgres multi-tenant
parent_us: US-NATIVE-BACKEND
status: done
actor: Engine
hours: 8
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-102 — Esquema Postgres multi-tenant

> **US padre:** [US-NATIVE-BACKEND](../us/US-01-specbox-para-equipos-sobre-postgres-nativo.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-04

Migracion SQL versionada crea projects, user_stories, use_cases, acceptance_criteria con project_id como FK; aplicarla sobre BBDD vacia y re-aplicarla (idempotente) no produce error.

- **Estado:** ✅ cumplido
- **Evidencia:** tests/test_native_schema.py (4 passed against dev Postgres); migración idempotente verificada 2x.

### AC-05

Una consulta de los UCs de project_id=A nunca devuelve filas de project_id=B (test inserta specs en dos proyectos y comprueba aislamiento en cada metodo de lectura).

- **Estado:** ✅ cumplido
- **Evidencia:** tests/test_native_schema.py (4 passed against dev Postgres); migración idempotente verificada 2x.

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
