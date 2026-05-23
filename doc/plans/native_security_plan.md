# Plan: [US-NATIVE-SECURITY] Blindar el Native Backend contra mutaciones de identidades revocadas

> Generado: 2026-05-23
> Origen: FreeForm local (board `ff-ed0c02f4565a`) | US-NATIVE-SECURITY
> PRD: doc/prd/native_security_prd.md
> Estado: Pendiente
> Stitch designs: N/A (feature backend-only, sin UI)
> VEG: DISABLED (heredado de app_spec.md — engine sin UI de producto)

---

## Resumen

Cerrar el hueco de seguridad donde las 9 mutaciones del `NativeBackend` no re-validan identidad por call. Se rediseña el modelo de identidad (developers + github_identities N:1 + mcp_tokens revocables), se introduce un gate con cache TTL 30s en cada mutación, y un audit log para las operaciones destructivas. Sin compatibilidad hacia atrás (nada en producción Native salvo el mantenedor). RLS Postgres diferido a v2.

## Análisis UI (Fase 0)

**N/A** — Feature de plataforma sin UI de producto. No hay componentes UI, VEG ni Stitch.

---

## Análisis técnico — puntos de integración verificados

| Punto | Ubicación | Hallazgo relevante para el plan |
|-------|-----------|---------------------------------|
| Migration runner casero | `server/db/migrate.py` | Lee `server/db/migrations/*.sql` por orden lexicográfico. **Las nuevas 0004/0005/0006 entran automáticamente**. La verdad en producción Supabase es el ledger `supabase_migrations.schema_migrations` — habrá que aplicar las migraciones por Supabase MCP (`apply_migration`) en paralelo a colocar los `.sql` en `server/db/migrations/`. Documentado en el plan. |
| `developers` schema actual | `server/db/migrations/0002_developers.sql:19-28` | `developer_id PK`, `token_hash NOT NULL`, `UNIQUE INDEX idx_developers_token_hash`. Para dropear `token_hash` hay que dropear el índice primero. |
| FKs que apuntan a `developers` | `0002_developers.sql:38` y `0003_claims.sql:20,38` | `project_members`, `uc_claims`, `branch_registry` referencian `developers(developer_id) ON DELETE CASCADE`. **Las nuevas tablas `github_identities` y `mcp_tokens` también** las referencian (consistencia). |
| 9 mutadores del NativeBackend | `server/backends/native_backend.py:389,573,779,809,845,907,927,987,1055` | `create_item`, `update_item`, `mark_acceptance_criterion`, `create_acceptance_criteria`, `update_acceptance_criterion`, `delete_acceptance_criterion`, `archive_item`, `add_comment`, `add_attachment`. Cada uno gana una llamada a `_require_membership_cached(self._dev_token)` antes del SQL de escritura. |
| `authenticate_and_authorize` | `server/coordination/identity.py:247` | Patrón ya implementado. UC-502 añade variante `_cached` con dict en memoria. |
| `resolve_developer` | `server/coordination/identity.py:189` | Hoy consulta `developers.token_hash`. UC-504 lo cambia a JOIN con `mcp_tokens WHERE revoked_at IS NULL`. |
| Dispatch native | `server/auth_gateway.py:64-69` | `NativeBackend(project_id=config["project_id"])`. UC-505 añade `dev_token=config["dev_token"]`. |
| `store_native_credentials` | `server/auth_gateway.py:151` | Hoy acepta `dev_token=""` opcional. UC-505 AC-03 lo rechaza vacío. |
| Fixture de conformance | `tests/test_native_backend_conformance.py:85` | Parametrizada sobre 2 factories (Freeform/Native). Para UC-506 AC-03 el factory native debe crear `developer + mcp_token + project_member` antes de instanciar `NativeBackend(project_id, dev_token)`. |
| `tests/_native_db.py` | `tests/_native_db.py` | Helper compartido `DSN + reachable()`. Las pruebas se gatean por `PG_OK`. Mismo patrón para los tests nuevos. |

---

## Fases de Implementación

