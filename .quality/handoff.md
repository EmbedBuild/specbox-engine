---
generated_at: 2026-05-21T21:07:18Z
generator: specbox-handoff-v1
schema_version: 1
project: specbox-engine
session_id: 9ffb927e0d53
trigger: manual
ttl_minutes: 1440
branch: main
active_uc: null
---

# SpecBox Handoff — specbox-engine

## State snapshot
- **Branch**: main
- **Active UC**: none
- **Backend**: freeform
- **Last commit**: 6d7aa88 "feat(native-backend): dispatch del NativeBackend opt-in por proyecto (UC-103) (#28)"
- **Healing events this session**: 0
- **Open feedback (blocking)**: 0
- **Context tokens estimated this session**: 1295

## What this session did
- Implementé y mergeé H1 completo del Native Backend Team: UC-102 (esquema Postgres multi-tenant + pool asyncpg, PR #26), UC-101 (NativeBackend con los 26 métodos del ABC + concurrencia optimista, PR #27), UC-103 (dispatch native opt-in, PR #28)
- Monté un Postgres dev local con docker-compose.dev.yml (postgres:16, puerto 55432, db specbox_native) contra el que se verifican migraciones y tests
- Resolví las 2 preguntas abiertas del handoff previo: AC-01 (no había suite de conformidad parametrizada, ahora creada) y AC-06 (Sala de Máquinas descubre por filesystem, independiente del backend de spec)
- Cada UC siguió el pipeline /implement: rama feature, delegación a Tasks aislados AG-03/AG-04, verificación independiente, commits por fase, PR con evidencia de AC, merge y limpieza de rama
- Detecté deuda preexistente en main (test_spec_mutations.py: InMemoryBackend mock sin archive_item, 13 errors) — verificada como ajena a mis cambios en worktree de main limpio
- Guardé preferencia de idioma del usuario (español de España, sin argentinismos) en memoria de feedback

## Decisions taken (with key)
- AC-06 reasignado de UC-102 a UC-101 → satisfecho-por-diseño (Sala de Máquinas vía heartbeat→registry, no requiere migrar overview a Postgres en v1)
- Postgres dev → docker-compose.dev.yml aparte (opción B), no en el compose de producción
- expected_version (AC-03) → se pasa vía meta['expected_version'] para no romper la firma del ABC; guard optimista solo en US/UC vía update_item
- project_id en set_auth_token → kwarg nuevo opcional (no sobrecarga root_path)
- NO usar tools MCP spec-driven (start_uc/find_next_uc/mark_ac) → el MCP es remoto (VPS); el board ff-ed0c02f4565a es FreeForm LOCAL, se edita doc/tracking/ directamente

## Open questions
- Deuda preexistente: ¿abrir PR de saneamiento para el InMemoryBackend mock (archive_item) de test_spec_mutations.py? → pendiente decisión del usuario
- CI con Postgres: exportar SPECBOX_NATIVE_DSN para que los tests de round-trip corran en vez de skipear
- Notas de review en NativeBackend: comments/attachments/labels en JSONB (UC-102 no creó tablas dedicadas); add_attachment guarda referencia native:// no el blob → revisar si hace falta almacenamiento first-class

## Hot files (top N by edits this session)
- .quality/handoff.md
- .quality/read_tracker.jsonl
- specbox-state.json

## Next concrete step
Arrancar H2 (identidad de developer) con /implement UC-201: tabla developers (developer_id PK, display_name, token_hash) en migración 0002_developers.sql, tokens hasheados, módulo nuevo server/coordination/identity.py (resolución token→developer, autenticación UNAUTHENTICATED + autorización dev↔project FORBIDDEN), tool whoami(). El Postgres dev se levanta con: docker compose -f docker-compose.dev.yml up -d. Orden H2→H3: UC-201 → 202 → 203 → 301 → 302 → 303 → 304.

## Pointers para la próxima sesión
_(none)_
