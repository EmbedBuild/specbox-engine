# PRD: [US-ORPHAN-PROVISION] El tenant huérfano de `setup_board` desactiva la auto-provisión de v6.9.3

> Origen: FreeForm board `ff-ed0c02f4565a` | discovery `orphan_tenant_provision`
> Generado: 2026-06-03
> Tipo: PRD Técnico (refactor de robustez de infraestructura native)
> Hallazgo origen: `HALLAZGO-v6.9.4-setup-board-tenant-huerfano.md`
> Discovery: `doc/discovery/orphan_tenant_provision/icp_jtbd.md` (READY_FOR_PRD)

## Resumen Ejecutivo

v6.9.3 "Tenant Provisioning" implementó `provision_native_project` (creación atómica
de tenant + membresía) e integró `_maybe_auto_provision` en `start_migration_session`.
La lógica es correcta. **Pero la migración real de un proyecto nuevo freeform→native
desde cero sigue fallando con `FORBIDDEN`.**

La causa es un bug de orden/atomicidad: `setup_board`
([`server/backends/native_backend.py:342-354`](../../server/backends/native_backend.py#L342))
hace `INSERT INTO projects ... ON CONFLICT` **sin crear membresía**, fuera de la
provisión atómica. Se dispara en cada `set_auth_token` native
([`spec_driven.py:276`](../../server/tools/spec_driven.py#L276)), en `import_spec`
([`spec_driven.py:460`](../../server/tools/spec_driven.py#L460)), y en las migraciones
legacy ([`migration.py:337,630,1009`](../../server/tools/migration.py#L337)). Cualquiera
de esas operaciones, ejecutada antes de la migración, deja un **tenant huérfano**
(fila en `public.projects` con CERO miembros).

Entonces `_maybe_auto_provision`
([`migration.py:1462-1467`](../../server/tools/migration.py#L1462)) ve `exists=True` →
`return False` (cree que es un tenant legítimo preexistente) → el gate de membresía
corre → no hay miembro → **FORBIDDEN**. El ecosistema se sabotea a sí mismo.

**Verificado por SQL directo** (dogfooding 2026-06-03): tras `start_migration_session`
sobre BD verificada vacía → `projects`=1 fila (sin membresía), `project_members`=0,
`audit_log`=0. Firma de `setup_board`, no de `provision_native_project`.

Esta US cierra el bug con el **Enfoque Combinado (3)** decidido en el discovery:
defensa en profundidad de dos capas independientes (cerrar la puerta + robustez ante
estado sucio), más un E2E que reproduce el **camino sucio real**.

## Alcance

### Incluye
- **FIX A**: que la creación de tenant native pase siempre por la provisión atómica
  (tenant + membresía juntos). `setup_board` native nunca debe dejar un proyecto con
  cero miembros cuando dispone de identidad (dev_token).
- **FIX B**: que `_maybe_auto_provision` distinga "tenant huérfano" (0 miembros →
  adopta) de "tenant real" (≥1 miembro → `FORBIDDEN`, AC-13 intacto).
- **E2E camino sucio**: un test que crea la fila huérfana **primero** (vía `setup_board`
  o equivalente) y luego verifica que `start_migration_session` se recupera sin
  `FORBIDDEN`, con el creador como `project_admin` y los datos preservados.
- Adopción del estándar transversal: los E2E de migración parten de **estados sucios
  realistas**, no solo de BD/fixtures vírgenes.

### No incluye
- Cambios en el contrato de `project_id` (`native_project_id_contract`, D1 v6.9.3) — se
  reutiliza tal cual.
- Cambios en el flujo de identidad / OAuth GitHub (la creación del `developer` al login
  ya está resuelta en v6.3.0; el bug es de **membresía al proyecto**, no de identidad).
- Cambios en el panel `specbox_cloud` (el panel sigue siendo editor de OTROS miembros;
  esta US solo toca la auto-provisión de bootstrap del engine).
- Migración de tenants huérfanos existentes en BD vía script de mantenimiento — la
  adopción ocurre on-demand en el primer `start_migration_session` (convergencia
  natural).

---

## Objetivos

1. **Establecer el invariante**: un tenant native nunca debe existir sin al menos un
   miembro; si por estado sucio legacy lo está, la auto-provisión lo adopta.
2. **Romper la cadena de 4 hallazgos**: el E2E debe partir de estado sucio realista,
   de modo que "pasa en test" implique "funciona en producción".
3. **Preservar la seguridad real** (D2 / AC-13): nunca auto-unir a un proyecto que ya
   tiene dueños (≥1 miembro).

---

## Estado Actual vs Propuesto

### ACTUAL (`_maybe_auto_provision`, migration.py:1462-1467)
```python
async with pool.acquire() as conn:
    exists = bool(
        await conn.fetchval("SELECT 1 FROM projects WHERE project_id = $1", canonical)
    )
if exists:
    return False        # ← un huérfano (0 miembros) cae aquí → FORBIDDEN
await provision_native_project(...)
```

### ACTUAL (`setup_board`, native_backend.py:342-354)
```python
await conn.execute(
    "INSERT INTO projects (...) VALUES (...) ON CONFLICT (project_id) DO UPDATE ..."
)   # ← crea tenant SIN membresía → deja huérfano
```

### PROPUESTO (FIX B — robustez)
```python
async with pool.acquire() as conn:
    row = await conn.fetchrow(
        "SELECT 1 AS exists, "
        "(SELECT count(*) FROM project_members WHERE project_id = $1) AS members "
        "FROM projects WHERE project_id = $1", canonical
    )
exists = row is not None
has_members = bool(row and row["members"] > 0)
if exists and has_members:
    return False        # tenant real con dueños → AC-13 protege (FORBIDDEN si no miembro)
# proyecto no existe O existe huérfano (0 miembros) → provisiona/adopta
await provision_native_project(...)   # idempotente: completa el huérfano
```

### PROPUESTO (FIX A — cerrar la puerta)
`setup_board` para native, cuando dispone de `dev_token` (identidad resoluble), delega
en `provision_native_project` en lugar del INSERT desnudo, de modo que el tenant nace
con su membresía. Si no hay identidad disponible (caso defensivo improbable en native),
no crea una fila huérfana silenciosamente.

---

## A Eliminar
- [ ] El `INSERT INTO projects` desnudo (sin membresía) de `setup_board` para el caso
      native con identidad disponible — reemplazado por delegación a la provisión atómica.

## A Mantener
- `provision_native_project` (atómico, idempotente, no degrada admin) — se reutiliza tal cual.
- El `_clear_auth_cache` tras provisionar en `_maybe_auto_provision`.
- El gate de membresía y el guard AC-13 para tenants con ≥1 miembro.
- El contrato `project_id` canónico (D1).

---

## User Story

**ID**: US-ORPHAN-PROVISION
**Nombre**: El tenant huérfano de `setup_board` desactiva la auto-provisión
**Actor**: Sistema (engine) / Owner-operator (ICP-1, dogfooding)
**Horas estimadas**: 16h
**Pantallas**: ninguna (infra backend)

> Como owner-operator que sube un proyecto nuevo a SpecBox Cloud (native) desde cero
> [JR-FOTP.1], quiero que la provisión de tenant + membresía sea atómica y robusta ante
> estado sucio [JR-FOTP.2], para no recibir un FORBIDDEN inexplicable siendo yo el
> creador con identidad válida [JE-FOTP.1].

---

## Use Cases

### UC-824: `setup_board` native nunca deja un tenant sin miembro (FIX A)
- **Actor**: Sistema
- **Horas**: 5h
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-01**: Cuando `setup_board` se invoca sobre el `NativeBackend` con un `dev_token`
  válido y el proyecto no existe, la fila de `public.projects` se crea **junto con** una
  fila de `public.project_members` (el caller como `project_admin`) en la misma transacción
  — verificable: tras `setup_board`, `SELECT count(*) FROM project_members WHERE project_id=$1`
  devuelve ≥1.
- [ ] **AC-02**: Cuando `setup_board` se invoca sobre un proyecto native que ya existe con
  ≥1 miembro, es idempotente y NO degrada el rol del admin existente — verificable:
  el `role` del miembro preexistente sigue siendo `project_admin` tras la llamada.
- [ ] **AC-03**: `setup_board` para native ya no ejecuta el `INSERT INTO projects` desnudo
  (sin membresía) en ninguna ruta donde haya identidad disponible — verificable por
  inspección de código + un test que afirma que ninguna ruta native deja `project_members`=0
  tras `setup_board` con dev_token.

### UC-825: `_maybe_auto_provision` adopta el tenant huérfano (FIX B)
- **Actor**: Sistema
- **Horas**: 4h
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-04**: Cuando `_maybe_auto_provision` corre y el proyecto existe pero tiene CERO
  miembros, provisiona (adopta) el tenant creando la membresía del caller como
  `project_admin` y devuelve `True` — verificable: con una fila huérfana presente,
  `_maybe_auto_provision` deja `project_members`=1 (el caller) y una fila en `audit_log`.
- [ ] **AC-05**: Cuando `_maybe_auto_provision` corre y el proyecto existe con ≥1 miembro
  del que el caller NO forma parte, devuelve `False` (no adopta) y el gate posterior emite
  `FORBIDDEN` — verificable: con un tenant ajeno (1 miembro = otro developer), un caller
  distinto recibe `FORBIDDEN`, sin alterar la membresía existente (AC-13 intacto).
- [ ] **AC-06**: Tras adoptar un huérfano, `_maybe_auto_provision` limpia la cache de auth
  (`_clear_auth_cache`) de modo que el gate de membresía relee el edge fresco de Postgres —
  verificable: la migración procede sin FORBIDDEN en la misma llamada, sin esperar al TTL.

### UC-826: E2E del camino sucio real — huérfano primero, recuperación después
- **Actor**: Sistema
- **Horas**: 5h
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-07**: Un test Postgres-gated crea la fila huérfana **primero** (llamando
  `setup_board` con el `INSERT` desnudo o insertando directamente una fila `projects` sin
  membresía), y LUEGO `start_migration_session` se recupera **sin** `FORBIDDEN` — verificable:
  el test afirma que el envelope de `start_migration_session` no es `FORBIDDEN` y la sesión
  de migración avanza.
- [ ] **AC-08**: Tras la migración del camino sucio, Postgres queda con exactamente 1 fila
  en `projects` (`project_id` canónico `owner/repo`), el creador como `project_admin`, y los
  US/UC/AC ingeridos con sus estados preservados 1:1 (done/backlog) — verificable: el test
  cuenta filas y compara estados contra el source.
- [ ] **AC-09**: El E2E ejerce el flujo completo de transporte por lotes (≥64 KB → batch
  ingest) sobre el estado sucio, no solo el camino no-batch — verificable: el test usa un
  source que cruza el `BATCH_TRANSPORT_THRESHOLD_BYTES` y confirma la ingesta atómica.

### UC-827: No-regresión de la suite native + estándar de estados sucios
- **Actor**: Sistema
- **Horas**: 2h
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-10**: La suite native completa (`tests/test_native_*.py`) sigue verde tras los
  cambios — verificable: `pytest tests/test_native_*.py` = 0 failed (con
  `docker compose -f docker-compose.dev.yml up`).
- [ ] **AC-11**: El E2E de provisión de v6.9.3 (UC-822,
  `test_e2e_provision_then_migrate_from_scratch`) sigue verde — verificable: el camino limpio
  no regresiona.
- [ ] **AC-12**: Queda documentado (en CLAUDE.md y/o en el plan) el estándar transversal:
  los E2E de migración deben partir de estados sucios realistas — verificable: existe la
  nota en la documentación de la versión.

---

## Interacciones UI

No aplica — feature de infraestructura backend sin UI.

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medición |
|-----|----------|----------|
| Atomicidad | Tenant + membresía se crean en una sola transacción Postgres | Test: fallo a mitad → rollback total (0 filas) |
| Seguridad (Frontier 2) | La provisión valida dev_token, escribe solo en el tenant, registra en audit_log, no relaja deny_anon/service_role, no serializa el DSN | Test de aislamiento + revisión |
| Seguridad (AC-13) | Nunca auto-unir a un tenant con ≥1 miembro | Test AC-05 (tenant ajeno → FORBIDDEN) |
| Idempotencia | Re-provisión / re-setup_board del mismo caller es no-op (no degrada admin) | Test AC-02 |
| Convergencia | Cualquier estado sucio (0 miembros) se recupera a limpio en el primer start_migration_session | Test AC-07 |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| FIX A rompe rutas non-native de `setup_board` (trello/plane/freeform) | Media | Alto | El cambio solo aplica a la rama native de `setup_board`; los demás backends no se tocan. Test de no-regresión por backend. |
| `setup_board` native sin dev_token disponible (sesión read-only) crea huérfano igual | Baja | Medio | Defensivo: si no hay identidad, no crear fila huérfana; FIX B la adopta si aparece. AC-03 cubre el caso con identidad. |
| Adoptar un huérfano con datos de otro flujo escala privilegios | Baja | Alto | Razonado en discovery: un huérfano (0 miembros) no tiene dueño a quien robar; el primer migrador legítimo es su dueño natural (coherente con D2). |
| El E2E sucio depende de Postgres real (gated) y no corre en CI sin docker | Media | Bajo | Marcar Postgres-gated como los tests native existentes; documentar `docker compose up` como prerequisito. |

---

## Stack Técnico (estimado)

- **Modelo**: Existente — `NativeBackend`, `provision_native_project`, `_maybe_auto_provision`.
- **Archivos principales**:
  - `server/backends/native_backend.py` (`setup_board` — FIX A)
  - `server/tools/migration.py` (`_maybe_auto_provision` — FIX B)
  - `server/migration/native_handling.py` (`provision_native_project` — reutilizado)
  - `tests/test_native_provision.py` o nuevo `tests/test_native_orphan_provision.py` (E2E sucio)
- **State**: Postgres (`public.projects`, `public.project_members`, `public.audit_log`)

## Dependencias
- v6.9.3 (`provision_native_project`, contrato `project_id`) — base reutilizada.
- v6.9.2 (batch ingest) — el E2E ejerce el transporte por lotes.
- Postgres dev local (`docker-compose.dev.yml`) para los tests gated.

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)
- [ ] **AC-01**: `setup_board` native + dev_token crea projects + project_members atómicamente (≥1 miembro).
- [ ] **AC-02**: `setup_board` native sobre proyecto con miembro es idempotente, no degrada admin.
- [ ] **AC-03**: `setup_board` native no ejecuta INSERT desnudo donde hay identidad; ninguna ruta deja 0 miembros.
- [ ] **AC-04**: `_maybe_auto_provision` adopta huérfano (0 miembros) → crea membresía + audit, devuelve True.
- [ ] **AC-05**: `_maybe_auto_provision` con tenant ajeno (≥1 miembro) → False → FORBIDDEN, membresía intacta (AC-13).
- [ ] **AC-06**: Tras adoptar, limpia auth cache; migración procede sin FORBIDDEN en la misma llamada.
- [ ] **AC-07**: E2E sucio: huérfano primero, start_migration_session se recupera sin FORBIDDEN.
- [ ] **AC-08**: Tras migración sucia: 1 projects (canónico), creador project_admin, US/UC/AC con estados preservados 1:1.
- [ ] **AC-09**: E2E ejerce el transporte por lotes (≥64 KB) sobre estado sucio.
- [ ] **AC-10**: Suite native completa verde tras los cambios.
- [ ] **AC-11**: E2E de provisión limpio de v6.9.3 (UC-822) sigue verde.
- [ ] **AC-12**: Documentado el estándar de estados sucios realistas en E2E de migración.

### Técnicos (no validados por AG-09)
- [ ] Proyecto compila / importa sin errores.
- [ ] Tests con cobertura sobre las ramas nuevas de `_maybe_auto_provision` y `setup_board`.

---
**Prioridad**: high
**Complejidad**: Media
*Generado: 2026-06-03*
