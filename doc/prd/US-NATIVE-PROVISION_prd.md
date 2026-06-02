# PRD: [US-NATIVE-PROVISION] Provisión de tenant+membresía y contrato canónico de project_id

> Origen: FreeForm board `ff-ed0c02f4565a` (specbox-engine) | Discovery `disc-73746ae3b2bc`
> Generado: 2026-06-03
> Tipo: PRD Técnico (cierre de gaps de diseño) — feature de engine, sin UI/VEG
> Discovery: [doc/discovery/provision_native_project_id_contract/icp_jtbd.md](../discovery/provision_native_project_id_contract/icp_jtbd.md)

## Resumen

Migrando un proyecto real freeform→native de cero (`specbox_cloud`, 13 US / 89 UC /
466 AC, items.json 186 KB), el **transporte por lotes de v6.9.2 funcionó** pero la
migración se bloqueó en la **provisión del tenant**: tras un dev_token válido (la
identidad autentica, `whoami` OK), `start_migration_session` rechazó con
`Developer jesusperezdeveloper is not a member of project EmbedBuild/specbox_cloud`.

Son **dos gaps de diseño combinados** que bloquean el caso de uso central del producto
("subir mi proyecto a SpecBox Cloud"):

- **GAP 1 — provisión**: el batch-ingest no crea `public.projects` + `public.project_members`
  (creador como `project_admin`) cuando el proyecto nace de cero. Huevo-gallina enforced
  por FK (`project_members.project_id REFERENCES projects(project_id)`): para ser miembro,
  el tenant debe existir; pero lo crearía la propia migración. El path **no-batch**
  (`migrate_backend`) sí provisiona (`setup_board` + `seed_native_identity`); el path
  **batch** no.
- **GAP 2 — contrato de project_id**: el engine/native usa `owner/repo`
  (`EmbedBuild/specbox_cloud`); el panel slugifica a `embedbuild-specbox-cloud`
  (`^[a-z0-9][a-z0-9-]*$`, lowercase, `/`→`-`). Los dos lados nunca acordaron el formato.

Esta US cierra ambos gaps como un solo flujo coherente, reutilizando `setup_board` y
`seed_native_identity`, materializando las dos decisiones canónicas del discovery, y
añadiendo el E2E "provisión + migración de proyecto nuevo a native desde cero" que hoy
no existe (por eso el gap pasó los tests de v6.9.2).

## Decisiones canónicas (del discovery, materializadas en esta US)

### D1 — `native_project_id_contract` = **owner/repo canónico + display slug derivado**
- Forma canónica almacenada en `public.projects.project_id` = `owner/repo` (case-preserving).
- Display slug = proyección URL-safe (`lowercase` + `/`→`-`) **solo** para URLs/visual.
- Punto único de normalización compartido engine↔panel: `canonical_project_id(owner, repo)`
  y `display_slug(project_id)`. El engine es la fuente de verdad del helper.
- **Cero migración** de project_ids existentes (ya son `owner/repo`).

### D2 — `native_provision_authority` = **engine auto-provisiona al creador como `project_admin` (excepción bootstrap)**
- En migración a Native que nace de cero, el engine crea `public.projects` + añade al
  **caller** (resuelto desde su dev_token) como `project_admin`, server-side, antes del gate.
- §6 del panel (*"el panel es el único editor de project_members"*) se acota a excepción
  de bootstrap: el panel sigue siendo editor de **otros** miembros; el engine solo
  auto-provisiona **al propio creador**.
- Valida dev_token, escribe solo en el tenant del caller, queda en `audit_log`, no relaja
  `deny_anon` ni expone `service_role`.

## Alcance

### Incluye
- Helper canónico de normalización de `project_id` (punto único de verdad, D1).
- `seed_native_identity` parametrizado por `role`, default `project_admin` en provisión.
- Provisión server-side de tenant+membresía (reutiliza `setup_board` + `seed_native_identity`),
  invocada **antes** del gate de membresía del flujo batch (GAP 1, D2).
- Integración con el flujo de migración por lotes de v6.9.2: provisión → ingesta sin que el
  gate de membresía bloquee.
- E2E "provisión + migración de proyecto nuevo a native desde cero".
- Documentación del cambio coordinado requerido en el panel (`specbox_cloud`).

