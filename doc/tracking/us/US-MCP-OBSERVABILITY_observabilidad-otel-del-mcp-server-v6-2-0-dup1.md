---
id: US-MCP-OBSERVABILITY
title: Observabilidad OTel del MCP server (v6.2.0)
status: draft
hours: 24.0
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# US-MCP-OBSERVABILITY — Observabilidad OTel del MCP server (v6.2.0)

## Como… quiero… para…

> # US-MCP-OBSERVABILITY: Observabilidad OTel del MCP server (v6.2.0)
> 
> **Horas estimadas:** 24.0
> **Pantallas:** 
> 
> Como mantenedor de SpecBox Engine MCP server, quiero instrumentar cada `tools/call` con OpenTelemetry (spans + metricas + logs correlacionados) exportado via OTLP, para tener visibilidad de que tools se llaman, con que latencia y que errores producen, sin acoplar el codigo a un backend concreto (Sentry, Datadog, Tempo, Honeycomb son intercambiables cambiando env vars) y sin pagar overhead en sesiones locales (opt-in por env var).
> 
> **Inspiracion**: el companero de DentalData libero v0.8.0 de su MCP con middleware OTel -> Sentry que emite 1 span por `tools/call` y alimenta los dashboards 'MCP' y 'AI Agents' de Sentry. Replicamos la idea pero con OTLP generico para no acoplar a Sentry.
> 
> **Scope v1**: instrumentacion pura, cero cambios en el comportamiento de las tools. Cubre: spans (perf + errores), 3 metricas (calls_total counter, errors_total counter, duration_ms histogram), logs estructurados correlacionados por trace_id.
> 
> **Activacion**: opt-in con `SPECBOX_OBSERVABILITY_ENABLED=true`. Si la env var no esta, OTel ni siquiera se importa, proyectos locales (stdio) cero overhead y cero dependencias en runtime.
> 
> **Decisiones cerradas con el user 2026-05-25**:
> - Backend: OTel puro + OTLP generico (NO Sentry SDK directo). Portable.
> - Scope v1: completo (spans + metricas + logs correlacionados).
> - Activacion: opt-in por env var. Local/stdio cero overhead.
> 
> **Pieza tecnica clave**: FastMCP 3.3+ (ya pineado en pyproject `>=3.3.1,<4.0.0`) trae middleware nativo (`mcp.add_middleware`) con hook `on_call_tool`. Sin parchear FastMCP ni envolver cada tool.
> 
> **Politica de redaccion CRITICA**: tools v6.0.1 content-passing reciben docs canonicos del cliente como `*_content`. El middleware NO emite contenido, solo `len()`, hash opcional, y nombres de keys del payload. Allowlist centralizada en `attributes.py`, NO denylist.
> 
> **Win secundario**: el counter `mcp.tool.calls_total{tool=run_quality_audit}` cierra el follow-up de v6.0.2 issue #60, sabremos cuantos consumers externos siguen llamando al shim deprecado antes de eliminarlo en v6.3.
> 
> **Riesgos identificados**:
> 1. Cardinality por `project` slug -> usar hash 8-char del sha256 si backend factura cardinality (Datadog si, Tempo no).
> 2. Bug historico OTel SDK con asyncio en FastMCP -> pinear `opentelemetry-sdk>=1.27` (tiene el fix).
> 3. Overhead stdio local -> opt-in lo cierra.
> 4. Fuga de contenido en spans -> politica de allowlist + test que falla si aparece `*_content` en atributos.
> 
> **Release target**: v6.2.0 (minor, no patch, anade dependencias opcionales y superficie nueva aunque sea opt-in).
> 
> **Referencias**:
> - Inspiracion: DentalData MCP v0.8.0 'MCP observability'
> - FastMCP middleware docs
> - OTel spec: https://opentelemetry.io/docs/specs/otel/

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-625 | [Crear modulo server/observability con setup OTel (tracer, meter, logger) inicializable desde env](../uc/UC-625_crear-modulo-server-observability-con-setup-otel-tracer-mete.md) | ready |
| UC-626 | [Implementar MCPObservabilityMiddleware con hook on_call_tool (spans + duracion + error capture)](../uc/UC-626_implementar-mcpobservabilitymiddleware-con-hook-on-call-tool.md) | ready |
| UC-627 | [Anadir 3 metricas OTel (calls_total counter, errors_total counter, duration_ms histogram) al middleware](../uc/UC-627_anadir-3-metricas-otel-calls-total-counter-errors-total-coun.md) | ready |
| UC-628 | [Correlacionar logs structlog con spans OTel (trace_id + span_id en cada log line)](../uc/UC-628_correlacionar-logs-structlog-con-spans-otel-trace-id-span-id.md) | ready |
| UC-629 | [Implementar politica de redaccion de atributos (allowlist + escrubeo de *_content y rutas absolutas)](../uc/UC-629_implementar-politica-de-redaccion-de-atributos-allowlist-esc.md) | ready |
| UC-630 | [Cablear init_observability + add_middleware condicional en server.py (opt-in por env var)](../uc/UC-630_cablear-init-observability-add-middleware-condicional-en-ser.md) | ready |
| UC-631 | [Suite de tests de observabilidad (unit + integration + redaccion + opt-in)](../uc/UC-631_suite-de-tests-de-observabilidad-unit-integration-redaccion-.md) | ready |
| UC-632 | [Documentacion + release v6.2.0 (CHANGELOG, CLAUDE.md, ADR, plan tecnico, pyproject extra, Dockerfile)](../uc/UC-632_documentacion-release-v6-2-0-changelog-claude-md-adr-plan-te.md) | ready |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
