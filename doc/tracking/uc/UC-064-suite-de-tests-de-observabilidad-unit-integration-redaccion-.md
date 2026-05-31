---
id: UC-631
ordinal: UC-064
title: Suite de tests de observabilidad (unit + integration + redaccion + opt-in)
parent_us: US-MCP-OBSERVABILITY
status: ready
actor: Engine
hours: 4.0
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-631 — Suite de tests de observabilidad (unit + integration + redaccion + opt-in)

> **US padre:** [US-MCP-OBSERVABILITY](../us/US-12-observabilidad-otel-del-mcp-server-v6-2-0.md)

## Objetivo / Descripción

**User Story:** US-MCP-OBSERVABILITY: Observabilidad OTel del MCP server (v6.2.0)
**Actor:** Engine
**Horas estimadas:** 4.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: `tests/test_observability.py` existe y contiene al menos 12 tests organizados en los 6 grupos descritos; `pytest tests/test_observability.py -v` retorna `passed >= 12, failed=0`.
- AC-02: El test suite usa `InMemorySpanExporter` e `InMemoryMetricReader`, NO requiere collector OTLP corriendo; un test ejecutado en CI sin red verifica que pasa igual.
- AC-03: Test `test_no_content_leak` (fuzz): registra una tool mock que recibe `app_prd_content='SECRET_LEAK_CANARY_xyz123'` como arg, ejecuta el middleware, busca el string canary en TODOS los spans, logs y data points de metricas exportados; assert que el canary NO aparece en ninguno.
- AC-04: La suite anade al global pytest `1243 -> 1255+` tests sin breaks de los pre-existentes (regression check: `pytest tests/ -q` mantiene `failed=0`).

## Contexto
Archivo nuevo: `tests/test_observability.py`. Cubre los 5 UCs anteriores end-to-end con `InMemorySpanExporter` y `InMemoryMetricReader` de `opentelemetry-sdk`.

Grupos de tests:
1. Opt-in (`test_observability_disabled_no_imports`, `test_observability_enabled_imports`)
2. Middleware span emission (`test_span_per_tool_call`, `test_span_attributes`, `test_span_error_status`)
3. Metricas (`test_calls_counter`, `test_errors_counter`, `test_duration_histogram`)
4. Log correlation (`test_trace_id_in_logs`, `test_no_span_no_trace_id`)
5. Redaccion (`test_content_keys_redacted`, `test_secret_keys_omitted`, `test_path_redaction`)
6. Fault tolerance (`test_init_failure_does_not_crash_server`)

Los tests deben funcionar SIN un OTLP endpoint real, todo en memoria. Usar fixtures `pytest` para configurar `TracerProvider(InMemorySpanExporter)` antes de cada test y resetear entre tests.

## Acceptance Criteria

### AC-01

`tests/test_observability.py` existe y contiene al menos 12 tests organizados en los 6 grupos descritos; `pytest tests/test_observability.py -v` retorna `passed >= 12, failed=0`.

- **Estado:** ⬜ pendiente

### AC-02

El test suite usa `InMemorySpanExporter` e `InMemoryMetricReader`, NO requiere collector OTLP corriendo; un test ejecutado en CI sin red verifica que pasa igual.

- **Estado:** ⬜ pendiente

### AC-03

Test `test_no_content_leak` (fuzz): registra una tool mock que recibe `app_prd_content='SECRET_LEAK_CANARY_xyz123'` como arg, ejecuta el middleware, busca el string canary en TODOS los spans, logs y data points de metricas exportados; assert que el canary NO aparece en ninguno.

- **Estado:** ⬜ pendiente

### AC-04

La suite anade al global pytest `1243 -> 1255+` tests sin breaks de los pre-existentes (regression check: `pytest tests/ -q` mantiene `failed=0`).

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
