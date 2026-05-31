---
id: UC-D005
ordinal: UC-041
title: Refactor app_docs a registro multi-doc
parent_us: US-D04
status: ready
actor: Engine
hours: 12
owner: Jesús Pérez
created: 2026-05-24
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-D005 — Refactor app_docs a registro multi-doc

> **US padre:** [US-D04](../us/US-06-multi-document-canonical-registry-foundation.md)

## Objetivo / Descripción

Extraer la lista de docs canónicos del código duplicado actual (PRD_PATH/SPEC_PATH en server/app_docs/sync.py:38-39, mismo patrón en app-docs-sync-guard.mjs:34-35, EVENT_ZONE_MAP en sync.py:166-179) a un registro único server/app_docs/registry.py + descriptor JSON consumible por el hook Node.js. Todo el resto del sistema itera sobre el registro.

**Crítico para Foundation** — bloquea UC-D006 y todo Discovery. Tests de regresión obligatorios contra proyectos fixture v5.29/v5.33/v5.35.

## Acceptance Criteria

### AC-01

[AC-01] Existe módulo server/app_docs/registry.py que expone CANONICAL_DOCS: list[CanonicalDoc]. Cada entrada tiene: id, path, introduced_in (semver), template_path, required_zones: dict[str, ZoneKind], event_zone_map: dict[event, list[zone_id]].

- **Estado:** ⬜ pendiente

### AC-02

[AC-02] server/app_docs/sync.py (verify_app_docs_in_sync, record_sync_signature, EVENT_ZONE_MAP) itera sobre CANONICAL_DOCS en lugar de tener 2 ramas hardcoded para PRD/SPEC. Las constantes PRD_PATH, SPEC_PATH se eliminan.

- **Estado:** ⬜ pendiente

### AC-03

[AC-03] .claude/hooks/app-docs-sync-guard.mjs lee templates/canonical_docs.json (descriptor generado desde el módulo Python como source-of-truth, D-10 opción b) e itera sobre la lista. Sin hardcoded checkDoc('app_prd', ...) / checkDoc('app_spec', ...).

- **Estado:** ⬜ pendiente

### AC-04

[AC-04] Cada CanonicalDoc lleva campo introduced_in: str (semver). El hook y verify_app_docs_in_sync ignoran un doc cuando: (a) no existe en disco, AND (b) project_meta.engine_version_at_onboard < doc.introduced_in. Esto evita warnings espurios en proyectos upgrade-from-v5.x.

- **Estado:** ⬜ pendiente

### AC-05

[AC-05] meta.json del proyecto incluye nuevo campo engine_version_at_onboard (capturado en onboard_project y preservado en upgrade_project). Para proyectos v5.x preexistentes que no tengan este campo en su meta.json, política conservadora: tratar como 'unknown', y el hook solo verifica docs con introduced_in <= 5.29.0. Esto resuelve D-11 como opción (b).

- **Estado:** ⬜ pendiente

### AC-06

[AC-06] Tests de regresión: matriz {proyectos fixture en v5.29, v5.33, v5.35} × {operaciones: verify, repair, hook commit, /app-sync} pasa sin cambio de comportamiento observable. Snapshot tests guardan output esperado.

- **Estado:** ⬜ pendiente

### AC-07

[AC-07] La extensión de CANONICAL_DOCS con app_market.md (UC-D006) requiere una sola línea de código + una entrada en el registro + una plantilla. Sin cambios en sync.py, hook, ni /app-sync.

- **Estado:** ⬜ pendiente

### AC-08

[AC-08] Tool MCP read_app_docs_tool recibe parámetro opcional doc_ids: list[str] = None. Si None, devuelve todos los docs canónicos del proyecto (incluyendo nuevos como app_market). Backwards compat: comportamiento previo = pasar doc_ids=['app_prd', 'app_spec'] explícito.

- **Estado:** ⬜ pendiente

### AC-09

[AC-09] La PR del refactor incluye un documento doc/decisions/multi_doc_registry.md explicando: por qué se hizo, qué patrón se eligió (registry vs subclasses vs plugins), qué se descartó, cómo extender en futuras versiones.

- **Estado:** ⬜ pendiente

### AC-10

[AC-10] upgrade_project se extiende para iterar sobre CANONICAL_DOCS y, para cada doc canónico con introduced_in > project_meta.engine_version_at_onboard: si el archivo NO existe en el proyecto destino escribe plantilla vacía con marcadores de zona desde template_path; si el archivo SÍ existe no toca nada (preserva contenido del usuario). Reporta en el return cuáles docs canónicos creó vs cuáles ya existían en campo nuevo canonical_docs_created: list[dict].

- **Estado:** ⬜ pendiente

### AC-11

[AC-11] La invariante 'upgrade_project nunca pisa contenido existente' se preserva. Lo que cambia es que ahora puede CREAR archivos nuevos, no MODIFICAR archivos existentes. Esa distinción se documenta explícitamente en el docstring de upgrade_project y en doc/decisions/multi_doc_registry.md.

- **Estado:** ⬜ pendiente

### AC-12

[AC-12] Test fixture específico: 'proyecto v5.35 con app_prd.md modificado manualmente recibe upgrade a v6.0'. Verifica: app_prd.md queda exactamente igual (byte por byte); app_spec.md queda exactamente igual; app_market.md se crea desde plantilla vacía con marcador status='template-pristine'; engine_version_at_onboard se preserva o se marca 'unknown' si no existía.

- **Estado:** ⬜ pendiente

### AC-13

[AC-13] Plantillas de docs canónicos llevan marcador status='template-pristine' en zonas manual. El hook app-docs-sync-guard.mjs lo respeta — no warnea sobre docs presentes pero no inicializados. /discovery y /app-init eliminan el marcador automáticamente cuando rellenan la primera zona.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
