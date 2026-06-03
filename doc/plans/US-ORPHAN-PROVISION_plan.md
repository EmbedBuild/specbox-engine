# Plan: [US-ORPHAN-PROVISION] El tenant huérfano de `setup_board` desactiva la auto-provisión

> Generado: 2026-06-03
> Origen: FreeForm board `ff-ed0c02f4565a` | US-ORPHAN-PROVISION
> PRD: [doc/prd/US-ORPHAN-PROVISION_prd.md](../prd/US-ORPHAN-PROVISION_prd.md)
> Discovery: [doc/discovery/orphan_tenant_provision/icp_jtbd.md](../discovery/orphan_tenant_provision/icp_jtbd.md)
> Estado: Pendiente
> **Tipo**: backend-only (Python/FastMCP). Sin UI → VEG y Stitch N/A.

---

## Resumen

Cerrar el bug v6.9.4 con defensa en profundidad: (A) que la creación de tenant
native pase siempre por la provisión atómica, y (B) que la auto-provisión adopte
tenants huérfanos (0 miembros), respetando AC-13 para tenants con dueños. Más un
E2E que reproduce el camino sucio real.

## Análisis UI (Fase 0)

**N/A** — feature de infraestructura backend. Sin pantallas, sin componentes UI,
sin VEG, sin Stitch. `stitch_designs: N/A`.

## Stack (heredado de app_spec.md)

- Python (FastMCP) >=3.12, gestor `uv`, tests `pytest` en `tests/`.
- Postgres dev local vía `docker compose -f docker-compose.dev.yml up` (puerto 55432, db `specbox_native`).
- Tests native son **Postgres-gated** (skip sin la BD levantada).

---

## Hechos verificados del código (base del plan)

