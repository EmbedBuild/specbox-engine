---
id: UC-503
title: Audit log de operaciones destructivas
parent_us: US-NATIVE-SECURITY
status: done
actor: Engine
hours: 6
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-503 — Audit log de operaciones destructivas

> **US padre:** [US-NATIVE-SECURITY](../us/US-NATIVE-SECURITY_blindar-el-native-backend-contra-mutaciones-de-identidades-r.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

server/coordination/audit.py (modulo nuevo) expone async def record_destructive(conn, *, developer_id, project_id, operation, target_id) que ejecuta INSERT INTO audit_log (developer_id, project_id, operation, target_id) VALUES ($1, $2, $3, $4); verificado por test que llama la funcion y consulta SELECT * FROM audit_log ORDER BY id DESC LIMIT 1 confirmando que los 4 campos llegaron tal cual.

- **Estado:** ✅ cumplido

### AC-02

NativeBackend.delete_acceptance_criterion invoca record_destructive con operation='delete_acceptance_criterion' y target_id=ac_id TRAS el DELETE SQL exitoso (si el DELETE falla, no se escribe audit); verificado por test que borra un AC existente y confirma una nueva fila en audit_log; y otro test que intenta borrar un AC inexistente y comprueba que audit_log NO crece.

- **Estado:** ✅ cumplido

### AC-03

NativeBackend.archive_item invoca record_destructive con operation='archive_item' y target_id=item_id tras el UPDATE SQL exitoso que marca el item como archivado; verificado por test analogo a AC-02: archive de US/UC exitoso - fila nueva en audit_log; archive de item inexistente - audit_log sin cambios.

- **Estado:** ✅ cumplido

### AC-04

Las otras 7 mutaciones (create_item, update_item, mark_acceptance_criterion, create_acceptance_criteria, update_acceptance_criterion, add_comment, add_attachment) NO escriben en audit_log; verificado por test parametrizado que ejecuta cada una y comprueba que audit_log permanece vacio tras todas ellas.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
