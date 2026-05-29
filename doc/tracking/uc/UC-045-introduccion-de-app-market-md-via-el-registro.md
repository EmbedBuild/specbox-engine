---
id: UC-D006
ordinal: UC-045
title: Introducción de app_market.md vía el registro
parent_us: US-D04
status: ready
actor: Engine
hours: 2
owner: Jesús Pérez
created: 2026-05-24
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-D006 — Introducción de app_market.md vía el registro

> **US padre:** [US-D04](../us/US-06-multi-document-canonical-registry-foundation.md)

## Objetivo / Descripción

Una vez existe el registro multi-doc (UC-D005), añadir app_market.md es trivial. Este UC valida que efectivamente lo es: la diff de la PR debe demostrar el cap (1 archivo nuevo + 1 línea modificada + 0 cambios en lógica).

## Acceptance Criteria

### AC-01

[AC-01] Plantilla templates/app_market.md.template existe con las 8 zonas definidas en sección 4.1.1 (ICPs primarios, no-ICPs, JTBDs racionales, JTBDs emocionales, NSM, posicionamiento, anti-features, exportable copy). Todas las zonas manuales llevan marcador status='template-pristine'.

- **Estado:** ⬜ pendiente

### AC-02

[AC-02] Entry añadida en CANONICAL_DOCS con id='app_market', introduced_in='6.0.0', template_path='templates/app_market.md.template', y los event_zone_map para eventos de Discovery (app_market_icp_added, app_market_jtbd_added, nsm_updated).

- **Estado:** ⬜ pendiente

### AC-03

[AC-03] Diff de la PR de UC-D006 muestra: 1 archivo nuevo (template), 1 entry nueva en registry.py, 0 cambios en sync.py / hook / skills. Validado por revisión visual del diff antes de merge.

- **Estado:** ⬜ pendiente

### AC-04

[AC-04] Hook app-docs-sync-guard.mjs corre verde en proyecto v5.35-upgraded-to-v6.0 sin app_market.md rellenado (solo con plantilla pristine). Verificado en test fixture.

- **Estado:** ⬜ pendiente

### AC-05

[AC-05] /app-sync --check reporta 'app_market: template-pristine (introduced_in 6.0.0, project_version_at_onboard 5.33.0, awaiting first /discovery)' como info, no como drift.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
