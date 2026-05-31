---
id: US-D01
ordinal: US-09
title: Discovery conversational flow per feature
status: ready
hours: 20
owner: Jesús Pérez
created: 2026-05-24
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# US-D01 — Discovery conversational flow per feature

## Como… quiero… para…

> Como developer sin formación formal de PM, quiero ser guiado por un flujo conversacional corto (15-30 min) que me ayude a identificar los ICPs involucrados en una feature y sus JTBDs racionales y emocionales, para definir el camino de validación de la feature antes de invocar /prd.
> 
> **ICPs involucrados**: ICP-1 (Developer solo con productos en mercado), ICP-2 (Developer experto cruzando a producto), ICP-3 (Profesional no-dev aprendiendo).
> 
> **JTBDs satisfechos**: JR-1.1, JR-2.1, JR-3.1, JR-3.2, JE-1.1, JE-2.1, JE-3.1, JE-3.3.
> 
> Slash command nuevo /discovery [feature_name] con 3 fases (ICP identification, JTBD extraction, validation gate) + modo bootstrap (primer uso en proyecto). Genera doc/discovery/<feature>/icp_jtbd.md.
> 
> Spec completa en doc/prd/discovery_module_v6_prd.md sección 3.

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-D001 | [Ejecutar /discovery [feature_name] en modo estándar](../uc/UC-042-ejecutar-discovery-feature-name-en-modo-estandar.md) | ready |
| UC-D002 | [Ejecutar /discovery en modo bootstrap (primer uso en proyecto)](../uc/UC-046-ejecutar-discovery-en-modo-bootstrap-primer-uso-en-proyecto.md) | ready |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
