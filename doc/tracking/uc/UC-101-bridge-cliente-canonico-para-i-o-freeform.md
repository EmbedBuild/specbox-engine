---
id: UC-661
ordinal: UC-101
title: Bridge cliente canonico para I/O FreeForm
parent_us: US-CONN-TRANSPORT
status: draft
actor: Client
hours: 6
owner: Jesús Pérez
created: 2026-05-31
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-661 — Bridge cliente canonico para I/O FreeForm

> **US padre:** [US-CONN-TRANSPORT](../us/US-18-freeform-operativo-sin-python-via-content-passing.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

lib/mcp-client-io.mjs expone helpers (readTrackingBundle/writeTrackingBundle o reuso de readContentBundle/writeContentBundle) que las skills FreeForm usan para leer/escribir doc/tracking resolviendo la raiz via git rev-parse --show-toplevel. Test node:test que lee un items.json de fixture y escribe el resultado, con guard de path-traversal activo (rechaza .. y paths absolutos fuera del repo).

- **Estado:** ✅ done — `readTrackingBundle`/`writeTrackingBundle` + `TRACKING_ITEMS_PATH` en `mcp-client-io.mjs`; 21 tests `node:test` verdes (incl. round-trip y guard).

### AC-02

Las skills que mutan FreeForm (/prd, /implement, /feedback en su ruta de tracking) usan el bridge en lugar de pasar paths al server. Verificable: grep en .claude/skills/ no encuentra llamadas a tools de mutacion FreeForm con project_path como ruta de filesystem del server.

- **Estado:** ✅ done — grep confirma 0 llamadas a las 7 tools de mutación FreeForm con project_path/root_path en /prd, /implement, /feedback. Los `project_path` presentes son de tools de lectura ya migradas en v6.0.1 (get_inheritable_values_tool, write_implementation_status), no mutadoras de tracking. El bridge queda como puerta canónica.

## Nota de implementación

`readTrackingBundle()`/`writeTrackingBundle(itemsContent)` son envoltorios finos sobre
`readContentBundle`/`writeContentBundle` (UC-621/v6.0.1) que fijan el path canónico
`doc/tracking/items.json` (constante exportada `TRACKING_ITEMS_PATH`). `readTrackingBundle`
devuelve `"[]"` para un board sin inicializar (en vez de `null`), de modo que el primer
`import_spec`/`add_uc` arranca de un board vacío. Bug latente arreglado de paso:
`readContentBundle`/`writeContentBundle` ignoraban `opts.cwd` al resolver el root
(llamaban `resolveProjectRoot()` sin args) — ahora propagan `opts`.

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
