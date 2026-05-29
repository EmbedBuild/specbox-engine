---
id: UC-701
ordinal: UC-084
title: Auto-detección de skills desde filesystem
parent_us: US-VSCODE-DISCOVERABILITY
status: review
actor: Engine + extensión VSCode
hours: 4.0
owner: Jesús Pérez
created: 2026-05-27
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-701 — Auto-detección de skills desde filesystem

> **US padre:** [US-VSCODE-DISCOVERABILITY](../us/US-16-sidebar-de-descubrimiento-y-ayuda-para-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-DISCOVERABILITY: Sidebar de descubrimiento y ayuda para la extensión VSCode
**Actor:** Engine + extensión VSCode
**Horas estimadas:** 4.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [JR-F.1] SkillsTreeProvider.getChildren() lee skills desde ~/.claude/skills/*/SKILL.md (global) y ${workspace}/.claude/skills/*/SKILL.md (local) en lugar del array CORE_SKILLS hardcoded; cada skill detectado es una entrada con su nombre (sin slash) y su description extraída del frontmatter YAML del SKILL.md.
- AC-02: Si un skill aparece tanto en global como en local, prevalece el local; el árbol nunca muestra duplicados.
- AC-03: Si el filesystem no es legible (permisos, FS corrupto), el TreeView muestra un único item informativo 'No skills detected — run /install or check ~/.claude/skills/' en vez de fallar; el bug se loguea a la output channel SpecBox con stack trace completo.
- AC-04: [JR-F.1] Tras instalar un skill nuevo vía installer.runFullInstall(), llamar skillsTree.refresh() repuebla el árbol con el skill nuevo sin reiniciar VSCode.

## Contexto
Refactor de skills-tree.ts para reemplazar el array hardcoded CORE_SKILLS por lectura dinámica de ~/.claude/skills/ (global) + ${workspace}/.claude/skills/ (local).

## Acceptance Criteria

### AC-01

[JR-F.1] SkillsTreeProvider.getChildren() lee skills desde ~/.claude/skills/*/SKILL.md (global) y ${workspace}/.claude/skills/*/SKILL.md (local) en lugar del array CORE_SKILLS hardcoded; cada skill detectado es una entrada con su nombre (sin slash) y su description extraída del frontmatter YAML del SKILL.md.

- **Estado:** ⬜ pendiente

### AC-02

Si un skill aparece tanto en global como en local, prevalece el local; el árbol nunca muestra duplicados.

- **Estado:** ⬜ pendiente

### AC-03

Si el filesystem no es legible (permisos, FS corrupto), el TreeView muestra un único item informativo 'No skills detected — run /install or check ~/.claude/skills/' en vez de fallar; el bug se loguea a la output channel SpecBox con stack trace completo.

- **Estado:** ⬜ pendiente

### AC-04

[JR-F.1] Tras instalar un skill nuevo vía installer.runFullInstall(), llamar skillsTree.refresh() repuebla el árbol con el skill nuevo sin reiniciar VSCode.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
