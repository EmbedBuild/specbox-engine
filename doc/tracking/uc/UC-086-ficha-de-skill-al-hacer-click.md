---
id: UC-703
ordinal: UC-086
title: Ficha de skill al hacer click
parent_us: US-VSCODE-DISCOVERABILITY
status: review
actor: Dev (ICP-1 y ICP-2)
hours: 6.0
owner: Jesús Pérez
created: 2026-05-27
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-703 — Ficha de skill al hacer click

> **US padre:** [US-VSCODE-DISCOVERABILITY](../us/US-16-sidebar-de-descubrimiento-y-ayuda-para-la-extension-vscode.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-DISCOVERABILITY: Sidebar de descubrimiento y ayuda para la extensión VSCode
**Actor:** Dev (ICP-1 y ICP-2)
**Horas estimadas:** 6.0
**Pantallas:** webview o quickpick (decisión técnica en /plan)

## Criterios de Aceptacion
- AC-01: [JR-F.4] Al hacer click en un skill del TreeView, se abre una ficha (webview panel o quickpick — decisión en plan) con cuatro bloques claramente separados: Qué hace, Cuándo usarlo, Comando exacto, Ejemplo.
- AC-02: La información de los cuatro bloques se lee del frontmatter description del SKILL.md correspondiente cuando esté presente, y de un fallback estático (objeto en código de la extensión) cuando el SKILL.md no tenga ese contenido estructurado. La fuente del contenido se etiqueta visiblemente al pie de la ficha ('from SKILL.md' o 'from extension defaults').
- AC-03: [JR-F.4] El bloque 'Comando exacto' muestra el slash command como string monoespaciado (p.ej. '/prd <feature_name>') con un botón 'Copiar al portapapeles' inmediatamente al lado.
- AC-04: Al pulsar 'Copiar al portapapeles', el comando se copia vía vscode.env.clipboard.writeText y aparece una notificación 'Comando copiado — pega en el chat de Claude Code' durante 3 segundos.
- AC-05: Cerrar la ficha (X del webview, Esc del quickpick) la cierra sin dejar estado residual; volver a hacer click en el mismo skill la vuelve a abrir.
- AC-06: [JE-F.3] El Ejemplo mostrado para cada skill es funcional — el comando exacto del bloque 'Comando exacto' debe ejecutarse correctamente si el usuario lo pega tal cual en el chat. Validado manualmente para los 5 skills más usados (prd, plan, implement, audit, handoff) antes del merge.

## Contexto
Click en un skill abre ficha con 4 bloques fijos: Qué hace, Cuándo usarlo, Comando exacto (+ botón copiar), Ejemplo. El click NO ejecuta el skill — solo despliega documentación.

## Acceptance Criteria

### AC-01

[JR-F.4] Al hacer click en un skill del TreeView, se abre una ficha (webview panel o quickpick — decisión en plan) con cuatro bloques claramente separados: Qué hace, Cuándo usarlo, Comando exacto, Ejemplo.

- **Estado:** ⬜ pendiente

### AC-02

La información de los cuatro bloques se lee del frontmatter description del SKILL.md correspondiente cuando esté presente, y de un fallback estático (objeto en código de la extensión) cuando el SKILL.md no tenga ese contenido estructurado. La fuente del contenido se etiqueta visiblemente al pie de la ficha ('from SKILL.md' o 'from extension defaults').

- **Estado:** ⬜ pendiente

### AC-03

[JR-F.4] El bloque 'Comando exacto' muestra el slash command como string monoespaciado (p.ej. '/prd <feature_name>') con un botón 'Copiar al portapapeles' inmediatamente al lado.

- **Estado:** ⬜ pendiente

### AC-04

Al pulsar 'Copiar al portapapeles', el comando se copia vía vscode.env.clipboard.writeText y aparece una notificación 'Comando copiado — pega en el chat de Claude Code' durante 3 segundos.

- **Estado:** ⬜ pendiente

### AC-05

Cerrar la ficha (X del webview, Esc del quickpick) la cierra sin dejar estado residual; volver a hacer click en el mismo skill la vuelve a abrir.

- **Estado:** ⬜ pendiente

### AC-06

[JE-F.3] El Ejemplo mostrado para cada skill es funcional — el comando exacto del bloque 'Comando exacto' debe ejecutarse correctamente si el usuario lo pega tal cual en el chat. Validado manualmente para los 5 skills más usados (prd, plan, implement, audit, handoff) antes del merge.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
