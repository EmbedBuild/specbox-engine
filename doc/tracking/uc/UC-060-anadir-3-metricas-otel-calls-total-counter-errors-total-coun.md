---
id: UC-627
ordinal: UC-060
title: Anadir 3 metricas OTel (calls_total counter, errors_total counter, duration_ms histogram) al middleware
parent_us: US-MCP-OBSERVABILITY
status: ready
actor: Engine
hours: 3.0
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-627 — Anadir 3 metricas OTel (calls_total counter, errors_total counter, duration_ms histogram) al middleware

> **US padre:** [US-MCP-OBSERVABILITY](../us/US-12-observabilidad-otel-del-mcp-server-v6-2-0.md)

## Objetivo / Descripción

**User Story:** US-MCP-OBSERVABILITY: Observabilidad OTel del MCP server (v6.2.0)
**Actor:** Engine
**Horas estimadas:** 3.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: El middleware crea 3 instrumentos OTel en el meter `specbox.mcp`: counter `mcp.tool.calls_total`, counter `mcp.tool.errors_total`, histogram `mcp.tool.duration_ms`; un test con `InMemoryMetricReader` y `MeterProvider` verifica que los 3 existen tras inicializar el middleware.
- AC-02: Una invocacion exitosa incrementa `calls_total` en 1 con labels `tool=<name>, status=ok, backend=<detected>, transport=<detected>`, y graba un sample en `duration_ms` con labels `tool=<name>, status=ok`; el test invoca tool mock y assert sobre los data points exportados.
- AC-03: Una invocacion con error incrementa `calls_total{status=error}` Y `errors_total{tool=<name>, error_type=<exception class>}` en 1; un test con tool que levanta `ValueError('x')` verifica los 2 counters incrementados con labels correctos.
- AC-04: Las metricas NO incluyen labels de alta cardinality (`project`, `developer_id`, `path`, `content`); un test list-checks que los `attributes` de cada data point son subset de `{tool, status, backend, transport, error_type}`.

## Contexto
Spans solo no bastan, para dashboards necesitamos metricas agregables. 3 instrumentos en el meter `specbox.mcp`:

- `mcp.tool.calls_total` (Counter): labels `tool`, `status` (ok|error|deprecated), `backend` (freeform|trello|plane|native|unknown), `transport` (stdio|http)
- `mcp.tool.errors_total` (Counter): labels `tool`, `error_type` (clase de la excepcion)
- `mcp.tool.duration_ms` (Histogram): labels `tool`, `status`. Buckets sugeridos: [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000] ms

Las metricas se incrementan dentro del mismo middleware, tras (o en paralelo a) la creacion del span. El detect de `backend` viene del registry del auth_gateway (`get_session_backend_type()` o equivalente), si no hay sesion activa (ej. tools de engine.py como `get_engine_version`), el label `backend=unknown`.

No anadir labels de alta cardinality (`project`, `developer_id`) a las metricas, esos van solo en spans.

## Acceptance Criteria

### AC-01

El middleware crea 3 instrumentos OTel en el meter `specbox.mcp`: counter `mcp.tool.calls_total`, counter `mcp.tool.errors_total`, histogram `mcp.tool.duration_ms`; un test con `InMemoryMetricReader` y `MeterProvider` verifica que los 3 existen tras inicializar el middleware.

- **Estado:** ⬜ pendiente

### AC-02

Una invocacion exitosa incrementa `calls_total` en 1 con labels `tool=<name>, status=ok, backend=<detected>, transport=<detected>`, y graba un sample en `duration_ms` con labels `tool=<name>, status=ok`; el test invoca tool mock y assert sobre los data points exportados.

- **Estado:** ⬜ pendiente

### AC-03

Una invocacion con error incrementa `calls_total{status=error}` Y `errors_total{tool=<name>, error_type=<exception class>}` en 1; un test con tool que levanta `ValueError('x')` verifica los 2 counters incrementados con labels correctos.

- **Estado:** ⬜ pendiente

### AC-04

Las metricas NO incluyen labels de alta cardinality (`project`, `developer_id`, `path`, `content`); un test list-checks que los `attributes` de cada data point son subset de `{tool, status, backend, transport, error_type}`.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
