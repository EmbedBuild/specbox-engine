---
id: UC-642
ordinal: UC-074
title: i18n de strings runtime de la extensión (vscode-l10n)
parent_us: US-VSCODE-MARKETPLACE
status: done
actor: Engine
hours: 6.0
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-642 — i18n de strings runtime de la extensión (vscode-l10n)

> **US padre:** [US-VSCODE-MARKETPLACE](../us/US-14-publicar-la-extension-specbox-al-vscode-marketplace-con-sync.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-MARKETPLACE: Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine
**Actor:** Engine
**Horas estimadas:** 6.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: vscode-extension/package.json declara l10n ./l10n apuntando al directorio que contiene los bundles. Mecanismo oficial vscode-l10n (VSCode >=1.86). engines.vscode bump a ^1.86.0.
- AC-02: vscode-extension/l10n/bundle.l10n.json contiene todos los strings user-facing en EN, extraídos de src/extension.ts y comandos. Cada key es el string EN literal (convención vscode-l10n).
- AC-03: vscode-extension/l10n/bundle.l10n.es.json traduce todas las keys al español. Strings con placeholders 0, 1 preservan el orden de argumentos.
- AC-04: src/extension.ts y archivos hermanos NO contienen literales de strings user-facing: todos pasan por vscode.l10n.t. Verificado por scripts/lint-extension-strings.mjs que falla si encuentra vscode.window.showInformationMessage literal sin l10n.t.
- AC-05: Smoke test: instalar la extensión en VSCode con locale es ejecutar SpecBox Comprobar Salud la notificación sale en español. Misma operación con locale en sale en inglés.

## Contexto
Refactor src/*.ts para que strings user-facing pasen por vscode.l10n.t(...). Bundles + linter CI.

## Acceptance Criteria

### AC-01

vscode-extension/package.json declara l10n ./l10n apuntando al directorio que contiene los bundles. Mecanismo oficial vscode-l10n (VSCode >=1.86). engines.vscode bump a ^1.86.0.

- **Estado:** ✅ cumplido

### AC-02

vscode-extension/l10n/bundle.l10n.json contiene todos los strings user-facing en EN, extraídos de src/extension.ts y comandos. Cada key es el string EN literal (convención vscode-l10n).

- **Estado:** ✅ cumplido

### AC-03

vscode-extension/l10n/bundle.l10n.es.json traduce todas las keys al español. Strings con placeholders 0, 1 preservan el orden de argumentos.

- **Estado:** ✅ cumplido

### AC-04

src/extension.ts y archivos hermanos NO contienen literales de strings user-facing: todos pasan por vscode.l10n.t. Verificado por scripts/lint-extension-strings.mjs que falla si encuentra vscode.window.showInformationMessage literal sin l10n.t.

- **Estado:** ✅ cumplido

### AC-05

Smoke test: instalar la extensión en VSCode con locale es ejecutar SpecBox Comprobar Salud la notificación sale en español. Misma operación con locale en sale en inglés.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
