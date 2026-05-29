---
id: UC-606
ordinal: UC-033
title: "Documentación del engine: CLAUDE.md, GLOBAL_RULES, READMEs, plans históricos"
parent_us: US-CLAIM-RENAME
status: review
actor: Engine
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-606 — Documentación del engine: CLAUDE.md, GLOBAL_RULES, READMEs, plans históricos

> **US padre:** [US-CLAIM-RENAME](../us/US-05-renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

**User Story:** US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
**Actor:** Engine
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [AC-01] `grep -rn 'uc_claims\|claim_uc\|claimed_at\|claims.py' CLAUDE.md rules/ server/coordination/__init__.py doc/app/` no devuelve ninguna línea (excepto la nota al pie histórica en CLAUDE.md y la decisión canónica nueva en app_spec.md que mencionan el término entre comillas como referencia histórica).
- AC-02: [AC-02] `CLAUDE.md` contiene una sección/nota explícita: "Desde v5.35.0 el concepto antes llamado 'claim' se llama 'reservation'. Las tools MCP `claim_uc` y el código `ALREADY_CLAIMED` están deprecados desde v5.35.0 y se eliminan en v5.37.0".
- AC-03: [AC-03] `ENGINE_VERSION.yaml` declara `version: 5.35.0` y el changelog incluye un bullet específico del rename con referencia a UC-604 (deprecación) y v5.37.0 (eliminación).
- AC-04: [AC-04] `doc/app/app_spec.md` zona canonical_decisions (hybrid) tiene un append: "`claim`→`reservation` (v5.35.0): renombre del concepto de coordinación multi-developer del Native Backend; rationale = legibilidad para no técnicos; alias deprecados v5.35–v5.36; tools MCP `claim_uc` removed in v5.37.0.".

## Contexto

## Acceptance Criteria

### AC-01

[AC-01] `grep -rn 'uc_claims\|claim_uc\|claimed_at\|claims.py' CLAUDE.md rules/ server/coordination/__init__.py doc/app/` no devuelve ninguna línea (excepto la nota al pie histórica en CLAUDE.md y la decisión canónica nueva en app_spec.md que mencionan el término entre comillas como referencia histórica).

- **Estado:** ✅ cumplido

### AC-02

[AC-02] `CLAUDE.md` contiene una sección/nota explícita: "Desde v5.35.0 el concepto antes llamado 'claim' se llama 'reservation'. Las tools MCP `claim_uc` y el código `ALREADY_CLAIMED` están deprecados desde v5.35.0 y se eliminan en v5.37.0".

- **Estado:** ✅ cumplido

### AC-03

[AC-03] `ENGINE_VERSION.yaml` declara `version: 5.35.0` y el changelog incluye un bullet específico del rename con referencia a UC-604 (deprecación) y v5.37.0 (eliminación).

- **Estado:** ✅ cumplido

### AC-04

[AC-04] `doc/app/app_spec.md` zona canonical_decisions (hybrid) tiene un append: "`claim`→`reservation` (v5.35.0): renombre del concepto de coordinación multi-developer del Native Backend; rationale = legibilidad para no técnicos; alias deprecados v5.35–v5.36; tools MCP `claim_uc` removed in v5.37.0.".

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
