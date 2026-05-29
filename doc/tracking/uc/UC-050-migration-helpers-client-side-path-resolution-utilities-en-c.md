---
id: UC-621
ordinal: UC-050
title: "Migration helpers: client-side path resolution utilities en .claude/hooks/lib/"
parent_us: US-MCP-PATH-CONTRACT
status: ready
actor: Engine
hours: 2
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-621 — Migration helpers: client-side path resolution utilities en .claude/hooks/lib/

> **US padre:** [US-MCP-PATH-CONTRACT](../us/US-10-eliminar-deuda-tecnica-de-paths-filesystem-mcp-remoto-en-tod.md)

## Objetivo / Descripción

Crear helpers reusables en cliente para resolver paths absolutos y leer archivos en bulk antes de llamar tools MCP. Sustituye al hook freeform-path-guard.mjs en pieza universal.

## Acceptance Criteria

### AC-01

Nuevo helper .claude/hooks/lib/mcp-client-io.mjs exporta funciones: resolveProjectRoot() (via git rev-parse), readContentBundle(paths: string[]) (lee paths relativos al root y devuelve {path: content|null}), writeContentBundle(bundle: dict) (escribe bundle de vuelta).

- **Estado:** ⬜ pendiente

### AC-02

Skills /discovery, /prd, /plan, /visual-setup, /app-sync, /onboard, /audit, /acceptance-check importan este helper en lugar de hacer Read/Write ad-hoc.

- **Estado:** ⬜ pendiente

### AC-03

El hook freeform-path-guard.mjs se marca como deprecated (no se elimina hasta v6.1 para no romper proyectos pre-v6.0.1). Doc en CLAUDE.md indica nueva ruta.

- **Estado:** ⬜ pendiente

### AC-04

Tests: tests/test_mcp_client_io.mjs (Node-side) verifica el helper.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
