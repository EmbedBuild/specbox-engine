---
id: UC-705
ordinal: UC-088
title: Tests + smoke manual + bump versión
parent_us: US-VSCODE-DISCOVERABILITY
status: review
actor: Engine (release pipeline)
hours: 6.0
owner: Jesús Pérez
created: 2026-05-27
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-705 — Tests + smoke manual + bump versión

> **US padre:** [US-VSCODE-DISCOVERABILITY](../us/US-15-sidebar-de-descubrimiento-y-ayuda-para-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-DISCOVERABILITY: Sidebar de descubrimiento y ayuda para la extensión VSCode
**Actor:** Engine (release pipeline)
**Horas estimadas:** 6.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: Nuevo archivo vscode-extension/tests/skills-tree.test.mjs con suite node:test que cubre: (a) loadSkillsFromFilesystem(rootPaths) lee correctamente desde dos directorios mock, (b) prevalencia local > global, (c) skill desconocido cae en Otros, (d) categorías con 0 skills aparecen con sufijo '(0)', (e) getCategoryFor(skillName) devuelve la categoría correcta para los 25 skills del mapping.
- AC-02: Nuevo archivo vscode-extension/tests/skill-card.test.mjs (o equivalente) con suite node:test que cubre: (a) lectura de frontmatter description de un SKILL.md sintético, (b) fallback a contenido estático cuando el frontmatter no tiene la estructura esperada, (c) función pura buildSkillCardContent(skill) que devuelve los cuatro bloques esperados como string/HTML.
- AC-03: La suite completa de la extensión (npm test en vscode-extension/) sigue verde — todos los tests previos de OAuth, secret storage, MCP launcher pasan sin regresión.
- AC-04: El package.json de la extensión sube de 6.3.0 a 6.6.0 (lockstep con engine v6.6.0). CHANGELOG.md de la extensión gana sección [6.6.0] — 'Discoverability' con el listado de cambios.
- AC-05: ENGINE_VERSION.yaml sube a 6.6.0 con codename 'VSCode Discoverability'. CLAUDE.md gana sección 'VSCode Discoverability (v6.6.0)' documentando el sidebar mejorado y referenciando el PRD.
- AC-06: [JE-F.1] Smoke test manual ejecutado antes del merge: el reviewer humano (JPS) (a) instala el VSIX recién compilado en una instancia limpia de VSCode, (b) verifica que el sidebar muestra las 7 categorías con conteos correctos, (c) hace click en al menos 3 skills de categorías distintas y confirma que la ficha carga y el botón Copiar funciona, (d) ejecuta el walkthrough completo (los 5 pasos) sin errores. El veredicto manual queda como comentario en el PR antes del merge.

## Contexto
Cierre de la US: tests unitarios para la lógica de loader + agrupación + builder de fichas, suite completa verde sin regresión, bump de versión 6.5.0→6.6.0 con CHANGELOG y CLAUDE.md, y smoke manual del reviewer humano antes del merge.

## Acceptance Criteria

### AC-01

Nuevo archivo vscode-extension/tests/skills-tree.test.mjs con suite node:test que cubre: (a) loadSkillsFromFilesystem(rootPaths) lee correctamente desde dos directorios mock, (b) prevalencia local > global, (c) skill desconocido cae en Otros, (d) categorías con 0 skills aparecen con sufijo '(0)', (e) getCategoryFor(skillName) devuelve la categoría correcta para los 25 skills del mapping.

- **Estado:** ⬜ pendiente

### AC-02

Nuevo archivo vscode-extension/tests/skill-card.test.mjs (o equivalente) con suite node:test que cubre: (a) lectura de frontmatter description de un SKILL.md sintético, (b) fallback a contenido estático cuando el frontmatter no tiene la estructura esperada, (c) función pura buildSkillCardContent(skill) que devuelve los cuatro bloques esperados como string/HTML.

- **Estado:** ⬜ pendiente

### AC-03

La suite completa de la extensión (npm test en vscode-extension/) sigue verde — todos los tests previos de OAuth, secret storage, MCP launcher pasan sin regresión.

- **Estado:** ⬜ pendiente

### AC-04

El package.json de la extensión sube de 6.3.0 a 6.6.0 (lockstep con engine v6.6.0). CHANGELOG.md de la extensión gana sección [6.6.0] — 'Discoverability' con el listado de cambios.

- **Estado:** ⬜ pendiente

### AC-05

ENGINE_VERSION.yaml sube a 6.6.0 con codename 'VSCode Discoverability'. CLAUDE.md gana sección 'VSCode Discoverability (v6.6.0)' documentando el sidebar mejorado y referenciando el PRD.

- **Estado:** ⬜ pendiente

### AC-06

[JE-F.1] Smoke test manual ejecutado antes del merge: el reviewer humano (JPS) (a) instala el VSIX recién compilado en una instancia limpia de VSCode, (b) verifica que el sidebar muestra las 7 categorías con conteos correctos, (c) hace click en al menos 3 skills de categorías distintas y confirma que la ficha carga y el botón Copiar funciona, (d) ejecuta el walkthrough completo (los 5 pasos) sin errores. El veredicto manual queda como comentario en el PR antes del merge.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
