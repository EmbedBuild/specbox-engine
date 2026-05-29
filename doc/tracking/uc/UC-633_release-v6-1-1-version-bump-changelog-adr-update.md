---
id: UC-633
title: Release v6.1.1 — version bump + CHANGELOG + ADR update
parent_us: US-CUTOVER-FOLLOWUP
status: ready
actor: Maintainer
hours: 0.7
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-633 — Release v6.1.1 — version bump + CHANGELOG + ADR update

> **US padre:** [US-CUTOVER-FOLLOWUP](../us/US-CUTOVER-FOLLOWUP_cerrar-deuda-residual-de-sala-de-maquinas-tras-v6-1-0.md)

## Objetivo / Descripción

**User Story:** US-CUTOVER-FOLLOWUP: Cerrar deuda residual de Sala de Máquinas tras v6.1.0
**Actor:** Maintainer
**Horas estimadas:** 0.7
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: ENGINE_VERSION.yaml version: 6.1.0 → 6.1.1, codename: 'Cloud Cutover' → 'Cutover Followup'
- AC-02: pyproject.toml version = '6.1.0' → '6.1.1' y la description se actualiza
- AC-03: CLAUDE.md header (# SpecBox Engine v6.1.0) y footer 'Engine Version' bumpean a v6.1.1 'Cutover Followup'
- AC-04: CHANGELOG.md añade entry [6.1.1] - 2026-05-25 — 'Cutover Followup' con secciones Removed / Changed / Tests al inicio del archivo. Entradas históricas intactas
- AC-05: doc/decisions/cloud_cutover.md recibe una sección final 'v6.1.1 followup' documentando que la deuda residual quedó cerrada en esta release

## Contexto
ENGINE_VERSION.yaml + pyproject.toml + CLAUDE.md header/footer + CHANGELOG.md entry + doc/decisions/cloud_cutover.md sección followup. version-consistency-check.mjs valida.

## Acceptance Criteria

### AC-01

ENGINE_VERSION.yaml version: 6.1.0 → 6.1.1, codename: 'Cloud Cutover' → 'Cutover Followup'

- **Estado:** ⬜ pendiente

### AC-02

pyproject.toml version = '6.1.0' → '6.1.1' y la description se actualiza

- **Estado:** ⬜ pendiente

### AC-03

CLAUDE.md header (# SpecBox Engine v6.1.0) y footer 'Engine Version' bumpean a v6.1.1 'Cutover Followup'

- **Estado:** ⬜ pendiente

### AC-04

CHANGELOG.md añade entry [6.1.1] - 2026-05-25 — 'Cutover Followup' con secciones Removed / Changed / Tests al inicio del archivo. Entradas históricas intactas

- **Estado:** ⬜ pendiente

### AC-05

doc/decisions/cloud_cutover.md recibe una sección final 'v6.1.1 followup' documentando que la deuda residual quedó cerrada en esta release

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
