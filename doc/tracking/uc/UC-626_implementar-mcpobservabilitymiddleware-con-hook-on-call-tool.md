---
id: UC-626
title: Implementar MCPObservabilityMiddleware con hook on_call_tool (spans + duracion + error capture)
parent_us: US-MCP-OBSERVABILITY
status: ready
actor: Engine
hours: 4.0
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-626 — Implementar MCPObservabilityMiddleware con hook on_call_tool (spans + duracion + error capture)

> **US padre:** [US-MCP-OBSERVABILITY](../us/US-MCP-OBSERVABILITY_observabilidad-otel-del-mcp-server-v6-2-0.md)

## Objetivo / Descripción

**User Story:** US-MCP-OBSERVABILITY: Observabilidad OTel del MCP server (v6.2.0)
**Actor:** Engine
**Horas estimadas:** 4.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: `MCPObservabilityMiddleware` hereda de `fastmcp.server.middleware.Middleware` y override `on_call_tool(context, call_next)`; un test con mock middleware context verifica que `await call_next(context)` es invocado exactamente una vez.
- AC-02: Tras una invocacion exitosa el span generado tiene `name=mcp.tool.<tool_name>`, atributos `mcp.tool.name`, `mcp.tool.duration_ms` (float > 0), `mcp.tool.status='ok'`, `engine.version`, `mcp.transport`; el test usa `InMemorySpanExporter` de `opentelemetry-sdk` y assert sobre el span exportado.
- AC-03: Si la tool levanta excepcion, el span queda con `StatusCode.ERROR`, atributos `mcp.error.type` y `mcp.error.message` (truncado a 500 chars), llamada a `record_exception(e)` registrada en el span; el test inyecta una tool que `raise RuntimeError('boom')` y assert sobre el span + verifica que la excepcion re-propaga al caller.
- AC-04: El middleware NO emite span cuando `SPECBOX_OBSERVABILITY_ENABLED != 'true'`, en realidad ni se registra (cableado en server.py condicional, ver UC-630); un test verifica que en ese estado el `on_call_tool` no es invocado para la tool.

## Contexto
El core del feature. FastMCP 3.3+ expone `fastmcp.server.middleware.Middleware` con hook async `on_call_tool(context, call_next)`. El middleware envuelve cada `tools/call`, abre un span, ejecuta la tool con `await call_next(context)`, registra duracion, marca status, captura excepciones.

Archivo nuevo: `server/observability/middleware.py`.

Atributos del span (todos prefijo `mcp.tool.`):
- `mcp.tool.name`: string, requerido
- `mcp.tool.duration_ms`: float, calculado con `time.perf_counter`
- `mcp.tool.status`: `ok | error | deprecated` (deprecated si la tool devuelve dict con `_deprecated=true` o levanta `DeprecationWarning`)
- `engine.version`: del env o `_load_engine_version()`
- `mcp.transport`: `stdio | http` (auto-detect via `os.getenv('FASTMCP_TRANSPORT')` o argv)

En caso de excepcion: `span.record_exception(e)`, `span.set_status(Status(StatusCode.ERROR))`, `mcp.error.type=type(e).__name__`, `mcp.error.message=str(e)[:500]` (truncado), re-raise.

El span name debe ser `mcp.tool.<tool_name>` (convencion OTel para facil filtrado en Tempo/Jaeger).

## Acceptance Criteria

### AC-01

`MCPObservabilityMiddleware` hereda de `fastmcp.server.middleware.Middleware` y override `on_call_tool(context, call_next)`; un test con mock middleware context verifica que `await call_next(context)` es invocado exactamente una vez.

- **Estado:** ⬜ pendiente

### AC-02

Tras una invocacion exitosa el span generado tiene `name=mcp.tool.<tool_name>`, atributos `mcp.tool.name`, `mcp.tool.duration_ms` (float > 0), `mcp.tool.status='ok'`, `engine.version`, `mcp.transport`; el test usa `InMemorySpanExporter` de `opentelemetry-sdk` y assert sobre el span exportado.

- **Estado:** ⬜ pendiente

### AC-03

Si la tool levanta excepcion, el span queda con `StatusCode.ERROR`, atributos `mcp.error.type` y `mcp.error.message` (truncado a 500 chars), llamada a `record_exception(e)` registrada en el span; el test inyecta una tool que `raise RuntimeError('boom')` y assert sobre el span + verifica que la excepcion re-propaga al caller.

- **Estado:** ⬜ pendiente

### AC-04

El middleware NO emite span cuando `SPECBOX_OBSERVABILITY_ENABLED != 'true'`, en realidad ni se registra (cableado en server.py condicional, ver UC-630); un test verifica que en ese estado el `on_call_tool` no es invocado para la tool.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
