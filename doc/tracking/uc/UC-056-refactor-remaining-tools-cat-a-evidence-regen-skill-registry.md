---
id: UC-620
ordinal: UC-056
title: Refactor remaining tools cat A (evidence_regen, skill_registry, hints, telemetry.get_context_budget, benchmark)
parent_us: US-MCP-PATH-CONTRACT
status: ready
actor: Engine
hours: 4
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-620 — Refactor remaining tools cat A (evidence_regen, skill_registry, hints, telemetry.get_context_budget, benchmark)

> **US padre:** [US-MCP-PATH-CONTRACT](../us/US-10-eliminar-deuda-tecnica-de-paths-filesystem-mcp-remoto-en-tod.md)

## Objetivo / Descripción

Bucket final de las tools cat A restantes: regenerate_evidence, list_skills_v2, discover_skills, get_skill_hint, record_skill_hint, get_context_budget, generate_benchmark_snapshot. Todas comparten patrón similar de filesystem scan.

## Acceptance Criteria

### AC-01

regenerate_evidence(prd_content: str, uc_evidence_inputs: dict[str, str]) recibe PRD + inputs de evidencia. NO lee filesystem. Devuelve regenerated_files_content dict que el skill escribe en cliente.

- **Estado:** ⬜ pendiente

### AC-02

list_skills_v2(skill_manifests: list[dict]) recibe la lista de manifests ya parseados en cliente (el cliente hace el Glob + Read de .claude/skills/*/manifest.yaml).

- **Estado:** ⬜ pendiente

### AC-03

discover_skills(skill_manifests: list[dict], stack: str, keywords: list[str]) similar — cliente provee inputs.

- **Estado:** ⬜ pendiente

### AC-04

get_skill_hint / record_skill_hint: el counter pasa a vivir en el state registry del MCP por project_slug en lugar de en .quality/hint_counters.json del cliente. Cambia el modelo de persistencia pero el API contract con el skill se mantiene equivalente.

- **Estado:** ⬜ pendiente

### AC-05

get_context_budget(file_inventory: dict[str, int]) recibe dict {path: file_size_bytes} construido en cliente. NO escanea filesystem.

- **Estado:** ⬜ pendiente

### AC-06

generate_benchmark_snapshot: el output_path se elimina; la tool devuelve el snapshot content como string y el cliente decide dónde escribirlo.

- **Estado:** ⬜ pendiente

### AC-07

Tests: tests/test_misc_cat_a_content_api.py cubre las 7 tools.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
