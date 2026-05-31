---
id: UC-643
ordinal: UC-075
title: Telemetría de instalaciones via Marketplace API
parent_us: US-VSCODE-MARKETPLACE
status: done
actor: Engine
hours: 6.0
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-643 — Telemetría de instalaciones via Marketplace API

> **US padre:** [US-VSCODE-MARKETPLACE](../us/US-13-publicar-la-extension-specbox-al-vscode-marketplace-con-sync.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-MARKETPLACE: Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine
**Actor:** Engine
**Horas estimadas:** 6.0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: .github/workflows/marketplace-stats.yml creado. Triggers: schedule cron 0 6 * * * (diario 06 00 UTC) + workflow_dispatch (manual). Job en ubuntu-latest con Node.js 20.
- AC-02: Script scripts/fetch-marketplace-stats.mjs invocado por el workflow: POST a https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery con body filterType=7 value EmbedBuild.specbox-engine flags=914. Parsea response, extrae statistics installs updateCount avgRating ratingCount trendingDaily trendingMonthly. Appendea a .quality/marketplace-stats.jsonl una línea JSON con shape date version installs downloads avg_rating rating_count trending_daily trending_monthly delta_installs_24h. delta_installs_24h se computa contra la última entry del jsonl.
- AC-03: Workflow commitea el jsonl actualizado a main con mensaje chore(stats) marketplace stats YYYY-MM-DD. Falla suave si el endpoint retorna 404 (extensión aún no publicada log warning exit 0).
- AC-04: server/tools/marketplace.py creado: registra tool MCP get_marketplace_stats window_days 30 jsonl_content optional que lee .quality/marketplace-stats.jsonl filtra por ventana retorna total_installs total_downloads avg_rating install_growth_pct daily_series current_trending_rank. Sigue MCP Path Contract v6.0.1 (content-passing).
- AC-05: Test tests/test_marketplace_tool.py con jsonl fixture 30 entries simuladas tool retorna métricas correctas install_growth_pct positivo daily_series tiene 30 entries. Edge case jsonl vacío tool retorna status no_data_yet reason extension_not_published_or_no_stats.
- AC-06: Documentación doc/runbooks/marketplace-stats.md con cómo el endpoint funciona qué flags 914 significa IncludeStatistics IncludeVersions IncludeCategoryAndTags IncludeFiles límites de rate limiting observados cron 1xdía muy lejos cómo consultar manualmente gh workflow run marketplace-stats.yml.
- AC-07: Privacy el workflow y la tool NO capturan ningún dato del usuario final solo agregados públicos del Marketplace listing documentado en doc/runbooks/marketplace-stats.md sección Privacy data sources.

## Contexto
Cron diario contra el endpoint público extensionquery del Marketplace. Persiste a .quality/marketplace-stats.jsonl. Tool MCP get_marketplace_stats. Zero PII.

## Acceptance Criteria

### AC-01

.github/workflows/marketplace-stats.yml creado. Triggers: schedule cron 0 6 * * * (diario 06 00 UTC) + workflow_dispatch (manual). Job en ubuntu-latest con Node.js 20.

- **Estado:** ✅ cumplido

### AC-02

Script scripts/fetch-marketplace-stats.mjs invocado por el workflow: POST a https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery con body filterType=7 value EmbedBuild.specbox-engine flags=914. Parsea response, extrae statistics installs updateCount avgRating ratingCount trendingDaily trendingMonthly. Appendea a .quality/marketplace-stats.jsonl una línea JSON con shape date version installs downloads avg_rating rating_count trending_daily trending_monthly delta_installs_24h. delta_installs_24h se computa contra la última entry del jsonl.

- **Estado:** ✅ cumplido

### AC-03

Workflow commitea el jsonl actualizado a main con mensaje chore(stats) marketplace stats YYYY-MM-DD. Falla suave si el endpoint retorna 404 (extensión aún no publicada log warning exit 0).

- **Estado:** ✅ cumplido

### AC-04

server/tools/marketplace.py creado: registra tool MCP get_marketplace_stats window_days 30 jsonl_content optional que lee .quality/marketplace-stats.jsonl filtra por ventana retorna total_installs total_downloads avg_rating install_growth_pct daily_series current_trending_rank. Sigue MCP Path Contract v6.0.1 (content-passing).

- **Estado:** ✅ cumplido

### AC-05

Test tests/test_marketplace_tool.py con jsonl fixture 30 entries simuladas tool retorna métricas correctas install_growth_pct positivo daily_series tiene 30 entries. Edge case jsonl vacío tool retorna status no_data_yet reason extension_not_published_or_no_stats.

- **Estado:** ✅ cumplido

### AC-06

Documentación doc/runbooks/marketplace-stats.md con cómo el endpoint funciona qué flags 914 significa IncludeStatistics IncludeVersions IncludeCategoryAndTags IncludeFiles límites de rate limiting observados cron 1xdía muy lejos cómo consultar manualmente gh workflow run marketplace-stats.yml.

- **Estado:** ✅ cumplido

### AC-07

Privacy el workflow y la tool NO capturan ningún dato del usuario final solo agregados públicos del Marketplace listing documentado en doc/runbooks/marketplace-stats.md sección Privacy data sources.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
