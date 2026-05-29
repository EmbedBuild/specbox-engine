---
id: UC-641
ordinal: UC-073
title: i18n del listing del Marketplace (EN + ES) via NLS
parent_us: US-VSCODE-MARKETPLACE
status: done
actor: Engine
hours: 4.0
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-641 — i18n del listing del Marketplace (EN + ES) via NLS

> **US padre:** [US-VSCODE-MARKETPLACE](../us/US-13-publicar-la-extension-specbox-al-vscode-marketplace-con-sync.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-MARKETPLACE: Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine
**Actor:** Engine
**Horas estimadas:** 4.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: vscode-extension/package.nls.json (EN) creado con keys: extension.displayName, extension.description, command.install.title, command.healthCheck.title, command.onboard.title, command.showStatus.title, command.configureMcp.title, view.status.title. Cada key con su valor en inglés.
- AC-02: vscode-extension/package.nls.es.json creado con las mismas keys traducidas al español neutro España (tuteo estándar, NO argentinismos). Ejemplos: command.install.title SpecBox Instalar Engine, command.healthCheck.title SpecBox Comprobar Salud.
- AC-03: vscode-extension/package.json actualizado: displayName y description apuntan a %extension.displayName% y %extension.description%. Cada command.title y view.name referencia su key NLS correspondiente.
- AC-04: Smoke test local: code --locale=es + abrir VSCode con la extensión instalada todos los items del Command Palette empiezan por SpecBox en español. code --locale=en en inglés.
- AC-05: El Marketplace listing (panel web) muestra la descripción en español cuando el navegador del usuario tiene Accept-Language es-* (verificable post-publish abriendo la URL del listing con cookie de idioma ES).

## Contexto
package.nls.json (EN fallback) + package.nls.es.json (ES). VSCode auto-resuelve según vscode.env.language.

## Acceptance Criteria

### AC-01

vscode-extension/package.nls.json (EN) creado con keys: extension.displayName, extension.description, command.install.title, command.healthCheck.title, command.onboard.title, command.showStatus.title, command.configureMcp.title, view.status.title. Cada key con su valor en inglés.

- **Estado:** ✅ cumplido

### AC-02

vscode-extension/package.nls.es.json creado con las mismas keys traducidas al español neutro España (tuteo estándar, NO argentinismos). Ejemplos: command.install.title SpecBox Instalar Engine, command.healthCheck.title SpecBox Comprobar Salud.

- **Estado:** ✅ cumplido

### AC-03

vscode-extension/package.json actualizado: displayName y description apuntan a %extension.displayName% y %extension.description%. Cada command.title y view.name referencia su key NLS correspondiente.

- **Estado:** ✅ cumplido

### AC-04

Smoke test local: code --locale=es + abrir VSCode con la extensión instalada todos los items del Command Palette empiezan por SpecBox en español. code --locale=en en inglés.

- **Estado:** ✅ cumplido

### AC-05

El Marketplace listing (panel web) muestra la descripción en español cuando el navegador del usuario tiene Accept-Language es-* (verificable post-publish abriendo la URL del listing con cookie de idioma ES).

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
