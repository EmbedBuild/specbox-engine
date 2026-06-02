# Plan: [US-BACKEND-SWITCH-NATIVE] Cambiar de backend como operación única, atómica y completa (hacia/desde Native)

> Generado: 2026-06-02
> Origen: US-BACKEND-SWITCH-NATIVE (FreeForm board `ff-ed0c02f4565a`)
> PRD: `doc/prd/US-BACKEND-SWITCH-NATIVE_prd.md`
> Discovery: `doc/discovery/backend_switch_native/icp_jtbd.md`
> Estado: Pendiente
> stitch_designs: N/A (feature backend-only, sin UI)
> VEG: DISABLED (sin targets de UI)

---

## Resumen

Refactorizar "cambiar de backend" en una **operación única atómica**
(`switch_project_backend`) que lee el source del **cliente** (content-passing,
nunca del FS del servidor remoto), preserva estados, y conmuta los 3 lugares de
config con rollback **end-to-end**. Reusa al máximo lo que ya existe
(`write_target`, `state_mapping`, `native_handling`, `apply_switch_transactional`,
`detect_local_root_path`, `mcp-client-io.mjs`) y cierra el path-bug de MCP remoto
dentro de la operación, no como parche aislado.

## Análisis UI (Fase 0)

N/A — feature de infraestructura del engine. Sin componentes UI. La interacción es
vía tool MCP `switch_project_backend` + skill `/switch-backend` (texto en chat).

---

## Arquitectura objetivo

```
                       ┌─────────────────────────────────────────┐
   CLIENTE (skill)     │  switch_project_backend (tool pública)   │   SERVER (MCP remoto)
 ┌──────────────────┐  │  ── orquesta todo-o-nada ──              │
 │ Read items.json  │──┼─▶ 1. resolve_source(source_content|API)  │  ← UC-810 content-passing
 │ Read app_spec.md │  │     └ freeform: del CONTENT del cliente  │
 │ Read settings    │  │     └ trello/plane: de la API            │
 └──────────────────┘  │     └ native: NativeBackend DTO          │  ← UC-814
        │              │  2. preview {read_counts, degradations,  │
        ▼              │       native_exit_report?} (dry_run)     │  ← UC-811 guard rail
   confirma conteo ────┼─▶ 3. (target native) require dev_token   │  ← UC-813 fail-fast
        │              │  4. write_target (preserva estados)      │  ← reusa writer.py
        │              │  5. (target native) seed_native_identity │  ← reusa native_handling
        │              │  6. (source native) build_exit_report    │  ← reusa native_handling
        │              │  7. apply_switch_transactional (3 lugares)│  ← reusa, +rollback datos
        ▼              │  8. rollback TOTAL si algo falla         │  ← UC-812 AC-07
 Write app_spec.md ◀───┼──   devuelve content de los 3 lugares    │  ← UC-815 write-back
 Write settings    ◀───┘                                          │
```

---

## Fases de Implementación

> **Orden por dependencias** (cada fase ⇒ 1 UC ⇒ 1 ciclo `/implement`). El
> `pipeline-phase-guard` enforça que no se salte el orden. Fases 1-2 son la base
> (content-passing + guard rail); 3 es el orquestador que las usa; 4-5 son los
> flujos native; 6 es el cliente; 7 cierra onboard; 8 son los E2E.

### Fase 1 — UC-810: Content-passing en `_read_source` + `migrate_preview` [base]

**Objetivo**: el source nunca se lee del FS del servidor. Raíz del bug.

- [ ] Refactor `_read_source(backend, board_id)` → aceptar una vía de **contenido**.
  Diseño: nueva función `resolve_source(source_type, ctx, source_id, source_content)`
  en `server/tools/migration.py` que:
  - `freeform` + `source_content` presente → construir un `FreeformBackend(items_content=source_content)` (el ctor YA acepta `items_content`, ver `freeform_backend.py.__init__`) y leer de ahí. **Nunca** tocar el FS.
  - `freeform` + `source_content=None` → `error: "freeform source requires source_content (read items.json on the client)"` (AC-02).
  - `trello`/`plane` → `get_session_backend(ctx)` y leer de la API (legítimo server-side, AC-03).
  - `native` → `NativeBackend` (cubierto en Fase 5, aquí solo el dispatch).
