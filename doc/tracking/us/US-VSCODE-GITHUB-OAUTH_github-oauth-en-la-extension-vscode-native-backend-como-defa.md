---
id: US-VSCODE-GITHUB-OAUTH
title: GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth
status: draft
hours:
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# US-VSCODE-GITHUB-OAUTH — GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth

## Como… quiero… para…

> # US-VSCODE-GITHUB-OAUTH: GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth
> 
> **Horas estimadas:** 0
> **Pantallas:** 
> 
> Integra GitHub OAuth en la extensión SpecBox v6.3.0 vía Supabase Auth de cloud.specbox.build con loopback server efímero. Native Backend pasa a ser el default recomendado en el onboarding; FreeForm preserva first-class como escape visible (decisión canónica v5.29 condicionada a 3 garantías auditables). Flujo: notification al primer activate → Sign in with GitHub abre browser → cloud.specbox.build/auth/github intercambia code GitHub por mcp_token y registra developer/github_identity/mcp_token en Supabase → callback al loopback 127.0.0.1:random → token guardado en VSCode SecretStorage (Keychain/DPAPI/libsecret) → MCP server local autenticado via env var inyectada al spawn. Revoke desde cloud visible en ≤30s vía authenticate_and_authorize_cached TTL ya existente (v5.34.1). Tools nativas (whoami/reserve_uc/release_uc/register_native_branch) responden UNAUTHENTICATED graceful sin auth; FreeForm/Trello/Plane operan offline. 5 decisiones congeladas off-band (Engram architecture/vscode-github-oauth #5746): default Native+OAuth recomendado / MCP sin auth graceful / SecretStorage zero plaintext / notification one-shot al activate dismissable / Supabase Auth como IdP único (no vscode.authentication native, no GitHub OAuth App propia).

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-644 | [Loopback OAuth server efímero en la extensión](../uc/UC-644_loopback-oauth-server-efimero-en-la-extension.md) | ready |
| UC-645 | [Consumir endpoint self-service cloud.specbox.build/vscode/issue-token (cross-repo dependency)](../uc/UC-645_consumir-endpoint-self-service-cloud-specbox-build-vscode-is.md) | ready |
| UC-646 | [VSCode SecretStorage + handshake con MCP server local](../uc/UC-646_vscode-secretstorage-handshake-con-mcp-server-local.md) | ready |
| UC-647 | [Onboarding notification al primer activate (one-shot, dismissable, persistente)](../uc/UC-647_onboarding-notification-al-primer-activate-one-shot-dismissa.md) | ready |
| UC-648 | [UNAUTHENTICATED graceful en las 4 tools nativas](../uc/UC-648_unauthenticated-graceful-en-las-4-tools-nativas.md) | done |
| UC-649 | [UI en sidebar de la extensión — 'Signed in as @user' + comando 'Sign out'](../uc/UC-649_ui-en-sidebar-de-la-extension-signed-in-as-user-comando-sign.md) | ready |
| UC-650 | [Tests de integración E2E del flow loopback OAuth (Supabase test mode)](../uc/UC-650_tests-de-integracion-e2e-del-flow-loopback-oauth-supabase-te.md) | ready |
| UC-651 | [Docs + README + CHANGELOG + ADR — onboarding default = Native+OAuth](../uc/UC-651_docs-readme-changelog-adr-onboarding-default-native-oauth.md) | ready |
| UC-652 | [Loopback timeout diferido + verificacion whoami en sign-in](../uc/UC-652_loopback-timeout-diferido-verificacion-whoami-en-sign-in.md) | review |
| UC-653 | [activate() no bloqueante — extension atascada en "Activating..."](../uc/UC-653_activate-no-bloqueante-extension-atascada-en-activating.md) | review |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
