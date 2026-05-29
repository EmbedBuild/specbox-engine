---
id: UC-707
ordinal: UC-097
title: Gate no bloqueante en el arranque
parent_us: US-VSCODE-PREREQ-GATE
status: done
actor: Dev solo con Claude Code (ICP-2)
hours: 1.0
owner: Jesús Pérez
created: 2026-05-28
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-707 — Gate no bloqueante en el arranque

> **US padre:** [US-VSCODE-PREREQ-GATE](../us/US-17-gate-de-prerequisitos-de-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-PREREQ-GATE: Gate de prerequisitos de la extensión VSCode
**Actor:** Dev solo con Claude Code (ICP-2)
**Horas estimadas:** 1.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: Cuando evaluatePrerequisites devuelve 'degraded' al arrancar, la extensión muestra showWarningMessage (no modal) que enumera los requisitos ausentes e indica explicitamente que SpecBox puede no funcionar correctamente sin ellos.
- AC-02: Cuando verdict='ready' al arrancar, NO se muestra ningún aviso de prerequisitos (silencio).
- AC-03: El gate de arranque nunca lanza excepción no controlada (guard try/catch propio); un fallo no rompe la activacion ni el resto de runStartupTasks.

## Contexto
En runStartupTasks, tras el health check, dispara el gate via showWarningMessage no bloqueante.

## Acceptance Criteria

### AC-01

Cuando evaluatePrerequisites devuelve 'degraded' al arrancar, la extensión muestra showWarningMessage (no modal) que enumera los requisitos ausentes e indica explicitamente que SpecBox puede no funcionar correctamente sin ellos.

- **Estado:** ✅ cumplido

### AC-02

Cuando verdict='ready' al arrancar, NO se muestra ningún aviso de prerequisitos (silencio).

- **Estado:** ✅ cumplido

### AC-03

El gate de arranque nunca lanza excepción no controlada (guard try/catch propio); un fallo no rompe la activacion ni el resto de runStartupTasks.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