- [ ] `migrate_preview` recibe nuevo param `source_content: str | None = None` y usa `resolve_source`. Reporta `read_counts={us, uc, ac}`.
- [ ] Mantener `_read_source` como wrapper interno compatible (callers existentes no rompen).
- **Archivos**: `server/tools/migration.py`.
- **Tests**: `tests/test_backend_switch_native.py::test_preview_freeform_content_passing` (11/88 desde content), `::test_preview_freeform_no_content_errors`, `::test_preview_trello_uses_api`.
- **Cubre**: AC-01, AC-02, AC-03.

### Fase 2 — UC-811: Guard rail de conteo confirmable [base]

**Objetivo**: imposible ejecutar el real leyendo el source equivocado.

- [ ] El preview retorna `read_counts` + un flag `executable` (false si counts==0).
- [ ] `migrate_backend`/`switch_project_backend` execute reciben `confirmed_count: dict | None`:
  - counts del source == 0 → `error: "refusing to execute: dry-run read 0 items — source path/content likely wrong"` (AC-04).
  - `confirmed_count` ausente o != read_counts → `error: "count mismatch: preview read {X}, execute confirmed {Y}"` (AC-05).
  - match → procede.
- **Archivos**: `server/tools/migration.py`; helper puro `server/migration/count_guard.py` (`verify_count(preview_counts, confirmed) -> None|raise`).
- **Tests**: `::test_execute_blocked_on_zero_count`, `::test_execute_count_mismatch_rejected`, `::test_execute_count_match_proceeds`.
- **Cubre**: AC-04, AC-05.

### Fase 3 — UC-812: Orquestador atómico `switch_project_backend` [core]

**Objetivo**: una sola tool pública todo-o-nada; rollback end-to-end.

- [ ] Nueva tool `switch_project_backend(project_slug, source_type, target_type, ctx, source_content=None, app_spec_content=None, settings_content=None, target_id=None, target_name=None, dev_token="", on_collision="fail", dry_run=True, confirmed_count=None)` en `server/tools/migration.py`, registrada en `register_migration_tools`.
- [ ] Internamente orquesta (reusando Fases 1-2 + helpers existentes):
  1. `resolve_source` (Fase 1) → preview.
  2. si `dry_run` → devolver preview {read_counts, degradations, native_exit_report?, collision?}.
  3. `verify_count` (Fase 2).
  4. (target native) `require_dev_token` (Fase 4).
  5. snapshot del estado previo del target (para rollback de datos).
  6. `write_target` (preserva estados) → Postgres / target.
  7. (target native) `seed_native_identity`.
  8. (source native) `collect_discarded_native_state` + `build_native_exit_report`.
  9. `apply_switch_transactional` (3 lugares) — extendido para devolver el content de app_spec/settings (write-back cliente).
  10. **rollback total**: helper `rollback_data_migration(target_backend, target_id, pre_snapshot)` que, si el target native NO preexistía, hace DELETE del proyecto recién creado; envuelve pasos 6-9 en try/except.
- [ ] `migrate_backend` y `switch_backend` añaden a su response `"note": "prefer switch_project_backend for atomic switches"` (AC-08).
- **Archivos**: `server/tools/migration.py`; nuevo `server/migration/orchestrator.py` (lógica pura del orquestador, testeable sin MCP); `server/migration/rollback.py` (`rollback_data_migration`).
- **Tests**: `::test_orchestrator_freeform_to_native_4_substeps`, `::test_orchestrator_rollback_on_switch_failure` (inyectar `_write_app_spec` que lanza → asserta proyecto Postgres vuelve a vacío + `rolled_back=true`), `::test_legacy_tools_emit_prefer_note`.
- **Cubre**: AC-06, AC-07, AC-08.

### Fase 4 — UC-813: Destino native (fail-fast + estados + idempotencia) [native-in]

- [ ] `require_dev_token(target_type, dev_token)` en `server/migration/native_handling.py`: si `target=="native"` y `dev_token` vacío → `error` ANTES de cualquier read/write (AC-09). Wire en orquestador paso 4, antes del paso 1 read.
- [ ] Verificar que el path usa `write_target` (preserva `state=item.state`) y NUNCA `import_spec`. Test con estados mixtos done/in_progress/review → asserta preservación en Postgres (AC-10).
- [ ] Idempotencia/colisión: antes del write, `NativeBackend.list_items(target_id)` → si tiene items, set `collision={project_exists:true, item_count}` en el preview; el execute exige `on_collision ∈ {reuse, skip, fail}`; sin resolución → error (AC-11).
- **Archivos**: `server/migration/native_handling.py`, `server/migration/orchestrator.py`, `server/backends/native_backend.py` (si hace falta un helper de count).
- **Tests**: `::test_native_target_requires_dev_token` (assert no INSERT, no source read), `::test_native_preserves_mixed_states`, `::test_native_collision_requires_resolution`. Marcar los que tocan Postgres con el fixture native (docker-compose.dev.yml).
- **Cubre**: AC-09, AC-10, AC-11.

