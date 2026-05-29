---
id: UC-646
ordinal: UC-078
title: VSCode SecretStorage + handshake con MCP server local
parent_us: US-VSCODE-GITHUB-OAUTH
status: ready
actor: Engine (VSCode extension + MCP server local)
hours:
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-646 — VSCode SecretStorage + handshake con MCP server local

> **US padre:** [US-VSCODE-GITHUB-OAUTH](../us/US-14-github-oauth-en-la-extension-vscode-native-backend-como-defa.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-GITHUB-OAUTH: GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth
**Actor:** Engine (VSCode extension + MCP server local)
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [JR-1] Tras callback OAuth exitoso, el mcp_token queda persistido en context.secrets.store('specbox.mcpToken', token). Verificable en macOS con security find-generic-password -s 'vscodeapplicationextension'; en Linux con secret-tool search application vscode; en Windows con la API de Credential Manager. Test E2E desde VSCode test runner que llama await context.secrets.get('specbox.mcpToken') y compara con el token devuelto por mock OAuth.
- AC-02: [JE-1] NINGÚN archivo en el workspace (.vscode/settings.json, .claude/settings.local.json, .claude/mcp.json, ni cualquier otro) contiene el mcp_token en plaintext después del sign-in. Verificable con grep -r '<token>' .vscode/ .claude/ retornando 0 matches. La config MCP que la extensión escribe usa placeholder ${SPECBOX_NATIVE_MCP_TOKEN} resuelto via proceso wrapper que lee de SecretStorage al spawn.
- AC-03: [JR-1] El MCP server local, al arrancar, lee SPECBOX_NATIVE_MCP_TOKEN de env, llama set_auth_token(api_key='', token=<env>, backend_type='native') automáticamente, y registra en .quality/logs/mcp-handshake.jsonl el evento {event: 'auto_authenticated', developer_handle: '...', timestamp: '...'} (sin token plaintext). Verificable con MCP test session que inicia con env set y llama whoami() retornando el developer correcto.
- AC-04: [JE-3] Si el mcp_token es revocado en Supabase, la próxima llamada a cualquier tool nativa retorna UNAUTHENTICATED en ≤30s (cubierto por authenticate_and_authorize_cached TTL 30s ya existente en v5.34.1). Test: revocar mcp_tokens.revoked_at = now() en Supabase mientras sesión MCP está activa; siguiente whoami() post-30s retorna {error: 'UNAUTHENTICATED'}. La extensión detecta y muestra notification.
- AC-05: [JE-1] El comando SpecBox: Sign out borra context.secrets.delete('specbox.mcpToken'), remueve la env var de la config MCP, mata el proceso MCP actual y lo respawn sin token. Tras sign-out, el sidebar muestra 'Not signed in (FreeForm mode)' y las tools nativas retornan UNAUTHENTICATED graceful. Verificable con e2e: sign-in → assert state='signed_in' → sign-out → assert state='signed_out' sin reiniciar VSCode.

## Contexto
Tras callback exitoso, la extensión persiste el mcp_token con context.secrets.store('specbox.mcpToken', token) (Keychain/DPAPI/libsecret). Para que el MCP server local lo use, la extensión configura claude.mcpServers.specbox-engine.env con SPECBOX_NATIVE_MCP_TOKEN inyectada via un wrapper que lee de SecretStorage al spawn (no plaintext en settings.json). MCP arranca, llama set_auth_token automáticamente y registra en .quality/logs/mcp-handshake.jsonl sin token plaintext.

## Acceptance Criteria

### AC-01

[JR-1] Tras callback OAuth exitoso, el mcp_token queda persistido en context.secrets.store('specbox.mcpToken', token). Verificable en macOS con security find-generic-password -s 'vscodeapplicationextension'; en Linux con secret-tool search application vscode; en Windows con la API de Credential Manager. Test E2E desde VSCode test runner que llama await context.secrets.get('specbox.mcpToken') y compara con el token devuelto por mock OAuth.

- **Estado:** ⬜ pendiente

### AC-02

[JE-1] NINGÚN archivo en el workspace (.vscode/settings.json, .claude/settings.local.json, .claude/mcp.json, ni cualquier otro) contiene el mcp_token en plaintext después del sign-in. Verificable con grep -r '<token>' .vscode/ .claude/ retornando 0 matches. La config MCP que la extensión escribe usa placeholder ${SPECBOX_NATIVE_MCP_TOKEN} resuelto via proceso wrapper que lee de SecretStorage al spawn.

- **Estado:** ⬜ pendiente

### AC-03

[JR-1] El MCP server local, al arrancar, lee SPECBOX_NATIVE_MCP_TOKEN de env, llama set_auth_token(api_key='', token=<env>, backend_type='native') automáticamente, y registra en .quality/logs/mcp-handshake.jsonl el evento {event: 'auto_authenticated', developer_handle: '...', timestamp: '...'} (sin token plaintext). Verificable con MCP test session que inicia con env set y llama whoami() retornando el developer correcto.

- **Estado:** ⬜ pendiente

### AC-04

[JE-3] Si el mcp_token es revocado en Supabase, la próxima llamada a cualquier tool nativa retorna UNAUTHENTICATED en ≤30s (cubierto por authenticate_and_authorize_cached TTL 30s ya existente en v5.34.1). Test: revocar mcp_tokens.revoked_at = now() en Supabase mientras sesión MCP está activa; siguiente whoami() post-30s retorna {error: 'UNAUTHENTICATED'}. La extensión detecta y muestra notification.

- **Estado:** ⬜ pendiente

### AC-05

[JE-1] El comando SpecBox: Sign out borra context.secrets.delete('specbox.mcpToken'), remueve la env var de la config MCP, mata el proceso MCP actual y lo respawn sin token. Tras sign-out, el sidebar muestra 'Not signed in (FreeForm mode)' y las tools nativas retornan UNAUTHENTICATED graceful. Verificable con e2e: sign-in → assert state='signed_in' → sign-out → assert state='signed_out' sin reiniciar VSCode.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
