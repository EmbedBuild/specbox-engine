---
id: UC-632
ordinal: UC-065
title: Documentacion + release v6.2.0 (CHANGELOG, CLAUDE.md, ADR, plan tecnico, pyproject extra, Dockerfile)
parent_us: US-MCP-OBSERVABILITY
status: ready
actor: Engine
hours: 4.0
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-632 — Documentacion + release v6.2.0 (CHANGELOG, CLAUDE.md, ADR, plan tecnico, pyproject extra, Dockerfile)

> **US padre:** [US-MCP-OBSERVABILITY](../us/US-12-observabilidad-otel-del-mcp-server-v6-2-0.md)

## Objetivo / Descripción

**User Story:** US-MCP-OBSERVABILITY: Observabilidad OTel del MCP server (v6.2.0)
**Actor:** Engine
**Horas estimadas:** 4.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: Existe `doc/decisions/mcp_observability.md` con secciones: Contexto, Decision, Alternativas consideradas (incluye Sentry SDK directo + razon de rechazo), Consecuencias, Politica de redaccion; el archivo es >= 800 palabras.
- AC-02: Existe `doc/plans/v6.2.0_mcp_observability_plan.md` con la estructura: TL;DR, 5 cambios principales, fases de implementacion, riesgos, metricas de exito, rollback plan; sigue el formato de los plans previos (`v6.0.1_mcp_path_contract_plan.md` como referencia).
- AC-03: `CHANGELOG.md` tiene entry v6.2.0 con bullets de los 8 UCs cubiertos (UC-625 a UC-632); el entry sigue el formato de v6.1.1 / v6.0.2.
- AC-04: `CLAUDE.md` tiene nueva seccion de nivel 2 '## MCP Observability (v6.2.0)' tras la seccion '## Smoke Test Followups (v6.0.2)' y antes de '## MCP Path Contract (v6.0.1)'; la seccion documenta env vars, los 3 instrumentos de metricas, atributos de spans, politica de redaccion y un ejemplo de query.
- AC-05: `pyproject.toml` tiene optional extra `[observability]` con `opentelemetry-sdk>=1.27`, `opentelemetry-exporter-otlp>=1.27`, `opentelemetry-instrumentation-logging>=0.48b0`; un test ejecuta `pip install -e '.[observability]'` en venv limpia y verifica resolucion de deps.
- AC-06: `Dockerfile` instala con extra observability (`pip install '.[observability]'`); build del Dockerfile no falla.
- AC-07: `ENGINE_VERSION.yaml` bumpeado a `version: 6.2.0` y `name: 'MCP Observability'`; el server log inicial reporta `engine_version=v6.2.0`.

## Contexto
Hace falta documentar el feature para que sea descubrible y mantenible. 7 entregables:

1. `doc/decisions/mcp_observability.md` (ADR): Por que OTel puro (no Sentry SDK directo), que se emite y que no (politica de redaccion), por que opt-in. Incluye el alternative-considered (Sentry directo) y por que se rechazo.
2. `doc/plans/v6.2.0_mcp_observability_plan.md` (plan tecnico): Estructura de los 8 UCs, fases, riesgos, metricas de exito, rollback plan.
3. `CHANGELOG.md`: Entry v6.2.0 'MCP Observability'.
4. `CLAUDE.md`: Nueva seccion 'MCP Observability (v6.2.0)' tras la seccion Smoke Test Followups: explica env vars (`SPECBOX_OBSERVABILITY_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `SPECBOX_OBSERVABILITY_HASH_CONTENT`), los 3 instrumentos de metricas, el contrato de atributos de spans, la politica de redaccion y un ejemplo de query Tempo/Jaeger.
5. `pyproject.toml`: Optional extra:
```toml
[project.optional-dependencies]
observability = [
  'opentelemetry-sdk>=1.27',
  'opentelemetry-exporter-otlp>=1.27',
  'opentelemetry-instrumentation-logging>=0.48b0',
]
```
6. `Dockerfile`: Cambiar `pip install .` a `pip install '.[observability]'` para que el VPS lo arrastre. Local stdio puede seguir sin el extra.
7. `ENGINE_VERSION.yaml`: Bump a 6.2.0 con `name: 'MCP Observability'`.

## Acceptance Criteria

### AC-01

Existe `doc/decisions/mcp_observability.md` con secciones: Contexto, Decision, Alternativas consideradas (incluye Sentry SDK directo + razon de rechazo), Consecuencias, Politica de redaccion; el archivo es >= 800 palabras.

- **Estado:** ⬜ pendiente

### AC-02

Existe `doc/plans/v6.2.0_mcp_observability_plan.md` con la estructura: TL;DR, 5 cambios principales, fases de implementacion, riesgos, metricas de exito, rollback plan; sigue el formato de los plans previos (`v6.0.1_mcp_path_contract_plan.md` como referencia).

- **Estado:** ⬜ pendiente

### AC-03

`CHANGELOG.md` tiene entry v6.2.0 con bullets de los 8 UCs cubiertos (UC-625 a UC-632); el entry sigue el formato de v6.1.1 / v6.0.2.

- **Estado:** ⬜ pendiente

### AC-04

`CLAUDE.md` tiene nueva seccion de nivel 2 '## MCP Observability (v6.2.0)' tras la seccion '## Smoke Test Followups (v6.0.2)' y antes de '## MCP Path Contract (v6.0.1)'; la seccion documenta env vars, los 3 instrumentos de metricas, atributos de spans, politica de redaccion y un ejemplo de query.

- **Estado:** ⬜ pendiente

### AC-05

`pyproject.toml` tiene optional extra `[observability]` con `opentelemetry-sdk>=1.27`, `opentelemetry-exporter-otlp>=1.27`, `opentelemetry-instrumentation-logging>=0.48b0`; un test ejecuta `pip install -e '.[observability]'` en venv limpia y verifica resolucion de deps.

- **Estado:** ⬜ pendiente

### AC-06

`Dockerfile` instala con extra observability (`pip install '.[observability]'`); build del Dockerfile no falla.

- **Estado:** ⬜ pendiente

### AC-07

`ENGINE_VERSION.yaml` bumpeado a `version: 6.2.0` y `name: 'MCP Observability'`; el server log inicial reporta `engine_version=v6.2.0`.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