> Mapeo **1 UC = 1 ciclo /implement**. Orden estricto por dependencias.
> Agentes: AG-03 (backend Python + SQL) en todas las fases; AG-04 (QA) en UC-506.
> Postgres dev (`docker-compose.dev.yml` puerto 55432) DEBE estar arriba antes de UC-501; SPECBOX_NATIVE_DSN exportado.

### Fase 1 — UC-501: Schema rediseñado (3 migraciones limpias) [AG-03]
**Dependencias**: ninguna (cimiento). **Estimado**: 8h.

- [ ] Crear `server/db/migrations/0004_github_identities.sql`: tabla `github_identities` con `github_user_id BIGINT PRIMARY KEY`, `github_login TEXT NOT NULL`, `developer_id TEXT NOT NULL REFERENCES developers(developer_id) ON DELETE CASCADE`, `linked_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Índice `idx_github_identities_developer_id`. Todo con `IF NOT EXISTS` para idempotencia (AC-05).
- [ ] Crear `server/db/migrations/0005_mcp_tokens.sql`: tabla `mcp_tokens` (token_id PK, developer_id FK, github_user_id FK NULL ON DELETE SET NULL, token_hash TEXT NOT NULL UNIQUE, created_at, last_used_at, revoked_at). Índices `idx_mcp_tokens_token_hash UNIQUE` y `idx_mcp_tokens_developer_id`. **En el mismo archivo**: `DROP INDEX IF EXISTS idx_developers_token_hash` + `ALTER TABLE developers DROP COLUMN IF EXISTS token_hash` (AC-03).
- [ ] Crear `server/db/migrations/0006_audit_log.sql`: tabla `audit_log` (id BIGSERIAL PK, developer_id NULL, project_id NOT NULL, operation NOT NULL, target_id NOT NULL, occurred_at TIMESTAMPTZ DEFAULT now()). Índice `idx_audit_log_project_occurred` sobre `(project_id, occurred_at DESC)`.
- [ ] **Aplicar paralelamente al ledger Supabase via MCP** (`mcp__supabase__apply_migration`) — las migraciones quedan byte-for-byte sincronizadas entre `server/db/migrations/` y el ledger remoto.
- [ ] **Fase QA**: `tests/test_native_security_schema.py` — para cada migración, verifica con `\d` o `information_schema` la estructura exacta; ejecuta `apply_migrations()` dos veces seguidas y comprueba 0 errores (AC-05).

**Cubre**: AC-01..05.

### Fase 2 — UC-505: Refactor firma `NativeBackend.__init__` + dispatch [AG-03]
**Dependencias**: UC-501 (schema). **Estimado**: 4h.

- [ ] Modificar `server/backends/native_backend.py:202` `NativeBackend.__init__(project_id: str, dev_token: str)` — ambos obligatorios. Validación: `if not dev_token: raise ValueError("dev_token is required for NativeBackend")`. Guarda `self._project_id` y `self._dev_token` para que UC-502 los use.
- [ ] Modificar `server/auth_gateway.py:64-69` (rama `native`): leer `config["dev_token"]` y pasarlo al constructor: `NativeBackend(project_id=config["project_id"], dev_token=config["dev_token"])`.
- [ ] Modificar `server/auth_gateway.py:151` `store_native_credentials`: si `dev_token=""` o `None` → raise explícito.
- [ ] **Esta fase ROMPE temporalmente** los tests existentes de conformance Native (el factory en `test_native_backend_conformance.py:85` instancia `NativeBackend(project_id)` sin token). Se documenta y se restaura en UC-506 (que actualiza el fixture). Aceptado por orden de dependencias.
- [ ] **Fase QA**: tests parametrizados de la firma — `NativeBackend("p", "")` lanza ValueError; `NativeBackend("p", "t1")` instancia OK con `_project_id=="p"` y `_dev_token=="t1"`. Test de `store_native_credentials` rechazando token vacío.

**Cubre**: AC-19, AC-20, AC-21.

### Fase 3 — UC-504: Limpieza CRUD + resolve_developer lee mcp_tokens [AG-03]
**Dependencias**: UC-501 (schema), UC-505 (refactor firma). **Estimado**: 4h.

- [ ] Eliminar `register_native_developer` de `server/tools/coordination.py` (función + entrada en el `mcp.tool` registry). Verificar con `grep -n 'register_native_developer' server/tools/coordination.py` → 0 líneas.
- [ ] Modificar `server/coordination/identity.py:189` `resolve_developer`: query pasa a `SELECT d.developer_id, d.display_name FROM mcp_tokens t JOIN developers d ON d.developer_id = t.developer_id WHERE t.token_hash = $1 AND t.revoked_at IS NULL`. Si la fila no se encuentra → `UnauthenticatedError` (igual comportamiento que antes).
- [ ] Modificar `register_developer` en `identity.py` (línea ~108): eliminar parámetro `token`. Nueva firma: `async def register_developer(conn, *, developer_id: str, display_name: str) -> Developer`. Solo inserta en `developers` (sin `token_hash`). La emisión de mcp_tokens es responsabilidad del panel (futura función `register_mcp_token(conn, developer_id, ...)` que NO se expone como tool MCP — la añadiré en este UC como helper interno para que UC-506 pueda usarla en fixtures).
- [ ] Añadir helper `register_mcp_token(conn, *, developer_id, token, github_user_id=None) -> str` en `identity.py` (NO expuesto como tool MCP): inserta en `mcp_tokens` con hash SHA-256 del token. Devuelve el `token_id`. Usado por el panel y por fixtures de tests.
- [ ] **Fase QA**: tests sobre `resolve_developer` (token activo → OK; token revoked_at NOT NULL → UnauthenticatedError; token inexistente → UnauthenticatedError). Test de `register_developer` con la firma nueva.

**Cubre**: AC-16, AC-17, AC-18.

### Fase 4 — UC-502: Gate de membresía con cache TTL 30s en los 9 mutadores [AG-03]
**Dependencias**: UC-501, UC-505, UC-504. **Estimado**: 12h.

- [ ] Modificar `server/coordination/identity.py`: añadir constante `_CACHE_TTL_SECONDS = 30` (módulo-level, hardcoded). Añadir cache `_AUTH_CACHE: dict[tuple[str, str], tuple[Developer, float]] = {}` y función:

```python
async def authenticate_and_authorize_cached(
    conn, *, token: str, project_id: str
) -> Developer:
    key = (hash_token(token), project_id)
    now = time.monotonic()
    cached = _AUTH_CACHE.get(key)
    if cached and cached[1] > now:
        return cached[0]
    dev = await authenticate_and_authorize(conn, token=token, project_id=project_id)
    _AUTH_CACHE[key] = (dev, now + _CACHE_TTL_SECONDS)
    return dev


