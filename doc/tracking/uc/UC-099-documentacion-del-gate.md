---
id: UC-709
ordinal: UC-099
title: Documentación del gate
parent_us: US-VSCODE-PREREQ-GATE
status: done
actor: Owner-operator (ICP-1)
hours: 1.0
owner: Jesús Pérez
created: 2026-05-28
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-709 — Documentación del gate

> **US padre:** [US-VSCODE-PREREQ-GATE](../us/US-18-gate-de-prerequisitos-de-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-PREREQ-GATE: Gate de prerequisitos de la extensión VSCode
**Actor:** Owner-operator (ICP-1)
**Horas estimadas:** 1.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: El walkthrough (step-prerequisites.md) menciona que la extensión avisa automaticamente si falta un requisito y como re-comprobar.
- AC-02: README.md y README.es.md documentan el comando 'SpecBox: Check Prerequisites' en la tabla de comandos.
- AC-03: npm run compile y npm test pasan sin errores tras todos los cambios (incluye tests nuevos de evaluatePrerequisites).

## Contexto
Walkthrough + README reflejan el nuevo gate/comando.

## Acceptance Criteria

### AC-01

El walkthrough (step-prerequisites.md) menciona que la extensión avisa automaticamente si falta un requisito y como re-comprobar.

- **Estado:** ✅ cumplido

### AC-02

README.md y README.es.md documentan el comando 'SpecBox: Check Prerequisites' en la tabla de comandos.

- **Estado:** ✅ cumplido

### AC-03

npm run compile y npm test pasan sin errores tras todos los cambios (incluye tests nuevos de evaluatePrerequisites).

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
