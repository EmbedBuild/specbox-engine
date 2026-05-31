---
id: UC-301
ordinal: UC-007
title: Tabla de claims con exclusion mutua
parent_us: US-NATIVE-BACKEND
status: done
actor: Engine
hours: 8
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-301 — Tabla de claims con exclusion mutua

> **US padre:** [US-NATIVE-BACKEND](../us/US-01-specbox-para-equipos-sobre-postgres-nativo.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-16

Tabla uc_claims con constraint UNIQUE(uc_id); dos claim_uc concurrentes sobre el mismo UC -> exactamente un claim concedido y uno rechazado con ALREADY_CLAIMED.

- **Estado:** ✅ cumplido

### AC-17

release_uc(uc_id) solo lo ejecuta el dueno del claim; ajeno -> NOT_CLAIM_OWNER y el claim permanece.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
