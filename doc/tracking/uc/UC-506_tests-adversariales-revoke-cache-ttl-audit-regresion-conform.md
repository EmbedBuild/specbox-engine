---
id: UC-506
title: "Tests adversariales: revoke, cache TTL, audit, regresion conformance"
parent_us: US-NATIVE-SECURITY
status: done
actor: Engine
hours: 6
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-506 — Tests adversariales: revoke, cache TTL, audit, regresion conformance

> **US padre:** [US-NATIVE-SECURITY](../us/US-NATIVE-SECURITY_blindar-el-native-backend-contra-mutaciones-de-identidades-r.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

tests/test_native_revoke_adversarial.py incluye un test end-to-end que: (a) registra dev + token + membresia + crea un proyecto Native con 3 ACs, (b) hace una mutacion exitosa (mark_acceptance_criterion done=True) que entra en cache, (c) revoca el token desde otra conexion, (d) hace inmediatamente otra mutacion dentro del TTL - la mutacion tiene exito (cache hit, comportamiento esperado y documentado), (e) invalida el cache (funcion de test _clear_auth_cache()), (f) intenta otra mutacion - UnauthenticatedError y count de la tabla no cambia. Este test documenta la ventana de exposicion real.

- **Estado:** ✅ cumplido

### AC-02

tests/test_native_revoke_adversarial.py incluye un test que: (a) registra dev + token + membresia, (b) ELIMINA al dev de project_members (sin revocar el token), (c) invalida el cache, (d) intenta cada una de las 9 mutaciones - todas lanzan ForbiddenError y los counts de las tablas afectadas no cambian.

- **Estado:** ✅ cumplido

### AC-03

tests/test_native_backend_conformance.py (la suite existente de los 26 metodos del ABC) sigue 100% verde tras los cambios - verificado ejecutando .venv/bin/pytest tests/test_native_backend_conformance.py -q y obteniendo todos los tests en PASS (los fixtures se actualizan para crear el dev + token + membresia antes de instanciar el NativeBackend).

- **Estado:** ✅ cumplido

### AC-04

tests/test_audit_log_destructive.py incluye tests que verifican que tras una secuencia de N mutaciones mixtas (creates, updates, marks, deletes, archives), el audit_log contiene exactamente las filas correspondientes a los delete_acceptance_criterion y archive_item exitosos, con developer_id correcto, project_id correcto, operation correcta y target_id correcto; los counts de filas no destructivas son 0 en audit_log.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
