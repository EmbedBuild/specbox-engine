# Plan: [US-NATIVE-PROVISION] Provisión de tenant+membresía y contrato canónico de project_id

> Generado: 2026-06-03
> Origen: FreeForm board `ff-ed0c02f4565a` (specbox-engine) | PRD `doc/prd/US-NATIVE-PROVISION_prd.md`
> Estado: Pendiente
> Tipo: feature de engine (Python + Postgres) — **backend-only, sin UI / VEG / Stitch**

---

## Resumen

Cerrar los 2 gaps del dogfooding v6.9.2: (GAP 1) provisión de tenant+membresía
server-side cuando un proyecto Native nace de cero, reutilizando `setup_board` +
`seed_native_identity`, invocada **antes** del gate de membresía; (GAP 2) contrato
canónico de `project_id` (`owner/repo` + display slug derivado) como punto único de
normalización compartido engine↔panel. Más el E2E "provisión + migración de cero" que
faltaba.

## Análisis UI (Fase 0)

**N/A** — feature 100% backend (módulos Python sobre asyncpg/Postgres). Sin pantallas,
sin VEG, sin Stitch. Pasos 2.5b y 6 de `/plan` omitidos por diseño.

---

## Hallazgo de arquitectura que ancla el plan (file:line)

El orquestador `switch_project_backend` ejecuta `_create_target` (`setup_board`) →
`_write` → `_seed` ([migration.py:1004-1043](../../server/tools/migration.py#L1004-L1043)).
En el path **batch**, `_write` llama `_commit_batch_session`, que exige que la sesión ya
esté **abierta** por `start_migration_session` — y ese `start` corre el gate de membresía
(`authenticate_and_authorize_cached`, [migration.py:1191](../../server/tools/migration.py#L1191))
**antes** de que `_seed` ([migration.py:1034](../../server/tools/migration.py#L1034)) llegue
a ejecutarse. **Conclusión**: la provisión NO puede vivir en `_seed` para el flujo batch;
debe ocurrir dentro de `start_migration_session` (o en un paso explícito previo a él)
cuando el target se crea de cero. Esto es UC-820 (provisión) + UC-821 (integración batch).

Además `_seed` pasa `developer_id=dev_token` ([migration.py:1042](../../server/tools/migration.py#L1042))
— smell preexistente: debería resolver el `dev_id` real desde el token. UC-819/UC-820 lo
corrigen pasando el `developer_id` resuelto y `role="project_admin"`.

---

## Fases de Implementación

### Fase 1: Helper canónico de project_id [UC-818] [AG-01]

- [ ] Crear `server/coordination/project_id.py` con funciones puras:
      `canonical_project_id(owner: str, repo: str) -> str`,
      `display_slug(project_id: str) -> str`,
      `validate_project_id(project_id: str) -> str` (acepta `owner/repo`, rechaza inválidos).
- [ ] Sin I/O. Idempotencia de `display_slug` sobre un slug ya derivado.
- [ ] Tests unitarios en `tests/test_native_provision.py` (AC-01..03).
- **Dependencias**: ninguna. Es la base; el resto la consume.
- **Tiempo estimado**: 30 min.

### Fase 2: seed_native_identity parametrizado por role [UC-819] [AG-01]

- [ ] `server/coordination/identity.py::add_project_member` — ya tiene `role` param
      ([identity.py:281](../../server/coordination/identity.py#L281)); añadir **validación**
      contra `{"project_admin", "member"}` antes del INSERT (AC-06).
- [ ] `server/migration/native_handling.py::seed_native_identity` — añadir parámetro
      `role: str = "member"` y propagarlo a `add_project_member` (AC-04).
- [ ] Confirmar idempotencia (UPSERT ya existe en `add_project_member`, ON CONFLICT
      DO UPDATE SET role) — test que re-ejecuta sin duplicar (AC-05).
- [ ] Tests (AC-04..06).
- **Dependencias**: ninguna (cambio aditivo en firma).
- **Tiempo estimado**: 25 min.

### Fase 3: Provisión server-side de tenant+membresía [UC-820] [AG-01]

- [ ] Añadir `provision_native_project(pool, project_id, developer_id, *, role="project_admin")`
      en `server/migration/native_handling.py` (o función dedicada `provisioning.py`):
      1. valida `project_id` con `validate_project_id` (UC-818);
      2. `setup_board`-equivalente: UPSERT `public.projects` (reutiliza la lógica de
         `NativeBackend.setup_board`, [native_backend.py:336](../../server/backends/native_backend.py#L336));
      3. `seed_native_identity(role="project_admin")` para el caller;
      4. una sola transacción (los 2-3 INSERT en `conn.transaction()`);
      5. fila en `audit_log` vía helper de `server/coordination/audit.py`
         ([audit.py:49](../../server/coordination/audit.py#L49)) con `operation` nuevo
         (ej. `provision_project`) tras éxito.
- [ ] El dev_token se valida fail-fast con `require_dev_token`
      ([native_handling.py:232](../../server/migration/native_handling.py#L232)) **antes** de
      cualquier escritura (AC-08); token inválido → cero filas + envelope `UNAUTHENTICATED`.
- [ ] Idempotencia: re-provisión no degrada `project_admin`→`member` (AC-10) — el UPSERT de
      membresía solo promueve, nunca degrada al caller que crea.
- [ ] Nunca serializa token ni DSN en el return (AC-09, NFR seguridad).
- [ ] Tests Postgres-gated (AC-07..10).
- **Dependencias**: Fase 1 (validate) + Fase 2 (role).
- **Tiempo estimado**: 50 min.

### Fase 4: Integración con el flujo batch [UC-821] [AG-01]

- [ ] `server/tools/migration.py::start_migration_session` — cuando `target_project_id` no
      existe en `public.projects` y el dev_token es válido, auto-provisionar (UC-820)
      **antes** del gate `authenticate_and_authorize_cached` (AC-11). Detección "de cero" =
      SELECT existence sobre `projects` con el `project_id` canónico.
- [ ] Garantizar que la auto-provisión escribe solo en el tenant target y reutiliza la
      identidad cacheada (un solo `resolve_developer`) (AC-13).
- [ ] `commit_migration_session` → `ingest_atomic` re-valida membresía
      ([native_backend.py:672](../../server/backends/native_backend.py#L672)); como la
      membresía ya existe tras la auto-provisión, pasa (AC-12).
- [ ] Resolver el `developer_id` real (no pasar `dev_token` como id) en el path de seed
      del orquestador.
- [ ] Tests Postgres-gated (AC-11..13).
- **Dependencias**: Fase 3.
- **Tiempo estimado**: 45 min.

### Fase 5: E2E provisión + migración de cero [UC-822] [AG-04]

- [ ] `tests/test_native_provision.py::test_e2e_provision_then_migrate_from_scratch`
      (Postgres-gated, `docker compose -f docker-compose.dev.yml up`):
      1. parte de `public.projects` SIN la fila target (AC-14);
      2. dev_token válido → `start_migration_session` (auto-provisiona) → append × N → commit;
      3. assert `public.projects` tiene 1 fila con `project_id` canónico (AC-14);
      4. assert `public.project_members` tiene al caller con `role='project_admin'` (AC-15);
      5. assert US/UC/AC == source 1:1, estados done/backlog preservados (AC-16);
      6. assert `display_slug(project_id)` == slug esperado (AC-17).
- [ ] Fixture: items.json de estados mixtos (reutilizar/mirror del fixture ≥100 KB de
      `tests/test_native_batch_ingestion.py` si aplica, o uno menor que cruce el flujo).
- **Dependencias**: Fases 3 y 4.
- **Tiempo estimado**: 1h.

### Fase 6: Documentación + decisiones canónicas [UC-823] [AG-01]

- [ ] Crear `doc/decisions/native_project_id_contract.md` declarando D1 + D2 con file:line
      del código actual (AC-18).
- [ ] Listar el cambio coordinado requerido en `specbox_cloud`
      (`apps/api/src/routes/projects.ts:140,173`: relajar patrón INSERT para native +
      derivar display slug con el contrato compartido) (AC-19).
- [ ] Registrar D1/D2 como decisiones canónicas del engine: añadir entradas a la zona
      `canonical_decisions` (§6) de `doc/app/app_spec.md` (append-only) + confirmar via
      `record_canonical_confirmation` (AC-20).
- [ ] Actualizar `CLAUDE.md` con la sección v6.9.3.
- **Dependencias**: ninguna (puede ir en paralelo con QA).
- **Tiempo estimado**: 40 min.

---

## Comandos Finales

```bash
docker compose -f docker-compose.dev.yml up -d   # postgres dev local
uv run pytest tests/test_native_provision.py -v
uv run pytest tests/test_native_batch_ingestion.py tests/test_native_*.py  # no regresión
uv run ruff check server/ tests/                  # lint (GGA / fallback)
```

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|----------|---------------|----------------------|-------|
| Contrato project_id | `owner/repo` canónico + display slug | slug canónico | Cero migración, sin colisión cross-owner, trazabilidad GitHub (discovery D1) |
| Autoridad de provisión | Engine auto-provisiona al creador (bootstrap) | Panel provisiona primero | Rompe el huevo-gallina sin paso manual; §6 acotado a excepción (discovery D2) |
| Dónde provisionar en el batch | Dentro de `start_migration_session` | En `_seed` del orquestador | El gate de membresía corre en `start`, antes de `_seed`; provisionar en `_seed` no desbloquea (hallazgo de arquitectura arriba) |
| Helper de normalización | Módulo puro `project_id.py` | Inline en cada caller | Punto único de verdad compartido engine↔panel (D1 lo exige) |

---

## Archivos a Crear/Modificar

```
server/
├── coordination/
│   ├── project_id.py            # CREAR — canonical_project_id / display_slug / validate
│   ├── identity.py              # MOD — add_project_member: validar role
│   └── audit.py                 # MOD — operación 'provision_project'
├── migration/
│   └── native_handling.py       # MOD — seed_native_identity(role=...); provision_native_project()
├── backends/
│   └── native_backend.py        # (lectura — reutilizar lógica setup_board projects UPSERT)
└── tools/
    └── migration.py             # MOD — start_migration_session auto-provisión + dev_id real
tests/
├── test_native_provision.py     # CREAR — UC-818..822
└── test_native_batch_ingestion.py  # MOD — no regresión
doc/
├── decisions/
│   └── native_project_id_contract.md  # CREAR — D1 + D2 + cambio panel
└── app/app_spec.md              # MOD — §6 canonical_decisions (append-only)
CLAUDE.md                        # MOD — sección v6.9.3
```

---

## Cambio coordinado en el repo del PANEL (`specbox_cloud`) — fuera de este repo

> Documentado aquí (UC-823 AC-19); la implementación se hace en `EmbedBuild/specbox_cloud`.

- `apps/api/src/routes/projects.ts:173` — el patrón `^[a-z0-9][a-z0-9-]*$` debe **relajarse**
  para aceptar `owner/repo` cuando el backend del proyecto es `native` (o derivar y almacenar
  `owner/repo` como id canónico y el slug solo como campo display).
- `apps/api/src/routes/projects.ts:140` — la slugificación pasa a ser **derivación de display**
  (no de identidad): `display_slug(project_id)` usando el mismo contrato que el engine.
- Resultado: el panel y el engine apuntan al **mismo** `project_id` (`owner/repo`); el panel
  sirve URLs con el display slug. Una sola fuente de verdad del formato.

---

## Referencias

- PRD: `doc/prd/US-NATIVE-PROVISION_prd.md`
- Discovery: `doc/discovery/provision_native_project_id_contract/icp_jtbd.md`
- Hallazgo: `HALLAZGO-v6.9.3-provision-y-project-id.md`
- v6.9.2 batch transport: `doc/prd/US-NATIVE-BATCH-INGEST_prd.md`