def _clear_auth_cache() -> None:
    """Test-only: invalidate the in-memory cache."""
    _AUTH_CACHE.clear()
```

- [ ] Modificar `server/backends/native_backend.py`: añadir helper interno

```python
async def _require_membership_cached(self) -> Developer:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await authenticate_and_authorize_cached(
            conn, token=self._dev_token, project_id=self._project_id
        )
```

- [ ] Inyectar `await self._require_membership_cached()` como **primera línea** del cuerpo de cada uno de los 9 mutadores (líneas 389, 573, 779, 809, 845, 907, 927, 987, 1055). Las lecturas (`list_items`, `get_item`, etc.) NO se modifican — decisión explícita documentada en AC-06.
- [ ] **Fase QA**: tests parametrizados con Postgres real:
  - AC-06 (UC-502): contador de queries → 5 calls dentro de TTL = 1 query única.
  - AC-07 (UC-502): import del símbolo y assert `_CACHE_TTL_SECONDS == 30`.
  - AC-08 (UC-502): parametrizado sobre los 9 mutadores; token inválido → UnauthenticatedError + count tabla sin cambios.
  - AC-09 (UC-502): token válido sin membresía → ForbiddenError + count sin cambios en los 9 mutadores.
  - AC-10 (UC-502): revoke en otra conn + `_clear_auth_cache()` → next mutación falla UnauthenticatedError.
  - AC-11 (UC-502): con token revocado, `list_items` y otras lecturas SIGUEN devolviendo datos (decisión explícita).

**Cubre**: AC-06..11.

### Fase 5 — UC-503: Audit log de operaciones destructivas [AG-03]
**Dependencias**: UC-502 (gate aplicado). **Estimado**: 6h.

- [ ] Crear `server/coordination/audit.py` con:

```python
async def record_destructive(
    conn, *, developer_id: str | None, project_id: str,
    operation: str, target_id: str,
) -> None:
    await conn.execute(
        "INSERT INTO audit_log (developer_id, project_id, operation, target_id) "
        "VALUES ($1, $2, $3, $4)",
        developer_id, project_id, operation, target_id,
    )
