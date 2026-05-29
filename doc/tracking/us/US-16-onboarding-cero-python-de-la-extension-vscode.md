---
id: US-VSCODE-ZERO-PYTHON
ordinal: US-16
title: Onboarding cero-Python de la extensión VSCode
status: draft
hours: 6.0
owner: Jesús Pérez
created: 2026-05-28
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# US-VSCODE-ZERO-PYTHON — Onboarding cero-Python de la extensión VSCode

## Como… quiero… para…

> # US-VSCODE-ZERO-PYTHON: Onboarding cero-Python de la extensión VSCode
> 
> **Horas estimadas:** 6.0
> **Pantallas:** 
> 
> Eliminar la dependencia de Python del onboarding/actualización de la extensión VSCode. Mata el modo Local del MCP (deja solo Remote, el MCP gratuito del owner), migra Engram de pip/pipx a brew (sigue Required), y purga toda referencia a Python de los artefactos visibles (health check, walkthrough, README EN+ES, package.json, status bar, onboarding, status tree). Discovery: doc/discovery/zero_python_onboarding/icp_jtbd.md. PRD: doc/prd/US-VSCODE-ZERO-PYTHON_prd.md. JTBDs: JR-FZPY.1..4, JE-FZPY.1..2.

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-001 | [Configuración MCP solo-Remote](../uc/UC-091-configuracion-mcp-solo-remote.md) | done |
| UC-002 | [Engram vía brew, sin Python](../uc/UC-092-engram-via-brew-sin-python.md) | done |
| UC-003 | [Health check sin Python](../uc/UC-093-health-check-sin-python.md) | done |
| UC-004 | [Documentación cero-Python](../uc/UC-094-documentacion-cero-python.md) | done |
| UC-005 | [Verificación global cero-Python](../uc/UC-095-verificacion-global-cero-python.md) | done |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
