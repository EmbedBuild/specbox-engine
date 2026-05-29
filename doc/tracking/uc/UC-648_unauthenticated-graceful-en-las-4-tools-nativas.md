---
id: UC-648
title: UNAUTHENTICATED graceful en las 4 tools nativas
parent_us: US-VSCODE-GITHUB-OAUTH
status: done
actor: Engine (MCP server, server/coordination/)
hours:
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-648 — UNAUTHENTICATED graceful en las 4 tools nativas

> **US padre:** [US-VSCODE-GITHUB-OAUTH](../us/US-VSCODE-GITHUB-OAUTH_github-oauth-en-la-extension-vscode-native-backend-como-defa.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-GITHUB-OAUTH: GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth
**Actor:** Engine (MCP server, server/coordination/)
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [JR-5] Las 4 tools (whoami, reserve_uc, release_uc, register_native_branch) cuando se invocan sin SPECBOX_NATIVE_MCP_TOKEN set retornan payload JSON {status: 'unauthenticated', code: 'UNAUTHENTICATED', message: 'Sign in with GitHub via the VSCode extension or run /onboard.', docs_url: 'https://github.com/EmbedBuild/specbox-engine#native-backend'} con MCP isError=true. Test: crear MCP session sin auth token + invocar cada tool + assertar exact shape del payload + assertar que NO hay stack trace en el message.
- AC-02: [JR-5] Si el token es válido pero mcp_tokens.revoked_at IS NOT NULL en Supabase, las mismas 4 tools retornan code='UNAUTHENTICATED' con message='Your session was revoked. Sign in again.' después de ≤30s (cubierto por TTL del cache). Test: revocar token en BD, esperar 31s, invocar tool, assertar message exacto.
- AC-03: [JR-5] Las tools NO-nativas (onboard_project, add_uc, mark_ac, list_us, complete_uc, etc. — todas las que operan sobre FreeForm/Trello/Plane) NO requieren SPECBOX_NATIVE_MCP_TOKEN. Test: invocar 20 tools no-nativas en sesión sin auth, assert todas retornan isError=false.
- AC-04: [JR-5] El comportamiento UNAUTHENTICATED graceful está cubierto por test tests/test_native_unauthenticated.py con al menos 8 casos: (a) cada una de las 4 tools sin token, (b) cada una de las 4 tools con token revocado post-30s. Suite verde en CI.
- AC-05: [JE-1] El message en el payload UNAUTHENTICATED está localizado server-side (i18n del server, no de la ext) usando un mecanismo similar al vscode.l10n.t de la ext: el cliente MCP envía Accept-Language header en el handshake, el server responde con message en EN o ES según corresponda. Test: 2 sesiones MCP con Accept-Language: en y Accept-Language: es, mismo error, distinto message.

## Contexto
Auditar y unificar whoami / reserve_uc / release_uc / register_native_branch para que cuando no hay token o el token es inválido retornen payload uniforme {status: 'unauthenticated', code: 'UNAUTHENTICATED', message: '...', docs_url: '...'} sin levantar exception. Tools no-nativas (FreeForm/Trello/Plane) NO se ven afectadas — no usan authenticate_and_authorize_cached.

## Acceptance Criteria

### AC-01

[JR-5] Las 4 tools (whoami, reserve_uc, release_uc, register_native_branch) cuando se invocan sin SPECBOX_NATIVE_MCP_TOKEN set retornan payload JSON {status: 'unauthenticated', code: 'UNAUTHENTICATED', message: 'Sign in with GitHub via the VSCode extension or run /onboard.', docs_url: 'https://github.com/EmbedBuild/specbox-engine#native-backend'} con MCP isError=true. Test: crear MCP session sin auth token + invocar cada tool + assertar exact shape del payload + assertar que NO hay stack trace en el message.

- **Estado:** ✅ cumplido

### AC-02

[JR-5] Si el token es válido pero mcp_tokens.revoked_at IS NOT NULL en Supabase, las mismas 4 tools retornan code='UNAUTHENTICATED' con message='Your session was revoked. Sign in again.' después de ≤30s (cubierto por TTL del cache). Test: revocar token en BD, esperar 31s, invocar tool, assertar message exacto.

- **Estado:** ✅ cumplido

### AC-03

[JR-5] Las tools NO-nativas (onboard_project, add_uc, mark_ac, list_us, complete_uc, etc. — todas las que operan sobre FreeForm/Trello/Plane) NO requieren SPECBOX_NATIVE_MCP_TOKEN. Test: invocar 20 tools no-nativas en sesión sin auth, assert todas retornan isError=false.

- **Estado:** ✅ cumplido

### AC-04

[JR-5] El comportamiento UNAUTHENTICATED graceful está cubierto por test tests/test_native_unauthenticated.py con al menos 8 casos: (a) cada una de las 4 tools sin token, (b) cada una de las 4 tools con token revocado post-30s. Suite verde en CI.

- **Estado:** ✅ cumplido

### AC-05

[JE-1] El message en el payload UNAUTHENTICATED está localizado server-side (i18n del server, no de la ext) usando un mecanismo similar al vscode.l10n.t de la ext: el cliente MCP envía Accept-Language header en el handshake, el server responde con message en EN o ES según corresponda. Test: 2 sesiones MCP con Accept-Language: en y Accept-Language: es, mismo error, distinto message.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
