---
id: UC-618
ordinal: UC-055
title: Refactor audit.py tools cat A (check_audit_tools_status, run_quality_audit)
parent_us: US-MCP-PATH-CONTRACT
status: ready
actor: Engine
hours: 5
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-618 — Refactor audit.py tools cat A (check_audit_tools_status, run_quality_audit)

> **US padre:** [US-MCP-PATH-CONTRACT](../us/US-10-eliminar-deuda-tecnica-de-paths-filesystem-mcp-remoto-en-tod.md)

## Objetivo / Descripción

check_audit_tools_status detecta stack para sugerir tools (depende de paths). run_quality_audit orquesta 8 analyzers que cada uno lee filesystem. El refactor es más sustancial porque los analyzers SQuaRE necesitan analizar código real — la decisión arquitectural es: estos analyzers solo se ejecutan en cliente (skill /audit en context: direct), el MCP recibe el reporte ya generado.

## Acceptance Criteria

### AC-01

check_audit_tools_status(stack: str|None) recibe el stack ya detectado por el skill (via UC-617). Devuelve {required_tools, installed, missing, install_commands}. NO lee filesystem.

- **Estado:** ⬜ pendiente

### AC-02

run_quality_audit deja de orquestar analyzers — se renombra a submit_quality_audit(project: str, report: QualityReport) que recibe el report ya construido en cliente y lo persiste en el state registry. Los 8 analyzers se mueven a un módulo Python ejecutable en cliente (.quality/scripts/audit/) que el skill /audit invoca via Bash.

- **Estado:** ⬜ pendiente

### AC-03

Compatibilidad: el skill /audit actualizado (UC-622) genera el QualityReport en cliente y lo envía al MCP. Resultado equivalente al pre-refactor pero arquitectura limpia.

- **Estado:** ⬜ pendiente

### AC-04

attach_audit_evidence y get_last_audit sin cambios (operan sobre state, no filesystem cliente).

- **Estado:** ⬜ pendiente

### AC-05

Tests: tests/test_audit_content_api.py + test_audit_analyzers_local.py.

- **Estado:** ⬜ pendiente

### AC-06

Decisión documentada: los analyzers SQuaRE viven en cliente porque escanear un repo entero por la red sería inviable. Es la única tool donde content-passing puro no aplica — en su lugar usamos report-passing (cliente computa, MCP persiste).

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
