# Plan: [US-BACKEND-SWITCH] Cambio guiado de backend entre los 4 (FreeForm/Trello/Plane/Native)

> Generado: 2026-05-22
> Origen: FreeForm local (board ff-ed0c02f4565a) | US-BACKEND-SWITCH
> PRD: doc/prd/backend_switch_prd.md
> Estado: Pendiente
> Stitch designs: N/A (feature backend-only, sin UI)
> VEG: DISABLED (heredado de app_spec.md — engine sin UI de producto)

---

## Resumen

Generalizar la migración de spec-driven a N×N completo entre los 4 backends (FreeForm/Trello/Plane/Native), garantizando preservación del avance de ejecución, consistencia de los 3 lugares de verdad tras el switch, y un flujo guiado vía `/switch-backend` con regeneración de evidencias opt-in.

## Análisis UI (Fase 0)

**N/A** — Feature de plataforma sin UI de producto. El único "frontend" es el skill conversacional `/switch-backend`. No hay componentes UI, no se genera VEG ni diseños Stitch.

---

## Análisis técnico — puntos de integración verificados

| Punto | Ubicación actual | Hallazgo relevante para el plan |
|-------|------------------|----------------------------------|
| Lectura backend-agnóstica | `server/tools/migration.py:56` `_read_source` | Ya devuelve dict con items/classified/ac_data/comments/labels/states. Reutilizable tal cual como origen N×N. |
| Creación idempotente | `server/spec_backend.py:181` `create_item` | Ya acepta `external_source`/`external_id` + `meta` + `parent_id` + `state`. `_write_target` se construye sobre esto. |
| Idempotencia existente | `migration.py:282` `find_item_by_field(target, "us_id", ...)` | Patrón ya probado en `migrate_project`. Replicar para UC/AC. |
| Dispatch por backend | `server/auth_gateway.py:51-73` | Ya despacha a los 4 (`freeform/trello/plane/native`). `_write_target` debe usar el mismo mapa, no el `if trello/plane` hardcodeado de migration.py. |
| switch_backend actual | `migration.py:550` | Solo registry + solo trello/plane. Hay que generalizar a 4 + añadir update de app_spec y settings. |
| app_spec tracking_backend | `server/app_docs/sync.py:173,278` | `apply_app_docs_sync` ya tiene el evento `set_auth_token → ("app_spec","tracking_backend")` y la rama `zone_id == "tracking_backend"`. UC-404 lo reutiliza. |
| Native local-only state | `server/db/migrations/0002_developers.sql`, `0003_claims.sql` | Tablas `developers`, `uc_claims`. UC-403 las lee para reportar descartes. |
| DSN Native | env `SPECBOX_NATIVE_DSN` (auth_gateway.py:65-69) | Nunca en sesión. UC-403 AC-03 lo verifica. |
| Evidencia | `.quality/evidence/{feature}/acceptance/results.json` (results-json-spec.md:13) | Indexada por `uc_id` lógico. UC-405 escanea por glob. |
| run_acceptance_check | `server/tools/acceptance.py:286` | Reutilizado por `regenerate_evidence`. |

---

## Fases de Implementación

> Mapeo 1 UC = 1 ciclo /implement. Orden por dependencias: UC-401 → UC-402 → UC-403 → UC-404 → UC-405 → UC-406.
> Agentes: AG-03 (DB/backend Python), AG-04 (QA/tests). Sin AG-02 (no UI).

### Fase 1 — UC-401: `_write_target` genérico + dispatch a los 4 [AG-03]
**Dependencias**: ninguna (cimiento). **Estimado**: 12h.

- [ ] Crear `server/migration/backend_dispatch.py`: helper `build_backend(backend_type, creds)` que centraliza el dispatch de los 4 (extraído del patrón de `auth_gateway.py:51-73`), reutilizable por origen y destino.
- [ ] Crear `_write_target(target_backend, target_id, source_data) -> dict` en `migration.py`: itera US → UC → AC respetando jerarquía (parent_id por id_map), usando `create_item` con `external_source/external_id` para idempotencia y `find_item_by_field` para skip de ya-migrados. AC vía `create_acceptance_criteria` + `mark_acceptance_criterion` para el `done`.
- [ ] Validación de `backend_type` con error explícito que nombra los 4 (`AC-02`).
- [ ] **Fase QA** [AG-04]: `tests/test_migrate_backend_nxn.py` — round-trip parametrizado A→B sobre los 4 tipos (usar InMemory/Freeform como fixtures donde Native requiera Postgres dev), doble pasada → 0 duplicados.

**Cubre**: AC-01, AC-02, AC-03.

