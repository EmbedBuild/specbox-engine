---
id: UC-651
ordinal: UC-083
title: Docs + README + CHANGELOG + ADR — onboarding default = Native+OAuth
parent_us: US-VSCODE-GITHUB-OAUTH
status: ready
actor: Engine
hours:
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-651 — Docs + README + CHANGELOG + ADR — onboarding default = Native+OAuth

> **US padre:** [US-VSCODE-GITHUB-OAUTH](../us/US-15-github-oauth-en-la-extension-vscode-native-backend-como-defa.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-GITHUB-OAUTH: GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth
**Actor:** Engine
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [JE-1] vscode-extension/README.md Quick Start reescrito: paso 1 sigue siendo 'Install from Marketplace', paso 2 ahora es 'Click Sign in with GitHub on first activate (or Continue in local mode (FreeForm) if preferred)', paso 3 es 'Start building' (igual). Sin mención a 'provisionar token manualmente'. README.es.md simétrico.
- AC-02: [JR-3] El README incluye sección explícita 'Local mode (no auth)' con 3 líneas explicando que FreeForm sigue first-class, link al runbook doc/runbooks/freeform-only-mode.md (nuevo), aclaración de que features no-Native funcionan idénticamente sin signing in. Visible en TOC del README, NO en footer.
- AC-03: [JR-6] vscode-extension/CHANGELOG.md entry [6.3.0] - 2026-XX-XX con sección Added (GitHub OAuth onboarding, Native default, sidebar identity), Changed (templates/settings.json.template default backend_type=native), Security (SecretStorage para mcp_token, ≤30s revoke visibility).
- AC-04: [JE-2] doc/decisions/native_default_oauth.md (ADR nuevo) replica tradeoff del discovery: rompe parcialmente la decisión canónica v5.29 'FreeForm first-class, cero auth requerida' pero compensa con las 3 garantías auditables. El ADR linkea al discovery icp_jtbd.md y al Engram architecture/vscode-github-oauth. Test: existe el archivo y grep -c 'documented_exception' doc/decisions/native_default_oauth.md ≥ 1.
- AC-05: [JE-2] CLAUDE.md añade sección 'Native Default OAuth (v6.3.0)' con la nueva default + el escape FreeForm + link al ADR. La sección 6.1.1 Cloud Cutover (que removió Sala de Máquinas) sigue intacta — esta US es complementaria, no contradice. Test manual: leer CLAUDE.md tras el merge y verificar coherencia narrativa (no hay 'FreeForm first-class' + 'Native default' contradictoriamente).

## Contexto
Actualizar docs user-facing y ADR para reflejar el cambio de default a Native+OAuth con FreeForm preservado. Toca: vscode-extension README/README.es/CHANGELOG, README raíz, docs/getting-started.md, doc/decisions/native_default_oauth.md (ADR nuevo), templates/settings.json.template (default backend_type=native + comment hacia FreeForm), CLAUDE.md.

## Acceptance Criteria

### AC-01

[JE-1] vscode-extension/README.md Quick Start reescrito: paso 1 sigue siendo 'Install from Marketplace', paso 2 ahora es 'Click Sign in with GitHub on first activate (or Continue in local mode (FreeForm) if preferred)', paso 3 es 'Start building' (igual). Sin mención a 'provisionar token manualmente'. README.es.md simétrico.

- **Estado:** ⬜ pendiente

### AC-02

[JR-3] El README incluye sección explícita 'Local mode (no auth)' con 3 líneas explicando que FreeForm sigue first-class, link al runbook doc/runbooks/freeform-only-mode.md (nuevo), aclaración de que features no-Native funcionan idénticamente sin signing in. Visible en TOC del README, NO en footer.

- **Estado:** ⬜ pendiente

### AC-03

[JR-6] vscode-extension/CHANGELOG.md entry [6.3.0] - 2026-XX-XX con sección Added (GitHub OAuth onboarding, Native default, sidebar identity), Changed (templates/settings.json.template default backend_type=native), Security (SecretStorage para mcp_token, ≤30s revoke visibility).

- **Estado:** ⬜ pendiente

### AC-04

[JE-2] doc/decisions/native_default_oauth.md (ADR nuevo) replica tradeoff del discovery: rompe parcialmente la decisión canónica v5.29 'FreeForm first-class, cero auth requerida' pero compensa con las 3 garantías auditables. El ADR linkea al discovery icp_jtbd.md y al Engram architecture/vscode-github-oauth. Test: existe el archivo y grep -c 'documented_exception' doc/decisions/native_default_oauth.md ≥ 1.

- **Estado:** ⬜ pendiente

### AC-05

[JE-2] CLAUDE.md añade sección 'Native Default OAuth (v6.3.0)' con la nueva default + el escape FreeForm + link al ADR. La sección 6.1.1 Cloud Cutover (que removió Sala de Máquinas) sigue intacta — esta US es complementaria, no contradice. Test manual: leer CLAUDE.md tras el merge y verificar coherencia narrativa (no hay 'FreeForm first-class' + 'Native default' contradictoriamente).

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
