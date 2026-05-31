---
id: UC-649
ordinal: UC-081
title: UI en sidebar de la extensión — 'Signed in as @user' + comando 'Sign out'
parent_us: US-VSCODE-GITHUB-OAUTH
status: ready
actor: Engine (VSCode extension)
hours:
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-649 — UI en sidebar de la extensión — 'Signed in as @user' + comando 'Sign out'

> **US padre:** [US-VSCODE-GITHUB-OAUTH](../us/US-14-github-oauth-en-la-extension-vscode-native-backend-como-defa.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-GITHUB-OAUTH: GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth
**Actor:** Engine (VSCode extension)
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [JR-6] La vista specbox.status añade primer elemento (top of tree) que muestra estado de identidad. Si hay mcp_token en SecretStorage Y whoami() retorna OK, label='Signed in as @<handle>'. Si no, label='Not signed in (FreeForm mode)'. Test: VSCode test runner activa la ext con/sin token mockeado y assert TreeItem.label correcto.
- AC-02: [JR-6] Click en el TreeItem signed-in despliega quick pick con 2 acciones: vscode.l10n.t('Sign out') (ejecuta SpecBox: Sign out) y vscode.l10n.t('Open profile on cloud.specbox.build') (abre browser a cloud.specbox.build/me). Click en TreeItem not-signed-in despliega quick pick con 1 acción: vscode.l10n.t('Sign in with GitHub').
- AC-03: [JE-3] La vista hace polling discreto cada 60s para detectar revoke: re-invoca whoami() desde el MCP local, y si pasa de OK a UNAUTHENTICATED, actualiza TreeItem y muestra vscode.l10n.t('Your session was revoked. Sign in again?') como notification con CTA. Test: mock whoami returning OK→UNAUTHENTICATED, assert que en ≤90s (60s polling + margen) la UI se actualiza.
- AC-04: [JR-6] El status bar de VSCode (área inferior) muestra $(github-inverted) @<handle> cuando signed-in, sin nada cuando no. Click en el status bar = vscode.commands.executeCommand('specbox.showStatus') (ya existe). Test: render del status bar con/sin token, assert texto e icono.
- AC-05: [JE-1] Tanto el sidebar como el status bar respetan locale: con code --locale=es, el label es 'Conectado como @<handle>' / 'Sin conexión (modo local FreeForm)'. Cubierto por package.nls.es.json extended (claves nuevas) + bundle.l10n.es.json extended. Smoke test workflow de UC-640 (matrix locale en/es) extendido para verificar también los nuevos labels.

## Contexto
Vista specbox.status del sidebar (existente desde US-VSCODE-MARKETPLACE) añade en su cabecera (top of tree) el bloque de identidad: 'Signed in as @<github_handle>' con icono $(github-inverted) si hay token activo; 'Not signed in (FreeForm mode)' con icono $(person) si no. Click abre quick pick contextual. Status bar inferior muestra @handle si signed-in. Polling discreto 60s para detectar revoke.

## Acceptance Criteria

### AC-01

[JR-6] La vista specbox.status añade primer elemento (top of tree) que muestra estado de identidad. Si hay mcp_token en SecretStorage Y whoami() retorna OK, label='Signed in as @<handle>'. Si no, label='Not signed in (FreeForm mode)'. Test: VSCode test runner activa la ext con/sin token mockeado y assert TreeItem.label correcto.

- **Estado:** ⬜ pendiente

### AC-02

[JR-6] Click en el TreeItem signed-in despliega quick pick con 2 acciones: vscode.l10n.t('Sign out') (ejecuta SpecBox: Sign out) y vscode.l10n.t('Open profile on cloud.specbox.build') (abre browser a cloud.specbox.build/me). Click en TreeItem not-signed-in despliega quick pick con 1 acción: vscode.l10n.t('Sign in with GitHub').

- **Estado:** ⬜ pendiente

### AC-03

[JE-3] La vista hace polling discreto cada 60s para detectar revoke: re-invoca whoami() desde el MCP local, y si pasa de OK a UNAUTHENTICATED, actualiza TreeItem y muestra vscode.l10n.t('Your session was revoked. Sign in again?') como notification con CTA. Test: mock whoami returning OK→UNAUTHENTICATED, assert que en ≤90s (60s polling + margen) la UI se actualiza.

- **Estado:** ⬜ pendiente

### AC-04

[JR-6] El status bar de VSCode (área inferior) muestra $(github-inverted) @<handle> cuando signed-in, sin nada cuando no. Click en el status bar = vscode.commands.executeCommand('specbox.showStatus') (ya existe). Test: render del status bar con/sin token, assert texto e icono.

- **Estado:** ⬜ pendiente

### AC-05

[JE-1] Tanto el sidebar como el status bar respetan locale: con code --locale=es, el label es 'Conectado como @<handle>' / 'Sin conexión (modo local FreeForm)'. Cubierto por package.nls.es.json extended (claves nuevas) + bundle.l10n.es.json extended. Smoke test workflow de UC-640 (matrix locale en/es) extendido para verificar también los nuevos labels.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