```

- [ ] Modificar `NativeBackend.delete_acceptance_criterion` (línea 907): tras el DELETE SQL exitoso (si afectó ≥1 fila), invocar `record_destructive(conn, developer_id=dev.developer_id, project_id=self._project_id, operation="delete_acceptance_criterion", target_id=ac_id)`. El `developer_id` viene del `Developer` retornado por `_require_membership_cached()` (UC-502).
- [ ] Modificar `NativeBackend.archive_item` (línea 927): tras el UPDATE SQL exitoso, invocar `record_destructive(conn, developer_id=dev.developer_id, project_id=self._project_id, operation="archive_item", target_id=item_id)`.
- [ ] Las otras 7 mutaciones NO se tocan en audit.
- [ ] **Fase QA**: `tests/test_audit_log_destructive.py`:
  - delete_ac exitoso → fila nueva con campos correctos.
  - delete_ac sobre AC inexistente → audit_log sin cambios.
  - archive_item exitoso/falla → análogo.
  - Test parametrizado sobre las 7 no-destructivas → audit_log permanece vacío.

**Cubre**: AC-12..15.

### Fase 6 — UC-506: Tests adversariales + restaurar conformance [AG-04]
**Dependencias**: UC-501..505 completos. **Estimado**: 6h.

- [ ] Actualizar `tests/test_native_backend_conformance.py:85` el factory `_native_backend_factory`: ahora crea `developer + mcp_token + project_member` antes de instanciar `NativeBackend(project_id, dev_token)` con el token recién creado. Reutiliza `register_developer` + `register_mcp_token` + `add_project_member`. Esto restaura los tests rotos por UC-505.
- [ ] Crear `tests/test_native_revoke_adversarial.py`:
  - **Test 1 (AC-22)**: revoke con cache → muta dentro del TTL (éxito esperado, comportamiento documentado), `_clear_auth_cache()`, mutación posterior falla UnauthenticatedError.
  - **Test 2 (AC-23)**: remove de `project_members` sin revocar token → `_clear_auth_cache()` → cada una de las 9 mutaciones lanza ForbiddenError + count tabla sin cambios.
- [ ] Verificar AC-24: `.venv/bin/pytest tests/test_native_backend_conformance.py -q` → 100% verde con nuevo modelo identidad.
- [ ] Verificar AC-25: test que ejecuta una secuencia mixta (3 creates, 2 updates, 1 mark, 2 deletes, 1 archive) → audit_log contiene exactamente las 3 filas correspondientes a deletes + archive con los campos correctos.

**Cubre**: AC-22..25.

---

## Comandos Finales (por fase)

```bash
# Pre-requisito: Postgres dev arriba + DSN exportado
docker compose -f docker-compose.dev.yml up -d
export SPECBOX_NATIVE_DSN="postgresql://specbox:specbox_dev_only@localhost:55432/specbox_native"

# Verificación por fase (cada UC corre lo suyo + lo previo sin regresión)
.venv/bin/pytest tests/test_native_security_schema.py -q   # UC-501
.venv/bin/pytest tests/test_native_init_signature.py -q    # UC-505 (test temporal)
.venv/bin/pytest tests/test_resolve_developer.py -q        # UC-504
.venv/bin/pytest tests/test_auth_cache_ttl.py tests/test_native_mutation_authz.py -q  # UC-502
.venv/bin/pytest tests/test_audit_log_destructive.py -q    # UC-503
.venv/bin/pytest tests/test_native_revoke_adversarial.py tests/test_native_backend_conformance.py -q  # UC-506

