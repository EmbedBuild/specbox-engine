---
id: UC-403
ordinal: UC-015
title: RLS y policies sobre las tablas public (silenciar advisors)
parent_us: US-NATIVE-SUPABASE
status: done
actor:
hours: 6
owner: Jesús Pérez
created: 2026-05-21
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-403 — RLS y policies sobre las tablas public (silenciar advisors)

> **US padre:** [US-NATIVE-SUPABASE](../us/US-02-migrar-el-native-backend-de-postgres-vps-a-supabase-gestiona.md)

## Objetivo / Descripción

Activar Row Level Security en todas las tablas del Native Backend en el schema public y definir policies. Aunque el MCP accede con service_role (que ignora RLS), el advisor de seguridad de Supabase marca como critico cualquier tabla public sin RLS. Cerrar ese gap.

## Acceptance Criteria

### AC-32

ALTER TABLE ... ENABLE ROW LEVEL SECURITY esta aplicado a las 8 tablas del Native Backend; get_advisors(type='security') no devuelve hallazgos de severidad ERROR del tipo 'RLS Disabled in Public' para ninguna de ellas.

- **Estado:** ✅ cumplido

### AC-33

El acceso del MCP con la service_role key sigue funcionando end-to-end (un import_spec + find_next_uc + start_uc completo) pese a RLS activo, confirmando que el rol de servicio bypassa las policies como se espera.

- **Estado:** ✅ cumplido

### AC-34

Existe al menos una policy explicita por tabla (no solo RLS habilitado sin policies) documentada en la migracion, de forma que un cliente anon/authenticated NO puede leer ni escribir filas de spec (verificado con la anon key: SELECT devuelve 0 filas o error de permiso).

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
