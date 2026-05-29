---
id: UC-001
ordinal: UC-091
title: Configuración MCP solo-Remote
parent_us: US-VSCODE-ZERO-PYTHON
status: done
actor: Dev solo con Claude Code (ICP-2)
hours: 1.5
owner: Jesús Pérez
created: 2026-05-28
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-001 — Configuración MCP solo-Remote

> **US padre:** [US-VSCODE-ZERO-PYTHON](../us/US-16-onboarding-cero-python-de-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-ZERO-PYTHON: Onboarding cero-Python de la extensión VSCode
**Actor:** Dev solo con Claude Code (ICP-2)
**Horas estimadas:** 1.5
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: AC-01: Al ejecutar 'Configure MCP Servers', la extensión escribe la config del servidor SpecBox-MCP apuntando a npx mcp-remote https://mcp-specbox-engine.jpsdeveloper.com/mcp SIN mostrar ninguna QuickPick de elección local-vs-remoto.
- AC-02: AC-02: vscode-extension/src/mcp.ts no contiene ninguna rama que construya serverConfig basado en 'uv run' o 'python -m server.server', ni ninguna llamada a commandExists('python3')/commandExists('python').

## Contexto
Eliminar la QuickPick local/remote y todo el branch de modo local en configureSpecbox (mcp.ts). La extensión configura Remote directamente.

## Acceptance Criteria

### AC-01

AC-01: Al ejecutar 'Configure MCP Servers', la extensión escribe la config del servidor SpecBox-MCP apuntando a npx mcp-remote https://mcp-specbox-engine.jpsdeveloper.com/mcp SIN mostrar ninguna QuickPick de elección local-vs-remoto.

- **Estado:** ✅ cumplido

### AC-02

AC-02: vscode-extension/src/mcp.ts no contiene ninguna rama que construya serverConfig basado en 'uv run' o 'python -m server.server', ni ninguna llamada a commandExists('python3')/commandExists('python').

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
