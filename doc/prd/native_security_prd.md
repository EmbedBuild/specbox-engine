# PRD: [US-NATIVE-SECURITY] Blindar el Native Backend contra mutaciones de identidades revocadas

> Origen: FreeForm board specbox-engine (`ff-ed0c02f4565a`) | US-NATIVE-SECURITY
> Generado: 2026-05-23
> Tipo: PRD Técnico (feature de plataforma, sin UI de producto)

## Resumen Ejecutivo

El Native Backend de SpecBox tiene hoy un **hueco de seguridad concreto**: las mutaciones del `NativeBackend` (`create_item`, `update_item`, `archive_item`, `mark_acceptance_criterion`, `delete_acceptance_criterion`, `create_acceptance_criteria`, `update_acceptance_criterion`, `add_comment`, `add_attachment`) **no re-validan identidad por call** — confían en que la sesión MCP arrancó autenticada. Solo las 5 tools de coordination (`claim_uc`, `release_uc`, `whoami`, `register_native_developer`, `register_native_branch`) pasan por `authenticate_and_authorize`.

Consecuencia: un developer expulsado de un proyecto (revoke desde el panel) sigue pudiendo mutar US/UC/AC desde su MCP en VSCode/Cursor hasta que reinicie el proceso — ventana de **horas**, no de segundos. Para operaciones destructivas (`delete_acceptance_criterion`, `archive_item`) esto es **brecha de responsabilidad** del mantenedor del MCP.

Esta US blinda el Native Backend antes de abrir el panel y onboardear más operadores: cada mutación re-valida identidad + membresía con cache de 30s, las operaciones destructivas quedan registradas en un audit log para recuperación, y el modelo de identidad se rediseña limpio (developer ↔ N github_identities + mcp_tokens revocables) eliminando el `developers.token_hash` actual.

## Alcance

### Incluye
- **Gate de membresía en cada mutación del NativeBackend** — `authenticate_and_authorize` invocado antes de cada INSERT/UPDATE/DELETE sobre las tablas tenant.
- **Cache TTL hardcoded 30s** en memoria del proceso MCP para amortizar el coste — ventana de exposición tras revoke ≤ 30 segundos.
- **Schema rediseñado** con 3 migraciones limpias (sin compatibilidad hacia atrás, porque no hay nada en producción Native):
  - `0004_github_identities.sql` — vinculación N:1 GitHub identity → developer (cubre el caso freelance con varias cuentas GitHub).
  - `0005_mcp_tokens.sql` — tabla separada de `developers`, sin TTL, revocable. Reemplaza `developers.token_hash`.
  - `0006_audit_log.sql` — registro de operaciones destructivas (developer_id + operation + target_id + project_id + occurred_at).
- **Audit log de operaciones destructivas**: `delete_acceptance_criterion` y `archive_item` registran cada llamada exitosa.
- **Refactor de `NativeBackend.__init__`** para recibir el `dev_token` de la sesión (necesario para el gate por mutación).
- **Eliminación del CRUD de equipo del MCP**: `register_native_developer` se elimina; el CRUD de developers/identities/tokens pasa a ser responsabilidad exclusiva del panel.
- **Tests adversariales completos**: revoke entre dos mutaciones, comportamiento dentro del TTL del cache, comportamiento tras expirar el cache, audit log poblado correctamente, suite de conformance Native sigue verde.

### No incluye
- **RLS Postgres** (Row Level Security a nivel DB). Diferido a v2. El gate vive en Python en v1.
- **El panel web** (`specbox-control-panel`) — se construye fuera de este repo. Esta US solo prepara el MCP para que confíe en lo que el panel hace.
- **Realtime broadcast al MCP**. El revoke desde el panel solo notifica al **panel del dev** (Supabase Realtime sobre `dev:{developer_id}`); el MCP no escucha — su próxima call falla `UNAUTHENTICATED` por el gate.
- **Bootstrap transitorio**: ninguna tool MCP para crear el primer developer "a mano". El mantenedor espera al panel (deploy en 1-2 días).
- **Audit log con diff before/after**. Solo metadata (quién + qué + cuándo + sobre qué item). Sin payload del cambio. La recuperación se hace desde backups Supabase, no desde el audit.
- **Refresh tokens / OAuth-style**. Los mcp_tokens son PATs estáticos sin expiración, revocables manualmente desde el panel.
- **`developers.token_hash` retrocompatible**. Se elimina de raíz junto con `register_native_developer`.

