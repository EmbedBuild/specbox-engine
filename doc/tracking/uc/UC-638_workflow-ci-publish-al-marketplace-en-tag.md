---
id: UC-638
title: "Workflow CI: publish al Marketplace en tag"
parent_us: US-VSCODE-MARKETPLACE
status: done
actor: Engine
hours: 6.0
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-638 — Workflow CI: publish al Marketplace en tag

> **US padre:** [US-VSCODE-MARKETPLACE](../us/US-VSCODE-MARKETPLACE_publicar-la-extension-specbox-al-vscode-marketplace-con-sync.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-MARKETPLACE: Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine
**Actor:** Engine
**Horas estimadas:** 6.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: Workflow file en .github/workflows/publish-vscode-extension.yml. Trigger: on push tags v*.*.* + workflow_dispatch.
- AC-02: Job corre en ubuntu-latest, Node.js 20 LTS, instala @vscode/vsce globalmente, hace cd vscode-extension && npm ci && npm run vscode prepublish.
- AC-03: Step Sync version corre bash scripts/sync-extension-version.sh --check y falla el workflow si hay drift (defense-in-depth).
- AC-04: Step Publish corre vsce publish --pat secrets.VSCE_PAT. Output capturado en logs del workflow.
- AC-05: Step Attach VSIX to release corre vsce package -o specbox-engine-VERSION.vsix + sube el .vsix al GitHub Release vVERSION usando softprops/action-gh-release@v2.
- AC-06: Workflow respeta el principio no skipping hooks: si vsce publish falla, el job entero falla y notifica.

## Contexto
Primer workflow CI del proyecto. Crea .github/workflows/. Dispara en tag v*.*.*

## Acceptance Criteria

### AC-01

Workflow file en .github/workflows/publish-vscode-extension.yml. Trigger: on push tags v*.*.* + workflow_dispatch.

- **Estado:** ✅ cumplido

### AC-02

Job corre en ubuntu-latest, Node.js 20 LTS, instala @vscode/vsce globalmente, hace cd vscode-extension && npm ci && npm run vscode prepublish.

- **Estado:** ✅ cumplido

### AC-03

Step Sync version corre bash scripts/sync-extension-version.sh --check y falla el workflow si hay drift (defense-in-depth).

- **Estado:** ✅ cumplido

### AC-04

Step Publish corre vsce publish --pat secrets.VSCE_PAT. Output capturado en logs del workflow.

- **Estado:** ✅ cumplido

### AC-05

Step Attach VSIX to release corre vsce package -o specbox-engine-VERSION.vsix + sube el .vsix al GitHub Release vVERSION usando softprops/action-gh-release@v2.

- **Estado:** ✅ cumplido

### AC-06

Workflow respeta el principio no skipping hooks: si vsce publish falla, el job entero falla y notifica.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
