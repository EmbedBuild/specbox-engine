---
id: UC-504
ordinal: UC-022
title: Eliminar register_native_developer del MCP + developers.token_hash del codigo Python
parent_us: US-NATIVE-SECURITY
status: done
actor: Engine
hours: 4
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-504 — Eliminar register_native_developer del MCP + developers.token_hash del codigo Python

> **US padre:** [US-NATIVE-SECURITY](../us/US-04-blindar-el-native-backend-contra-mutaciones-de-identidades-r.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

La funcion register_native_developer ya no existe en server/tools/coordination.py (eliminada, no marcada deprecated); el registro de tools del modulo ya no la incluye; verificado con grep -n 'register_native_developer' server/tools/coordination.py que devuelve 0 lineas y con un test que importa el modulo y comprueba que el simbolo no existe (hasattr falso).

- **Estado:** ✅ cumplido

### AC-02

server/coordination/identity.py resolve_developer ahora consulta mcp_tokens en vez de developers.token_hash: query SELECT d.developer_id, d.display_name FROM mcp_tokens t JOIN developers d ON d.developer_id = t.developer_id WHERE t.token_hash = $1 AND t.revoked_at IS NULL; verificado por test que registra developer + mcp_token activo, llama resolve_developer y obtiene el Developer correcto; y un segundo test que revoca el token (UPDATE revoked_at) y verifica que resolve_developer lanza UnauthenticatedError.

- **Estado:** ✅ cumplido

### AC-03

La funcion register_developer en server/coordination/identity.py ya no escribe en developers.token_hash (porque la columna no existe tras UC-501); su firma cambia: el parametro token se elimina, y la funcion queda como register_developer(conn, *, developer_id, display_name) que solo inserta en developers. La emision de mcp_tokens es responsabilidad del panel; verificado por inspeccion de firma y por test que llama register_developer(conn, developer_id='x', display_name='X') con exito y comprueba la fila en developers.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
