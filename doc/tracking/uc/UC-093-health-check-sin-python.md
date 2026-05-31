---
id: UC-003
ordinal: UC-093
title: Health check sin Python
parent_us: US-VSCODE-ZERO-PYTHON
status: done
actor: Owner-operator (ICP-1)
hours: 1.0
owner: Jesús Pérez
created: 2026-05-28
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-003 — Health check sin Python

> **US padre:** [US-VSCODE-ZERO-PYTHON](../us/US-16-onboarding-cero-python-de-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-ZERO-PYTHON: Onboarding cero-Python de la extensión VSCode
**Actor:** Owner-operator (ICP-1)
**Horas estimadas:** 1.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: AC-05: El reporte del Health Check no incluye ninguna fila ni cadena referida a 'Python'; HealthReport no expone el campo python y REQUIRED_PYTHON_VERSION no existe en constants.ts.
- AC-02: AC-06: La status bar, el reporte de onboarding y el status tree no muestran ningún issue ni item relativo a Python.

## Contexto
Eliminar checkPython y el campo python de HealthReport, REQUIRED_PYTHON_VERSION de constants, y todas las referencias derivadas en statusbar/onboard/status-tree.

## Acceptance Criteria

### AC-01

AC-05: El reporte del Health Check no incluye ninguna fila ni cadena referida a 'Python'; HealthReport no expone el campo python y REQUIRED_PYTHON_VERSION no existe en constants.ts.

- **Estado:** ✅ cumplido

### AC-02

AC-06: La status bar, el reporte de onboarding y el status tree no muestran ningún issue ni item relativo a Python.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
