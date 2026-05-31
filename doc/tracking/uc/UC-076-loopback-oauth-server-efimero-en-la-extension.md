---
id: UC-644
ordinal: UC-076
title: Loopback OAuth server efímero en la extensión
parent_us: US-VSCODE-GITHUB-OAUTH
status: ready
actor: Engine (VSCode extension)
hours:
owner: Jesús Pérez
created: 2026-05-26
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-644 — Loopback OAuth server efímero en la extensión

> **US padre:** [US-VSCODE-GITHUB-OAUTH](../us/US-14-github-oauth-en-la-extension-vscode-native-backend-como-defa.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-GITHUB-OAUTH: GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth
**Actor:** Engine (VSCode extension)
**Horas estimadas:** 0
**Pantallas:** 

## Criterios de Aceptacion
- AC-01: [JR-2] El comando SpecBox: Sign in with GitHub levanta servidor HTTP en 127.0.0.1 con puerto random (puerto 0), escucha solo loopback (NUNCA 0.0.0.0), abre el browser via vscode.env.openExternal apuntando a cloud.specbox.build/auth/github con redirect_uri=http://127.0.0.1:<port>/callback y state=<random-32-byte-hex> en menos de 1s desde el click del CTA.
- AC-02: [JR-2] El servidor loopback acepta exactamente UNA request a /callback con query params mcp_token y state; valida que state matchea el enviado (HTTP 400 si no matchea), guarda mcp_token en SecretStorage y cierra el server en el mismo tick. Cualquier segunda request al puerto recibe HTTP 410 Gone.
- AC-03: [JE-1] Si callback no llega en 5min desde openExternal, el server se cierra automáticamente y la extensión muestra notification vscode.l10n.t('Sign in cancelled — no callback received. Try again from the SpecBox sidebar.') con variante ES en bundle.l10n.es.json. Test verificable con timer mock.
- AC-04: [JR-2] Tras callback exitoso, la página HTML servida en el browser muestra título vscode.l10n.t('Signed in to SpecBox') + cuerpo vscode.l10n.t('You can close this tab and return to VSCode.') + style inline mínimo (sin assets externos para evitar leaks de telemetría) + auto-close del tab via window.close() con fallback de texto si el browser lo bloquea.
- AC-05: [JE-3] El servidor loopback rechaza con HTTP 400 cualquier request que no venga del Origin: cloud.specbox.build o que use methods distintos de GET (defense in depth contra DNS rebinding). Test cubierto con request manual desde origen falso.

## Contexto
Foundational. La extensión levanta un HTTP server local efímero (127.0.0.1 puerto random asignado por SO via puerto 0) para recibir el callback OAuth, abre el browser hacia cloud.specbox.build/auth/github con CSRF state, espera callback single-use con timeout 5min, cierra el server tras callback. Defense in depth: rechaza requests no-loopback, methods distintos de GET, origins no-cloud.

## Acceptance Criteria

### AC-01

[JR-2] El comando SpecBox: Sign in with GitHub levanta servidor HTTP en 127.0.0.1 con puerto random (puerto 0), escucha solo loopback (NUNCA 0.0.0.0), abre el browser via vscode.env.openExternal apuntando a cloud.specbox.build/auth/github con redirect_uri=http://127.0.0.1:<port>/callback y state=<random-32-byte-hex> en menos de 1s desde el click del CTA.

- **Estado:** ⬜ pendiente

### AC-02

[JR-2] El servidor loopback acepta exactamente UNA request a /callback con query params mcp_token y state; valida que state matchea el enviado (HTTP 400 si no matchea), guarda mcp_token en SecretStorage y cierra el server en el mismo tick. Cualquier segunda request al puerto recibe HTTP 410 Gone.

- **Estado:** ⬜ pendiente

### AC-03

[JE-1] Si callback no llega en 5min desde openExternal, el server se cierra automáticamente y la extensión muestra notification vscode.l10n.t('Sign in cancelled — no callback received. Try again from the SpecBox sidebar.') con variante ES en bundle.l10n.es.json. Test verificable con timer mock.

- **Estado:** ⬜ pendiente

### AC-04

[JR-2] Tras callback exitoso, la página HTML servida en el browser muestra título vscode.l10n.t('Signed in to SpecBox') + cuerpo vscode.l10n.t('You can close this tab and return to VSCode.') + style inline mínimo (sin assets externos para evitar leaks de telemetría) + auto-close del tab via window.close() con fallback de texto si el browser lo bloquea.

- **Estado:** ⬜ pendiente

### AC-05

[JE-3] El servidor loopback rechaza con HTTP 400 cualquier request que no venga del Origin: cloud.specbox.build o que use methods distintos de GET (defense in depth contra DNS rebinding). Test cubierto con request manual desde origen falso.

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
