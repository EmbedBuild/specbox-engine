---
id: UC-D004
title: Drift detection ICP/JTBD entre feature y producto
parent_us: US-D03
status: ready
actor: Engine
hours: 6
owner: Jesús Pérez
created: 2026-05-24
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-D004 — Drift detection ICP/JTBD entre feature y producto

> **US padre:** [US-D03](../us/US-D03_strategic-drift-detection-across-project-lifetime.md)

## Objetivo / Descripción

Cada /discovery por feature compara los ICPs y JTBDs declarados contra app_market.md. Si introduce elementos no presentes a nivel producto, dispara warning estructurado que el user debe responder explícitamente.

## Acceptance Criteria

### AC-01

[AC-01] Al final de la Fase 2 (JTBD extraction) en UC-D001, el sistema compara cada ICP y JTBD declarado contra app_market.md. Elementos nuevos se listan explícitamente. [JR-1.2, JE-1.2]

- **Estado:** ⬜ pendiente

### AC-02

[AC-02] Para cada elemento nuevo, el sistema pregunta '¿Es esto: (a) feature creep que debería rechazarse, (b) extensión legítima que debería actualizar app_market.md, o (c) excepción puntual aceptable solo para esta feature?'. La respuesta se registra. [JR-1.2, JE-1.2]

- **Estado:** ⬜ pendiente

### AC-03

[AC-03] Si la respuesta es (b), el sistema ofrece actualizar app_market.md ahí mismo. Si la respuesta es (c), registra 'excepción documentada' en icp_jtbd.md con justificación obligatoria. [JR-2.2]

- **Estado:** ⬜ pendiente

### AC-04

[AC-04] Si la respuesta es (a), la feature se marca como cancelada en /discovery y no genera artefacto que permita pasar a /prd. [JR-1.2]

- **Estado:** ⬜ pendiente

### AC-05

[AC-05] El hook verify_app_market (extensión de verify_app_docs existente) chequea sync entre app_market.md y los icp_jtbd.md de las últimas N features (default N=5). Si hay drift sistemático sin resolver, warning durante invocación de cualquier slash command. [JR-1.2, JE-1.2]

- **Estado:** ⬜ pendiente

### AC-06

[AC-06] Comando opcional /discovery --review muestra dashboard de drift: ICPs nuevos introducidos por feature en últimas 30 días, JTBDs emergentes, excepciones documentadas pendientes de resolver. NOTA: D-08 resuelve este AC como DEFERRED a v6.1 (no implementar en v6.0). [JR-1.2]

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
