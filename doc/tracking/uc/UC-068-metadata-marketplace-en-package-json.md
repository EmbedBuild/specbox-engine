---
id: UC-636
ordinal: UC-068
title: Metadata Marketplace en package.json
parent_us: US-VSCODE-MARKETPLACE
status: done
actor: Engine
hours: 3.0
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-636 — Metadata Marketplace en package.json

> **US padre:** [US-VSCODE-MARKETPLACE](../us/US-13-publicar-la-extension-specbox-al-vscode-marketplace-con-sync.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-MARKETPLACE: Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine
**Actor:** Engine
**Horas estimadas:** 3.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: package.json declara: displayName, description, version, publisher EmbedBuild, license MIT, engines.vscode, icon (path a PNG >=128x128), categories (mínimo AI y Other), keywords (mínimo claude, claude-code, agentic, MCP, spec-driven, BDD).
- AC-02: package.json declara repository.url=https://github.com/EmbedBuild/specbox-engine, bugs.url=https://github.com/EmbedBuild/specbox-engine/issues, homepage=https://github.com/EmbedBuild/specbox-engine#readme. Publisher Marketplace es EmbedBuild.
- AC-03: package.json declara galleryBanner.color y galleryBanner.theme (dark o light) consistente con el branding.
- AC-04: vscode prepublish script existe y compila TypeScript sin errores (tsc -p ./).
- AC-05: vsce ls --tree corre sin warnings ni errores sobre missing fields o .vscodeignore mal configurado.

## Contexto
Audit y refresh del package.json para cumplir best practices del Marketplace.

## Acceptance Criteria

### AC-01

package.json declara: displayName, description, version, publisher EmbedBuild, license MIT, engines.vscode, icon (path a PNG >=128x128), categories (mínimo AI y Other), keywords (mínimo claude, claude-code, agentic, MCP, spec-driven, BDD).

- **Estado:** ✅ cumplido

### AC-02

package.json declara repository.url=https://github.com/EmbedBuild/specbox-engine, bugs.url=https://github.com/EmbedBuild/specbox-engine/issues, homepage=https://github.com/EmbedBuild/specbox-engine#readme. Publisher Marketplace es EmbedBuild.

- **Estado:** ✅ cumplido

### AC-03

package.json declara galleryBanner.color y galleryBanner.theme (dark o light) consistente con el branding.

- **Estado:** ✅ cumplido

### AC-04

vscode prepublish script existe y compila TypeScript sin errores (tsc -p ./).

- **Estado:** ✅ cumplido

### AC-05

vsce ls --tree corre sin warnings ni errores sobre missing fields o .vscodeignore mal configurado.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
