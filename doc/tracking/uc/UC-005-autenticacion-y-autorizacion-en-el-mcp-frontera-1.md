---
id: UC-202
ordinal: UC-005
title: Autenticacion y autorizacion en el MCP (Frontera 1)
parent_us: US-NATIVE-BACKEND
status: done
actor: MCP server
hours: 10
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-202 — Autenticacion y autorizacion en el MCP (Frontera 1)

> **US padre:** [US-NATIVE-BACKEND](../us/US-01-specbox-para-equipos-sobre-postgres-nativo.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-12

Una llamada a tool del backend Nativo sin token valido es rechazada con UNAUTHENTICATED y no toca Postgres.

- **Estado:** ✅ cumplido

### AC-13

Token valido pero a proyecto no asociado -> FORBIDDEN; al proyecto correcto procede.

- **Estado:** ✅ cumplido

### AC-14

La credencial de servicio de Postgres (Frontera 2) se lee solo de la env del VPS; no aparece en ninguna respuesta de tool ni en settings.local.json de ningun dev.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
