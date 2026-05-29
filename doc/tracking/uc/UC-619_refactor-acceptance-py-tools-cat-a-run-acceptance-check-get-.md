---
id: UC-619
title: Refactor acceptance.py tools cat A (run_acceptance_check, get_acceptance_report, get_e2e_gap_report)
parent_us: US-MCP-PATH-CONTRACT
status: ready
actor: Engine
hours: 5
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-619 — Refactor acceptance.py tools cat A (run_acceptance_check, get_acceptance_report, get_e2e_gap_report)

> **US padre:** [US-MCP-PATH-CONTRACT](../us/US-MCP-PATH-CONTRACT_eliminar-deuda-tecnica-de-paths-filesystem-mcp-remoto-en-tod.md)

## Objetivo / Descripción

Tres tools de acceptance que leen PRDs + evidencia. run_acceptance_check valida AC contra código (necesita código en cliente). get_acceptance_report lee .quality/evidence/. get_e2e_gap_report escanea PRDs.

## Acceptance Criteria

### AC-01

run_acceptance_check(prd_content: str, item_id: str, branch: str, code_diff: str|None) recibe contenido del PRD + opcionalmente el diff de código. NO lee filesystem cliente. Devuelve verdict por AC.

- **Estado:** ⬜ pendiente

### AC-02

get_acceptance_report(prd_content: str, evidence_files: dict[str, str]) recibe contenido del PRD + dict con paths-relativos→contenido de results.json y HTML reports. Devuelve report consolidado.

- **Estado:** ⬜ pendiente

### AC-03

get_e2e_gap_report(prd_contents: list[str]) recibe lista de contenidos de PRDs del proyecto. Devuelve gap report.

- **Estado:** ⬜ pendiente

### AC-04

Skill /acceptance-check (.claude/skills/acceptance-check/) actualizado para leer PRDs + evidence con Read en cliente y pasar contenido al MCP.

- **Estado:** ⬜ pendiente

### AC-05

Tests: tests/test_acceptance_content_api.py.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