### Fase 5 — UC-814: Origen native (DTO + exit-report) [native-out]

- [ ] En `resolve_source`, rama `native`: leer vía `NativeBackend.list_items` / `get_acceptance_criteria` / `get_item_children` (DTO, no FS) → mismo shape que `_read_source` devuelve (AC-12).
- [ ] El preview de salida incluye `native_exit_report` (reusar `collect_discarded_native_state` + `build_native_exit_report`) mostrado ANTES de confirmar (AC-13).
- [ ] El execute escribe US/UC/AC al target preservando estados, descarta coordinación, y el result final incluye el exit-report con lo descartado (AC-14).
- **Archivos**: `server/tools/migration.py` (resolve_source native), `server/migration/orchestrator.py`, `server/migration/native_handling.py` (ya existe lo necesario).
- **Tests**: `::test_native_source_read_via_dto`, `::test_native_exit_report_before_confirm`, `::test_native_exit_discards_coordination`. Fixture Postgres.
- **Cubre**: AC-12, AC-13, AC-14.

### Fase 6 — UC-815: Skill `/switch-backend` online-first + write-back [cliente]

- [ ] Eliminar la precondición BLOQUEANTE "MCP local" (`.claude/skills/switch-backend/SKILL.md:25-38`). Sustituir por flujo online-first: la skill lee con `Read` el `items.json` (source), `app_spec.md`, `settings.local.json` del cliente y los pasa por content-passing (reusar `readTrackingBundle`/`readContentBundle` de `mcp-client-io.mjs`).
- [ ] Tras el execute, escribir el content devuelto de `app_spec.md` + `settings.local.json` en el FS del CLIENTE (`writeContentBundle`). (AC-15).
- [ ] La skill muestra "N US / M UC leídas del cliente" y exige confirmación literal del conteo antes del execute (AC-16).
- **Archivos**: `.claude/skills/switch-backend/SKILL.md` (reescritura de pasos), reuso `.claude/hooks/lib/mcp-client-io.mjs`.
- **Tests**: validación manual del SKILL (el flujo es de skill, no Python). Añadir test del helper si se toca `mcp-client-io.mjs` (`mcp-client-io.test.mjs`).
- **Cubre**: AC-15, AC-16.
- **Nota**: este UC es de tipo "skill", su evidencia es el SKILL.md actualizado + smoke. Marca de gate humano recomendable.

### Fase 7 — UC-816: `onboard_project --backend native` documenta "registry sin BD" [cierre]

- [ ] En `server/tools/onboarding.py`, cuando `backend_type=="native"` y no hay populate, el result incluye `next_action: "project registered, native DB empty — run switch_project_backend or import_spec to populate"` (AC-17).
- **Archivos**: `server/tools/onboarding.py`.
- **Tests**: `::test_onboard_native_documents_empty_db`.
- **Cubre**: AC-17.

### Fase 8 — UC-817: E2E de no-regresión [verificación]

- [ ] `::test_e2e_remote_mcp_reads_client_not_server` (AC-18): set `SPECBOX_ENGINE_MCP_URL`, mock del FS del servidor con un items.json 22/112, pasar `source_content` de 11/88; assert conteo == 11/88 y que el mock del FS del servidor **no fue leído** (spy/no-call assertion).
- [ ] `::test_e2e_freeform_to_native_preserves_states` (AC-19): usar el backup `native-project-backup-pre-delete.json` como fixture (10 US / 84 UC / 440 AC), migrar freeform→native contra Postgres de test; assert conteos, developer como project_admin, estados NO degradados.
- **Archivos**: `tests/test_backend_switch_native.py`, fixture copiado a `tests/fixtures/` (o referenciar el backup del repo cliente).
- **Cubre**: AC-18, AC-19.

---

## Mapa UC → Fase → AC → Archivos

