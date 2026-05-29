---
id: UC-652
ordinal: UC-089
title: Loopback timeout diferido + verificacion whoami en sign-in
parent_us: US-VSCODE-GITHUB-OAUTH
status: review
actor: Engine (VSCode extension)
hours: 3
owner: Jesús Pérez
created: 2026-05-28
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-652 — Loopback timeout diferido + verificacion whoami en sign-in

> **US padre:** [US-VSCODE-GITHUB-OAUTH](../us/US-14-github-oauth-en-la-extension-vscode-native-backend-como-defa.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-GITHUB-OAUTH: GitHub OAuth en la extension VSCode, Native Backend como default registrado en Supabase Auth
**Actor:** Engine (VSCode extension)
**Horas estimadas:** 3
**Pantallas:** sidebar specbox.status, notification de sign-in

## Contexto

Fix de UX y defensa en profundidad descubierto en el smoke test post-deploy de v6.3.0 (cross-repo con specbox_cloud PR #49, UC-905). Dos problemas reales reproducidos en vivo:

1. El servidor loopback de la extension arrancaba su timeout de 5 min en startLoopbackServer, ANTES de que el usuario navegara. Al leer la pantalla "Confirm your account" del cloud, cambiar de cuenta GitHub o despejar el dialogo "open external website" de VS Code, el reloj se agotaba y el callback llegaba a un puerto muerto (ERR_CONNECTION_REFUSED), sin mensaje accionable. Reproducido 4 veces.
2. runSignIn persistia el mcp_token recibido SIN verificar a que developer resuelve, dejando a la extension ciega ante el bug de identidad cruzada que arreglo el cloud.

## Fix (solo vscode-extension/)

- oauth.ts: CALLBACK_TIMEOUT_MS subido a 10 min; el timeout ya no arranca al crear el server, se arma via armTimeout() idempotente que runSignIn invoca solo tras un openExternal exitoso (el setup no cuenta contra la ventana).
- auth.ts: runSignIn llama fetchWhoami(token) antes de persistir en SecretStorage; rechaza con error 'identity_unverified' si el cloud no confirma identidad; muestra "Signed in as @handle" con el handle real. Helper describeSignInError() centraliza copys accionables.
- extension.ts: el comando directo specbox.signIn usa el mismo helper.

## Criterios de Aceptacion
- AC-01: Timeout 10 min, armado solo tras openExternal via armTimeout() idempotente; no arranca en startLoopbackServer. Tests: 'no timeout fires before armTimeout is called' + 'armTimeout: callback still resolves after the timeout is armed'.
- AC-02: runSignIn llama fetchWhoami antes de persistir; null -> error 'identity_unverified' sin guardar token; ok -> muestra 'Signed in as @handle'. Cubierto por suite cloud-api (200->handle, 401->null, 5xx->null).
- AC-03: describeSignInError centraliza copys para timeout/browser_blocked/identity_unverified; usado por maybeShowOnboarding y el comando directo specbox.signIn. Sin ERR_CONNECTION_REFUSED crudo al usuario.
- AC-04: tsc -p ./ limpio + suite node:test 47/47 verde (+4 nuevos del timeout diferido, sin regresion sobre los 43 previos).

## Acceptance Criteria

### AC-01

Timeout 10 min, armado solo tras openExternal via armTimeout() idempotente; no arranca en startLoopbackServer. Tests: 'no timeout fires before armTimeout is called' + 'armTimeout: callback still resolves after the timeout is armed'.

- **Estado:** ✅ cumplido

### AC-02

runSignIn llama fetchWhoami antes de persistir en SecretStorage; null -> error 'identity_unverified' sin guardar token; ok -> muestra 'Signed in as @handle'. Cubierto por suite cloud-api (200->handle, 401->null, 5xx->null).

- **Estado:** ✅ cumplido

### AC-03

describeSignInError centraliza copys accionables para timeout/browser_blocked/identity_unverified; usado por maybeShowOnboarding y el comando directo specbox.signIn. Sin stack traces ni ERR_CONNECTION_REFUSED crudo al usuario.

- **Estado:** ✅ cumplido

### AC-04

tsc -p ./ limpio + suite node:test 47/47 verde (+4 nuevos del timeout diferido, sin regresion sobre los 43 previos).

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
