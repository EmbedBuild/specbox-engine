---
id: UC-404
ordinal: UC-011
title: Gestion y rotacion de la credencial Supabase (Frontera 2)
parent_us: US-NATIVE-SUPABASE
status: done
actor:
hours: 6
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-404 — Gestion y rotacion de la credencial Supabase (Frontera 2)

> **US padre:** [US-NATIVE-SUPABASE](../us/US-02-migrar-el-native-backend-de-postgres-vps-a-supabase-gestiona.md)

## Objetivo / Descripción

Definir donde vive el DSN del Pooler de Supabase en VPS y CI, como se rota, y como se distingue de la antigua credencial del Postgres-VPS. La credencial es el service-role/DB password de Supabase. Incluye el runbook de retirada del Postgres viejo.

## Acceptance Criteria

### AC-35

Existe un runbook documentado (doc/) que indica: (a) como obtener el DSN del Pooler transaction-mode desde el dashboard de Supabase, (b) en que variable/secreto vive en el VPS y en CI (SPECBOX_NATIVE_DSN), (c) el procedimiento de rotacion sin downtime.

- **Estado:** ✅ cumplido

### AC-36

La credencial del Postgres-VPS antiguo (specbox_dev_only / DSN viejo) queda retirada de la config de produccion tras verificar que el MCP opera contra Supabase; el runbook incluye el paso de teardown del contenedor/instancia VPS y la verificacion previa de que no quedan datos sin migrar.

- **Estado:** ✅ cumplido

### AC-37

Ningun secreto de Supabase (service_role key, DB password, DSN completo) queda commiteado al repo ni impreso en logs: una busqueda de los prefijos conocidos en el arbol git y en los logs de arranque del MCP no encuentra coincidencias.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
