---
id: US-VSCODE-DISCOVERABILITY
title: Sidebar de descubrimiento y ayuda para la extensión VSCode
status: draft
hours: 24.0
owner: Jesús Pérez
created: 2026-05-27
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# US-VSCODE-DISCOVERABILITY — Sidebar de descubrimiento y ayuda para la extensión VSCode

## Como… quiero… para…

> # US-VSCODE-DISCOVERABILITY: Sidebar de descubrimiento y ayuda para la extensión VSCode
> 
> **Horas estimadas:** 24.0
> **Pantallas:** sidebar specbox.skills, skill card (webview o quickpick)
> 
> Cierra el funnel post-install de la extensión SpecBox (Marketplace v6.2.0 + OAuth v6.3.0). Hoy el TreeView 'specbox.skills' lista 15 skills hardcoded (1 fantasma 'remote' eliminado en v6.1.0, 11 ausentes) y el click no hace nada. Esta US refactoriza el sidebar para que (a) liste automáticamente los skills reales del filesystem, (b) los agrupe en 7 categorías (Pipeline / Quality / Visual / Tracking / Stripe / Lifecycle / Otros), (c) al hacer click despliegue una ficha con qué hace, cuándo usarlo, comando exacto a teclear y ejemplo realista, (d) actualice el walkthrough con un quinto step de tour. El click NO ejecuta el skill — la invocación queda manual en el chat de Claude Code. Discovery: disc-6e6f4a7048af (READY_FOR_PRD). Target release: v6.6.0 'VSCode Discoverability'.

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-701 | [Auto-detección de skills desde filesystem](../uc/UC-701_auto-deteccion-de-skills-desde-filesystem.md) | review |
| UC-702 | [Agrupación de skills por categoría](../uc/UC-702_agrupacion-de-skills-por-categoria.md) | review |
| UC-703 | [Ficha de skill al hacer click](../uc/UC-703_ficha-de-skill-al-hacer-click.md) | review |
| UC-704 | [Walkthrough actualizado + tooltip rico](../uc/UC-704_walkthrough-actualizado-tooltip-rico.md) | review |
| UC-705 | [Tests + smoke manual + bump versión](../uc/UC-705_tests-smoke-manual-bump-version.md) | review |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
