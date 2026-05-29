---
id: UC-616
title: Refactor app_docs.py (read_app_docs_tool + get_inheritable_values_tool)
parent_us: US-MCP-PATH-CONTRACT
status: ready
actor: Engine
hours: 3
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-616 — Refactor app_docs.py (read_app_docs_tool + get_inheritable_values_tool)

> **US padre:** [US-MCP-PATH-CONTRACT](../us/US-MCP-PATH-CONTRACT_eliminar-deuda-tecnica-de-paths-filesystem-mcp-remoto-en-tod.md)

## Objetivo / Descripción

Las 2 tools del módulo app_docs.py se refactorizan a content-passing. Helpers internos read_app_docs() y get_inheritable_values() en server/app_docs/canonical.py pueden seguir operando sobre Path para usos internos del MCP (e.g. validators del state registry) pero las @mcp.tool wrappers cambian.

## Acceptance Criteria

### AC-01

read_app_docs_tool(app_prd_content: str|None, app_spec_content: str|None, app_market_content: str|None) devuelve dict con zones parsed por documento. NO lee filesystem.

- **Estado:** ⬜ pendiente

### AC-02

get_inheritable_values_tool(app_spec_content: str) devuelve dict con valores inheritable (stack, brand, naming, decisiones canonical). NO lee filesystem.

- **Estado:** ⬜ pendiente

### AC-03

Helpers internos (no @mcp.tool) read_app_docs(project_path) y get_inheritable_values(project_path) permanecen sin cambios para callers internos del MCP que viven en el mismo proceso (CWD coherent).

- **Estado:** ⬜ pendiente

### AC-04

Tests: tests/test_app_docs_content_api.py cubre las 2 tools con docs completos, vacíos, malformados.

- **Estado:** ⬜ pendiente

### AC-05

Skills que las usaban (/prd, /plan, /visual-setup, /app-sync) consumen ahora la nueva API — se actualizan en UC-622.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