### Fase 2 — UC-402: Matriz de estados bidireccional [AG-03]
**Dependencias**: UC-401 (`_write_target` consume el mapeo). **Estimado**: 8h.

- [ ] Crear `server/migration/state_mapping.py`: tabla canónica `{user_stories, backlog, in_progress, review, done}` ↔ estado nativo de cada backend + funciones `to_canonical(backend_type, native)` / `from_canonical(backend_type, canonical)`.
- [ ] Fallback documentado: `done→done`, estado intermedio desconocido → `backlog`, con registro de warning estructurado (UC + estado degradado) en el resultado de migración.
- [ ] Integrar el mapeo en `_write_target` (traduce `state` al escribir) y en `_read_source` (normaliza a canónico al leer).
- [ ] Preservación de `ChecklistItemDTO.done` end-to-end.
- [ ] **Fase QA** [AG-04]: test de `in_progress` round-trip en los 4; caso sin equivalente → fallback + warning; UC con 3/5 AC done → exactamente 3 done en destino.

**Cubre**: AC-04, AC-05, AC-06.

### Fase 3 — UC-403: Manejo del backend Native [AG-03]
**Dependencias**: UC-401, UC-402. **Estimado**: 10h. Requiere Postgres dev (`docker-compose.dev.yml`).

- [ ] Crear `server/migration/native_handling.py`:
  - **Salida** (Native→otro): tras migrar el avance vía `_write_target`, consultar `uc_claims`, `developers`, branches y construir la sección `discarded_native_state` del reporte (conteos + detalle). No se trasladan.
  - **Entrada** (otro→Native): al crear cada US/UC, sembrar `expected_version=1` (vía `meta['expected_version']`, patrón ya usado en NativeBackend) y asociar `developer_id` resuelto del developer actual (`whoami`/token de sesión).
- [ ] Garantía Frontier 2: el módulo accede a Postgres solo vía el pool que lee `SPECBOX_NATIVE_DSN`; ningún output (reporte, projects.json, settings) serializa el DSN.
- [ ] **Fase QA** [AG-04]: migrar Native con ≥1 claim activo → destino con avance + reporte enumera el claim; →Native → filas con `expected_version=1` y `developer_id` no nulo (assert en Postgres); grep del DSN en outputs = 0.

**Cubre**: AC-07, AC-08, AC-09.

### Fase 4 — UC-404: `migrate_backend` N×N + `switch_backend` generalizado + update transaccional [AG-03]
**Dependencias**: UC-401, UC-402, UC-403. **Estimado**: 12h.

- [ ] `migrate_backend(source_type, source_id, target_type, target_id?, dry_run=True)` en `migration.py`: dry-run devuelve preview (counts + state_mapping) sin escribir; `dry_run=False` ejecuta migración aditiva (origen intacto) + id_map + counts migrados/skipped/errores. Reutiliza `set_migration_target` para credenciales del destino.
- [ ] Generalizar `switch_backend` a los 4 backend_types. Tras el switch, actualización transaccional de los 3 lugares con rollback:
  1. `projects.json` (`spec_backend` + `board_id` + `backend_history`).
  2. `app_spec.md` zona `tracking_backend` vía `apply_app_docs_sync("set_auth_token", ...)` (sync.py ya soporta el evento).
  3. `.claude/settings.local.json` → `specbox.backend_type`.
  - Patrón: snapshot previo de los 3 → escribir en orden → si alguno falla, restaurar los snapshots y devolver error nombrando el lugar fallido.
- [ ] **Fase QA** [AG-04]: dry-run → destino vacío; `dry_run=False` → origen `list_items` igual antes/después; post-switch los 3 archivos coherentes y `detect_project_backend` devuelve el nuevo; fallo simulado en settings → `projects.json`+`app_spec` sin cambios.

**Cubre**: AC-10, AC-11, AC-12, AC-13.

### Fase 5 — UC-405: `regenerate_evidence` con progreso [AG-03]
**Dependencias**: independiente de UC-404 (puede paralelizarse), pero conceptualmente posterior. **Estimado**: 6h.

- [ ] Crear `server/tools/evidence_regen.py`: `regenerate_evidence(project, ucs=None)` — escanea `.quality/evidence/*/acceptance/results.json`, deduce UCs con evidencia previa, y por cada uno invoca `run_acceptance_check` (acceptance.py:286) regenerando results.json + HTML.
- [ ] Progreso por UC `[X/N] UC-XXX: {PASS|FAIL|SKIP} (n_acs ACs con evidencia)` + resumen final (regenerados/fallidos/pendientes).
- [ ] Persistir `doc/migrations/evidence_regeneration_{timestamp}.md`.
- [ ] **Fase QA** [AG-04]: proyecto con ≥2 UCs con evidencia → cada results.json con `generated_at` fresco; salida con línea por UC + resumen; archivo de reporte existe con entrada por UC.

