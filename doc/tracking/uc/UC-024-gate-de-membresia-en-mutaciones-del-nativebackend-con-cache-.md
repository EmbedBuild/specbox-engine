---
id: UC-502
ordinal: UC-024
title: Gate de membresía en mutaciones del NativeBackend con cache TTL 30s
parent_us: US-NATIVE-SECURITY
status: done
actor: Engine
hours: 12
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-502 — Gate de membresía en mutaciones del NativeBackend con cache TTL 30s

> **US padre:** [US-NATIVE-SECURITY](../us/US-04-blindar-el-native-backend-contra-mutaciones-de-identidades-r.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

server/coordination/identity.py anade authenticate_and_authorize_cached(conn, token, project_id) que mantiene un dict en memoria {(token_hash, project_id): (Developer, expires_at)}; en cache hit (now < expires_at) devuelve el Developer sin tocar Postgres; en cache miss llama a authenticate_and_authorize y guarda el resultado con expires_at = monotonic() + 30; verificado por test que mide nro de queries Postgres en 5 calls consecutivas dentro del TTL == 1 query unica (la primera).

- **Estado:** ✅ cumplido

### AC-02

El TTL es la constante de modulo _CACHE_TTL_SECONDS = 30 en identity.py (no env var, no configurable runtime); verificado por inspeccion estatica del modulo (test que importa el simbolo y comprueba == 30).

- **Estado:** ✅ cumplido

### AC-03

Los 9 metodos de mutacion del NativeBackend (create_item, update_item, archive_item, mark_acceptance_criterion, delete_acceptance_criterion, create_acceptance_criteria, update_acceptance_criterion, add_comment, add_attachment) invocan _require_membership_cached(self._dev_token) antes de cualquier INSERT/UPDATE/DELETE; verificado por test parametrizado sobre los 9 metodos: cuando el token NO esta en mcp_tokens (o tiene revoked_at NOT NULL), la mutacion lanza UnauthenticatedError y un SELECT posterior sobre la tabla afectada confirma que no hubo escritura (count antes == count despues).

- **Estado:** ✅ cumplido

### AC-04

Cuando el dev tiene token valido pero NO es member de project_members para el project_id del NativeBackend, las 9 mutaciones lanzan ForbiddenError y la escritura no ocurre; verificado por test parametrizado: alta de dev + token en mcp_tokens pero SIN row en project_members - cada metodo mutador falla con ForbiddenError y count antes == count despues.

- **Estado:** ✅ cumplido

### AC-05

Tras un revoke (UPDATE mcp_tokens SET revoked_at = now() desde otra conexion que simula el panel), el siguiente cache miss del mismo token devuelve UnauthenticatedError; verificado por test que (a) hace una mutacion exitosa con el token, (b) revoca el token desde otra conn, (c) invalida el cache via _clear_auth_cache() de test, (d) intenta otra mutacion - UnauthenticatedError.

- **Estado:** ✅ cumplido

### AC-06

Las lecturas (list_items, get_item, get_acceptance_criteria, get_comments, get_attachments, find_item_by_field, get_item_children) NO invocan el gate - solo las mutaciones (las 9 listadas en AC-03); verificado por test que con token valido + membresia valida, las lecturas funcionan; con token revocado, las lecturas siguen funcionando (decision explicita: forensics/whoami debe seguir disponible).

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