| Símbolo | Ubicación | Estado actual |
|---------|-----------|---------------|
| `NativeBackend.setup_board` | [native_backend.py:336-361](../../server/backends/native_backend.py#L336) | `INSERT INTO projects ... ON CONFLICT` **sin** membresía. Tiene `self._dev_token` y `self.project_id` y `self._pool()`. |
| `NativeBackend.__init__` | [native_backend.py:205-226](../../server/backends/native_backend.py#L205) | Recibe `project_id` + `dev_token` (ambos obligatorios). |
| `provision_native_project` | [native_handling.py:238-330](../../server/migration/native_handling.py#L238) | Atómico (projects + members + audit en 1 transacción). Idempotente. `*, project_id, developer_id, display_name=None, role="project_admin"`. |
| `_maybe_auto_provision` | [migration.py:1436-1481](../../server/tools/migration.py#L1436) | `exists = SELECT 1 FROM projects` → `if exists: return False`. **No mira miembros.** |
| `resolve_developer` | [identity.py:329](../../server/coordination/identity.py#L329) | token → `Developer(developer_id, display_name)` o `UnauthenticatedError`. Acepta `Connection | Pool`. |
| `_clear_auth_cache` | importado en migration.py:1478 | Ya se usa tras provisionar. |

**Sin riesgo de import circular**: `native_handling` NO importa `native_backend`,
así que FIX A puede hacer `from ..migration.native_handling import provision_native_project`
dentro de `setup_board` (import diferido, como ya hace `_maybe_auto_provision`).

---

## Fases de Implementación

> Una fase por UC. Orden: FIX B primero (es el que recupera el estado sucio y
> desbloquea el dogfooding inmediato), luego FIX A (cierra la puerta), luego el
> E2E que ejercita ambos, luego no-regresión + docs.

### Fase 1 — UC-825: `_maybe_auto_provision` adopta el huérfano (FIX B)

**Archivo**: `server/tools/migration.py` (`_maybe_auto_provision`, ~líneas 1462-1475).

- [ ] Cambiar la consulta de existencia por una que también cuente miembros:
  ```python
  async with pool.acquire() as conn:
      row = await conn.fetchrow(
          """
          SELECT
              EXISTS(SELECT 1 FROM projects WHERE project_id = $1) AS exists,
              (SELECT count(*) FROM project_members WHERE project_id = $1) AS members
          """,
          canonical,
      )
  exists = bool(row["exists"])
  has_members = (row["members"] or 0) > 0
  if exists and has_members:
      return False            # tenant real con dueños → AC-13 (gate decide FORBIDDEN)
  # no existe O existe huérfano (0 miembros) → provisiona/adopta
  ```
- [ ] La rama de provisión existente (`await provision_native_project(...)` +
  `_clear_auth_cache`) queda **igual** — `provision_native_project` es idempotente
  y completa el huérfano (UPSERT projects no-op + INSERT membership + audit).
- [ ] Actualizar el docstring de `_maybe_auto_provision`: documentar el tercer
  estado (huérfano → adopta) y la garantía AC-13 (≥1 miembro → no adopta).
- **Cubre**: AC-04, AC-05, AC-06.
- **Tiempo estimado**: 45 min.

### Fase 2 — UC-824: `setup_board` native nunca deja tenant sin miembro (FIX A)

**Archivo**: `server/backends/native_backend.py` (`setup_board`, líneas 336-361).

- [ ] Reemplazar el `INSERT INTO projects` desnudo por delegación a la provisión
  atómica cuando hay identidad (siempre la hay en native: `self._dev_token`):
  ```python
  async def setup_board(self, name: str) -> BoardConfig:
      board_id = self.project_id
      board_url = f"native://{board_id}"
      pool = await self._pool()
      # FIX A (UC-824): resolve identity and provision atomically so the
      # tenant is never created without a member. provision_native_project
      # is idempotent (UPSERT projects, UPSERT membership without degrading
      # an existing admin) — safe to call on every setup_board.
      from ..coordination.identity import resolve_developer
      from ..migration.native_handling import provision_native_project
      developer = await resolve_developer(pool, self._dev_token)  # UNAUTHENTICATED if bad
      await provision_native_project(
          pool,
          project_id=board_id,
          developer_id=developer.developer_id,
          display_name=developer.display_name,
          role="project_admin",
      )
      return BoardConfig(board_id=board_id, board_url=board_url,
                         states=dict(NATIVE_STATES), labels=dict(_DEFAULT_LABELS),
                         custom_fields={})
  ```
- [ ] **Nota sobre `name`**: el `INSERT` desnudo guardaba `name` en `projects.name`;
  `provision_native_project` usa `project_id` como `name` (`VALUES ($1, $1, ...)`).
  Verificar si algún consumidor depende de `projects.name != project_id`. Si sí,
  extender `provision_native_project` con un `name` opcional (default = project_id)
  para preservar el comportamiento. **Decisión**: revisar `get_board_name` y usos;
  si nadie depende del name custom, dejar `name=project_id` (coherente con
  `provision_native_project` y con el contrato D1). Documentar la decisión.
- [ ] Considerar el caso defensivo: si `resolve_developer` lanza
  `UnauthenticatedError` (token inválido), `setup_board` propaga el error en vez
  de crear un huérfano. Hoy `setup_board` se llama tras `validate_auth` en
  `set_auth_token` ([spec_driven.py:274-276](../../server/tools/spec_driven.py#L274)),
  así que el token ya está validado — pero propagar es lo correcto (no crear
  huérfano silencioso).
- **Cubre**: AC-01, AC-02, AC-03.
- **Tiempo estimado**: 1.5h.

### Fase 3 — UC-826: E2E del camino sucio real

**Archivo**: `tests/test_native_orphan_provision.py` (nuevo) o extensión de
`tests/test_native_provision.py`. Postgres-gated (mismo patrón que la suite native).

- [ ] **AC-07** — Test `test_e2e_dirty_path_orphan_then_migrate`:
  1. Sobre BD limpia, crear la fila huérfana **primero** simulando el bug
     pre-fix: insertar directamente una fila en `projects` SIN membresía
     (`INSERT INTO projects (project_id, name, backend_type, board_url, meta)
     VALUES (...)`), o llamar a una versión que reproduzca el `INSERT` desnudo.
     Verificar precondición: `project_members` = 0 para ese project_id.
  2. Llamar `start_migration_session(target=<canonical>, dev_token=<válido>)`.
  3. Afirmar que el envelope **NO** es `FORBIDDEN` (es `accepted` / `status:'open'`).
- [ ] **AC-08** — Tras completar la migración (append + commit del batch):
  - `SELECT count(*) FROM projects WHERE project_id=$1` = 1, `project_id` canónico.
  - El creador es `project_admin` en `project_members`.
  - US/UC/AC ingeridos con estados preservados 1:1 (comparar done/backlog contra source).
- [ ] **AC-09** — Usar un `source_content` que cruce `BATCH_TRANSPORT_THRESHOLD_BYTES`
  (≥64 KB) para forzar el camino de batch ingest (`start → append × N → commit`),
  no solo el no-batch. Afirmar ingesta atómica.
- [ ] Reutilizar fixtures/helpers de `test_native_provision.py` (conexión, dev_token
  de prueba, limpieza de tablas entre tests).
- **Cubre**: AC-07, AC-08, AC-09.
- **Tiempo estimado**: 2.5h.

### Fase 4 — UC-827: No-regresión + estándar de estados sucios

- [ ] **AC-10** — Correr `pytest tests/test_native_*.py` con docker dev arriba →
  0 failed. Ajustar cualquier test que asumiera el comportamiento viejo de
  `setup_board` (huérfano) — esos asserts ahora deben esperar membresía.
- [ ] **AC-11** — Verificar que `test_e2e_provision_then_migrate_from_scratch`
  (UC-822, camino limpio) sigue verde sin cambios.
- [ ] **AC-12** — Documentar en CLAUDE.md (sección nueva de v6.9.4) y en este plan
  el estándar transversal: *los E2E de migración parten de estados sucios
  realistas, no solo de BD/fixtures vírgenes*. Añadir nota explícita en el
  docstring del nuevo test.
- **Cubre**: AC-10, AC-11, AC-12.
- **Tiempo estimado**: 1h (+ tiempo de corrida de la suite).

---

## Orden de implementación y dependencias

```
Fase 1 (FIX B) ──┐
                 ├──> Fase 3 (E2E sucio, ejercita A+B) ──> Fase 4 (no-regresión + docs)
Fase 2 (FIX A) ──┘
```

Fases 1 y 2 son independientes (archivos distintos) pero ambas deben estar antes
de la Fase 3. La Fase 4 cierra.

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|----------|---------------|----------------------|-------|
| Enfoque de fix | Combinado (A+B) | Solo B (robustez) o solo A (cerrar puerta) | Defensa en profundidad: A elimina la causa, B recupera estados sucios legacy ya en BD. Confirmado con usuario en discovery. |
| Condición de adopción en FIX B | `exists AND has_members` | Comparar `created_at` o flags | Contar miembros es el invariante semántico exacto: 0 miembros = huérfano. Simple, sin estado extra. |
| `setup_board` name | `name = project_id` (vía provision) | Extender provision con `name` opcional | Coherente con D1 y con `provision_native_project`. Solo se extiende si algún consumidor depende del name custom (a verificar en Fase 2). |
| Reproducción del huérfano en el E2E | INSERT directo sin membresía | Llamar al `setup_board` pre-fix | El INSERT directo es deterministra y no depende de revertir FIX A; reproduce exactamente el estado sucio (projects sí, members no). |

---

## Archivos a Crear/Modificar

```
server/
├── tools/migration.py                       # MODIFICAR — _maybe_auto_provision (FIX B)
└── backends/native_backend.py               # MODIFICAR — setup_board (FIX A)

server/migration/native_handling.py          # (posible) extender provision con name opcional — solo si Fase 2 lo requiere

tests/
└── test_native_orphan_provision.py          # CREAR — E2E camino sucio (AC-07..09) + unit de FIX A/B

CLAUDE.md                                     # MODIFICAR — sección v6.9.4 + estándar estados sucios (AC-12)
```

---

## Comandos Finales

```bash
docker compose -f docker-compose.dev.yml up -d   # Postgres dev (gated tests)
uv run pytest tests/test_native_orphan_provision.py -v
uv run pytest tests/test_native_*.py             # no-regresión (AC-10, AC-11)
uv run ruff check server/ tests/                 # lint
```

---

## Mapeo a Acceptance Criteria

| AC | Fase | UC | Verificación |
|----|------|-----|--------------|
| AC-01 | 2 | UC-824 | setup_board native → project_members≥1 |
| AC-02 | 2 | UC-824 | idempotente, no degrada admin |
| AC-03 | 2 | UC-824 | sin INSERT desnudo; ninguna ruta deja 0 miembros |
| AC-04 | 1 | UC-825 | adopta huérfano → members=1 + audit, True |
| AC-05 | 1 | UC-825 | tenant ajeno (≥1 miembro) → False → FORBIDDEN, intacto |
| AC-06 | 1 | UC-825 | limpia auth cache; sin FORBIDDEN en la misma llamada |
| AC-07 | 3 | UC-826 | huérfano primero → start_migration_session sin FORBIDDEN |
| AC-08 | 3 | UC-826 | 1 projects canónico, creador admin, estados 1:1 |
| AC-09 | 3 | UC-826 | transporte por lotes (≥64 KB) sobre estado sucio |
| AC-10 | 4 | UC-827 | suite native verde |
| AC-11 | 4 | UC-827 | E2E limpio v6.9.3 verde |
| AC-12 | 4 | UC-827 | estándar de estados sucios documentado |

---

## Referencias

- PRD: [doc/prd/US-ORPHAN-PROVISION_prd.md](../prd/US-ORPHAN-PROVISION_prd.md)
- Discovery: [doc/discovery/orphan_tenant_provision/icp_jtbd.md](../discovery/orphan_tenant_provision/icp_jtbd.md)
- Hallazgo: [HALLAZGO-v6.9.4-setup-board-tenant-huerfano.md](../../HALLAZGO-v6.9.4-setup-board-tenant-huerfano.md)
- Decisiones canónicas D1/D2 (v6.9.3): `doc/app/app_spec.md` §6
- `provision_native_project`: `server/migration/native_handling.py`
