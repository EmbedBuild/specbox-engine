---
id: US-NATIVE-BACKEND
title: SpecBox para equipos sobre Postgres nativo
status: done
hours: 85
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# US-NATIVE-BACKEND — SpecBox para equipos sobre Postgres nativo

## Como… quiero… para…

> Como equipo de desarrolladores que usa SpecBox sobre la misma app, quiero un backend centralizado con identidad y coordinacion de UCs, para trabajar en paralelo sin pisarnos las US/UC ni colisionar branches. Alcance v1 = H1+H2+H3 (Modo A: Postgres interno en VPS, solo el MCP tiene credenciales).

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-101 | [Implementar NativeBackend sobre el SpecBackend ABC](../uc/UC-101_implementar-nativebackend-sobre-el-specbackend-abc.md) | done |
| UC-102 | [Esquema Postgres multi-tenant](../uc/UC-102_esquema-postgres-multi-tenant.md) | done |
| UC-103 | [Seleccion de backend Nativo opt-in por proyecto](../uc/UC-103_seleccion-de-backend-nativo-opt-in-por-proyecto.md) | done |
| UC-201 | [Modelo de developer y token](../uc/UC-201_modelo-de-developer-y-token.md) | done |
| UC-202 | [Autenticacion y autorizacion en el MCP (Frontera 1)](../uc/UC-202_autenticacion-y-autorizacion-en-el-mcp-frontera-1.md) | done |
| UC-203 | [Tool whoami](../uc/UC-203_tool-whoami.md) | done |
| UC-301 | [Tabla de claims con exclusion mutua](../uc/UC-301_tabla-de-claims-con-exclusion-mutua.md) | done |
| UC-302 | [start_uc consulta claims](../uc/UC-302_start-uc-consulta-claims.md) | done |
| UC-303 | [find_next_uc excluye reclamados](../uc/UC-303_find-next-uc-excluye-reclamados.md) | done |
| UC-304 | [active_uc.json como cache + branch_registry](../uc/UC-304_active-uc-json-como-cache-branch-registry.md) | done |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
