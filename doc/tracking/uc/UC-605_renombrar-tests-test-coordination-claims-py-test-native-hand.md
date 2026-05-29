---
id: UC-605
title: "Renombrar tests: test_coordination_claims.py + test_native_handling.py + assertions"
parent_us: US-CLAIM-RENAME
status: review
actor: Engine
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-605 — Renombrar tests: test_coordination_claims.py + test_native_handling.py + assertions

> **US padre:** [US-CLAIM-RENAME](../us/US-CLAIM-RENAME_renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

**User Story:** US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
**Actor:** Engine
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [AC-01] `tests/test_coordination_reservations.py` existe; `tests/test_coordination_claims.py` ya no existe; `.venv/bin/pytest tests/test_coordination_reservations.py -q` termina 100% en verde contra Postgres dev local.
- AC-02: [AC-02] `tests/test_coordination_reservations.py::test_deprecated_claim_uc_alias_emits_warning` existe y verifica con `pytest.warns(DeprecationWarning)` que llamar a la tool `claim_uc` emite warning y devuelve payload con ambas claves (`reserved_at` y `claimed_at`).
- AC-03: [AC-03] La suite completa de native (`.venv/bin/pytest tests/test_native_*.py tests/test_coordination_reservations.py -q`) termina en 50 passed + el test nuevo del alias = 51 passed, 0 skipped, contra el Postgres dev local.

## Contexto

## Acceptance Criteria

### AC-01

[AC-01] `tests/test_coordination_reservations.py` existe; `tests/test_coordination_claims.py` ya no existe; `.venv/bin/pytest tests/test_coordination_reservations.py -q` termina 100% en verde contra Postgres dev local.

- **Estado:** ✅ cumplido

### AC-02

[AC-02] `tests/test_coordination_reservations.py::test_deprecated_claim_uc_alias_emits_warning` existe y verifica con `pytest.warns(DeprecationWarning)` que llamar a la tool `claim_uc` emite warning y devuelve payload con ambas claves (`reserved_at` y `claimed_at`).

- **Estado:** ✅ cumplido

### AC-03

[AC-03] La suite completa de native (`.venv/bin/pytest tests/test_native_*.py tests/test_coordination_reservations.py -q`) termina en 50 passed + el test nuevo del alias = 51 passed, 0 skipped, contra el Postgres dev local.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
