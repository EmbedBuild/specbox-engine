---
id: UC-660
ordinal: UC-100
title: Tools de mutacion FreeForm con content-passing
parent_us: US-CONN-TRANSPORT
status: draft
actor: Engine
hours: 10
owner: Jesús Pérez
created: 2026-05-31
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-660 — Tools de mutacion FreeForm con content-passing

> **US padre:** [US-CONN-TRANSPORT](../us/US-18-freeform-operativo-sin-python-via-content-passing.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

Cada tool de mutacion FreeForm (add_uc, add_ac, mark_ac, update_uc, import_spec, complete_uc, start_uc) acepta el contenido de items.json como parametro string y devuelve el items.json mutado como string, sin que el server llame Path(...).resolve() contra un filesystem ajeno. Test: ejecuta cada tool con SPECBOX_ENGINE_MCP_URL set y un items.json inyectado por string, y asserta que el resultado refleja la mutacion sin tocar el FS del server.

- **Estado:** ⬜ pendiente

### AC-02

Con el MCP en modo remoto, una secuencia add_uc -> mark_ac -> find_next_uc sobre un items.json de cliente pasado por content-passing devuelve resultados correctos (el UC aparece, el AC queda marcado, el siguiente UC es el esperado), replicando el flujo que hoy falla con 'esto no existe'.

- **Estado:** ⬜ pendiente

### AC-03

Las tools de mutacion FreeForm migradas conservan compatibilidad in-process (callers Python del propio server) via helper *_impl(path) preservado, patron v6.0.1. Test: los tests existentes de FreeForm in-process siguen verdes sin modificacion.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
