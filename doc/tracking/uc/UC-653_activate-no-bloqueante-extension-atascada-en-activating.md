---
id: UC-653
title: activate() no bloqueante — extension atascada en "Activating..."
parent_us: US-VSCODE-GITHUB-OAUTH
status: review
actor: Engine (VSCode extension)
hours: 2
owner: Jesús Pérez
created: 2026-05-28
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-653 — activate() no bloqueante — extension atascada en "Activating..."

> **US padre:** [US-VSCODE-GITHUB-OAUTH](../us/US-VSCODE-GITHUB-OAUTH_github-oauth-en-la-extension-vscode-native-backend-como-defa.md)

## Objetivo / Descripción

**User Story:** US-VSCODE-GITHUB-OAUTH
**Actor:** Engine (VSCode extension)
**Horas estimadas:** 2
**Pantallas:** ninguna (arranque de la extension)

## Contexto

Hotfix critico descubierto tras publicar v6.6.1 al Marketplace: la extension
se quedaba indefinidamente en "Activating..." para practicamente todos los
usuarios. Confirmado via Extension Host log: specbox-engine inicia activacion
(activationEvent workspaceContains:ENGINE_VERSION.yaml) y nunca reporta fin.

## Causa raiz

activate() hacia await en serie de: health.run(), el prompt del ExtensionUpdater
("SpecBox Engine updated to vX. Update extension?") y el onboarding gate. El
showInformationMessage del updater BLOQUEA hasta que el usuario pulsa. Como cada
release bumpa la version, tras publicar v6.6.1 todos los usuarios tenian engine
local en 6.6.0 != extension 6.6.1 -> el prompt de update saltaba en CADA primer
activate y, al estar awaiteado dentro de activate(), VS Code se quedaba en
"Activating..." hasta que el usuario respondiera (o para siempre si lo ignoraba).

## Fix (solo vscode-extension/src/extension.ts)

activate() ahora registra comandos/vistas y arma el polling de identidad de
forma sincrona, y retorna de inmediato. Todo el trabajo lento o interactivo
(health check, prompt de update, onboarding gate, refresh inicial de identidad)
se mueve a runStartupTasks(), disparado con `void` (fire-and-forget) y con
guards en cada paso para que nada pueda volver a colgar la activacion.

## Criterios de Aceptacion
- AC-01: activate() no contiene ningun await sobre showInformationMessage ni sobre red. Registra comandos/vistas + arma setInterval de polling de forma sincrona y retorna. El trabajo diferido vive en runStartupTasks() invocado con `void`.
- AC-02: runStartupTasks() envuelve cada fase (health+update, onboarding, skills context, identity refresh) en try/catch o .catch; ningun fallo propaga fuera y por tanto no puede afectar al estado de activacion.
- AC-03: El disposal del setInterval de polling queda registrado en context.subscriptions de forma sincrona dentro de activate(), independiente de como resuelva runStartupTasks.
- AC-04: tsc -p ./ limpio, lint i18n verde y suite node:test 47/47 sin regresion. Verificacion manual: instalar la extension y confirmar que el sidebar pasa de "Activating..." a estado normal sin requerir interaccion del usuario.

## Acceptance Criteria

### AC-01

activate() no contiene ningun await sobre showInformationMessage ni sobre red. Registra comandos/vistas + arma el setInterval de polling de forma sincrona y retorna. El trabajo diferido vive en runStartupTasks() invocado con void.

- **Estado:** ✅ cumplido

### AC-02

runStartupTasks() envuelve cada fase (health+update, onboarding, skills context, identity refresh) en try/catch o .catch; ningun fallo propaga fuera y no puede afectar al estado de activacion.

- **Estado:** ✅ cumplido

### AC-03

El disposal del setInterval de polling queda registrado en context.subscriptions de forma sincrona dentro de activate().

- **Estado:** ✅ cumplido

### AC-04

tsc limpio + lint i18n verde + 47/47 node:test sin regresion. Verificacion manual: la extension pasa de 'Activating...' a estado normal sin requerir interaccion.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
