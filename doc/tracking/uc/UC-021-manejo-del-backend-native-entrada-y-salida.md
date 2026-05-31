---
id: UC-803
ordinal: UC-021
title: Manejo del backend Native (entrada y salida)
parent_us: US-BACKEND-SWITCH
status: done
actor: Engine
hours: 10
owner: Jesús Pérez
created: 2026-05-22
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-803 — Manejo del backend Native (entrada y salida)

> **US padre:** [US-BACKEND-SWITCH](../us/US-03-cambio-guiado-de-backend-entre-los-4-freeform-trello-plane-n.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

Native -> single-user migra avance completo (US/UC/AC con estado, comentarios) y descarta claims/identidad/branches, listandolos en seccion discarded_native_state del reporte con conteo; verificado migrando Native con >=1 claim activo.

- **Estado:** ⬜ pendiente

### AC-02

Cualquier backend -> Native siembra expected_version=1 y asocia identidad del developer actual (whoami/token) en cada US/UC; verificado leyendo en Postgres expected_version=1 y developer_id no nulo.

- **Estado:** ⬜ pendiente

### AC-03

El DSN de Postgres nunca se solicita ni persiste en sesion ni disco; acceso solo via env SPECBOX_NATIVE_DSN (Frontier 2), verificado con grep del DSN en todos los archivos de salida = 0 coincidencias.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
