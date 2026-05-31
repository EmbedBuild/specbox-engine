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

- **Estado:** ⬜ pendiente

### AC-02

Las skills que mutan FreeForm (/prd, /implement, /feedback en su ruta de tracking) usan el bridge en lugar de pasar paths al server. Verificable: grep en .claude/skills/ no encuentra llamadas a tools de mutacion FreeForm con project_path como ruta de filesystem del server.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