### No incluye
- Implementar el cambio en el repo del panel (`specbox_cloud`) — se documenta aquí, se
  implementa en su propio repo.
- Gestión de **otros** miembros desde el engine (sigue siendo del panel, §6).
- Migración de project_ids existentes (D1 = cero migración).
- Cambios en el transporte por lotes de v6.9.2 (chunking, SHA-256, atomicidad) — intactos.

---

## User Story

**ID**: US-NATIVE-PROVISION
**Nombre**: Provisión de tenant+membresía y contrato canónico de project_id
**Actor**: Dev solo / equipo que sube su proyecto a SpecBox Cloud por primera vez
**Horas estimadas**: 28h

> Como dev que sube su proyecto local a SpecBox Cloud por primera vez, quiero que la
> migración provisione automáticamente mi tenant y mi membresía como admin con un
> identificador de proyecto acordado entre engine y panel, para no chocarme con un
> "no eres miembro de un proyecto que aún no existe" ni con dos proyectos divergentes.

---

## Use Cases

### UC-818: Helper canónico de normalización de project_id (punto único de verdad)
- **Actor**: Sistema
- **Horas**: 4h
- **Estado**: backlog
- **Contexto**: Materializa D1. `server/coordination/project_id.py` (o módulo equivalente)
  con `canonical_project_id(owner, repo) -> "owner/repo"` y
  `display_slug(project_id) -> "owner-repo"`. Funciones puras, sin I/O, testeables.
  Es la única fuente de verdad del formato; engine y panel consumen el mismo contrato.

#### Acceptance Criteria
- [ ] **AC-01** [JR-F693.2]: `canonical_project_id("EmbedBuild", "specbox_cloud")` devuelve
  exactamente `"EmbedBuild/specbox_cloud"` (case-preserving, una sola barra, sin recortes).
- [ ] **AC-02** [JR-F693.2]: `display_slug("EmbedBuild/specbox_cloud")` devuelve
  `"embedbuild-specbox-cloud"` (lowercase + `/`→`-`), y es idempotente sobre un slug ya derivado.
- [ ] **AC-03** [JR-F693.2]: un `project_id` ya en formato `owner/repo` pasado a
  `canonical_project_id` (o a su validador) se acepta sin alterarlo; un id inválido
  (vacío, sin owner, con múltiples barras) lanza un error explícito identificable.

### UC-819: seed_native_identity parametrizado por role (creador como project_admin)
- **Actor**: Sistema
- **Horas**: 3h
- **Estado**: backlog
- **Contexto**: Hoy `seed_native_identity` llama `add_project_member` con default
  `role="member"` (`identity.py:281`). Materializa D2: la provisión debe poder conceder
  `project_admin`. Cambio aditivo: nuevo parámetro `role` en `seed_native_identity`,
  propagado a `add_project_member`; default explícito `project_admin` en el camino de provisión.

#### Acceptance Criteria
- [ ] **AC-04** [JR-F693.3]: `seed_native_identity(..., role="project_admin")` deja la fila
  `project_members` con `role='project_admin'` para el `(project_id, developer_id)` indicado.
- [ ] **AC-05** [JR-F693.3]: la llamada es idempotente sobre `(project_id, developer_id)`:
  re-ejecutar con el mismo `role` no duplica filas ni lanza UNIQUE violation (UPSERT).
- [ ] **AC-06** [JR-F693.4]: el valor de `role` se valida contra el conjunto permitido
  (`project_admin` / `member`); un `role` desconocido se rechaza con error explícito antes
  del INSERT (no se persiste un rol arbitrario).

### UC-820: Provisión server-side de tenant+membresía antes del gate
- **Actor**: Sistema
- **Horas**: 6h
- **Estado**: backlog
- **Contexto**: Materializa GAP 1 + D2. Función/paso de provisión que, dado un dev_token
  válido y un `target_project_id` canónico, ejecuta atómicamente: (1) `setup_board` →
  UPSERT `public.projects`; (2) `seed_native_identity(role="project_admin")` para el caller.
  Reutiliza piezas existentes — no reinventa. Escribe fila en `audit_log` tras éxito.

