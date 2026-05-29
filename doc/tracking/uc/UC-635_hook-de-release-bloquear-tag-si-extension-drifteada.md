---
id: UC-635
title: "Hook de release: bloquear tag si extensión drifteada"
parent_us: US-VSCODE-MARKETPLACE
status: done
actor: Engine
hours: 3.0
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-635 — Hook de release: bloquear tag si extensión drifteada

> **US padre:** [US-VSCODE-MARKETPLACE](../us/US-VSCODE-MARKETPLACE_publicar-la-extension-specbox-al-vscode-marketplace-con-sync.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-MARKETPLACE: Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine
**Actor:** Engine
**Horas estimadas:** 3.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: /release SKILL.md actualizado: nuevo paso Pre-flight verify VSCode extension version sync antes del paso de tagging.
- AC-02: El paso corre bash scripts/sync-extension-version.sh --check. Si exit 0, sigue.
- AC-03: Si exit != 0, el skill prompta al usuario: opción 1 auto-fix + commit (corre --write, hace commit chore(vscode-ext) sync version to vX.Y.Z), opción 2 abort release. Sin opción 3 (no se permite tagear con drift).
- AC-04: Si se elige opción 1, el commit de sync entra ANTES del commit de release notes y del tag. Verificado por git log --oneline -3 post-release.
- AC-05: Test manual documentado en el SKILL.md de /release: cómo simular drift y verificar que el gate dispara.

## Contexto
Integra sync-extension-version.sh --check en /release skill como gate pre-tag. Sin opción ignore.

## Acceptance Criteria

### AC-01

/release SKILL.md actualizado: nuevo paso Pre-flight verify VSCode extension version sync antes del paso de tagging.

- **Estado:** ✅ cumplido

### AC-02

El paso corre bash scripts/sync-extension-version.sh --check. Si exit 0, sigue.

- **Estado:** ✅ cumplido

### AC-03

Si exit != 0, el skill prompta al usuario: opción 1 auto-fix + commit (corre --write, hace commit chore(vscode-ext) sync version to vX.Y.Z), opción 2 abort release. Sin opción 3 (no se permite tagear con drift).

- **Estado:** ✅ cumplido

### AC-04

Si se elige opción 1, el commit de sync entra ANTES del commit de release notes y del tag. Verificado por git log --oneline -3 post-release.

- **Estado:** ✅ cumplido

### AC-05

Test manual documentado en el SKILL.md de /release: cómo simular drift y verificar que el gate dispara.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
