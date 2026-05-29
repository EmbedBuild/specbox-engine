---
id: UC-706
ordinal: UC-096
title: Evaluación de prerequisitos (función pura)
parent_us: US-VSCODE-PREREQ-GATE
status: done
actor: Dev solo con Claude Code (ICP-2)
hours: 1.0
owner: Jesús Pérez
created: 2026-05-28
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-706 — Evaluación de prerequisitos (función pura)

> **US padre:** [US-VSCODE-PREREQ-GATE](../us/US-18-gate-de-prerequisitos-de-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-PREREQ-GATE: Gate de prerequisitos de la extensión VSCode
**Actor:** Dev solo con Claude Code (ICP-2)
**Horas estimadas:** 1.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: Existe función pura evaluatePrerequisites(health) que devuelve {verdict:'ready'|'degraded', missing:string[]} con missing = requisitos criticos ausentes (Claude Code, Engram, Node, MCP SpecBox, MCP Engram). verdict='degraded' sii missing.length>0.
- AC-02: GGA ausente NO produce 'degraded' (es opcional). Con todos los criticos presentes y GGA ausente, verdict='ready'.

## Contexto
Función pura evaluatePrerequisites(health) testeable sin vscode.

## Acceptance Criteria

### AC-01

Existe función pura evaluatePrerequisites(health) que devuelve {verdict:'ready'|'degraded', missing:string[]} con missing = requisitos criticos ausentes (Claude Code, Engram, Node, MCP SpecBox, MCP Engram). verdict='degraded' sii missing.length>0.

- **Estado:** ✅ cumplido

### AC-02

GGA ausente NO produce 'degraded' (es opcional). Con todos los criticos presentes y GGA ausente, verdict='ready'.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
