---
id: UC-629
ordinal: UC-062
title: Implementar politica de redaccion de atributos (allowlist + escrubeo de *_content y rutas absolutas)
parent_us: US-MCP-OBSERVABILITY
status: ready
actor: Engine
hours: 3.0
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-629 — Implementar politica de redaccion de atributos (allowlist + escrubeo de *_content y rutas absolutas)

> **US padre:** [US-MCP-OBSERVABILITY](../us/US-12-observabilidad-otel-del-mcp-server-v6-2-0.md)

## Objetivo / Descripción

**User Story:** US-MCP-OBSERVABILITY: Observabilidad OTel del MCP server (v6.2.0)
**Actor:** Engine
**Horas estimadas:** 3.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: `safe_tool_attributes(tool='x', args={'project':'foo','app_prd_content':'<huge>'}, result=None)` devuelve dict que contiene `project='foo'` pero NO contiene `app_prd_content`, si contiene `app_prd_content_length=<int>`; test cubre el caso.
- AC-02: Con `SPECBOX_OBSERVABILITY_HASH_CONTENT=true`, ademas se incluye `app_prd_content_sha256_prefix` de 8 hex chars; test cubre toggle on/off.
- AC-03: Claves sensibles `developer_token`, `api_key`, `secret`, `password`, `body`, `payload` son omitidas del output incluso si estan en el allowlist parcial; test parametrico cubre las 6 claves prohibidas.
- AC-04: `redact_path('/Users/foo/bar')` con cwd `/Users/foo` devuelve `bar`; con cwd no relacionado devuelve `<redacted>`; test cubre ambos casos.
- AC-05: Un fuzz test: para cada tool registrada en el MCP, simula args sinteticos con claves `*_content` enormes y verifica que ninguna invocacion del middleware produce span con el contenido raw, el contenido NO aparece en ningun atributo, log line ni etiqueta de metrica.

## Contexto
CRITICO para evitar fuga de datos del cliente. Tools v6.0.1 content-passing reciben `app_prd_content`, `app_market_content`, `app_spec_content`, etc, contenido confidencial. El middleware NO debe emitir contenido en spans/logs/metricas.

Archivo nuevo: `server/observability/attributes.py`.

Funciones publicas:
- `safe_tool_attributes(tool_name: str, args: dict, result: dict | None) -> dict`: devuelve solo claves del ALLOWLIST. Para claves terminadas en `_content`, emite solo `<key>_length` (int) y opcionalmente `<key>_sha256_prefix` (8 chars) si la flag `SPECBOX_OBSERVABILITY_HASH_CONTENT=true` (default false).
- `redact_path(p: str) -> str`: convierte rutas absolutas a relativas al cwd o reemplaza por `<redacted>` si no es relativa.

ALLOWLIST de claves de args que pueden viajar (todas hashed si son strings largas): `project`, `feature`, `uc_id`, `us_id`, `ac_id`, `backend_type`, `stack`, `mode`, `gate_mode`, `transport`, `version`. Cualquier otra clave se omite (no se trunca: directamente no aparece).

NUNCA emitir: `*_content`, `*_token`, `*_api_key`, `*_secret`, `password`, `developer_token`, `payload`, `body`, valores de configuracion custom.

## Acceptance Criteria

### AC-01

`safe_tool_attributes(tool='x', args={'project':'foo','app_prd_content':'<huge>'}, result=None)` devuelve dict que contiene `project='foo'` pero NO contiene `app_prd_content`, si contiene `app_prd_content_length=<int>`; test cubre el caso.

- **Estado:** ⬜ pendiente

### AC-02

Con `SPECBOX_OBSERVABILITY_HASH_CONTENT=true`, ademas se incluye `app_prd_content_sha256_prefix` de 8 hex chars; test cubre toggle on/off.

- **Estado:** ⬜ pendiente

### AC-03

Claves sensibles `developer_token`, `api_key`, `secret`, `password`, `body`, `payload` son omitidas del output incluso si estan en el allowlist parcial; test parametrico cubre las 6 claves prohibidas.

- **Estado:** ⬜ pendiente

### AC-04

`redact_path('/Users/foo/bar')` con cwd `/Users/foo` devuelve `bar`; con cwd no relacionado devuelve `<redacted>`; test cubre ambos casos.

- **Estado:** ⬜ pendiente

### AC-05

Un fuzz test: para cada tool registrada en el MCP, simula args sinteticos con claves `*_content` enormes y verifica que ninguna invocacion del middleware produce span con el contenido raw, el contenido NO aparece en ningun atributo, log line ni etiqueta de metrica.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
