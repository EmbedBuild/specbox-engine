---
id: US-NATIVE-SECURITY
ordinal: US-04
title: Blindar el Native Backend contra mutaciones de identidades revocadas
status: review
hours: 40
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# US-NATIVE-SECURITY — Blindar el Native Backend contra mutaciones de identidades revocadas

## Como… quiero… para…

> Como mantenedor del MCP SpecBox, quiero que ningun developer expulsado de un proyecto Native pueda mutar su tracking mas alla de 30 segundos tras el revoke, y que toda operacion destructiva quede registrada, para no ser responsable de dano causado por identidades revocadas y para poder recuperar desde backups si algo se cuela. Cierra el hueco actual donde las 9 mutaciones del NativeBackend no re-validan identidad por call.

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-501 | [Schema rediseñado: github_identities + mcp_tokens + audit_log](../uc/UC-023-schema-redisenado-github-identities-mcp-tokens-audit-log.md) | done |
| UC-502 | [Gate de membresía en mutaciones del NativeBackend con cache TTL 30s](../uc/UC-024-gate-de-membresia-en-mutaciones-del-nativebackend-con-cache-.md) | done |
| UC-503 | [Audit log de operaciones destructivas](../uc/UC-027-audit-log-de-operaciones-destructivas.md) | done |
| UC-504 | [Eliminar register_native_developer del MCP + developers.token_hash del codigo Python](../uc/UC-022-eliminar-register-native-developer-del-mcp-developers-token-.md) | done |
| UC-505 | [Refactor NativeBackend.__init__ + auth_gateway dispatch](../uc/UC-026-refactor-nativebackend-init-auth-gateway-dispatch.md) | done |
| UC-506 | [Tests adversariales: revoke, cache TTL, audit, regresion conformance](../uc/UC-025-tests-adversariales-revoke-cache-ttl-audit-regresion-conform.md) | done |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
