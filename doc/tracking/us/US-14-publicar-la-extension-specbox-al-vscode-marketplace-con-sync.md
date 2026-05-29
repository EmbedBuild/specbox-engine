---
id: US-VSCODE-MARKETPLACE
ordinal: US-14
title: Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine
status: draft
hours: 42.0
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# US-VSCODE-MARKETPLACE — Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine

## Como… quiero… para…

> # US-VSCODE-MARKETPLACE: Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine
> 
> **Horas estimadas:** 42.0
> **Pantallas:** 
> 
> Publicar la extensión EmbedBuild.specbox-engine en el VSCode Marketplace + establecer CI lockstep que mantenga extension.version == engine.version en cada tag + i18n EN/ES (listing NLS + runtime l10n) + telemetría Marketplace API pública (cron diario → .quality/marketplace-stats.jsonl → tool MCP get_marketplace_stats). Hoy la extensión está drifteada 6 versiones (5.21.1 vs engine 6.1.1) y no es descubrible vía Marketplace. Target release: v6.2.0 'VSCode Marketplace' (minor). Decisiones de scope: Solo VSCode Marketplace (no Open VSX en V1). Lockstep estricto. Vía A pura (NO thin-extension refactor). i18n EN canon + ES localizado. Telemetría solo via Marketplace REST API público (cero PII, cero telemetría activa). Publisher Marketplace = EmbedBuild. Repo GitHub = EmbedBuild/specbox-engine.

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-634 | [Script sync-extension-version.sh con modos --check/--write](../uc/UC-066-script-sync-extension-version-sh-con-modos-check-write.md) | done |
| UC-635 | [Hook de release: bloquear tag si extensión drifteada](../uc/UC-067-hook-de-release-bloquear-tag-si-extension-drifteada.md) | done |
| UC-636 | [Metadata Marketplace en package.json](../uc/UC-068-metadata-marketplace-en-package-json.md) | done |
| UC-637 | [README y CHANGELOG de la extensión para Marketplace](../uc/UC-069-readme-y-changelog-de-la-extension-para-marketplace.md) | done |
| UC-638 | [Workflow CI: publish al Marketplace en tag](../uc/UC-070-workflow-ci-publish-al-marketplace-en-tag.md) | done |
| UC-639 | [Setup inicial del publisher y secrets](../uc/UC-071-setup-inicial-del-publisher-y-secrets.md) | done |
| UC-640 | [Smoke test post-publish con matrix locale [en, es]](../uc/UC-072-smoke-test-post-publish-con-matrix-locale-en-es.md) | done |
| UC-641 | [i18n del listing del Marketplace (EN + ES) via NLS](../uc/UC-073-i18n-del-listing-del-marketplace-en-es-via-nls.md) | done |
| UC-642 | [i18n de strings runtime de la extensión (vscode-l10n)](../uc/UC-074-i18n-de-strings-runtime-de-la-extension-vscode-l10n.md) | done |
| UC-643 | [Telemetría de instalaciones via Marketplace API](../uc/UC-075-telemetria-de-instalaciones-via-marketplace-api.md) | done |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