# No-regresión global al cerrar la US
.venv/bin/pytest tests/test_native_*.py tests/test_coordination_*.py tests/test_write_target_dispatch.py tests/test_state_mapping.py tests/test_switch_backend_transactional.py -q
gga run
```

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|----------|---------------|----------------------|-------|
| Estrategia de validación | Gate por mutación + cache 30s | RLS Postgres a nivel DB | RLS requiere JWT con claims + `current_setting()` + refactor de cómo se pasa identidad. Diferido a v2 — esta US se centra en cerrar el hueco rápido. |
| Cache TTL | Hardcoded `_CACHE_TTL_SECONDS = 30` | Env var configurable | Decisión consciente del usuario para simplicidad. Si hace falta, futura PR cambia una línea. |
| Audit log scope | Solo destructivas (delete_ac, archive_item) | Audit en las 9 mutaciones | Storage + ruido. Recovery desde backup ya cubre el resto. |
| Audit log payload | Quién + qué + cuándo + target | Diff before/after | Privacy + storage. Para revertir se usan backups Supabase, no el audit. |
| Compat hacia atrás | Sin compat — breaking limpio | Deprecation warnings + migración progresiva | El usuario confirmó que nada está en producción Native salvo él mismo. Limpieza > deuda técnica. |
| `register_native_developer` | Eliminada del MCP | Esconder tras flag `SPECBOX_ALLOW_ADMIN_TOOLS` | El panel sale en 1-2 días; no merece mantener doble vía. |
| Bootstrap transitorio | Ninguno | Script `server/scripts/bootstrap_native_dev.py` | El usuario espera al panel. Cero deuda. |

---

## Archivos a Crear/Modificar

```
server/
├── db/migrations/
│   ├── 0004_github_identities.sql       # NUEVO (UC-501)
│   ├── 0005_mcp_tokens.sql              # NUEVO — dropea developers.token_hash atómicamente (UC-501)
│   └── 0006_audit_log.sql               # NUEVO (UC-501)
├── coordination/
│   ├── identity.py                      # MODIFICAR (UC-502 cache + cached; UC-504 resolve via mcp_tokens; register_developer sin token; nuevo register_mcp_token helper)
│   └── audit.py                         # NUEVO (UC-503)
├── backends/native_backend.py           # MODIFICAR (UC-505 __init__; UC-502 9 mutadores; UC-503 delete_ac + archive_item)
├── auth_gateway.py                      # MODIFICAR (UC-505 dispatch + store_native_credentials)
└── tools/coordination.py                # MODIFICAR (UC-504 elimina register_native_developer)

tests/
├── test_native_security_schema.py       # NUEVO (UC-501 — 5 ACs)
├── test_native_init_signature.py        # NUEVO (UC-505 — 3 ACs)
├── test_resolve_developer.py            # NUEVO (UC-504 — 3 ACs)
├── test_auth_cache_ttl.py               # NUEVO (UC-502 — AC-01,02)
├── test_native_mutation_authz.py        # NUEVO (UC-502 — AC-03,04,05,06)
├── test_audit_log_destructive.py        # NUEVO (UC-503 — 4 ACs + UC-506 AC-25)
├── test_native_revoke_adversarial.py    # NUEVO (UC-506 — AC-22,23)
└── test_native_backend_conformance.py   # MODIFICAR (UC-506 — fixture actualizada; AC-24)

supabase/migrations/                     # ALINEAR byte-for-byte con server/db/migrations/0004-0006 (apply_migration via Supabase MCP)
```

---

## Referencias

- PRD: `doc/prd/native_security_prd.md`
- Schema previo: `server/db/migrations/0001..0003_*.sql`
- Identity: `server/coordination/identity.py`
- NativeBackend: `server/backends/native_backend.py`
- Dispatch: `server/auth_gateway.py`
- Test helper Native: `tests/_native_db.py`
- Suite conformance: `tests/test_native_backend_conformance.py`
