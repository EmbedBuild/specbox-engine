---
id: UC-647
ordinal: UC-079
title: Onboarding notification al primer activate (one-shot, dismissable, persistente)
parent_us: US-VSCODE-GITHUB-OAUTH
status: ready
actor: Engine (VSCode extension)
hours:
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-647 — Onboarding notification al primer activate (one-shot, dismissable, persistente)

> **US padre:** [US-VSCODE-GITHUB-OAUTH](../us/US-15-github-oauth-en-la-extension-vscode-native-backend-como-defa.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-GITHUB-OAUTH: GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth
**Actor:** Engine (VSCode extension)
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [JR-1] Al primer activate() por workspace, si context.workspaceState.get('specbox.onboardingDecision') === undefined, la extensión llama vscode.window.showInformationMessage con EXACTAMENTE 2 botones: el primero vscode.l10n.t('Sign in with GitHub'), el segundo vscode.l10n.t('Continue in local mode (FreeForm)'). NO existe un tercer botón 'Dismiss'/'Later' — la X del corner cierra sin elegir y eso NO persiste decisión.
- AC-02: [JE-2] Si el usuario hace click en 'Continue in local mode (FreeForm)', la extensión escribe context.workspaceState.update('specbox.onboardingDecision', {mode: 'freeform', timestamp: ISO, ext_version: '...'}). En el siguiente activate del mismo workspace, el notification NO se muestra. Verificable: reload workspace x3, el notification aparece solo en el primer activate.
- AC-03: [JR-3] Al elegir 'Continue in local mode (FreeForm)', la extensión ejecuta equivalente a set_auth_token(backend_type='freeform', token='', root_path=<absolute>) resolviendo root_path via el helper existente .claude/hooks/lib/freeform-path.mjs (defensa v5.29). El sidebar muestra 'Local mode (FreeForm)' sin status bar de identidad.
- AC-04: [JE-2] Aún en modo FreeForm, el comando SpecBox: Sign in with GitHub permanece disponible en el Command Palette (no oculto). Pero NO aparecen notifications proactivas como 'consider signing in' en ningún momento. Test: simular 10 días de uso en modo FreeForm con activates diarios → 0 notifications de auth aparecen.
- AC-05: [JE-2] Si el usuario cierra la X del notification sin elegir (decisión ambígua), la extensión registra el evento en telemetría local .quality/logs/onboarding.jsonl como {event: 'dismissed_without_decision', workspace_hash: sha256, ext_version} pero NO cambia workspaceState. En el próximo activate vuelve a aparecer. Justificación: la ambigüedad del cierre lateral no se trata como opt-out — fuerza decisión explícita.

## Contexto
Al activate de la ext (workspaceContains: ENGINE_VERSION.yaml o .claude/settings.json), si workspaceState no tiene specbox.onboardingDecision, mostrar showInformationMessage con 2 botones EXACTOS: 'Sign in with GitHub' (primary) y 'Continue in local mode (FreeForm)' (secondary, equally visible — NO 'Dismiss'). Cualquier elección persiste; el cierre lateral NO persiste y vuelve a aparecer.

## Acceptance Criteria

### AC-01

[JR-1] Al primer activate() por workspace, si context.workspaceState.get('specbox.onboardingDecision') === undefined, la extensión llama vscode.window.showInformationMessage con EXACTAMENTE 2 botones: el primero vscode.l10n.t('Sign in with GitHub'), el segundo vscode.l10n.t('Continue in local mode (FreeForm)'). NO existe un tercer botón 'Dismiss'/'Later' — la X del corner cierra sin elegir y eso NO persiste decisión.

- **Estado:** ⬜ pendiente

### AC-02

[JE-2] Si el usuario hace click en 'Continue in local mode (FreeForm)', la extensión escribe context.workspaceState.update('specbox.onboardingDecision', {mode: 'freeform', timestamp: ISO, ext_version: '...'}). En el siguiente activate del mismo workspace, el notification NO se muestra. Verificable: reload workspace x3, el notification aparece solo en el primer activate.

- **Estado:** ⬜ pendiente

### AC-03

[JR-3] Al elegir 'Continue in local mode (FreeForm)', la extensión ejecuta equivalente a set_auth_token(backend_type='freeform', token='', root_path=<absolute>) resolviendo root_path via el helper existente .claude/hooks/lib/freeform-path.mjs (defensa v5.29). El sidebar muestra 'Local mode (FreeForm)' sin status bar de identidad.

- **Estado:** ⬜ pendiente

### AC-04

[JE-2] Aún en modo FreeForm, el comando SpecBox: Sign in with GitHub permanece disponible en el Command Palette (no oculto). Pero NO aparecen notifications proactivas como 'consider signing in' en ningún momento. Test: simular 10 días de uso en modo FreeForm con activates diarios → 0 notifications de auth aparecen.

- **Estado:** ⬜ pendiente

### AC-05

[JE-2] Si el usuario cierra la X del notification sin elegir (decisión ambígua), la extensión registra el evento en telemetría local .quality/logs/onboarding.jsonl como {event: 'dismissed_without_decision', workspace_hash: sha256, ext_version} pero NO cambia workspaceState. En el próximo activate vuelve a aparecer. Justificación: la ambigüedad del cierre lateral no se trata como opt-out — fuerza decisión explícita.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
