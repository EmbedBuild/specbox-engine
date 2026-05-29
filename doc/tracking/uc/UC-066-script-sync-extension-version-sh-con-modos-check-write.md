---
id: UC-634
ordinal: UC-066
title: Script sync-extension-version.sh con modos --check/--write
parent_us: US-VSCODE-MARKETPLACE
status: done
actor: Engine
hours: 4.0
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-634 — Script sync-extension-version.sh con modos --check/--write

> **US padre:** [US-VSCODE-MARKETPLACE](../us/US-13-publicar-la-extension-specbox-al-vscode-marketplace-con-sync.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-MARKETPLACE: Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine
**Actor:** Engine
**Horas estimadas:** 4.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: Script lee version: de ENGINE_VERSION.yaml usando el mismo pattern que install.sh:11 (grep version | head -1 | awk print 2).
- AC-02: Modo --check (default sin args): exit 0 si package.json.version == engine version; exit 1 con mensaje claro si difieren. No escribe nada.
- AC-03: Modo --write: actualiza vscode-extension/package.json con la versión del engine usando jq o un parser Python json (NO sed/regex sobre JSON). Preserva indentación 2-space y orden de keys.
- AC-04: Modo --write también actualiza vscode-extension/package-lock.json si existe (top-level version field).
- AC-05: Tests en scripts/tests/test-sync-extension-version.sh: caso ya sincronizadas, caso drift detectado en --check, caso drift corregido en --write.

## Contexto
Foundational. Lee ENGINE_VERSION.yaml y mantiene vscode-extension/package.json en lockstep.

## Acceptance Criteria

### AC-01

Script lee version: de ENGINE_VERSION.yaml usando el mismo pattern que install.sh:11 (grep version | head -1 | awk print 2).

- **Estado:** ✅ cumplido

### AC-02

Modo --check (default sin args): exit 0 si package.json.version == engine version; exit 1 con mensaje claro si difieren. No escribe nada.

- **Estado:** ✅ cumplido

### AC-03

Modo --write: actualiza vscode-extension/package.json con la versión del engine usando jq o un parser Python json (NO sed/regex sobre JSON). Preserva indentación 2-space y orden de keys.

- **Estado:** ✅ cumplido

### AC-04

Modo --write también actualiza vscode-extension/package-lock.json si existe (top-level version field).

- **Estado:** ✅ cumplido

### AC-05

Tests en scripts/tests/test-sync-extension-version.sh: caso ya sincronizadas, caso drift detectado en --check, caso drift corregido en --write.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
