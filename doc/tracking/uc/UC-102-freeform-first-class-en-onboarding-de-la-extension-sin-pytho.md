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

- **Estado:** ✅ done — `maybeShowOnboarding` ofrece FreeForm equal-weight (PR #82); `configureFreeformBackend` ahora usa el helper puro `buildFreeformProjectSettings` (mcp.ts). 4 tests `mcp.test.mjs`: backend_type=freeform + root absoluto, 0 refs python/uv/local, rechaza root relativo, reusa el endpoint hosted.

### AC-02

Tras elegir FreeForm en el onboarding, el health check / sidebar reporta el backend como operativo (no degraded por falta de modo local). Test: tras configurar FreeForm, evaluatePrerequisites devuelve ready para ese proyecto.

- **Estado:** ✅ done — 2 tests `prerequisites.test.mjs`: proyecto FreeForm configurado → `ready`/`missing:[]`; no existe prerequisito oculto python/local-mode.

## Nota de implementación

El grueso ya lo entregó el PR #82 (`maybeShowOnboarding` ofrece FreeForm como
opción de primer nivel; `configureFreeformBackend` escribe `settings.local.json`
con `backend_type=freeform` + `freeform_root_absolute` y cero Python). UC-662
cierra el AC haciendo la lógica **testeable**: extrae el shape a
`buildFreeformProjectSettings(workspaceRootAbsolute)` (puro, en `mcp.ts`,
exporta también `FREEFORM_ROOT_RELATIVE`), que valida path absoluto (v5.29
BLOCKER). `configureFreeformBackend` lo reutiliza. FreeForm comparte el endpoint
hosted con los demás backends (content-passing vía el bridge UC-660/661), sin
modo local. Suite extensión: 64/64 verde (56 baseline + 8 nuevos).

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
