---
id: UC-625
ordinal: UC-058
title: Crear modulo server/observability con setup OTel (tracer, meter, logger) inicializable desde env
parent_us: US-MCP-OBSERVABILITY
status: ready
actor: Engine
hours: 3.0
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-625 — Crear modulo server/observability con setup OTel (tracer, meter, logger) inicializable desde env

> **US padre:** [US-MCP-OBSERVABILITY](../us/US-12-observabilidad-otel-del-mcp-server-v6-2-0.md)

## Objetivo / Descripción

**User Story:** US-MCP-OBSERVABILITY: Observabilidad OTel del MCP server (v6.2.0)
**Actor:** Engine
**Horas estimadas:** 3.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: Existe `server/observability/__init__.py` que exporta `init_observability` y `MCPObservabilityMiddleware`; un test verifica que se pueden importar sin error.
- AC-02: `init_observability()` retorna `None` y NO importa `opentelemetry.*` cuando `SPECBOX_OBSERVABILITY_ENABLED != 'true'`; un test con monkeypatch del env var lo verifica usando `importlib.util.find_spec` o capturando `sys.modules`.
- AC-03: Con `SPECBOX_OBSERVABILITY_ENABLED=true` y `OTEL_EXPORTER_OTLP_ENDPOINT=http://mock:4318` seteados, `init_observability()` configura un `TracerProvider`, `MeterProvider` y `LoggerProvider` globales con resource attributes `service.name=specbox-engine` y `service.version=<engine_version del YAML>`.
- AC-04: Pinea `opentelemetry-sdk>=1.27` y `opentelemetry-exporter-otlp>=1.27` en pyproject como optional extra `[observability]`; el test verifica que sin el extra el modulo levanta `ImportError` legible (mensaje incluye instruccion de instalacion).

## Contexto
Pieza base. Sin esto el middleware no puede emitir nada. Tiene que ser totalmente lazy: si `SPECBOX_OBSERVABILITY_ENABLED != 'true'`, `init_observability()` retorna inmediatamente sin importar opentelemetry. Esto permite que proyectos locales NO arrastren la dependencia ni paguen el coste de import.

Archivos nuevos:
- `server/observability/__init__.py`: export publico (`init_observability`, `MCPObservabilityMiddleware`)
- `server/observability/setup.py`: `init_tracer()`, `init_meter()`, `init_logs()` configuran SDK desde env (OTLP endpoint, resource attributes, sampling)

Resource attributes obligatorios: `service.name=specbox-engine`, `service.version=<ENGINE_VERSION>` (leido del YAML, igual que `_load_engine_version` en server.py), `deployment.environment=<env var SPECBOX_ENV o 'unknown'>`.

Sampling: TraceIdRatioBased(1.0) por defecto en v1 (capturar todo, ya optimizamos en v2 si el volumen molesta).

## Acceptance Criteria

### AC-01

Existe `server/observability/__init__.py` que exporta `init_observability` y `MCPObservabilityMiddleware`; un test verifica que se pueden importar sin error.

- **Estado:** ⬜ pendiente

### AC-02

`init_observability()` retorna `None` y NO importa `opentelemetry.*` cuando `SPECBOX_OBSERVABILITY_ENABLED != 'true'`; un test con monkeypatch del env var lo verifica usando `importlib.util.find_spec` o capturando `sys.modules`.

- **Estado:** ⬜ pendiente

### AC-03

Con `SPECBOX_OBSERVABILITY_ENABLED=true` y `OTEL_EXPORTER_OTLP_ENDPOINT=http://mock:4318` seteados, `init_observability()` configura un `TracerProvider`, `MeterProvider` y `LoggerProvider` globales con resource attributes `service.name=specbox-engine` y `service.version=<engine_version del YAML>`.

- **Estado:** ⬜ pendiente

### AC-04

Pinea `opentelemetry-sdk>=1.27` y `opentelemetry-exporter-otlp>=1.27` en pyproject como optional extra `[observability]`; el test verifica que sin el extra el modulo levanta `ImportError` legible (mensaje incluye instruccion de instalacion).

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
