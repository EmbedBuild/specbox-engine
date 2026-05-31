---
id: UC-614
ordinal: UC-052
title: Refactor 3 tools v6.0 Discovery a content-passing API
parent_us: US-MCP-PATH-CONTRACT
status: ready
actor: Engine
hours: 4
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-614 — Refactor 3 tools v6.0 Discovery a content-passing API

> **US padre:** [US-MCP-PATH-CONTRACT](../us/US-10-eliminar-deuda-tecnica-de-paths-filesystem-mcp-remoto-en-tod.md)

## Objetivo / Descripción

Las 3 tools nuevas de v6.0 (start_discovery, validate_discovery_completeness, detect_v60_migration_case) son las que el usuario detectó rotas hoy desde el proyecto specbox-control-panel. API change: aceptan contenido por parámetro en lugar de project_path. Es el caso más urgente porque es feature recién shippeada y todavía sin uso productivo — ventana ideal para romper API.

## Acceptance Criteria

### AC-01

start_discovery(feature_name: str, app_market_content: str|None = None, existing_artifact_content: str|None = None, mode: str = "auto") devuelve {discovery_id, status, mode_used, app_market_present, skeleton_content, next_step}. NO escribe filesystem. Si existing_artifact_content viene None, devuelve status=created + skeleton_content. Si viene con texto, devuelve status=resumable + parsea el contenido para detectar discovery_id previo.

- **Estado:** ⬜ pendiente

### AC-02

validate_discovery_completeness(feature_name: str, icp_jtbd_content: str) devuelve {verdict, missing[], drift{section_present, resolved}, sections_found[]}. NO lee filesystem. El parser sigue siendo _validate_icp_jtbd() existente pero ahora opera sobre el string del parámetro.

- **Estado:** ⬜ pendiente

### AC-03

detect_v60_migration_case(app_prd_content: str|None, app_spec_content: str|None, app_market_content: str|None, settings_local_json_content: str|None) devuelve {case, label, action_required, backup_required, notes[]}. NO lee filesystem. Si los 4 parámetros vienen None, devuelve case="empty_or_fresh_clone".

- **Estado:** ⬜ pendiente

### AC-04

El parámetro project_path se elimina completamente de las firmas — NO se mantiene como opcional ni como deprecation warning. Justificación: v6.0 lleva <24h en main, expone API rota a MCP remoto que es el caso default, no hay callers externos.

- **Estado:** ⬜ pendiente

### AC-05

Tests: tests/test_discovery_content_api.py cubre las 3 tools con casos: (a) contenido completo bootstrap mode, (b) contenido completo standard mode, (c) contenido vacío/None, (d) contenido malformado, (e) idempotencia (segunda llamada con artifact existing).

- **Estado:** ⬜ pendiente

### AC-06

tests/test_discovery.py existente se adapta a la nueva API; 0 regresión de tests previos no relacionados con paths.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
