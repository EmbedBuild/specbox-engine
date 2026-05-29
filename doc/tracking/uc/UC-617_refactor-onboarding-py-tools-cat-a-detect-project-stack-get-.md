---
id: UC-617
title: Refactor onboarding.py tools cat A (detect_project_stack, get_onboarding_status, get_visual_gap_report)
parent_us: US-MCP-PATH-CONTRACT
status: ready
actor: Engine
hours: 5
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-617 — Refactor onboarding.py tools cat A (detect_project_stack, get_onboarding_status, get_visual_gap_report)

> **US padre:** [US-MCP-PATH-CONTRACT](../us/US-MCP-PATH-CONTRACT_eliminar-deuda-tecnica-de-paths-filesystem-mcp-remoto-en-tod.md)

## Objetivo / Descripción

Tres tools críticas en onboarding.py que escanean filesystem del proyecto cliente. detect_project_stack lee package.json/go.mod/pubspec.yaml; get_onboarding_status lee .claude/, doc/; get_visual_gap_report escanea doc/design/.

## Acceptance Criteria

### AC-01

detect_project_stack(stack_signals: dict[str, str|None]) recibe un dict con contenidos de archivos signal (package_json_content, go_mod_content, pubspec_yaml_content, requirements_txt_content, pyproject_toml_content, app_yaml_content). Devuelve {stack, confidence, signals_used}. NO lee filesystem.

- **Estado:** ⬜ pendiente

### AC-02

get_onboarding_status(project_files: dict[str, str|None]) recibe contenidos de archivos clave (.claude/settings.json, .claude/settings.local.json, doc/app/app_prd.md, doc/app/app_spec.md, .quality/baseline.json). Devuelve status report.

- **Estado:** ⬜ pendiente

### AC-03

get_visual_gap_report(design_inventory: dict[str, list[str]]) recibe un dict {feature_name: [list of HTML files present]} construido en cliente. Devuelve gap report.

- **Estado:** ⬜ pendiente

### AC-04

Skill /onboard (si existe) o el flujo de onboard_project consumen las nuevas APIs.

- **Estado:** ⬜ pendiente

### AC-05

Tests: tests/test_onboarding_content_api.py cubre las 3 tools.

- **Estado:** ⬜ pendiente

### AC-06

detect_local_root_path() permanece sin cambios — sigue siendo declaración de contrato.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
