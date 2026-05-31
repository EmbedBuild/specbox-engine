---
id: UC-704
ordinal: UC-087
title: Walkthrough actualizado + tooltip rico
parent_us: US-VSCODE-DISCOVERABILITY
status: review
actor: Dev nuevo tras Install (ICP-2)
hours: 3.0
owner: Jesús Pérez
created: 2026-05-27
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-704 — Walkthrough actualizado + tooltip rico

> **US padre:** [US-VSCODE-DISCOVERABILITY](../us/US-15-sidebar-de-descubrimiento-y-ayuda-para-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-DISCOVERABILITY: Sidebar de descubrimiento y ayuda para la extensión VSCode
**Actor:** Dev nuevo tras Install (ICP-2)
**Horas estimadas:** 3.0
**Pantallas:** walkthrough specbox.gettingStarted, tooltips del TreeView

## Criterios de Aceptacion
- AC-01: [JR-F.3] El step step-install.md del walkthrough deja de afirmar 'Install 15 skills' — la nueva copy es agnóstica al número: 'Install all SpecBox skills and hooks'.
- AC-02: [JR-F.3] El walkthrough gana un quinto step step-discover-skills con título 'Explore your new skills' + descripción que indica abrir el sidebar SpecBox y hacer click en cualquier skill; incluye command link a 'command:workbench.view.extension.specbox'.
- AC-03: [JR-F.2] Cada item de skill en el TreeView muestra como tooltip la primera frase de 'Qué hace' tomada del mismo source que la ficha. Tooltip legible en <5s (≤120 caracteres en la primera línea).
- AC-04: El package.json declara step-discover-skills y su markdown asociado en vscode-extension/media/walkthrough/step-discover-skills.md; el step pasa el linter de i18n existente.

## Contexto
Walkthrough deja de hardcodear 'Install 15 skills' y gana un quinto step que tour-guía el sidebar. Cada item del TreeView gana tooltip con la primera frase de 'Qué hace'.

## Acceptance Criteria

### AC-01

[JR-F.3] El step step-install.md del walkthrough deja de afirmar 'Install 15 skills' — la nueva copy es agnóstica al número: 'Install all SpecBox skills and hooks'.

- **Estado:** ⬜ pendiente

### AC-02

[JR-F.3] El walkthrough gana un quinto step step-discover-skills con título 'Explore your new skills' + descripción que indica abrir el sidebar SpecBox y hacer click en cualquier skill; incluye command link a 'command:workbench.view.extension.specbox'.

- **Estado:** ⬜ pendiente

### AC-03

[JR-F.2] Cada item de skill en el TreeView muestra como tooltip la primera frase de 'Qué hace' tomada del mismo source que la ficha. Tooltip legible en <5s (≤120 caracteres en la primera línea).

- **Estado:** ⬜ pendiente

### AC-04

El package.json declara step-discover-skills y su markdown asociado en vscode-extension/media/walkthrough/step-discover-skills.md; el step pasa el linter de i18n existente.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