#### Acceptance Criteria
- [ ] **AC-07** [JR-F693.1]: invocar la provisión con dev_token válido sobre un
  `target_project_id` inexistente crea la fila en `public.projects` (UPSERT) y la membresía
  del caller como `project_admin` en `public.project_members`, en una sola transacción.
- [ ] **AC-08** [JR-F693.4]: la provisión valida el dev_token (fail-fast, reutiliza
  `require_dev_token`) **antes** de cualquier escritura; un token ausente/ inválido deja
  Postgres sin tocar (cero filas creadas) y devuelve envelope `UNAUTHENTICATED`.
- [ ] **AC-09** [JR-F693.4]: tras una provisión exitosa existe una fila en `audit_log`
  que registra la creación de tenant+membresía con el `developer_id` y `project_id`, sin
  exponer el token ni credenciales de la BD (`SPECBOX_NATIVE_DSN` nunca serializado).
- [ ] **AC-10** [JR-F693.1]: re-invocar la provisión sobre un proyecto ya provisionado por
  el mismo caller es un no-op idempotente (tenant UPSERT, membresía ya admin → sin cambios)
  y NO degrada el rol del caller de `project_admin` a `member`.

### UC-821: Integración con el flujo batch — auto-provisión antes del gate de membresía
- **Actor**: Sistema
- **Horas**: 5h
- **Estado**: backlog
- **Contexto**: Materializa GAP 1 en el contexto del transporte por lotes de v6.9.2. Cuando
  el caller migra freeform→native de cero por lotes, `start_migration_session` (o
  `switch_project_backend` con `batch_session_id`) auto-provisiona (UC-820) cuando el caller
  es quien crea el proyecto, de modo que el gate de `authenticate_and_authorize_cached` ya pase.
  La re-validación de membresía en `ingest_atomic` (commit) también pasa porque la membresía
  ya existe.

#### Acceptance Criteria
- [ ] **AC-11** [JR-F693.1]: `start_migration_session` con dev_token válido sobre un
  `target_project_id` inexistente, con flag/condición de "proyecto de cero", auto-provisiona
  (UC-820) y devuelve `status:'open'` en vez del envelope de bloqueo por membresía.
- [ ] **AC-12** [JR-F693.1]: tras la auto-provisión en `start`, el `commit_migration_session`
  pasa la re-validación de membresía de `ingest_atomic` y completa la ingesta (no vuelve a
  bloquear por membresía a mitad del flujo).
- [ ] **AC-13** [JR-F693.4]: el dev_token se valida una sola vez al `start` (la auto-provisión
  reutiliza la identidad cacheada); la auto-provisión escribe solo en el tenant target y nunca
  añade al caller a un proyecto que no está creando.

### UC-822: E2E provisión + migración de proyecto nuevo a native desde cero
- **Actor**: Sistema
- **Horas**: 7h
- **Estado**: backlog
- **Contexto**: El test que faltaba (por eso el gap pasó v6.9.2). Postgres-gated
  (`docker compose -f docker-compose.dev.yml up`). Cruza el flujo completo: BD vacía →
  dev_token válido → auto-provisión → ingesta por lotes de un items.json de estados mixtos →
  verificación de que el proyecto quedó en native con el creador como `project_admin` y el
  `project_id` en formato canónico.

#### Acceptance Criteria
- [ ] **AC-14** [JR-F693.1]: el E2E parte de `public.projects` SIN la fila del target, ejecuta
  el flujo de provisión+migración de cero, y al final `public.projects` contiene exactamente
  una fila con `project_id` == el canónico esperado (`owner/repo`).
- [ ] **AC-15** [JR-F693.3]: al final del E2E, `public.project_members` contiene al creador
  con `role='project_admin'` para ese `project_id`.
- [ ] **AC-16** [JR-F693.1]: al final del E2E, las US/UC/AC ingestadas en Postgres coinciden
  1:1 con el source (conteos y estados done/backlog preservados verbatim, sin degradar a backlog).
- [ ] **AC-17** [JR-F693.2]: el E2E verifica que `display_slug(project_id)` del proyecto creado
  es el slug URL-safe esperado, demostrando que el contrato D1 es consistente end-to-end.

