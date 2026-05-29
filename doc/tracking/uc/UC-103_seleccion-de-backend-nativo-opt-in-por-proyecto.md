---
id: UC-103
title: Seleccion de backend Nativo opt-in por proyecto
parent_us: US-NATIVE-BACKEND
status: done
actor: Dev configurando proyecto
hours: 6
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-103 — Seleccion de backend Nativo opt-in por proyecto

> **US padre:** [US-NATIVE-BACKEND](../us/US-NATIVE-BACKEND_specbox-para-equipos-sobre-postgres-nativo.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-07

set_auth_token(backend_type='native') registra el proyecto contra Postgres; detect_project_backend devuelve 'native' cuando specbox.backend_type='native' esta en settings.local.json, con prioridad sobre senales de filesystem.

- **Estado:** ✅ cumplido
- **Evidencia:** tests/test_native_dispatch.py: resolución + store + detect native.

### AC-08

Con backend Nativo, import_spec persiste US/UC/AC en Postgres y list_us/list_uc la recuperan identica (round-trip campo a campo).

- **Estado:** ✅ cumplido
- **Evidencia:** test_round_trip_us_uc_ac: import/list idéntico vía sesión native.

### AC-09

Un proyecto Trello/Plane/FreeForm sigue funcionando sin cambios cuando NativeBackend esta disponible (suite de regresion de los 3 backends en verde).

- **Estado:** ✅ cumplido
- **Evidencia:** test_*_still_resolves: freeform/plane/trello sin regresión.

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
