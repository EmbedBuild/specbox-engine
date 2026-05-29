---
id: UC-622
title: Migrar skills consumidores (/prd, /plan, /visual-setup, /app-sync, /audit, /acceptance-check)
parent_us: US-MCP-PATH-CONTRACT
status: ready
actor: Engine
hours: 4
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-622 — Migrar skills consumidores (/prd, /plan, /visual-setup, /app-sync, /audit, /acceptance-check)

> **US padre:** [US-MCP-PATH-CONTRACT](../us/US-MCP-PATH-CONTRACT_eliminar-deuda-tecnica-de-paths-filesystem-mcp-remoto-en-tod.md)

## Objetivo / Descripción

Cada skill que usa las tools refactorizadas en UC-616..UC-620 se actualiza para construir el bundle de contenido en cliente y pasarlo al MCP. Reuso del helper UC-621.

## Acceptance Criteria

### AC-01

/prd SKILL.md Paso 0 lee bundle (app_prd, app_spec, app_market, discovery_artifact) con el helper y pasa contenido a las tools.

- **Estado:** ⬜ pendiente

### AC-02

/plan SKILL.md actualizado equivalente.

- **Estado:** ⬜ pendiente

### AC-03

/visual-setup SKILL.md actualizado equivalente.

- **Estado:** ⬜ pendiente

### AC-04

/app-sync SKILL.md actualizado equivalente (las 4 subcommands --check/--repair/--review/--rebuild-from-tracking).

- **Estado:** ⬜ pendiente

### AC-05

/audit SKILL.md mueve la ejecución de los 8 analyzers a cliente, genera QualityReport localmente, llama submit_quality_audit.

- **Estado:** ⬜ pendiente

### AC-06

/acceptance-check SKILL.md actualizado.

- **Estado:** ⬜ pendiente

### AC-07

Smoke test manual de cada skill con MCP remoto activo — las 6 skills deben funcionar end-to-end sin tocar filesystem del VPS.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
