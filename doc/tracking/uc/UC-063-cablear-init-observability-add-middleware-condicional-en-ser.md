---
id: UC-630
ordinal: UC-063
title: Cablear init_observability + add_middleware condicional en server.py (opt-in por env var)
parent_us: US-MCP-OBSERVABILITY
status: ready
actor: Engine
hours: 1.0
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-630 — Cablear init_observability + add_middleware condicional en server.py (opt-in por env var)

> **US padre:** [US-MCP-OBSERVABILITY](../us/US-12-observabilidad-otel-del-mcp-server-v6-2-0.md)

## Objetivo / Descripción

**User Story:** US-MCP-OBSERVABILITY: Observabilidad OTel del MCP server (v6.2.0)
**Actor:** Engine
**Horas estimadas:** 1.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: Con `SPECBOX_OBSERVABILITY_ENABLED=true`, tras `import server.server`, `mcp._middlewares` (o equivalente API publica de FastMCP) contiene 1 instancia de `MCPObservabilityMiddleware`; test integration verifica.
- AC-02: Con `SPECBOX_OBSERVABILITY_ENABLED` ausente o `=false`, tras `import server.server`, `opentelemetry` NO esta en `sys.modules` y `mcp._middlewares` no contiene `MCPObservabilityMiddleware`; test verifica ambas condiciones.
- AC-03: Si `init_observability()` levanta excepcion (ej. OTLP endpoint invalido), el server termina de cargarse sin crashear y emite log `mcp_observability_init_failed` con el error; test con monkeypatch fuerza la excepcion y verifica que `import server.server` no levanta.
- AC-04: Con observabilidad activa, log inicial `mcp_observability_enabled` incluye campo `exporter` con el valor de `OTEL_EXPORTER_OTLP_ENDPOINT` (o `'console'` si no esta seteado); test captura log output.

## Contexto
Cambio minimo y quirurgico en `server/server.py`. Despues del bloque `mcp = FastMCP(...)` (linea ~111 actual), anadir:

```python
if os.getenv('SPECBOX_OBSERVABILITY_ENABLED') == 'true':
    from .observability import init_observability, MCPObservabilityMiddleware
    init_observability()
    mcp.add_middleware(MCPObservabilityMiddleware())
    logger.info('mcp_observability_enabled', exporter=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'console'))
```

El import de `.observability` es lazy (dentro del if) para que cuando la env var este off, el modulo ni siquiera se cargue y sus dependencias (opentelemetry) no se importen en cadena.

Si la inicializacion falla (ej. OTLP endpoint malformado), log warning pero NO crashear el server, observabilidad rota no debe tirar el MCP. Wrap todo el bloque en try/except logging del error.

## Acceptance Criteria

### AC-01

Con `SPECBOX_OBSERVABILITY_ENABLED=true`, tras `import server.server`, `mcp._middlewares` (o equivalente API publica de FastMCP) contiene 1 instancia de `MCPObservabilityMiddleware`; test integration verifica.

- **Estado:** ⬜ pendiente

### AC-02

Con `SPECBOX_OBSERVABILITY_ENABLED` ausente o `=false`, tras `import server.server`, `opentelemetry` NO esta en `sys.modules` y `mcp._middlewares` no contiene `MCPObservabilityMiddleware`; test verifica ambas condiciones.

- **Estado:** ⬜ pendiente

### AC-03

Si `init_observability()` levanta excepcion (ej. OTLP endpoint invalido), el server termina de cargarse sin crashear y emite log `mcp_observability_init_failed` con el error; test con monkeypatch fuerza la excepcion y verifica que `import server.server` no levanta.

- **Estado:** ⬜ pendiente

### AC-04

Con observabilidad activa, log inicial `mcp_observability_enabled` incluye campo `exporter` con el valor de `OTEL_EXPORTER_OTLP_ENDPOINT` (o `'console'` si no esta seteado); test captura log output.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