---

## Objetivos

1. **Cerrar el hueco de mutaciones** — Que un dev expulsado no pueda mutar el tracking de un proyecto Native más allá de 30 segundos tras el revoke.
2. **Trazabilidad de daño irreversible** — Que toda operación destructiva quede registrada con quién/qué/cuándo, para reversión desde backup si hace falta.
3. **Modelo de identidad limpio** — Reemplazar el `developers.token_hash` opaco actual por un modelo (`developers` + `github_identities` + `mcp_tokens`) que (a) modele identidades reales GitHub, (b) cubra el caso freelance con varias cuentas, (c) habilite revocación y rotación granular.
4. **Desacople total MCP ↔ Panel** — Que el CRUD de equipo (alta/baja de devs, emisión/revoke de tokens) viva solo en el panel; el MCP solo lee identidad y la consume.
5. **Cero impacto perceptible en `/implement`** — El cache de 30s mantiene la latencia añadida por mutación en ~1ms en cache hit (mayoría de operaciones de una sesión MCP normal).

---

## Estado Actual vs Propuesto

### ACTUAL
```
NativeBackend(project_id)
  └── métodos de mutación NO re-validan identidad
        └── confían en que set_auth_token autenticó al iniciar sesión
              └── token revocado en T1 → mutaciones siguen ok hasta restart MCP

developers
  ├── developer_id PK
  ├── display_name
  └── token_hash NOT NULL UNIQUE   ← acoplamiento "1 dev = 1 token opaco"

[no existe github_identities]
[no existe mcp_tokens]
[no existe audit_log]
```

