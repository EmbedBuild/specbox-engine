---
id: UC-005
ordinal: UC-095
title: Verificación global cero-Python
parent_us: US-VSCODE-ZERO-PYTHON
status: done
actor: Owner-operator (ICP-1)
hours: 1.0
owner: Jesús Pérez
created: 2026-05-28
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-005 — Verificación global cero-Python

> **US padre:** [US-VSCODE-ZERO-PYTHON](../us/US-16-onboarding-cero-python-de-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-ZERO-PYTHON: Onboarding cero-Python de la extensión VSCode
**Actor:** Owner-operator (ICP-1)
**Horas estimadas:** 1.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: AC-10: Un grep case-insensitive de 'python' sobre los artefactos user-facing de vscode-extension/ (src, media/walkthrough, package.json, README*, l10n) devuelve cero resultados user-facing.
- AC-02: AC-11: npm run compile y npm test pasan en vscode-extension/ sin errores tras todos los cambios.

## Contexto
Gate final: grep exhaustivo cero-Python user-facing + compile + tests verdes (incluyendo casos nuevos).

## Acceptance Criteria

### AC-01

AC-10: Un grep case-insensitive de 'python' sobre los artefactos user-facing de vscode-extension/ (src, media/walkthrough, package.json, README*, l10n) devuelve cero resultados user-facing.

- **Estado:** ✅ cumplido

### AC-02

AC-11: npm run compile y npm test pasan en vscode-extension/ sin errores tras todos los cambios.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
