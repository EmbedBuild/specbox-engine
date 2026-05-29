---
id: UC-002
ordinal: UC-092
title: Engram vía brew, sin Python
parent_us: US-VSCODE-ZERO-PYTHON
status: done
actor: Dev solo con Claude Code (ICP-2)
hours: 1.0
owner: Jesús Pérez
created: 2026-05-28
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-002 — Engram vía brew, sin Python

> **US padre:** [US-VSCODE-ZERO-PYTHON](../us/US-17-onboarding-cero-python-de-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-ZERO-PYTHON: Onboarding cero-Python de la extensión VSCode
**Actor:** Dev solo con Claude Code (ICP-2)
**Horas estimadas:** 1.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: AC-03: configureEngram ofrece instalar Engram con 'brew install gentleman-programming/tap/engram' y NO con pip install ni pipx install.
- AC-02: AC-04: Cuando brew no está disponible, la extensión muestra un mensaje accionable con la vía de instalación manual de Engram (no pip), sin abortar el resto del onboarding.

## Contexto
Migrar la instalación de Engram de pip/pipx a brew install gentleman-programming/tap/engram. Engram sigue Required. Fallback manual (no pip) si no hay brew.

## Acceptance Criteria

### AC-01

AC-03: configureEngram ofrece instalar Engram con 'brew install gentleman-programming/tap/engram' y NO con pip install ni pipx install.

- **Estado:** ✅ cumplido

### AC-02

AC-04: Cuando brew no está disponible, la extensión muestra un mensaje accionable con la vía de instalación manual de Engram (no pip), sin abortar el resto del onboarding.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
