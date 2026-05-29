---
id: US-CUTOVER-FOLLOWUP
ordinal: US-11
title: Cerrar deuda residual de Sala de Máquinas tras v6.1.0
status: draft
hours: 2.5
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# US-CUTOVER-FOLLOWUP — Cerrar deuda residual de Sala de Máquinas tras v6.1.0

## Como… quiero… para…

> # US-CUTOVER-FOLLOWUP: Cerrar deuda residual de Sala de Máquinas tras v6.1.0
> 
> **Horas estimadas:** 2.5
> **Pantallas:** 
> 
> v6.1.0 'Cloud Cutover' eliminó la Sala de Máquinas pero quedaron 11 residuos en main: tool MCP get_sala_de_maquinas todavía registrada (la pieza más grave — superficie API expuesta), docstrings en 5 módulos Python, 2 hooks Node, 3 skills, 2 canónicos doc/app/, ENGINE_VERSION.yaml features array, .claude/settings.local.json y VSCode extension (comando + setting). Patch release v6.1.1 'Cutover Followup' cierra toda la deuda en una PR squashable. Cero código nuevo, sólo deletes + cleanup de strings. PRD completo en doc/prd/US-CUTOVER-FOLLOWUP_prd.md.

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-633 | [Release v6.1.1 — version bump + CHANGELOG + ADR update](../uc/UC-057-release-v6-1-1-version-bump-changelog-adr-update.md) | ready |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
