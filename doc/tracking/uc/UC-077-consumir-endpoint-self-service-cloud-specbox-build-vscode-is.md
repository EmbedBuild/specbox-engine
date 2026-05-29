---
id: UC-645
ordinal: UC-077
title: Consumir endpoint self-service cloud.specbox.build/vscode/issue-token (cross-repo dependency)
parent_us: US-VSCODE-GITHUB-OAUTH
status: ready
actor: Engine (VSCode extension, consumer)
hours:
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-645 — Consumir endpoint self-service cloud.specbox.build/vscode/issue-token (cross-repo dependency)

> **US padre:** [US-VSCODE-GITHUB-OAUTH](../us/US-14-github-oauth-en-la-extension-vscode-native-backend-como-defa.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-GITHUB-OAUTH: GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth
**Actor:** Engine (servicio cloud externo, repositorio specbox_cloud separado)
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [JR-2] GET /auth/github?redirect_uri=<URI>&state=<TOKEN> valida que redirect_uri matchea regex ^http://127\.0\.0\.1:\d+/callback$ (loopback puerto random) y rechaza con HTTP 400 + página HTML de error si no matchea (defense contra open redirect). Test: curl con redirect_uri=https://evil.com/cb retorna 400.
- AC-02: [JR-2] El endpoint redirige a https://github.com/login/oauth/authorize con client_id=$SPECBOX_GH_OAUTH_APP_ID, scope=read:user user:email, state=<TOKEN-propagado>. El client_secret se lee de env var SPECBOX_GH_OAUTH_APP_SECRET (Supabase secret), NUNCA hardcoded ni en logs.
- AC-03: [JR-6] Tras recibir el code de GitHub, el endpoint llama Supabase.auth.signInWithIdToken({provider: 'github', token: <github_id_token>}) y hace upsert idempotente transaccional (BEGIN/COMMIT) en developers(github_id, email, display_name, last_login_at), github_identities(developer_id, github_handle, github_id, granted_scopes), mcp_tokens(developer_id, token_hash, created_at, last_used_at=NULL, revoked_at=NULL). Si cualquiera falla, ROLLBACK + HTTP 500 + página de error sin filtrar detalle interno.
- AC-04: [JE-3] El mcp_token retornado es random hex 32 bytes (64 chars) generado por crypto.randomBytes(32).toString('hex'). Se guarda en BD como sha256(token) (token_hash), NUNCA en plaintext. El plaintext solo viaja en el redirect 302 a redirect_uri?mcp_token=<plaintext> y se elimina del log de acceso del proxy (Cloudflare/Vercel) via allowlist explícita.
- AC-05: [JR-4] Si un mismo developer_id ya tiene mcp_tokens activos no-revoked, el endpoint NO los invalida — añade uno nuevo. Multi-device support implícito. Solo el revoke explícito desde panel cloud cierra tokens. Test: flow OAuth ejecutado 2x consecutivos desde el mismo GitHub account; SELECT count(*) FROM mcp_tokens WHERE developer_id=X AND revoked_at IS NULL retorna 2.
- AC-06: [JR-4] Telemetría: cada sign-in exitoso escribe entry en tabla auth_log con developer_id, event='sign_in', source='vscode_ext', ext_version, github_handle, ip_hash(sha256), timestamp. Sin PII directa (email no se loguea aquí, solo en developers). Sirve a NSM de growth (app_market.md §5).

## Contexto
Endpoint Supabase Edge Function (Deno/TypeScript) en /auth/github. Recibe redirect_uri + state del loopback, redirige a GitHub OAuth, intercambia el code por GitHub access token, llama Supabase.auth.signInWithIdToken({provider: 'github'}), upsert idempotente en developers/github_identities/mcp_tokens (transaccional), redirige al loopback con mcp_token + state. mcp_token = 64-hex random; en BD se guarda sha256(token), nunca plaintext. Telemetría en auth_log para NSM growth.

## Acceptance Criteria

### AC-01

[JR-2] La URL que la extensión abre via vscode.env.openExternal es exactamente https://cloud.specbox.build/vscode/issue-token?return_to=<URI-encoded-loopback>&state=<csrf-token> (NO /auth/github ni endpoints OAuth directos — el OAuth real vive dentro del web flow de specbox_cloud). Test: spy sobre openExternal en VSCode test runner, assert el URL exacto con regex ^https://cloud\.specbox\.build/vscode/issue-token\?return_to=http%3A%2F%2F127\.0\.0\.1%3A\d+%2Fcallback&state=[a-f0-9]{64}$.

- **Estado:** ⬜ pendiente

### AC-02

[JR-2] El callback al loopback que la página cloud.specbox.build/vscode/issue-token envía tiene la forma GET /callback?mcp_token=<64-hex>&state=<csrf>. La extensión valida state matchea el enviado en AC-01 y que mcp_token matchea regex ^[a-f0-9]{64}$ (formato fijado por lib/tokens.ts del cloud — sha256_hex). Si no matchea, rechaza con HTTP 400 desde el loopback sin guardar nada.

- **Estado:** ⬜ pendiente

### AC-03

[JE-3] La extensión NO toca directamente POST /api/mcp-tokens/issue-for-self ni gestiona JWT — esa interacción vive completamente dentro del browser flow de specbox_cloud. El acoplamiento de specbox-engine con specbox_cloud queda restringido a 2 puntos: URL del web flow (AC-01) y shape del callback (AC-02). Test: grep en vscode-extension/src/ no encuentra referencias a 'Authorization: Bearer' ni a 'supabase.auth.' ni a '/api/mcp-tokens' directas — el contrato es solo URL params del browser flow.

- **Estado:** ⬜ pendiente

### AC-04

[JE-1] Si el browser flow del cloud falla y retorna ?error=<code>&error_description=<msg> al loopback (en vez de mcp_token), la extensión muestra notification vscode.l10n.t('Sign in failed: {0}', error_description) con CTA 'Try again' (re-dispara UC-644 con state nuevo) y CTA 'Continue in local mode (FreeForm)' (cae a UC-647 path FreeForm). Cero stack traces visibles al usuario.

- **Estado:** ⬜ pendiente

### AC-05

[JR-4] El mcp_token recibido se valida llamando whoami() al MCP server local con el token inyectado vía env. Si whoami() retorna OK (válido + developer activo en Supabase), la extensión persiste en SecretStorage (UC-646). Si whoami() retorna UNAUTHENTICATED u otro error, la extensión muestra notification con CTA 'Sign in again' sin guardar nada — el flow se considera roto del lado del cloud y se reporta como bug si es repetible. Test E2E cubierto en UC-650.

- **Estado:** ⬜ pendiente

### AC-06

[JR-4] Documentación: vscode-extension/README.md sección 'How sign-in works under the hood' referencia explícitamente la US paralela del cloud (EmbedBuild/specbox_cloud US-AUTH-VSCODE-SELF-SERVICE-TOKEN) y link a las dos páginas del cloud que la extensión consume (/vscode/issue-token). Mantiene a los futuros maintainers conscientes del acoplamiento cross-repo. Test: grep -c 'vscode/issue-token' vscode-extension/README.md ≥ 1.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