### PROPUESTO
```
NativeBackend(project_id, dev_token)
  └── _require_membership_cached(dev_token, project_id)  ← invocado en CADA mutación
        ├── cache hit (TTL 30s)  → ~1ms (lookup dict en proceso)
        └── cache miss           → ~10-25ms (SELECT en Supabase via Pooler)

developers
  ├── developer_id PK
  ├── display_name
  ├── primary_github_id BIGINT   ← FK a github_identities (puede ser NULL inicialmente)
  [token_hash ELIMINADO]

github_identities                ← N:1 con developers (caso freelance)
  ├── github_user_id BIGINT PK   ← ID numérico estable de GitHub (sobrevive a renames)
  ├── github_login TEXT NOT NULL
  ├── developer_id TEXT FK
  └── linked_at TIMESTAMPTZ

mcp_tokens                       ← reemplaza developers.token_hash
  ├── token_id TEXT PK           ← prefijo visible "spec_xxx", el resto secreto
  ├── developer_id TEXT FK
  ├── github_user_id BIGINT FK (NULL permitido para tokens no asociados a una identidad concreta)
  ├── token_hash TEXT NOT NULL UNIQUE  ← SHA-256 del clear-token
  ├── created_at, last_used_at TIMESTAMPTZ
  └── revoked_at TIMESTAMPTZ (NULL = activo)

audit_log                        ← solo operaciones destructivas
  ├── id BIGSERIAL PK
  ├── developer_id TEXT          ← quién (puede ser NULL si la fila se mantiene tras hard-delete del dev)
  ├── project_id TEXT NOT NULL
  ├── operation TEXT NOT NULL    ← 'delete_acceptance_criterion' | 'archive_item'
  ├── target_id TEXT NOT NULL    ← AC id, item id, etc.
  └── occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

---

## User Story

**ID**: US-NATIVE-SECURITY
**Nombre**: Blindar el Native Backend contra mutaciones de identidades revocadas
**Actor**: Mantenedor del MCP / Operador de instancia Supabase Native
**Horas estimadas**: 40h
**Pantallas**: ninguna (feature de plataforma)

> Como mantenedor del MCP SpecBox, quiero que ningún developer expulsado de un proyecto Native pueda mutar su tracking más allá de 30 segundos tras el revoke, y que toda operación destructiva quede registrada, para no ser responsable de daño causado por identidades revocadas y para poder recuperar desde backups si algo se cuela.

---

## Use Cases

### UC-501: Schema rediseñado — github_identities + mcp_tokens + audit_log
- **Actor**: Engine
- **Horas**: 8h
- **Estado**: backlog

Tres migraciones limpias (`0004_github_identities.sql`, `0005_mcp_tokens.sql`, `0006_audit_log.sql`) que reemplazan el modelo de identidad actual. Sin compat: `developers.token_hash` se dropea, `register_native_developer` deja de funcionar (eliminada en UC-504).

#### Acceptance Criteria
- [ ] **AC-01**: La migración `0004_github_identities.sql` crea la tabla `github_identities` con `github_user_id BIGINT PRIMARY KEY`, `github_login TEXT NOT NULL`, `developer_id TEXT NOT NULL REFERENCES developers(developer_id) ON DELETE CASCADE`, `linked_at TIMESTAMPTZ NOT NULL DEFAULT now()`; añade índice `idx_github_identities_developer_id` sobre `developer_id`; verificado aplicando la migración a un Postgres limpio y consultando `\d github_identities` que devuelve esa estructura exacta.
- [ ] **AC-02**: La migración `0005_mcp_tokens.sql` crea la tabla `mcp_tokens` con `token_id TEXT PRIMARY KEY`, `developer_id TEXT NOT NULL REFERENCES developers(developer_id) ON DELETE CASCADE`, `github_user_id BIGINT NULL REFERENCES github_identities(github_user_id) ON DELETE SET NULL`, `token_hash TEXT NOT NULL UNIQUE`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `last_used_at TIMESTAMPTZ NULL`, `revoked_at TIMESTAMPTZ NULL`; añade índices `idx_mcp_tokens_token_hash UNIQUE` y `idx_mcp_tokens_developer_id`; verificado igual que AC-01 con `\d mcp_tokens`.
- [ ] **AC-03**: La migración `0005_mcp_tokens.sql` dropea la columna `developers.token_hash` y el índice `idx_developers_token_hash` en el mismo archivo de migración (un solo paso atómico); verificado aplicando la migración y comprobando que `\d developers` ya no muestra `token_hash` y que `\di` ya no lista `idx_developers_token_hash`.
- [ ] **AC-04**: La migración `0006_audit_log.sql` crea la tabla `audit_log` con `id BIGSERIAL PRIMARY KEY`, `developer_id TEXT NULL`, `project_id TEXT NOT NULL`, `operation TEXT NOT NULL`, `target_id TEXT NOT NULL`, `occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()`; añade índice `idx_audit_log_project_occurred` sobre `(project_id, occurred_at DESC)` para queries del SuperAdmin por proyecto; verificado con `\d audit_log` y `\di`.
- [ ] **AC-05**: Las 3 migraciones son **idempotentes** (`IF NOT EXISTS`/`IF EXISTS`) — reaplicarlas sobre una DB que ya las tiene no lanza error ni duplica nada; verificado con un test que llama `apply_migrations()` dos veces seguidas contra el Postgres dev local y comprueba 0 errores en la segunda pasada.

### UC-502: Gate de membresía en mutaciones del NativeBackend con cache TTL 30s
- **Actor**: Engine
- **Horas**: 12h
- **Estado**: backlog

Cada método de mutación del `NativeBackend` (las 9 listadas) invoca `authenticate_and_authorize_cached(dev_token, project_id)` antes del SQL de escritura. Cache en memoria del proceso MCP con TTL hardcoded 30s. En cache miss, consulta `mcp_tokens.token_hash` + `project_members.developer_id`. Revoke desde el panel (UPDATE `mcp_tokens` SET `revoked_at` = now()) se observa en el siguiente miss.

#### Acceptance Criteria
- [ ] **AC-01**: `server/coordination/identity.py` añade `authenticate_and_authorize_cached(conn, token, project_id)` que mantiene un dict en memoria `{(token_hash, project_id): (Developer, expires_at)}`; en cache hit (now < expires_at) devuelve el Developer sin tocar Postgres; en cache miss llama a `authenticate_and_authorize` y guarda el resultado con `expires_at = monotonic() + 30`; verificado por test que mide nº de queries Postgres (mock o counter) en 5 calls consecutivas dentro del TTL → 1 query única (la primera).
- [ ] **AC-02**: El TTL es la **constante de módulo** `_CACHE_TTL_SECONDS = 30` en `identity.py` (no env var, no configurable runtime); verificado por inspección estática del módulo (test que importa el símbolo y comprueba `== 30`).
- [ ] **AC-03**: Los 9 métodos de mutación del `NativeBackend` (`create_item`, `update_item`, `archive_item`, `mark_acceptance_criterion`, `delete_acceptance_criterion`, `create_acceptance_criteria`, `update_acceptance_criterion`, `add_comment`, `add_attachment`) invocan `_require_membership_cached(self._dev_token)` antes de cualquier INSERT/UPDATE/DELETE; verificado por test parametrizado sobre los 9 métodos: cuando el token NO está en `mcp_tokens` (o tiene `revoked_at` NOT NULL), la mutación lanza `UnauthenticatedError` y un SELECT posterior sobre la tabla afectada confirma que **no hubo escritura** (count antes == count después).
- [ ] **AC-04**: Cuando el dev tiene token válido pero NO es member de `project_members` para el `project_id` del NativeBackend, las 9 mutaciones lanzan `ForbiddenError` y la escritura no ocurre; verificado por test parametrizado: alta de dev en `developers` + token en `mcp_tokens` pero SIN row en `project_members` → cada método mutador falla con ForbiddenError y count antes == count después.
- [ ] **AC-05**: Tras un revoke (UPDATE `mcp_tokens` SET `revoked_at` = now() FROM otra conexión que simula el panel), el siguiente cache miss del mismo token devuelve `UnauthenticatedError`; verificado por test que (a) hace una mutación exitosa con el token, (b) revoca el token desde otra conn, (c) espera 31 segundos (o llama directamente a una función `_clear_auth_cache()` de test), (d) intenta otra mutación → `UnauthenticatedError`.
- [ ] **AC-06**: Las lecturas (`list_items`, `get_item`, `get_acceptance_criteria`, `get_comments`, `get_attachments`, `find_item_by_field`, `get_item_children`, etc.) NO invocan el gate — solo las mutaciones (las 9 listadas en AC-03); verificado por test que con token válido + membresía válida en `project_members`, las lecturas funcionan; con token revocado, las lecturas siguen funcionando (a propósito: queremos que `whoami` y la inspección de items siga disponible para forense); este AC documenta y verifica esta decisión explícita.

### UC-503: Audit log de operaciones destructivas
- **Actor**: Engine
- **Horas**: 6h
- **Estado**: backlog

`delete_acceptance_criterion` y `archive_item` (las dos operaciones que destruyen trazabilidad) escriben una fila en `audit_log` tras la mutación exitosa. Las demás mutaciones (create/update/mark/add_comment/add_attachment) no escriben audit (son reversibles o no destructivas).

#### Acceptance Criteria
- [ ] **AC-01**: `server/coordination/audit.py` (módulo nuevo) expone `async def record_destructive(conn, *, developer_id, project_id, operation, target_id)` que ejecuta `INSERT INTO audit_log (developer_id, project_id, operation, target_id) VALUES ($1, $2, $3, $4)`; verificado por test que llama la función y consulta `SELECT * FROM audit_log ORDER BY id DESC LIMIT 1` confirmando que los 4 campos llegaron tal cual.
- [ ] **AC-02**: `NativeBackend.delete_acceptance_criterion` invoca `record_destructive` con `operation='delete_acceptance_criterion'` y `target_id=ac_id` **tras** el DELETE SQL exitoso (si el DELETE falla, no se escribe audit); verificado por test que: borra un AC existente, confirma una nueva fila en `audit_log` con esos valores; y otro test que intenta borrar un AC inexistente, comprueba que `audit_log` NO crece (la operación falló antes del audit).
- [ ] **AC-03**: `NativeBackend.archive_item` invoca `record_destructive` con `operation='archive_item'` y `target_id=item_id` tras el UPDATE SQL exitoso que marca el item como archivado; verificado por test análogo a AC-02: archive de US/UC exitoso → fila nueva en `audit_log`; archive de item inexistente → `audit_log` sin cambios.
- [ ] **AC-04**: Las otras 7 mutaciones (`create_item`, `update_item`, `mark_acceptance_criterion`, `create_acceptance_criteria`, `update_acceptance_criterion`, `add_comment`, `add_attachment`) **NO escriben** en `audit_log`; verificado por test parametrizado que ejecuta cada una y comprueba que `audit_log` permanece vacío tras todas ellas.

### UC-504: Eliminar register_native_developer del MCP + developers.token_hash
- **Actor**: Engine
- **Horas**: 4h
- **Estado**: backlog

Limpieza limpia (sin deprecation): `register_native_developer` desaparece de `server/tools/coordination.py` y del registro de tools; `developers.token_hash` se elimina (en realidad ya lo dropea la migración de UC-501 AC-03, este UC consolida la limpieza del código Python que la usaba). El CRUD de developers/identities/tokens pasa a ser responsabilidad exclusiva del panel.

#### Acceptance Criteria
- [ ] **AC-01**: La función `register_native_developer` ya no existe en `server/tools/coordination.py` (eliminada, no marcada deprecated); el registro de tools del módulo ya no la incluye; verificado con `grep -n 'register_native_developer' server/tools/coordination.py` que devuelve 0 líneas y con un test que importa el módulo y comprueba que el símbolo no existe (`hasattr` falso).
- [ ] **AC-02**: `server/coordination/identity.py` `resolve_developer` ahora consulta `mcp_tokens` en vez de `developers.token_hash`: query `SELECT d.developer_id, d.display_name FROM mcp_tokens t JOIN developers d ON d.developer_id = t.developer_id WHERE t.token_hash = $1 AND t.revoked_at IS NULL`; verificado por test que registra un developer + un mcp_token activo, llama `resolve_developer` y obtiene el Developer correcto; y un segundo test que revoca el token (UPDATE `revoked_at`) y verifica que `resolve_developer` ahora lanza `UnauthenticatedError`.
- [ ] **AC-03**: La función `register_developer` en `server/coordination/identity.py` ya no escribe en `developers.token_hash` (porque la columna no existe tras UC-501); su firma cambia: el parámetro `token` se elimina, y la función queda como `register_developer(conn, *, developer_id, display_name)` que solo inserta en `developers`. La emisión de mcp_tokens es responsabilidad del panel (que llamará al panel-only `register_mcp_token` que NO se expone como tool MCP); verificado por inspección de firma y por test que llama `register_developer(conn, developer_id="x", display_name="X")` con éxito y comprueba la fila en `developers`.

### UC-505: Refactor NativeBackend.__init__ + auth_gateway dispatch
- **Actor**: Engine
- **Horas**: 4h
- **Estado**: backlog

`NativeBackend.__init__` ahora recibe el `dev_token` además del `project_id`, para que cada mutación pueda llamar al gate. `auth_gateway.get_session_backend` para `backend_type="native"` lee `dev_token` de la sesión y lo pasa al constructor.

#### Acceptance Criteria
- [ ] **AC-01**: `NativeBackend.__init__(self, project_id: str, dev_token: str)` — ambos parámetros obligatorios (no opcionales); pasar `dev_token=""` o `None` lanza `ValueError("dev_token is required for NativeBackend")` desde el constructor; verificado por test parametrizado con casos válidos e inválidos.
- [ ] **AC-02**: `server/auth_gateway.py` `get_session_backend`, en la rama `backend_type == "native"`, lee `config["dev_token"]` (que ya existe en la sesión native, según `store_native_credentials`) y lo pasa al constructor: `NativeBackend(project_id=config["project_id"], dev_token=config["dev_token"])`; verificado por test que mockea la sesión MCP con `backend_type=native`, `project_id=p1`, `dev_token=t1` y comprueba que la instancia devuelta tiene `_project_id == "p1"` y `_dev_token == "t1"`.
- [ ] **AC-03**: `store_native_credentials` (en `auth_gateway.py`) exige `dev_token` no vacío al guardar la sesión native — pasar `""` o `None` lanza un error explícito en `set_auth_token(backend_type="native", token="", ...)`; verificado por test que llama `set_auth_token` sin token con backend_type native y comprueba el error.

### UC-506: Tests adversariales
- **Actor**: Engine
- **Horas**: 6h
- **Estado**: backlog

Suite que prueba el escenario completo de un dev expulsado intentando mutar entre T1 y T1+30s, tras T1+30s, y que la suite de conformance Native existente (`tests/test_native_backend_conformance.py`) sigue verde con el nuevo modelo de identidad.

#### Acceptance Criteria
- [ ] **AC-01**: `tests/test_native_revoke_adversarial.py` incluye un test end-to-end que: (a) registra dev + token + membresía + crea un proyecto Native con 3 ACs, (b) hace una mutación exitosa (mark_acceptance_criterion done=True) que entra en cache, (c) revoca el token desde otra conexión, (d) hace inmediatamente otra mutación dentro del TTL → la mutación tiene éxito (cache hit, comportamiento esperado y documentado), (e) invalida el cache (función de test `_clear_auth_cache()`), (f) intenta otra mutación → `UnauthenticatedError` y count de la tabla no cambia. Este test documenta la ventana de exposición real.
- [ ] **AC-02**: `tests/test_native_revoke_adversarial.py` incluye un test que: (a) registra dev + token + membresía, (b) **elimina al dev de project_members** (sin revocar el token), (c) invalida el cache, (d) intenta cada una de las 9 mutaciones → todas lanzan `ForbiddenError` y los counts de las tablas afectadas no cambian.
- [ ] **AC-03**: `tests/test_native_backend_conformance.py` (la suite existente de los 26 métodos del ABC) sigue **100% verde** tras los cambios — verificado ejecutando `.venv/bin/pytest tests/test_native_backend_conformance.py -q` y obteniendo todos los tests en PASS (los fixtures se actualizan para crear el dev + token + membresía antes de instanciar el `NativeBackend`).
- [ ] **AC-04**: `tests/test_audit_log_destructive.py` incluye tests que verifican que tras una secuencia de N mutaciones mixtas (creates, updates, marks, deletes, archives), el `audit_log` contiene exactamente las filas correspondientes a los `delete_acceptance_criterion` y `archive_item` exitosos, con `developer_id` correcto, `project_id` correcto, `operation` correcta y `target_id` correcto; los counts de filas no destructivas son 0 en `audit_log`.

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| El cache TTL de 30s deja una ventana de exposición real | Alta (es por diseño) | Medio | Audit log en operaciones destructivas + recuperación desde backup Supabase. Documentado explícitamente en AC-01 de UC-506. |
| `apply_migrations` runner casero no maneja bien una DB que ya tiene `developers.token_hash` | Media | Alto | UC-501 AC-05 exige idempotencia de las 3 migraciones; tests específicos lo verifican. |
| Tests Native existentes se rompen al cambiar la firma de `NativeBackend.__init__` | Alta (es breaking) | Bajo | UC-506 AC-03 cubre exactamente esto: el fixture de conformance se actualiza para crear dev + token + membership; sin esto, los tests no pasan. |
| Cache hit en mutaciones tras revoke deja escribir cosas | Media | Medio (limitado por TTL 30s) | Aceptado como decisión consciente. Para v2 se considera RLS Postgres como muro real. |
| `mcp_tokens` mal indexado hace lento el lookup en cache miss | Baja | Bajo | UC-501 AC-02 exige `UNIQUE INDEX` sobre `token_hash`; cada miss es un SELECT por índice, ~10-20ms en Pooler Supabase. |
| Audit log crece sin límite | Media | Bajo | El SuperAdmin del panel puede archivar/purgar; fuera del alcance de esta US (v2). Para v1 el growth rate es bajo (solo destructivas). |

---

## Stack Técnico (estimado)

- **Stack**: Python 3.12+, asyncpg, FastMCP (heredado del proyecto).
- **DB**: Supabase Postgres 17+ vía Pooler transaction-mode.
- **Tests**: pytest con fixtures Postgres reales (gated por `PG_OK` de `tests/_native_db.py`).
- **Patrón inyectable** ya usado en UC-404 (`transactional_switch`): el cache tendrá una función `_clear_auth_cache()` de test no pública.

## Archivos Principales (estimado)
```
server/db/migrations/
  ├── 0004_github_identities.sql       (nuevo)
  ├── 0005_mcp_tokens.sql              (nuevo, dropea developers.token_hash)
  └── 0006_audit_log.sql               (nuevo)