**Cubre**: AC-14, AC-15, AC-16.

### Fase 6 — UC-406: Skill `/switch-backend` [AG-01/orquestador]
**Dependencias**: UC-404 (migrate_backend + switch_backend), UC-405 (oferta de regen). **Estimado**: 4h.

- [ ] Crear `.claude/skills/switch-backend/SKILL.md` (`context: direct` — escribe filesystem + llama tools de escritura):
  1. Detecta backend actual (`detect_project_backend`).
  2. Pregunta destino entre los 3 restantes.
  3. Pide credenciales del destino de forma segura (Native → indica `SPECBOX_NATIVE_DSN` en env, NO pide DSN por chat).
  4. Preview obligatorio (`migrate_backend dry_run=True`) + confirmación literal bloqueante.
  5. Ejecuta `migrate_backend dry_run=False` → `switch_backend`.
  6. Reporte final con 4 secciones: switch+consistencia 3 lugares / evidencia intacta / estado Native descartado (si aplica) / oferta de `regenerate_evidence`.
- [ ] Precondición documentada: el skill exige MCP **local** (stdio) porque escribe filesystem local (decisión canónica "FreeForm requiere MCP local").
- [ ] Registrar el skill en `install.sh` y en la tabla de skills de CLAUDE.md.
- [ ] **Verificación**: SKILL.md documenta los 6 pasos, la convención de credenciales por backend, el gate de confirmación, y las 4 secciones del reporte.

**Cubre**: AC-17, AC-18, AC-19.

---

## Comandos Finales (por fase)

```bash
# Tests Python (requiere Postgres dev para los casos Native)
docker compose -f docker-compose.dev.yml up -d
export SPECBOX_NATIVE_DSN="postgresql://...@localhost:55432/specbox_native"
.venv/bin/pytest tests/test_migrate_backend_nxn.py tests/test_switch_backend_transactional.py -q
# No-regresión de migración existente
.venv/bin/pytest tests/test_migration.py tests/test_migration_v529.py -q
gga run  # lint cached
```

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|----------|---------------|----------------------|-------|
| Estructura de migración | `_write_target` simétrico a `_read_source` | Una función por par (12 funciones) | El ABC ya normaliza; un solo writer genérico es DRY y testeable |
| Update post-switch | Transaccional con rollback en 3 lugares | Best-effort sin rollback | Evita drift inconsistente; AC-13 lo exige |
| Estado Native al salir | Descartar con reporte | Snapshot a JSON / bloquear si hay claims | Decisión del usuario: los otros 3 no tienen multi-dev; honesto y simple |
| Evidencia | No mover, regenerar opt-in | Re-vincular binarios al board | Evidencia vive en filesystem indexada por uc_id lógico; mover es frágil y arriesgado |
| Credenciales destino | Reutilizar `set_migration_target` + env para Native | Pedir todo por chat | Frontier 2: DSN nunca en sesión |
| Skill context | `direct` | `fork:Explore` | Escribe filesystem + llama tools de escritura → debe ser direct (regla CLAUDE.md) |

---

## Archivos a Crear/Modificar

```
server/
├── migration/                          # NUEVO paquete
│   ├── backend_dispatch.py             # build_backend(type, creds) — los 4
│   ├── state_mapping.py                # matriz bidireccional + fallback
│   └── native_handling.py              # entrada/salida Native + discarded_native_state
├── tools/
│   ├── migration.py                    # MODIFICAR: _write_target, migrate_backend, switch_backend gen.
│   └── evidence_regen.py               # NUEVO: regenerate_evidence
└── app_docs/sync.py                    # REUTILIZAR: apply_app_docs_sync(set_auth_token)

.claude/skills/switch-backend/SKILL.md  # NUEVO: orquestador guiado
install.sh                              # MODIFICAR: registrar skill
CLAUDE.md                               # MODIFICAR: tabla de skills + sección feature

tests/
├── test_migrate_backend_nxn.py         # NUEVO: round-trip parametrizado + idempotencia
├── test_switch_backend_transactional.py # NUEVO: rollback + 3 lugares
└── test_state_mapping.py               # NUEVO: mapeo bidireccional + fallback
```

---

## Referencias

- PRD: doc/prd/backend_switch_prd.md
- ABC: server/spec_backend.py
- Migración actual: server/tools/migration.py, server/app_docs/migrate_freeform.py
- Sync app_spec: server/app_docs/sync.py
- Evidencia: doc/specs/results-json-spec.md
- Native: server/backends/native_backend.py, server/db/migrations/000{2,3}_*.sql
