---
id: UC-639
ordinal: UC-071
title: Setup inicial del publisher y secrets
parent_us: US-VSCODE-MARKETPLACE
status: done
actor: Humano
hours: 2.0
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-639 — Setup inicial del publisher y secrets

> **US padre:** [US-VSCODE-MARKETPLACE](../us/US-13-publicar-la-extension-specbox-al-vscode-marketplace-con-sync.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-MARKETPLACE: Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine
**Actor:** Humano
**Horas estimadas:** 2.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: doc/runbooks/vscode-marketplace-publisher-setup.md creado. Documenta: crear cuenta Azure DevOps, crear org, crear PAT scope Marketplace Manage, registrar publisher EmbedBuild con vsce create-publisher, añadir VSCE_PAT a GitHub Secrets del repo EmbedBuild/specbox-engine.
- AC-02: El runbook incluye sección Rotación del PAT (PATs Azure DevOps caducan máx 1 año): cómo regenerar sin perder ownership del publisher, cómo actualizar el secret en GitHub.
- AC-03: El runbook incluye comando de verificación: vsce ls-publishers debe mostrar EmbedBuild y vsce show EmbedBuild.specbox-engine debe responder OK tras el primer publish.
- AC-04: El runbook documenta el unpublish de emergencia (vsce unpublish EmbedBuild.specbox-engine) y advertencias del Marketplace (puede tardar horas en propagarse).
- AC-05: Una vez ejecutado el setup, en GitHub Repo Settings Secrets and variables Actions existe VSCE_PAT (verificable por listado, no por valor).

## Contexto
One-time setup. Documentar publisher EmbedBuild en VSCode Marketplace + PAT en GitHub Secrets. Bloqueante para UC-638.

## Acceptance Criteria

### AC-01

doc/runbooks/vscode-marketplace-publisher-setup.md creado. Documenta: crear cuenta Azure DevOps, crear org, crear PAT scope Marketplace Manage, registrar publisher EmbedBuild con vsce create-publisher, añadir VSCE_PAT a GitHub Secrets del repo EmbedBuild/specbox-engine.

- **Estado:** ✅ cumplido

### AC-02

El runbook incluye sección Rotación del PAT (PATs Azure DevOps caducan máx 1 año): cómo regenerar sin perder ownership del publisher, cómo actualizar el secret en GitHub.

- **Estado:** ✅ cumplido

### AC-03

El runbook incluye comando de verificación: vsce ls-publishers debe mostrar EmbedBuild y vsce show EmbedBuild.specbox-engine debe responder OK tras el primer publish.

- **Estado:** ✅ cumplido

### AC-04

El runbook documenta el unpublish de emergencia (vsce unpublish EmbedBuild.specbox-engine) y advertencias del Marketplace (puede tardar horas en propagarse).

- **Estado:** ✅ cumplido

### AC-05

Una vez ejecutado el setup, en GitHub Repo Settings Secrets and variables Actions existe VSCE_PAT (verificable por listado, no por valor).

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
