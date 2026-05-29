---
id: UC-D002
title: Ejecutar /discovery en modo bootstrap (primer uso en proyecto)
parent_us: US-D01
status: ready
actor: Engine
hours: 8
owner: Jesús Pérez
created: 2026-05-24
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-D002 — Ejecutar /discovery en modo bootstrap (primer uso en proyecto)

> **US padre:** [US-D01](../us/US-D01_discovery-conversational-flow-per-feature.md)

## Objetivo / Descripción

Cuando doc/app/app_market.md está vacío o ausente, /discovery [feature_name] detecta la situación y entra en modo bootstrap: primero completa el nivel producto (ICPs canónicos, JTBDs globales, NSM, posicionamiento), luego desciende al nivel feature.

## Acceptance Criteria

### AC-01

[AC-01] La detección de app_market.md vacío/ausente lanza modo bootstrap automáticamente sin requerir flag explícito. [JR-3.1, JE-3.2]

- **Estado:** ⬜ pendiente

### AC-02

[AC-02] El modo bootstrap muestra mensaje pedagógico inicial: 'Antes de definir esta feature, necesitamos definir para quién es el producto entero. Esto solo se hace una vez por proyecto.' [JE-3.2, JE-3.3]

- **Estado:** ⬜ pendiente

### AC-03

[AC-03] La fase producto completa los 5 bloques esenciales de app_market.md: ICPs primarios, no-ICPs, JTBDs racionales globales, JTBDs emocionales globales, NSM. Los bloques opcionales (posicionamiento, anti-features) se ofrecen pero pueden saltarse. [JR-2.2, JR-3.1]

- **Estado:** ⬜ pendiente

### AC-04

[AC-04] El app_market.md generado incluye sección 'Exportable copy' con extractos pre-formateados para landing, LinkedIn post y elevator pitch, derivados automáticamente de ICPs+JTBDs. [JR-2.2]

- **Estado:** ⬜ pendiente

### AC-05

[AC-05] Tras completar app_market.md, el flujo desciende automáticamente al modo estándar de UC-D001 para la feature solicitada. [JR-1.1]

- **Estado:** ⬜ pendiente

### AC-06

[AC-06] El tiempo total de bootstrap (producto + primera feature) no supera 75 minutos. [JE-1.1, JE-3.3]

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
