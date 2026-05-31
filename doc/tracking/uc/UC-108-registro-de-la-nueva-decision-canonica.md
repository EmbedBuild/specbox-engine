---
id: UC-668
ordinal: UC-108
title: Registro de la nueva decision canonica
parent_us: US-CONN-GATE
status: draft
actor: Engine
hours: 2
owner: Jesús Pérez
created: 2026-05-31
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-668 — Registro de la nueva decision canonica

> **US padre:** [US-CONN-GATE](../us/US-21-drift-gate-consciente-de-las-decisiones-canonicas.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

app_spec.md canonical_decisions registra la nueva decision (MCP server nunca toca filesystem ajeno; estado cliente via content-passing/bridge; transporte unico remoto online-first) y marca la anterior (FreeForm requiere MCP local) como revisada/sustituida con referencia a este PRD, sin borrar el historico (append-only). Verificable: el archivo contiene ambas entradas con la relacion de sustitucion explicita.

- **Estado:** ✅ done — zona `canonical_decisions` de `doc/app/app_spec.md` (merge=append_only): la decisión "FreeForm requiere MCP local" queda tachada (`~~...~~`) y marcada REVISADA/SUSTITUIDA; se añade "Transporte único MCP remoto + content-passing", ambas referenciando el PRD. 4 tests `tests/test_canonical_decision_registered.py`, incluido el loop completo (gate UC-667 acepta el Discovery real como documented_exception → no auto-bloqueo).

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
