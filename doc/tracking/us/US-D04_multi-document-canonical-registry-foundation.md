---
id: US-D04
title: Multi-document canonical registry foundation
status: ready
hours: 16
owner: Jesús Pérez
created: 2026-05-24
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# US-D04 — Multi-document canonical registry foundation

## Como… quiero… para…

> Como mantenedor del SpecBox Engine, quiero que el sistema app_docs (sync, drift detection, hook enforcement, upgrade path) opere sobre un registro extensible de N documentos canónicos en lugar de hardcodear app_prd y app_spec, para poder añadir app_market.md en v6.0 y futuros documentos canónicos en v6.x+ sin duplicar código ni introducir bugs por casuística asimétrica.
> 
> **Foundation arquitectural permanente** para Discovery (US-D01..D03). Se implementa PRIMERO. Refactor del módulo server/app_docs/ + descriptor JSON consumible por el hook Node.js. Backwards compatibility total con proyectos v5.x.
> 
> **JTBDs satisfechos**: JR-M.1 (un único punto de modificación), JR-M.2 (proyectos v5.x upgrade-safe), JE-M.1 (arquitectura honesta).
> 
> Spec completa en doc/prd/discovery_module_v6_prd.md sección 3.

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-D005 | [Refactor app_docs a registro multi-doc](../uc/UC-D005_refactor-app-docs-a-registro-multi-doc.md) | ready |
| UC-D006 | [Introducción de app_market.md vía el registro](../uc/UC-D006_introduccion-de-app-market-md-via-el-registro.md) | ready |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