| UC | Fase | AC | Archivos principales |
|----|------|----|----|
| UC-810 | 1 | 01-03 | `server/tools/migration.py` |
| UC-811 | 2 | 04-05 | `server/tools/migration.py`, `server/migration/count_guard.py` (nuevo) |
| UC-812 | 3 | 06-08 | `server/tools/migration.py`, `server/migration/orchestrator.py` (nuevo), `server/migration/rollback.py` (nuevo) |
| UC-813 | 4 | 09-11 | `server/migration/native_handling.py`, `orchestrator.py`, `native_backend.py` |
| UC-814 | 5 | 12-14 | `server/tools/migration.py`, `orchestrator.py`, `native_handling.py` |
| UC-815 | 6 | 15-16 | `.claude/skills/switch-backend/SKILL.md`, `mcp-client-io.mjs` |
| UC-816 | 7 | 17 | `server/tools/onboarding.py` |
| UC-817 | 8 | 18-19 | `tests/test_backend_switch_native.py`, `tests/fixtures/` |

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|----------|----------------|------------------------|-------|
| Interfaz pública | Tool atómica nueva `switch_project_backend` + skill | Mantener tools sueltas, atomicidad solo en skill | El prompt + D1 exigen operación única; la atomicidad en una tool es testeable y no depende de que el agente encadene bien |
| Lectura del source freeform | `FreeformBackend(items_content=...)` (ctor ya lo soporta) | Parser ad-hoc del items.json | Reusa el backend real → mismo `list_items`/`get_acceptance_criteria`, una sola forma interna |
| Rollback de datos en native | DELETE del proyecto si NO preexistía + snapshot | Transacción Postgres abarcando todo | `setup_board` + writes son múltiples statements; un DELETE condicional es simple y suficiente para el caso "proyecto nuevo" (el más común) |
| Preservación de estados | `write_target` (ya identidad para native) | `import_spec` | `import_spec` hardcodea estado → degrada. `write_target` preserva. Ya verificado en discovery |
| Write-back de los 3 lugares | content-passing vía `mcp-client-io.mjs` | Server escribe el FS | Decisión canónica UC-668: server nunca toca FS ajeno |

---

## Estrategia de Rollback (crítica — datos productivos)

`apply_switch_transactional` ya hace snapshot+restore de los 3 lugares de config.
El plan **extiende** la atomicidad a la migración de datos:

1. **Antes** del paso 6 (write_target): snapshot del estado previo del target.
   - native nuevo (no preexistía) → marca `created_fresh=true`.
   - native preexistente con `on_collision=reuse` → snapshot de items (o rechazar rollback de datos y solo permitir switch-config-rollback, documentado).
2. **try** pasos 6-9; **except** cualquier fallo →
   - revertir config (lo hace `apply_switch_transactional` internamente).
   - `rollback_data_migration`: si `created_fresh` → DELETE proyecto native; resultado `rolled_back=true` + `failing_step`.
3. Resultado: proyecto en su backend original, target limpio. (AC-07.)

---

## Riesgos

| Riesgo | Prob | Impacto | Mitigación |
|--------|------|---------|------------|
| Rollback de datos en Postgres con proyecto preexistente (reuse) es complejo | Media | Medio | v1: rollback de datos SOLO garantizado para `created_fresh`. Para `reuse`, documentar que el rollback cubre config pero el merge de items no se deshace; avisar en el preview |
| DTO de source diverge entre las 3 fuentes | Media | Medio | Normalizar todo al shape de `_read_source` (`{board_name, items, classified, ac_data, comments_data, labels, states}`) |
| Romper callers de migrate_backend/switch_backend | Media | Medio | Params nuevos opcionales; wrappers compatibles; deprecar no eliminar |
| Tests native requieren Postgres | Media | Bajo | Reusar `docker-compose.dev.yml` (postgres:16 :55432); marcar tests con skip si no hay BD |

---

## Comandos finales (por fase y al cierre)

```bash
# Por fase (durante /implement)
uv run pytest tests/test_backend_switch_native.py -x -q
# Native (fases 4-5-8) — requiere Postgres dev
docker compose -f docker-compose.dev.yml up -d
uv run pytest tests/test_backend_switch_native.py -k native -q
# Cierre
uv run pytest tests/ -q          # suite completa, sin regresión native
gga run                          # lint cacheado
```

---

## Referencias

- PRD: `doc/prd/US-BACKEND-SWITCH-NATIVE_prd.md`
- Discovery: `doc/discovery/backend_switch_native/icp_jtbd.md`
- Piezas reusadas: `server/migration/{writer,state_mapping,native_handling,transactional_switch}.py`, `server/tools/onboarding.py::detect_local_root_path`, `.claude/hooks/lib/mcp-client-io.mjs`
- Decisión canónica: "Transporte único MCP remoto + content-passing" (app_spec.md, UC-668)
- Backup no-regresión: `specbox_cloud/.quality/dogfood-backup/native-project-backup-pre-delete.json`
