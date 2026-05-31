---
id: UC-664
ordinal: UC-104
title: Deteccion de configuracion obsoleta (cliente)
parent_us: US-CONN-UPGRADE
status: draft
actor: Client
hours: 5
owner: Jesús Pérez
created: 2026-05-31
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-664 — Deteccion de configuracion obsoleta (cliente)

> **US padre:** [US-CONN-UPGRADE](../us/US-20-actualizacion-robusta-y-pedagogica-consciente-de-la-configur.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

Al activarse tras una actualizacion, la extension lee .claude/settings.local.json + la config MCP y clasifica el estado del cliente en uno de los casos canonicos (FreeForm+Local-obsoleto, FreeForm+Remoto-ya-ok, Trello/Plane-sin-cambios, Native+OAuth-sin-cambios, onboarding-incompleto). Funcion pura detectClientConfigCase(settings, mcpConfig) con test que cubre los 5 casos.

- **Estado:** ⬜ pendiente

### AC-02

La extension envia el caso detectado + la version origen al server via upgrade_project / detect_*_migration_case y recibe un plan de migracion (acciones + diffs propuestos). Test de integracion mock-server que asserta que el plan recibido corresponde al caso.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
