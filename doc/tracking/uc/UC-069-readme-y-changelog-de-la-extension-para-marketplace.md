---
id: UC-637
ordinal: UC-069
title: README y CHANGELOG de la extensión para Marketplace
parent_us: US-VSCODE-MARKETPLACE
status: done
actor: Engine
hours: 4.0
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-637 — README y CHANGELOG de la extensión para Marketplace

> **US padre:** [US-VSCODE-MARKETPLACE](../us/US-13-publicar-la-extension-specbox-al-vscode-marketplace-con-sync.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-MARKETPLACE: Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine
**Actor:** Engine
**Horas estimadas:** 4.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: vscode-extension/README.md reescrito: sección Features con los 5 comandos (SpecBox Install, Health Check, Onboard Project, Show Status, Configure MCP), Requirements (Claude Code CLI o VSCode extension de Claude), Quick Start (3 pasos), Troubleshooting, link al repo del engine.
- AC-02: README incluye al menos 1 screenshot del Command Palette filtrado por SpecBox. Imagen vive en vscode-extension/media/screenshots/.
- AC-03: README incluye badges: VSCode Marketplace version, VSCode Marketplace installs, License, engine version compatibility.
- AC-04: vscode-extension/CHANGELOG.md creado con formato Keep a Changelog. Entry 6.2.0 describe First Marketplace release; lockstep versioning with SpecBox Engine; EN+ES localization; Marketplace stats telemetry.
- AC-05: README.es.md creado con traducción completa al español neutro España (NO argentinismos), tuteo estándar. Link cruzado en header de ambos READMEs.

## Contexto
Reescribir README.md (EN canon) + README.es.md + CHANGELOG.md.

## Acceptance Criteria

### AC-01

vscode-extension/README.md reescrito: sección Features con los 5 comandos (SpecBox Install, Health Check, Onboard Project, Show Status, Configure MCP), Requirements (Claude Code CLI o VSCode extension de Claude), Quick Start (3 pasos), Troubleshooting, link al repo del engine.

- **Estado:** ✅ cumplido

### AC-02

README incluye al menos 1 screenshot del Command Palette filtrado por SpecBox. Imagen vive en vscode-extension/media/screenshots/.

- **Estado:** ✅ cumplido

### AC-03

README incluye badges: VSCode Marketplace version, VSCode Marketplace installs, License, engine version compatibility.

- **Estado:** ✅ cumplido

### AC-04

vscode-extension/CHANGELOG.md creado con formato Keep a Changelog. Entry 6.2.0 describe First Marketplace release; lockstep versioning with SpecBox Engine; EN+ES localization; Marketplace stats telemetry.

- **Estado:** ✅ cumplido

### AC-05

README.es.md creado con traducción completa al español neutro España (NO argentinismos), tuteo estándar. Link cruzado en header de ambos READMEs.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
