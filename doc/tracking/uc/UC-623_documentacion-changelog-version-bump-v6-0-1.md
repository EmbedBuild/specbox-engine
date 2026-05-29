---
id: UC-623
title: Documentación + CHANGELOG + version bump v6.0.1
parent_us: US-MCP-PATH-CONTRACT
status: ready
actor: Engine
hours: 2
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-623 — Documentación + CHANGELOG + version bump v6.0.1

> **US padre:** [US-MCP-PATH-CONTRACT](../us/US-MCP-PATH-CONTRACT_eliminar-deuda-tecnica-de-paths-filesystem-mcp-remoto-en-tod.md)

## Objetivo / Descripción

Actualizar docs canonical del engine para reflejar el nuevo contrato MCP path-free. Cerrar la US con un release v6.0.1 hotfix.

## Acceptance Criteria

### AC-01

CLAUDE.md: sección nueva "## MCP Path Contract (v6.0.1)" documenta el patrón content-passing como contract de las @mcp.tool, explica por qué sustituye el patrón v5.29 absolute-path, lista las 17 tools migradas.

- **Estado:** ⬜ pendiente

### AC-02

doc/decisions/mcp_path_contract.md: nueva decisión arquitectural documenta (a) el bug, (b) las 3 opciones consideradas (absolute-path universal, content-passing universal, híbrido), (c) por qué content-passing universal gana, (d) trade-offs (cliente hace más I/O, MCP más simple y testeable).

- **Estado:** ⬜ pendiente

### AC-03

CHANGELOG.md: entry v6.0.1 "MCP Path Contract — elimina deuda técnica filesystem-vs-remote en 17 tools cat A".

- **Estado:** ⬜ pendiente

### AC-04

ENGINE_VERSION.yaml bump a 6.0.1.

- **Estado:** ⬜ pendiente

### AC-05

pyproject.toml bump.

- **Estado:** ⬜ pendiente

### AC-06

Tag git v6.0.1 creado al cierre.

- **Estado:** ⬜ pendiente

### AC-07

PR final agrupa todos los UCs (614–623) en un solo PR de hotfix con squash merge.

- **Estado:** ⬜ pendiente

### AC-08

Script de cleanup en .quality/scripts/cleanup-mcp-phantom-fs.sh borra basura acumulada en filesystem del VPS pre-v6.0.1 (doc/discovery/* huérfanos, doc/app/app_market.md fantasma creados por API rota). Ejecutable manualmente post-deploy via SSH al VPS. Documentado en CHANGELOG y plan.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
