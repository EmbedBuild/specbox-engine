---
id: UC-501
ordinal: UC-023
title: "Schema rediseñado: github_identities + mcp_tokens + audit_log"
parent_us: US-NATIVE-SECURITY
status: done
actor: Engine
hours: 8
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-501 — Schema rediseñado: github_identities + mcp_tokens + audit_log

> **US padre:** [US-NATIVE-SECURITY](../us/US-04-blindar-el-native-backend-contra-mutaciones-de-identidades-r.md)

## Objetivo / Descripción

_Sin descripción en el board. El detalle vive en el PRD/plan de la US._

## Acceptance Criteria

### AC-01

La migracion 0004_github_identities.sql crea la tabla github_identities con github_user_id BIGINT PRIMARY KEY, github_login TEXT NOT NULL, developer_id TEXT NOT NULL REFERENCES developers(developer_id) ON DELETE CASCADE, linked_at TIMESTAMPTZ NOT NULL DEFAULT now(); anade indice idx_github_identities_developer_id sobre developer_id; verificado aplicando la migracion a un Postgres limpio y consultando \d github_identities que devuelve esa estructura exacta.

- **Estado:** ✅ cumplido

### AC-02

La migracion 0005_mcp_tokens.sql crea la tabla mcp_tokens con token_id TEXT PRIMARY KEY, developer_id TEXT NOT NULL REFERENCES developers(developer_id) ON DELETE CASCADE, github_user_id BIGINT NULL REFERENCES github_identities(github_user_id) ON DELETE SET NULL, token_hash TEXT NOT NULL UNIQUE, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), last_used_at TIMESTAMPTZ NULL, revoked_at TIMESTAMPTZ NULL; anade indices idx_mcp_tokens_token_hash UNIQUE y idx_mcp_tokens_developer_id; verificado con \d mcp_tokens.

- **Estado:** ✅ cumplido

### AC-03

La migracion 0005_mcp_tokens.sql dropea atomicamente la columna developers.token_hash y el indice idx_developers_token_hash en el mismo archivo (un solo paso); verificado aplicando la migracion y comprobando que \d developers ya no muestra token_hash y que \di ya no lista idx_developers_token_hash.

- **Estado:** ✅ cumplido

### AC-04

La migracion 0006_audit_log.sql crea la tabla audit_log con id BIGSERIAL PRIMARY KEY, developer_id TEXT NULL, project_id TEXT NOT NULL, operation TEXT NOT NULL, target_id TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(); anade indice idx_audit_log_project_occurred sobre (project_id, occurred_at DESC) para queries del SuperAdmin por proyecto; verificado con \d audit_log y \di.

- **Estado:** ✅ cumplido

### AC-05

Las 3 migraciones son idempotentes (IF NOT EXISTS / IF EXISTS) - reaplicarlas sobre una DB que ya las tiene no lanza error ni duplica nada; verificado con un test que llama apply_migrations() dos veces seguidas contra el Postgres dev local y comprueba 0 errores en la segunda pasada.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
