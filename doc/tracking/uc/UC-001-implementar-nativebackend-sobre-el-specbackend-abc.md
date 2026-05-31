---
id: UC-101
ordinal: UC-001
title: Implementar NativeBackend sobre el SpecBackend ABC
parent_us: US-NATIVE-BACKEND
status: done
actor: Engine
hours: 16
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-101 — Implementar NativeBackend sobre el SpecBackend ABC

> **US padre:** [US-NATIVE-BACKEND](../us/US-01-specbox-para-equipos-sobre-postgres-nativo.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

NativeBackend implementa los ~30 metodos abstractos de SpecBackend; un test de conformidad ejecuta la misma suite de contrato que pasa FreeformBackend y termina en verde para NativeBackend.

- **Estado:** ✅ cumplido
- **Evidencia:** tests/test_native_backend_conformance.py: 11 tests de contrato × [freeform,native] en verde.

### AC-02

Las escrituras usan un pool asyncpg inicializado al arrancar el MCP; 50 ops CRUD concurrentes no agotan el pool ni dejan conexiones colgadas (verificado contando conexiones en pg_stat_activity antes y despues).

- **Estado:** ✅ cumplido
- **Evidencia:** test_concurrency_50_ops: 50 ops sin fuga de conexiones (pg_stat_activity).

### AC-03

Cada fila US/UC/AC tiene columna version (entero) que se incrementa en cada UPDATE; un UPDATE con version distinta a la almacenada es rechazado con STALE_VERSION y no muta la fila.

- **Estado:** ✅ cumplido
- **Evidencia:** test_optimistic_version_increment: version+1, STALE_VERSION rechaza fila stale.

### AC-06

La Sala de Maquinas (get_sala_de_maquinas / get_all_projects_overview) lista los proyectos en Postgres junto a los de otros backends, sin escanear el filesystem.

- **Estado:** ✅ cumplido
- **Evidencia:** Satisfecho por diseño (Sala de Máquinas vía heartbeat→registry).

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
