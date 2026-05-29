---
id: UC-702
title: Agrupación de skills por categoría
parent_us: US-VSCODE-DISCOVERABILITY
status: review
actor: Extensión VSCode
hours: 3.0
owner: Jesús Pérez
created: 2026-05-27
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-702 — Agrupación de skills por categoría

> **US padre:** [US-VSCODE-DISCOVERABILITY](../us/US-VSCODE-DISCOVERABILITY_sidebar-de-descubrimiento-y-ayuda-para-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-DISCOVERABILITY: Sidebar de descubrimiento y ayuda para la extensión VSCode
**Actor:** Extensión VSCode
**Horas estimadas:** 3.0
**Pantallas:** sidebar specbox.skills

## Criterios de Aceptacion
- AC-01: [JR-F.5] El TreeView muestra 7 categorías de primer nivel colapsables en orden fijo: Pipeline, Quality, Visual, Tracking, Stripe, Lifecycle, Otros.
- AC-02: Cada categoría tiene un icono ThemeIcon distinto y consistente (rocket / shield / paintcan / list-tree / credit-card / tools / question).
- AC-03: El mapping skill→categoría está declarado en skill-categories.ts con tipado TypeScript estricto; skills no listados caen automáticamente en Otros.
- AC-04: Cada categoría muestra entre paréntesis el número de skills detectados que contiene (p.ej. 'Pipeline (4)', 'Otros (0)'). Una categoría con 0 skills sigue mostrándose colapsada con '(0)' para preservar el mental model.
- AC-05: El mapping cubre al menos los 25 skills actuales del engine: prd, plan, implement, feedback (Pipeline); audit, compliance, quality-gate, acceptance-check (Quality); visual-setup, adapt-ui, check-designs (Visual); switch-backend, app-init, app-sync, queue-review (Tracking); stripe-connect, stripe-standard, stripe-switch-account (Stripe); release, handoff, discovery, quickstart, manual-test, optimize-agents, explore (Lifecycle).

## Contexto
Introduce 7 categorías root en el TreeView (Pipeline / Quality / Visual / Tracking / Stripe / Lifecycle / Otros). Mapping skill→categoría declarado en archivo dedicado skill-categories.ts con tipado TypeScript estricto.

## Acceptance Criteria

### AC-01

[JR-F.5] El TreeView muestra 7 categorías de primer nivel colapsables en orden fijo: Pipeline, Quality, Visual, Tracking, Stripe, Lifecycle, Otros.

- **Estado:** ⬜ pendiente

### AC-02

Cada categoría tiene un icono ThemeIcon distinto y consistente (rocket / shield / paintcan / list-tree / credit-card / tools / question).

- **Estado:** ⬜ pendiente

### AC-03

El mapping skill→categoría está declarado en skill-categories.ts con tipado TypeScript estricto; skills no listados caen automáticamente en Otros.

- **Estado:** ⬜ pendiente

### AC-04

Cada categoría muestra entre paréntesis el número de skills detectados que contiene (p.ej. 'Pipeline (4)', 'Otros (0)'). Una categoría con 0 skills sigue mostrándose colapsada con '(0)' para preservar el mental model.

- **Estado:** ⬜ pendiente

### AC-05

El mapping cubre al menos los 25 skills actuales del engine: prd, plan, implement, feedback (Pipeline); audit, compliance, quality-gate, acceptance-check (Quality); visual-setup, adapt-ui, check-designs (Visual); switch-backend, app-init, app-sync, queue-review (Tracking); stripe-connect, stripe-standard, stripe-switch-account (Stripe); release, handoff, discovery, quickstart, manual-test, optimize-agents, explore (Lifecycle).

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
