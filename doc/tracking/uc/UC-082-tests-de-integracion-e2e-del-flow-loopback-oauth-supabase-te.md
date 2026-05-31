---
id: UC-650
ordinal: UC-082
title: Tests de integración E2E del flow loopback OAuth (Supabase test mode)
parent_us: US-VSCODE-GITHUB-OAUTH
status: ready
actor: Engine (CI + test infrastructure)
hours:
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-650 — Tests de integración E2E del flow loopback OAuth (Supabase test mode)

> **US padre:** [US-VSCODE-GITHUB-OAUTH](../us/US-14-github-oauth-en-la-extension-vscode-native-backend-como-defa.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-GITHUB-OAUTH: GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth
**Actor:** Engine (CI + test infrastructure)
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [JR-4] Test tests/e2e/oauth-flow.spec.ts con Playwright: (a) lanza VSCode + ext, (b) ejecuta comando 'Sign in with GitHub', (c) intercepta openExternal y dispara Playwright contra cloud.specbox.build-test/auth/github, (d) Playwright completa el GitHub mock OAuth, (e) callback llega al loopback, (f) verifica context.secrets.get('specbox.mcpToken') retorna valor non-null. Test corre en <60s.
- AC-02: [JR-4] Test tests/e2e/oauth-flow.spec.ts::reject_csrf verifica que un callback con state distinto al enviado falla con HTTP 400 desde el loopback y NO actualiza SecretStorage. Defense in depth contra CSRF.
- AC-03: [JR-4] Test tests/e2e/oauth-flow.spec.ts::timeout_5min simula que el callback nunca llega (mock GitHub que no redirect), verifica que el server loopback se cierra en 5min + 30s margen, y la extension muestra notification de cancelación.
- AC-04: [JE-3] Test tests/e2e/oauth-flow.spec.ts::revoke_visible_in_30s integration: completa OAuth → invoca whoami() exitoso → revoca mcp_tokens.revoked_at = now() en Supabase test DB → espera 35s → invoca whoami() nuevamente → assert que retorna UNAUTHENTICATED.
- AC-05: [JR-5] Test tests/e2e/oauth-flow.spec.ts::freeform_unaffected verifica que en una sesión sin sign-in, todas las tools FreeForm/Trello/Plane funcionan normalmente (onboard_project, add_uc, mark_ac, list_us). Suite verde en CI.
- AC-06: [JR-4] Workflow CI .github/workflows/oauth-e2e.yml corre en cada PR con touch en vscode-extension/src/{onboard,mcp,sidebar}.ts o server/coordination/identity.py. Job en ubuntu-latest, xvfb, Playwright pinned, Supabase test mode credentials desde GitHub Secrets (SPECBOX_TEST_SUPABASE_URL, SPECBOX_TEST_SUPABASE_ANON_KEY). Falla con issue auto-created si rompe (siguiendo patrón de UC-640).

## Contexto
Suite Playwright + @vscode/test-electron + Supabase test mode (proyecto specbox-cloud-test con su propia GitHub OAuth App de test) que cubre el flow completo: click 'Sign in' → mock GitHub OAuth → callback al loopback → SecretStorage → handshake MCP. Workflow CI nuevo oauth-e2e.yml en cada PR con touch en paths relevantes.

## Acceptance Criteria

### AC-01

[JR-4] Test tests/e2e/oauth-flow.spec.ts con Playwright: (a) lanza VSCode + ext, (b) ejecuta comando 'Sign in with GitHub', (c) intercepta openExternal y dispara Playwright contra cloud.specbox.build-test/auth/github, (d) Playwright completa el GitHub mock OAuth, (e) callback llega al loopback, (f) verifica context.secrets.get('specbox.mcpToken') retorna valor non-null. Test corre en <60s.

- **Estado:** ⬜ pendiente

### AC-02

[JR-4] Test tests/e2e/oauth-flow.spec.ts::reject_csrf verifica que un callback con state distinto al enviado falla con HTTP 400 desde el loopback y NO actualiza SecretStorage. Defense in depth contra CSRF.

- **Estado:** ⬜ pendiente

### AC-03

[JR-4] Test tests/e2e/oauth-flow.spec.ts::timeout_5min simula que el callback nunca llega (mock GitHub que no redirect), verifica que el server loopback se cierra en 5min + 30s margen, y la extension muestra notification de cancelación.

- **Estado:** ⬜ pendiente

### AC-04

[JE-3] Test tests/e2e/oauth-flow.spec.ts::revoke_visible_in_30s integration: completa OAuth → invoca whoami() exitoso → revoca mcp_tokens.revoked_at = now() en Supabase test DB → espera 35s → invoca whoami() nuevamente → assert que retorna UNAUTHENTICATED.

- **Estado:** ⬜ pendiente

### AC-05

[JR-5] Test tests/e2e/oauth-flow.spec.ts::freeform_unaffected verifica que en una sesión sin sign-in, todas las tools FreeForm/Trello/Plane funcionan normalmente (onboard_project, add_uc, mark_ac, list_us). Suite verde en CI.

- **Estado:** ⬜ pendiente

### AC-06

[JR-4] Workflow CI .github/workflows/oauth-e2e.yml corre en cada PR con touch en vscode-extension/src/{onboard,mcp,sidebar}.ts o server/coordination/identity.py. Job en ubuntu-latest, xvfb, Playwright pinned, Supabase test mode credentials desde GitHub Secrets (SPECBOX_TEST_SUPABASE_URL, SPECBOX_TEST_SUPABASE_ANON_KEY). Falla con issue auto-created si rompe (siguiendo patrón de UC-640).

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
