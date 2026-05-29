---
id: UC-708
ordinal: UC-098
title: Comando Check Prerequisites a demanda
parent_us: US-VSCODE-PREREQ-GATE
status: done
actor: Owner-operator (ICP-1)
hours: 1.0
owner: Jesús Pérez
created: 2026-05-28
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-708 — Comando Check Prerequisites a demanda

> **US padre:** [US-VSCODE-PREREQ-GATE](../us/US-18-gate-de-prerequisitos-de-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-PREREQ-GATE: Gate de prerequisitos de la extensión VSCode
**Actor:** Owner-operator (ICP-1)
**Horas estimadas:** 1.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: Existe el comando specbox.checkPrerequisites registrado y declarado en package.json con titulo 'SpecBox: Check Prerequisites'.
- AC-02: Al invocarlo con todo OK muestra mensaje informativo de entorno listo; con requisitos ausentes muestra el mismo gate accionable que el de arranque.

## Contexto
Comando specbox.checkPrerequisites para re-evaluar a demanda.

## Acceptance Criteria

### AC-01

Existe el comando specbox.checkPrerequisites registrado y declarado en package.json con titulo 'SpecBox: Check Prerequisites'.

- **Estado:** ✅ cumplido

### AC-02

Al invocarlo con todo OK muestra mensaje informativo de entorno listo; con requisitos ausentes muestra el mismo gate accionable que el de arranque.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
