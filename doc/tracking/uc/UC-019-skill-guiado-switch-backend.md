---
id: UC-406
ordinal: UC-019
title: Skill guiado /switch-backend
parent_us: US-BACKEND-SWITCH
status: done
actor: Desarrollador/equipo
hours: 4
owner: Jesús Pérez
created: 2026-05-22
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-406 — Skill guiado /switch-backend

> **US padre:** [US-BACKEND-SWITCH](../us/US-03-cambio-guiado-de-backend-entre-los-4-freeform-trello-plane-n.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

El skill detecta backend actual via detect_project_backend, pregunta destino entre los 3 restantes y solicita credenciales del destino de forma segura (Native: indica env SPECBOX_NATIVE_DSN y NO pide DSN por chat); verificado por SKILL.md que documenta cada paso.

- **Estado:** ✅ cumplido

### AC-02

Antes de ejecutar muestra preview (migrate_backend dry_run=True) con counts y exige confirmacion literal del usuario; verificado por SKILL.md con paso de confirmacion bloqueante antes de dry_run=False.

- **Estado:** ✅ cumplido

### AC-03

Tras migrar presenta reporte con 4 secciones: switch+consistencia de 3 lugares, aviso de evidencia intacta, lista de estado Native descartado si aplica, y oferta de lanzar regenerate_evidence; verificado por SKILL.md que enumera las 4 secciones.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
