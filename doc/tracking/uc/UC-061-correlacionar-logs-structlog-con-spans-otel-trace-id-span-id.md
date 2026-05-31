---
id: UC-628
ordinal: UC-061
title: Correlacionar logs structlog con spans OTel (trace_id + span_id en cada log line)
parent_us: US-MCP-OBSERVABILITY
status: ready
actor: Engine
hours: 2.0
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-628 — Correlacionar logs structlog con spans OTel (trace_id + span_id en cada log line)

> **US padre:** [US-MCP-OBSERVABILITY](../us/US-12-observabilidad-otel-del-mcp-server-v6-2-0.md)

## Objetivo / Descripción

**User Story:** US-MCP-OBSERVABILITY: Observabilidad OTel del MCP server (v6.2.0)
**Actor:** Engine
**Horas estimadas:** 2.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: `server/observability/logging.py` exporta `add_otel_context_processor(logger, method_name, event_dict)` que retorna `event_dict` enriquecido con keys `trace_id` (32 hex chars) y `span_id` (16 hex chars) cuando hay span activo; un test dentro de `tracer.start_as_current_span` verifica que las keys se anaden.
- AC-02: El processor es no-op (retorna `event_dict` inalterado) cuando no hay span activo o cuando OTel no esta inicializado; 2 tests cubren ambos casos.
- AC-03: `server/server.py` anade el processor al stack de structlog SOLO dentro del bloque condicional `if SPECBOX_OBSERVABILITY_ENABLED == 'true'`; el test importa server con env OFF y verifica que `add_otel_context_processor` no esta en la lista de processors configurados.
- AC-04: Un test end-to-end: dentro de un span activo, un `logger.info('msg', foo='bar')` produce output JSON que contiene `trace_id`, `span_id`, `foo='bar'`, `event='msg'` simultaneamente (verifica que la correlacion esta intacta).

## Contexto
`server/server.py` linea 64 ya configura structlog con processors estandar. Anadir un nuevo processor `add_otel_context` que, si hay span activo, inyecta `trace_id` (32 hex chars) y `span_id` (16 hex chars) en el event_dict del log. Esto permite ir desde un span lento en Tempo/Jaeger al log estructurado del MCP filtrando por trace_id.

El processor debe ser no-op si:
- OTel no esta inicializado (`SPECBOX_OBSERVABILITY_ENABLED != 'true'`)
- No hay span activo (`get_current_span()` retorna `INVALID_SPAN`)

Archivo: nuevo helper en `server/observability/logging.py` exportando `add_otel_context_processor`. server.py lo importa condicionalmente y lo anade al stack de structlog SOLO si OTel esta activo.

## Acceptance Criteria

### AC-01

`server/observability/logging.py` exporta `add_otel_context_processor(logger, method_name, event_dict)` que retorna `event_dict` enriquecido con keys `trace_id` (32 hex chars) y `span_id` (16 hex chars) cuando hay span activo; un test dentro de `tracer.start_as_current_span` verifica que las keys se anaden.

- **Estado:** ⬜ pendiente

### AC-02

El processor es no-op (retorna `event_dict` inalterado) cuando no hay span activo o cuando OTel no esta inicializado; 2 tests cubren ambos casos.

- **Estado:** ⬜ pendiente

### AC-03

`server/server.py` anade el processor al stack de structlog SOLO dentro del bloque condicional `if SPECBOX_OBSERVABILITY_ENABLED == 'true'`; el test importa server con env OFF y verifica que `add_otel_context_processor` no esta en la lista de processors configurados.

- **Estado:** ⬜ pendiente

### AC-04

Un test end-to-end: dentro de un span activo, un `logger.info('msg', foo='bar')` produce output JSON que contiene `trace_id`, `span_id`, `foo='bar'`, `event='msg'` simultaneamente (verifica que la correlacion esta intacta).

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
