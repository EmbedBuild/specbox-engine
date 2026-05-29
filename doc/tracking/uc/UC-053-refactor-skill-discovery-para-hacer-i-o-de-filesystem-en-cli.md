---
id: UC-615
ordinal: UC-053
title: Refactor skill /discovery para hacer I/O de filesystem en cliente
parent_us: US-MCP-PATH-CONTRACT
status: ready
actor: Engine
hours: 3
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-615 — Refactor skill /discovery para hacer I/O de filesystem en cliente

> **US padre:** [US-MCP-PATH-CONTRACT](../us/US-10-eliminar-deuda-tecnica-de-paths-filesystem-mcp-remoto-en-tod.md)

## Objetivo / Descripción

El skill .claude/skills/discovery/SKILL.md cambia de orquestador-remoto a orquestador-cliente. El skill ahora: (1) lee app_market.md + artifact previo con Read en cliente, (2) llama tools v6.0 con contenido, (3) escribe artifact resultante con Write en cliente. El MCP no toca filesystem.

## Acceptance Criteria

### AC-01

SKILL.md Paso 0 añade boot-detection que lee doc/app/app_market.md y doc/discovery/<feature>/icp_jtbd.md (si existe) con Read tool antes de cualquier llamada MCP.

- **Estado:** ⬜ pendiente

### AC-02

SKILL.md Paso 0.5 llama start_discovery pasando app_market_content + existing_artifact_content. Recibe skeleton_content. Si status=created, escribe skeleton con Write a doc/discovery/<feature>/icp_jtbd.md.

- **Estado:** ⬜ pendiente

### AC-03

SKILL.md Paso 6 (validation gate) llama validate_discovery_completeness pasando el contenido actual del artifact (re-leído con Read). Itera hasta verdict=READY_FOR_PRD.

- **Estado:** ⬜ pendiente

### AC-04

SKILL.md mantiene el frontmatter context: direct (necesario para Read/Write/Edit en cliente). allowed-tools incluye Read, Write, Edit, Glob, Grep, Bash(git:*), Bash(pwd), mcp__SpecBox-MCP__start_discovery, mcp__SpecBox-MCP__validate_discovery_completeness, mcp__SpecBox-MCP__detect_v60_migration_case.

- **Estado:** ⬜ pendiente

### AC-05

Smoke test manual: ejecutar /discovery test_inheritance_helper en un proyecto con MCP remoto (SPECBOX_ENGINE_MCP_URL set) — debe completar las 3 fases y emitir verdict READY_FOR_PRD sin tocar filesystem del VPS.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
