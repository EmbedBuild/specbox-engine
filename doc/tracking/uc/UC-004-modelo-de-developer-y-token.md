---
id: UC-201
ordinal: UC-004
title: Modelo de developer y token
parent_us: US-NATIVE-BACKEND
status: done
actor: Engine/admin
hours: 8
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-201 — Modelo de developer y token

> **US padre:** [US-NATIVE-BACKEND](../us/US-01-specbox-para-equipos-sobre-postgres-nativo.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-10

Tabla developers con developer_id (estable, PK), display_name y token_hash; tokens hasheados, nunca en claro (verificado: la columna no contiene el token literal).

- **Estado:** ✅ cumplido

### AC-11

Un dev declara su token en settings.local.json (specbox.native.token); el cliente MCP lo adjunta en cada llamada y el token nunca se escribe en logs del server (verificado grepeando logs).

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
