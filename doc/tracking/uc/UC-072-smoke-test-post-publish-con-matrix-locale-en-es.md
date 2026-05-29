---
id: UC-640
ordinal: UC-072
title: Smoke test post-publish con matrix locale [en, es]
parent_us: US-VSCODE-MARKETPLACE
status: done
actor: Engine
hours: 4.0
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-640 — Smoke test post-publish con matrix locale [en, es]

> **US padre:** [US-VSCODE-MARKETPLACE](../us/US-13-publicar-la-extension-specbox-al-vscode-marketplace-con-sync.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-MARKETPLACE: Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine
**Actor:** Engine
**Horas estimadas:** 4.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: Workflow en .github/workflows/smoke-test-marketplace.yml. Trigger: workflow_run después de publish-vscode-extension.yml exitoso, O manual via workflow_dispatch.
- AC-02: Job en ubuntu-latest, instala VSCode CLI (code via apt o snap), corre code --install-extension EmbedBuild.specbox-engine --force.
- AC-03: Job verifica code --list-extensions | grep EmbedBuild.specbox-engine retorna exit 0 y la versión instalada matchea el tag actual.
- AC-04: Job crea un workspace dummy con ENGINE_VERSION.yaml (trigger de activación de la extensión), abre VSCode headless, verifica via code --status o un test script que la extensión está activa.
- AC-05: Job corre el smoke en matrix locale en y es: instala con code --locale=en y luego code --locale=es, verifica para cada uno que el comando SpecBox Install Engine (EN) / SpecBox Instalar Engine (ES) aparece en el listado de comandos registrados. Falla el job si alguna variante no resuelve la traducción correcta.
- AC-06: Si el smoke test falla, el workflow abre automáticamente un issue en el repo con label marketplace-smoke-fail y el output del workflow. NO hace rollback automático.

## Contexto
Workflow disparado tras publish exitoso. Instala desde Marketplace en VSCode headless, verifica activación y i18n.

## Acceptance Criteria

### AC-01

Workflow en .github/workflows/smoke-test-marketplace.yml. Trigger: workflow_run después de publish-vscode-extension.yml exitoso, O manual via workflow_dispatch.

- **Estado:** ✅ cumplido

### AC-02

Job en ubuntu-latest, instala VSCode CLI (code via apt o snap), corre code --install-extension EmbedBuild.specbox-engine --force.

- **Estado:** ✅ cumplido

### AC-03

Job verifica code --list-extensions | grep EmbedBuild.specbox-engine retorna exit 0 y la versión instalada matchea el tag actual.

- **Estado:** ✅ cumplido

### AC-04

Job crea un workspace dummy con ENGINE_VERSION.yaml (trigger de activación de la extensión), abre VSCode headless, verifica via code --status o un test script que la extensión está activa.

- **Estado:** ✅ cumplido

### AC-05

Job corre el smoke en matrix locale en y es: instala con code --locale=en y luego code --locale=es, verifica para cada uno que el comando SpecBox Install Engine (EN) / SpecBox Instalar Engine (ES) aparece en el listado de comandos registrados. Falla el job si alguna variante no resuelve la traducción correcta.

- **Estado:** ✅ cumplido

### AC-06

Si el smoke test falla, el workflow abre automáticamente un issue en el repo con label marketplace-smoke-fail y el output del workflow. NO hace rollback automático.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