### UC-823: Documentar el cambio coordinado requerido en el panel
- **Actor**: Sistema
- **Horas**: 3h
- **Estado**: backlog
- **Contexto**: GAP 2 puede requerir cambio en el repo del panel (`specbox_cloud`). Se
  documenta aquí como parte del plan; la implementación del panel se hace en su propio repo.
  Doc de decisión + entrada de cambio cross-repo: relajar la validación INSERT de
  `apps/api/src/routes/projects.ts` para aceptar `owner/repo` cuando el backend es native, y
  derivar el display slug para sus rutas usando el contrato D1.

#### Acceptance Criteria
- [ ] **AC-18** [JR-F693.2]: existe `doc/decisions/native_project_id_contract.md` que declara
  D1 (formato canónico, display slug, punto único de normalización) y D2 (autoridad de
  provisión, excepción de bootstrap) como decisiones canónicas, con file:line del código actual.
- [ ] **AC-19** [JR-F693.2]: el doc lista el cambio concreto requerido en `specbox_cloud`
  (archivo `apps/api/src/routes/projects.ts` líneas 140/173: relajar patrón para native +
  derivar display slug), con el contrato de la función compartida de normalización.
- [ ] **AC-20** [JE-F693.2]: D1 y D2 quedan registradas como decisiones canónicas del engine
  (vía `record_canonical_confirmation` / sección 6 de `app_spec.md`) para que engine y panel
  tengan una sola fuente de verdad consultable.

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medición |
|-----|----------|----------|
| Seguridad | La provisión no relaja `deny_anon` ni expone `service_role`; DSN nunca serializado | Revisión + test de que el envelope/return no contiene token ni DSN |
| Atomicidad | Tenant+membresía se crean en una transacción; fallo posterior no deja medio-provisión | Test de rollback (AC-08) |
| Idempotencia | Re-provisión es no-op; no degrada rol ni duplica filas | AC-05, AC-10 |
| Compatibilidad | 100% backwards-compatible: path no-batch y proyectos ya provisionados intactos | Suite native sin regresión |

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Auto-provisión añade al caller a un proyecto que no creó | Baja | Alto | AC-13: solo auto-provisiona cuando el target no existe (de cero); proyecto existente → gate normal |
| Degradar rol de admin existente en re-provisión | Media | Medio | AC-10: UPSERT que no degrada `project_admin`→`member` |
| Cambio del panel desincronizado del engine | Media | Alto | UC-823: contrato de normalización compartido documentado; panel consume el mismo helper |
| Romper la atomicidad del batch de v6.9.2 | Baja | Alto | Provisión ocurre en `start` (antes), no toca `ingest_atomic`; suite batch sin regresión |

## Stack Técnico (estimado)

- **Lenguaje**: Python (FastMCP), asyncpg sobre Postgres/Supabase.
- **Módulos tocados**: `server/coordination/project_id.py` (nuevo), `server/coordination/identity.py`
  (`add_project_member` role ya existe; validación), `server/migration/native_handling.py`
  (`seed_native_identity` role), `server/tools/migration.py` (provisión + integración batch),
  `server/coordination/audit.py` (fila de provisión).
- **Tests**: `tests/test_native_provision.py` (nuevo) + ampliación `tests/test_native_batch_ingestion.py`.
- **Docs**: `doc/decisions/native_project_id_contract.md` (nuevo).

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)
- [ ] **AC-01..03** (UC-818): helper canónico de normalización.
- [ ] **AC-04..06** (UC-819): role parametrizado, creador como project_admin.
- [ ] **AC-07..10** (UC-820): provisión server-side, fail-fast, audit, idempotencia.
- [ ] **AC-11..13** (UC-821): integración batch, auto-provisión antes del gate.
- [ ] **AC-14..17** (UC-822): E2E provisión+migración de cero.
- [ ] **AC-18..20** (UC-823): documentación + decisiones canónicas registradas.

### Técnicos (no validados por AG-09)
- [ ] Proyecto compila / importa sin errores; suite native verde (sin regresión).
- [ ] Tests Postgres-gated pasan con `docker compose -f docker-compose.dev.yml up`.

---
**Prioridad**: high
**Complejidad**: Media
*Generado: 2026-06-03*
