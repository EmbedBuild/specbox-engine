---
id: UC-505
ordinal: UC-026
title: Refactor NativeBackend.__init__ + auth_gateway dispatch
parent_us: US-NATIVE-SECURITY
status: done
actor: Engine
hours: 4
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-505 — Refactor NativeBackend.__init__ + auth_gateway dispatch

> **US padre:** [US-NATIVE-SECURITY](../us/US-04-blindar-el-native-backend-contra-mutaciones-de-identidades-r.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

NativeBackend.__init__(self, project_id: str, dev_token: str) - ambos parametros obligatorios (no opcionales); pasar dev_token='' o None lanza ValueError('dev_token is required for NativeBackend') desde el constructor; verificado por test parametrizado con casos validos e invalidos.

- **Estado:** ✅ cumplido

### AC-02

server/auth_gateway.py get_session_backend, en la rama backend_type == 'native', lee config['dev_token'] (que ya existe en la sesion native segun store_native_credentials) y lo pasa al constructor: NativeBackend(project_id=config['project_id'], dev_token=config['dev_token']); verificado por test que mockea la sesion MCP con backend_type=native, project_id=p1, dev_token=t1 y comprueba que la instancia devuelta tiene _project_id == 'p1' y _dev_token == 't1'.

- **Estado:** ✅ cumplido

### AC-03

store_native_credentials (en auth_gateway.py) exige dev_token no vacio al guardar la sesion native - pasar '' o None lanza un error explicito en set_auth_token(backend_type='native', token='', ...); verificado por test que llama set_auth_token sin token con backend_type native y comprueba el error.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