server/coordination/
  ├── identity.py                       (modificar: authenticate_and_authorize_cached, _CACHE_TTL_SECONDS=30; resolve_developer pasa a leer mcp_tokens; register_developer firma sin token)
  └── audit.py                          (nuevo: record_destructive)
server/backends/native_backend.py       (modificar: __init__ acepta dev_token; los 9 mutadores invocan _require_membership_cached; delete_ac/archive_item llaman record_destructive)
server/auth_gateway.py                  (modificar: dispatch native pasa dev_token al constructor; store_native_credentials exige dev_token)
server/tools/coordination.py            (modificar: ELIMINAR register_native_developer)
tests/
  ├── test_native_security_schema.py    (nuevo: AC de UC-501)
  ├── test_auth_cache_ttl.py            (nuevo: AC-01,02 de UC-502)
  ├── test_native_mutation_authz.py     (nuevo: AC-03..06 de UC-502)
  ├── test_audit_log_destructive.py     (nuevo: AC de UC-503 + AC-04 de UC-506)
  ├── test_native_revoke_adversarial.py (nuevo: AC-01,02 de UC-506)
  └── test_native_backend_conformance.py (modificar fixtures para nuevo modelo identidad — AC-03 de UC-506)
```

## Dependencias

- Postgres dev local (`docker-compose.dev.yml`, puerto 55432) levantado para tests durante implementación.
- `SPECBOX_NATIVE_DSN` exportado en la sesión del implementador.
- Native Backend operativo (US-NATIVE-BACKEND, US-NATIVE-SUPABASE — ambas done).

---

## Plan de Implementación (alto nivel)

### Fase 1: UC-501 — Schema (8h)
3 migraciones SQL. Sin código Python aún. Test de idempotencia.

### Fase 2: UC-505 — Refactor firma constructor (4h)
`NativeBackend.__init__` acepta `dev_token`. `auth_gateway` lo pasa. **Esta fase rompe los tests de conformance** y dejarán de pasar hasta UC-502; aceptado por el orden de dependencias.

### Fase 3: UC-504 — Limpieza CRUD y resolve_developer (4h)
Elimina `register_native_developer`. `resolve_developer` lee `mcp_tokens`. `register_developer` sin token.

### Fase 4: UC-502 — Gate en mutaciones + cache (12h)
`authenticate_and_authorize_cached` + invocación en los 9 mutadores. **Esta fase repara los tests de conformance** porque el fixture del test pasa a crear el dev + token + membership.

### Fase 5: UC-503 — Audit log (6h)
`record_destructive` + invocación en `delete_acceptance_criterion` y `archive_item`.

### Fase 6: UC-506 — Tests adversariales (6h)
Suite completa que cubre escenarios de revoke + comportamiento de cache + audit + regresión del conformance.

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)

#### UC-501 — Schema
- [ ] **AC-01** (UC-501): Migración `0004_github_identities.sql` crea tabla con estructura exacta.
- [ ] **AC-02** (UC-501): Migración `0005_mcp_tokens.sql` crea tabla con estructura exacta + índices.
- [ ] **AC-03** (UC-501): La misma migración dropea `developers.token_hash` y su índice atómicamente.
- [ ] **AC-04** (UC-501): Migración `0006_audit_log.sql` crea tabla + índice por `(project_id, occurred_at)`.
- [ ] **AC-05** (UC-501): Las 3 migraciones son idempotentes — `apply_migrations()` dos veces no falla.

#### UC-502 — Gate + cache
- [ ] **AC-06** (UC-502): `authenticate_and_authorize_cached` con cache dict en memoria; 5 calls dentro de TTL = 1 query Postgres.
- [ ] **AC-07** (UC-502): TTL hardcoded `_CACHE_TTL_SECONDS = 30` como constante de módulo.
- [ ] **AC-08** (UC-502): Los 9 mutadores del NativeBackend invocan el gate; token inválido → `UnauthenticatedError` + escritura no ocurre.
- [ ] **AC-09** (UC-502): Token válido sin membresía → `ForbiddenError` + escritura no ocurre.
- [ ] **AC-10** (UC-502): Revoke + cache invalidado → siguiente mutación falla.
- [ ] **AC-11** (UC-502): Lecturas NO pasan por el gate (decisión documentada).

#### UC-503 — Audit
- [ ] **AC-12** (UC-503): `record_destructive` escribe fila completa en `audit_log`.
- [ ] **AC-13** (UC-503): `delete_acceptance_criterion` exitoso → fila audit con `operation='delete_acceptance_criterion'` y `target_id=ac_id`.
- [ ] **AC-14** (UC-503): `archive_item` exitoso → fila audit con `operation='archive_item'` y `target_id=item_id`.
- [ ] **AC-15** (UC-503): Las 7 mutaciones no destructivas no escriben en `audit_log`.

#### UC-504 — Limpieza
- [ ] **AC-16** (UC-504): `register_native_developer` eliminada del módulo y del registro de tools.
- [ ] **AC-17** (UC-504): `resolve_developer` lee `mcp_tokens` JOIN `developers`, filtrando `revoked_at IS NULL`.
- [ ] **AC-18** (UC-504): `register_developer` sin parámetro `token` (firma limpia).

#### UC-505 — Refactor firma
- [ ] **AC-19** (UC-505): `NativeBackend.__init__` exige `dev_token` no vacío.
- [ ] **AC-20** (UC-505): `auth_gateway` pasa `dev_token` al constructor.
- [ ] **AC-21** (UC-505): `store_native_credentials` rechaza `dev_token` vacío.

#### UC-506 — Tests adversariales
- [ ] **AC-22** (UC-506): Test end-to-end de revoke con cache → muta dentro del TTL, falla tras invalidar.
- [ ] **AC-23** (UC-506): Eliminación de membresía sin revocar token → todas las 9 mutaciones lanzan `ForbiddenError`.
- [ ] **AC-24** (UC-506): Suite `test_native_backend_conformance.py` 100% verde con nuevo modelo de identidad.
- [ ] **AC-25** (UC-506): Audit log poblado correctamente tras secuencia mixta de mutaciones.

### Técnicos (no validados por AG-09)
- [ ] Lint 0/0 (ruff) en todos los archivos tocados.
- [ ] Cobertura ≥85% en los módulos nuevos/modificados (`identity.py`, `audit.py`, `native_backend.py`).
- [ ] Sin regresión: `pytest tests/test_native_*.py tests/test_coordination_*.py tests/test_migrat*.py tests/test_write_target_dispatch.py tests/test_state_mapping.py tests/test_switch_backend_transactional.py` todo verde.

---
**Prioridad**: high
**Complejidad**: Media-Alta (3 migraciones + refactor de identidad + tests adversariales)
**VEG Readiness**: DISABLED (feature de plataforma sin UI — heredado de app_spec.md)
*Generado: 2026-05-23*
