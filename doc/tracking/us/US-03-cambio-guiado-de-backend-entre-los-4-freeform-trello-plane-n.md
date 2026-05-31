---
id: US-BACKEND-SWITCH
ordinal: US-03
title: Cambio guiado de backend entre los 4 (FreeForm/Trello/Plane/Native)
status: review
hours: 52
owner: Jesús Pérez
created: 2026-05-22
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# US-BACKEND-SWITCH — Cambio guiado de backend entre los 4 (FreeForm/Trello/Plane/Native)

## Como… quiero… para…

> Como desarrollador o equipo que usa SpecBox, quiero cambiar el backend de tracking de mi proyecto entre cualquiera de los 4 (FreeForm/Trello/Plane/Native) de forma guiada, para adaptar el gestor a la fase del proyecto (local -> reporting a cliente -> multi-dev) sin perder datos ni el avance de ejecucion registrado. Generaliza la migracion a N×N (12 pares) + skill /switch-backend + regeneracion de evidencias.

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-801 | [Lectura/escritura generica entre los 4 backends](../uc/UC-020-lectura-escritura-generica-entre-los-4-backends.md) | done |
| UC-802 | [Matriz de mapeo de estados bidireccional entre los 4 backends](../uc/UC-016-matriz-de-mapeo-de-estados-bidireccional-entre-los-4-backend.md) | done |
| UC-803 | [Manejo del backend Native (entrada y salida)](../uc/UC-021-manejo-del-backend-native-entrada-y-salida.md) | done |
| UC-804 | [Tool migrate_backend N×N + switch_backend generalizado + update transaccional](../uc/UC-017-tool-migrate-backend-nn-switch-backend-generalizado-update-t.md) | done |
| UC-805 | [Regeneracion de evidencias con progreso por UC](../uc/UC-018-regeneracion-de-evidencias-con-progreso-por-uc.md) | done |
| UC-806 | [Skill guiado /switch-backend](../uc/UC-019-skill-guiado-switch-backend.md) | done |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
