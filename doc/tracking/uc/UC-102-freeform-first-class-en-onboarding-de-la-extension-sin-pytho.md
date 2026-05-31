---
id: UC-662
ordinal: UC-102
title: FreeForm first-class en onboarding de la extension (sin Python)
parent_us: US-CONN-TRANSPORT
status: draft
actor: Client
hours: 5
owner: Jesús Pérez
created: 2026-05-31
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-662 — FreeForm first-class en onboarding de la extension (sin Python)

> **US padre:** [US-CONN-TRANSPORT](../us/US-18-freeform-operativo-sin-python-via-content-passing.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

El onboarding de la extension ofrece FreeForm como opcion operativa de primer nivel junto a Native/Trello; al elegirla, configura el MCP remoto + el bridge sin pedir Python en ningun punto. Test de la extension que simula la eleccion de FreeForm y asserta que el settings.json resultante apunta al remoto y NO contiene referencias a Python/uv/modo Local.

- **Estado:** ⬜ pendiente

### AC-02

Tras elegir FreeForm en el onboarding, el health check / sidebar reporta el backend como operativo (no degraded por falta de modo local). Test: tras configurar FreeForm, evaluatePrerequisites devuelve ready para ese proyecto.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
