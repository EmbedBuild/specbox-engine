# Plan: [US-NATIVE-BATCH-INGEST] Ingesta por lotes de sources grandes a Native

> Generado: 2026-06-02
> Origen: FreeForm board `ff-ed0c02f4565a` | US-NATIVE-BATCH-INGEST
> PRD: doc/prd/US-NATIVE-BATCH-INGEST_prd.md
> Discovery: doc/discovery/native_batch_ingestion/icp_jtbd.md (disc-9409945c825b)
> Estado: Pendiente de aprobación
> Stack: Python (FastMCP) — **feature backend-only, sin UI / Stitch / VEG**

---

## Resumen

Resolver el transporte de sources freeform grandes a Native como **ingesta por lotes
server-side** (`start → append × N → commit`), preservando la atomicidad de la escritura
(commit diferido en una transacción, rollback total) y reutilizando los INSERT item-por-item
que el engine ya tiene. Cierra el gap de v6.9.1 reproducido en dogfooding con `specbox_cloud`.

## Análisis UI (Fase 0)

**N/A** — feature de backend / MCP server. No hay pantallas, componentes UI, VEG ni diseños
Stitch. El PRD marca `VEG Readiness: DISABLED`. Pasos 2.5b y 6 del skill `/plan` omitidos.

---

## Decisión arquitectural clave: dónde vive la transacción atómica

`write_target` (`server/migration/writer.py`) es **genérico y multi-backend** (escribe en
FreeForm/Trello/Plane/Native vía el ABC `SpecBackend`). Hilar un `conn` de asyncpg por todos
sus `create_item`/`create_acceptance_criteria` rompería esa abstracción (Trello/Plane no tienen
`conn`). Cada `_insert_*` de `NativeBackend` además hace su propio `pool.acquire()` hoy
(native_backend.py:511-512, 550-551), así que un fallo a mitad NO revierte los inserts previos.

**Decisión**: añadir un método **específico de Native** `NativeBackend.ingest_atomic(board_id,
source_data)` que adquiere **una** conexión del pool, abre **una** `conn.transaction()`, y ejecuta
las 3 fases (US, UC+AC, comments) sobre esa conexión. Reutiliza la lógica de clasificación/orden
de `write_target` (extraída a un helper puro `build_write_plan(source_data)` que no toca I/O), pero
los INSERT corren todos en la transacción única. `write_target` genérico queda intacto para los
otros 3 backends; el commit por lotes a Native usa `ingest_atomic`.

| Alternativa | Descartada porque |
|-------------|-------------------|
| Hilar `conn` por todos los métodos del ABC | Rompe la abstracción multi-backend; Trello/Plane no tienen `conn`. |
| `savepoint` por item dentro de write_target | No da rollback total; deja US de fase 1 si falla fase 2 (viola AC-10). |
| **`ingest_atomic` específico de Native (elegida)** | Atomicidad real, write_target genérico intacto, reusa `build_write_plan`. |

---

## Fases de Implementación

> Una fase por UC. Autopilot agresivo. Tests pytest contra Postgres real
> (`docker compose -f docker-compose.dev.yml up`).

### Fase 1 — UC-680: Sesión de migración multi-llamada con dev_token cacheado [3h]

**Archivos nuevos**:
- `server/migration/batch_session.py` — `MigrationSession` (dataclass: `session_id`,
  `developer`, `target_project_id`, `source_type`, `declared_items`, `declared_bytes`,
  `source_sha256`, `chunks_expected`, `chunks: dict[int, str]`, `created_at`, `ttl`) +
  `SessionStore` (dict en memoria `session_id → MigrationSession`, con `_prune_expired()` por TTL).

**Archivos modificados**:
- `server/tools/migration.py` — nueva tool `start_migration_session(target_project_id,
  source_type, declared_items, declared_bytes, source_sha256, chunk_count)`:
  1. Valida `dev_token` vía `authenticate_and_authorize_cached` (identity.py:400) — 1 sola consulta;
     fail-fast `UNAUTHENTICATED` si ausente/inválido (reusa el contrato `require_dev_token`).
  2. Genera `session_id` (uuid), crea `MigrationSession`, la registra en el `SessionStore`.
  3. Devuelve `{session_id, status:'open', declared_items, chunks_expected, chunks_received:0}`.
  4. NO toca Postgres (verificable: conteo de filas == previo).

**Diseño de seguridad**: la sesión se ata al `developer` autenticado y al `target_project_id`
(tenant). Los appends/commit re-resuelven la sesión por `session_id` y verifican que el caller
es el mismo developer. No se relaja `deny_anon`; el DSN sigue solo en `SPECBOX_NATIVE_DSN`.

**ACs**: AC-01 (open sin escribir), AC-02 (UNAUTHENTICATED fail-fast), AC-03 (identidad cacheada).

**Tests**: `tests/test_native_batch_ingestion.py::test_start_session_*` — abre sesión, asserta
0 filas en Postgres, asserta UNAUTHENTICATED con token vacío, cuenta consultas de identidad
(monkeypatch contador sobre `authenticate_and_authorize`).

---

### Fase 2 — UC-681: Staging server-side de chunks con verificación por chunk [3h]

**Archivos modificados**:
- `server/migration/batch_session.py` — `SessionStore.append_chunk(session_id, chunk_index,
  chunk_data, chunk_sha256)`:
  - `SESSION_NOT_FOUND` si la sesión no existe/expiró/cerrada (AC-06).
  - calcula `sha256(chunk_data)`; si != `chunk_sha256` declarado → `CHUNK_HASH_MISMATCH`
    `{chunk_index, expected, actual}`, no acumula, no incrementa (AC-05).
  - `DUPLICATE_CHUNK_INDEX` si `chunk_index` ya presente, no sobrescribe (AC-07).
  - en caso correcto: `session.chunks[chunk_index] = chunk_data`, devuelve `{status:'accepted',
    chunks_received:len(chunks), chunks_expected}` (AC-04).
- `server/tools/migration.py` — tool `append_migration_chunk(session_id, chunk_index, chunk_data,
  chunk_sha256)` que delega en `SessionStore.append_chunk` y verifica que el caller == owner.

**Helper compartido**: `server/migration/integrity.py` — `sha256_hex(s: str) -> str` (puro,
usado por chunk-check, reensamblado y E2E). Un solo punto de verdad para el hashing.

**ACs**: AC-04, AC-05, AC-06, AC-07.

**Tests**: `test_append_chunk_*` — acepta hash correcto, rechaza mismatch sin acumular, rechaza
session inexistente, rechaza index duplicado sin sobrescribir.

---

### Fase 3 — UC-682: Commit diferido con pre-flight global y escritura atómica [5h]

**Archivos nuevos**:
- `server/backends/native_backend.py` — método `ingest_atomic(board_id, source_data)`:
  ```
  async with pool.acquire() as conn:
      async with conn.transaction():
          # fase 1: US (+ módulo best-effort)
          # fase 2: UC (+ AC en el mismo conn) preservando state
          # fase 3: comments
  ```
  Reutiliza las mismas sentencias INSERT que `_insert_us/_uc/_ac` y `create_acceptance_criteria`,
  pero **sobre el `conn` de la transacción** (no `pool.acquire()` por item). Cualquier excepción
  propaga → la transacción hace rollback total (AC-10). Devuelve `{migrated:{us,uc,ac}, skipped}`.
  Re-valida membresía/identidad al entrar (cubre TTL expirado en migración lenta — riesgo del PRD).
- `server/migration/writer.py` — helper puro `build_write_plan(source_data)` que extrae la lógica
  de clasificación + resolución de parent + orden de `write_target` (hoy inline en el bucle) a una
  estructura de datos (`[US...], [(UC, parent, [AC...])...], [comments...]`) sin I/O. `write_target`
  genérico lo usa internamente (refactor sin cambio de comportamiento); `ingest_atomic` lo consume.

**Archivos modificados**:
- `server/tools/migration.py` — tool `commit_migration_session(session_id, confirmed_count)`:
  1. Resuelve sesión + valida owner (`SESSION_NOT_FOUND` si no, AC-11).
  2. **Pre-flight global** (antes de cualquier INSERT):
     - `chunks_received == chunks_expected`,
     - `sha256_hex(reensamblado) == source_sha256`,
     - parsear con `FreeformBackend(items_content=reensamblado)` → contar items;
       `count == declared_items == confirmed_count`.
     - cualquier fallo → `PREFLIGHT_FAILED {reason}`, 0 INSERT (AC-09).
  3. `_read_source(FreeformBackend(...), board_id_freeform)` → `source_data`.
  4. `native_backend.ingest_atomic(target_project_id, source_data)` → escritura atómica;
     excepción → `COMMIT_FAILED {failing_phase, error}` con rollback ya hecho por la transacción (AC-10).
  5. Éxito → libera el staging (`SessionStore.close(session_id)`), devuelve
     `{status:'committed', migrated, skipped, target_id}` (AC-08, AC-11).
  6. Estados preservados: `ingest_atomic` escribe `uc.state` tal cual (no degrada a backlog) (AC-12).

**ACs**: AC-08, AC-09, AC-10, AC-11, AC-12.

**Tests**: `test_commit_*` contra Postgres real — commit OK escribe == source; preflight fallido
(hash/conteo) → 0 filas; fallo inyectado a mitad → 0 filas (rollback total); staging liberado;
estados done/backlog preservados 1:1.

---

### Fase 4 — UC-683: Integración con switch_project_backend y skill /switch-backend [2h]

**Archivos modificados**:
- `server/tools/migration.py` — `switch_project_backend` (target native, source freeform): cuando
  `len(source_content or "")` excede un umbral (`BATCH_TRANSPORT_THRESHOLD_BYTES`, ~64 KB) **o** el
  caller invoca la ruta por lotes, el paso `write_target` del orquestador (`orchestrator.run_switch`,
  `SwitchSteps.write_target`) se sustituye por una función que ejecuta el commit de la sesión por
  lotes ya acumulada (la sesión se abre/llena fuera, vía las tools, y el switch referencia su
  `session_id`). El resto del orquestador (count guard, ensure_target, seed_identity, apply_switch
  de los 3 lugares de config, native_exit_report, rollback) queda **sin cambios** — la atomicidad
  global ya la garantiza `run_switch` (AC-13, AC-14).
  - Si la ingesta devuelve `PREFLIGHT_FAILED`/`COMMIT_FAILED`, `SwitchSteps.write_target` lanza →
    `run_switch` entra en `_rollback`, NO toca config (AC-14).
- `.claude/skills/switch-backend/SKILL.md` — añadir el modo "source freeform grande": el skill
  (1) lee el `items.json` del cliente, (2) calcula `sha256` + nº de chunks (≤16 KB cada uno),
  (3) muestra al usuario el **plan de transporte** (nº chunks, tamaño, hash) antes de ejecutar,
  (4) ejecuta `start_migration_session → append_migration_chunk × N → commit_migration_session`,
  (5) encadena el `switch_project_backend` referenciando la sesión, (6) muestra **resumen
  post-commit** (US/UC/AC migrados, estados preservados). Nunca pide al usuario pegar el blob (AC-15).

**ACs**: AC-13, AC-14, AC-15.

**Tests**: `test_switch_uses_batch_route_*` — switch con source grande usa la ruta por lotes y
solo cambia config si commit OK; ingesta fallida → 0 cambios de config.

---

### Fase 5 — UC-684: E2E de transporte con items.json de tamaño real [1h]

**Archivos nuevos**:
- `tests/test_native_batch_ingestion.py` (sección E2E) + fixture
  `tests/fixtures/large_items.json` (o generador in-test) ≥100 KB con ≥100 UC de estados mixtos
  done/backlog.

**Test E2E** (gated por Postgres dev, como la suite native existente):
- `test_e2e_large_source_roundtrip` (AC-16): genera/carga items.json ≥100 KB, lo trocea en ≥4
  chunks reales, ejecuta `start → append × N → commit` contra Postgres, asserta conteo US/UC/AC
  en Postgres == source y estados done/backlog 1:1.
- `test_e2e_atomicity_and_retry` (AC-17): inyecta fallo a mitad del commit (chunk corrupto que
  falla preflight, y un fallo de constraint a mitad de `ingest_atomic`), asserta 0 filas
  (rollback total), luego reintenta con sesión limpia y asserta reconstrucción completa.

**Este test es el que faltaba** (los actuales usan `CLIENT_11_88` en memoria) y por el que el gap
no se detectó — cruza el camino real de transporte por lotes con un source de tamaño real.

**ACs**: AC-16, AC-17.

---

## Orden de ejecución y dependencias

```
UC-680 (sesión + identidad)
   └── UC-681 (staging chunks)        [depende de la sesión]
          └── UC-682 (commit atómico) [depende de staging + ingest_atomic]
                 ├── UC-683 (switch integration) [depende del commit]
                 └── UC-684 (E2E)                [depende de todo lo anterior]
```

Secuencial. UC-682 es el corazón (gaps #3 + #4). UC-680/681 son el transporte (gaps #1 + #2).

## Archivos a Crear/Modificar

```
server/
├── migration/
│   ├── batch_session.py        # NUEVO — MigrationSession + SessionStore (staging memoria + TTL)
│   ├── integrity.py            # NUEVO — sha256_hex puro
│   └── writer.py               # MOD — extraer build_write_plan(source_data) puro
├── backends/
│   └── native_backend.py       # MOD — ingest_atomic(board_id, source_data) transaccional
└── tools/
    └── migration.py            # MOD — start_migration_session / append_migration_chunk /
                                #       commit_migration_session + switch_project_backend ruta lotes
.claude/skills/switch-backend/
    └── SKILL.md                # MOD — modo source freeform grande (plan de transporte + resumen)
tests/
├── test_native_batch_ingestion.py   # NUEVO — unit + E2E (AC-01..17)
└── fixtures/large_items.json        # NUEVO — source ≥100 KB / ≥100 UC mixtos (o generador in-test)
```

## Alternativas y Tradeoffs

| Decisión | Elegida | Descartada | Razón |
|----------|---------|-----------|-------|
| Staging | Dict en memoria + TTL | Tabla temporal Postgres | Menos infra, reusa más; staging efímero por diseño (discovery). |
| Reanudación | Descartar + reiniciar | Re-append a sesión viva | YAGNI v1; commit es el único punto que toca Postgres (discovery). |
| Transacción atómica | `ingest_atomic` en NativeBackend | Hilar conn por el ABC | Preserva abstracción multi-backend; rollback total real. |
| Tamaño de chunk | ≤16 KB | sin límite / gzip | Margen amplio bajo el techo de un parámetro; sin blob no verificable. |
| Verificación | SHA-256 por chunk + global | solo conteo | Detecta corrupción de transporte, no solo pérdida de ítems. |

## NFRs (del PRD)

Integridad (SHA-256 por chunk + global), atomicidad (rollback total), seguridad (dev_token
server-side, escritura solo en tenant, sin relajar deny_anon ni exponer service_role), 1 consulta
de identidad por sesión (reúso TTL), auditoría (audit_log en el commit).

## Riesgos (del PRD)

Staging perdido en reinicio MCP (mitigado: efímero, sin estado parcial en Postgres), transacción
larga sobre Pooler (mitigado: patrón probado + medido en E2E), colisión project_id (mitigado:
idempotencia write_target + on_collision), TTL identidad expira en migración lenta (mitigado:
re-validar en commit).

## Comandos finales

```bash
docker compose -f docker-compose.dev.yml up -d   # Postgres dev para E2E
uv run pytest tests/test_native_batch_ingestion.py -v
uv run pytest tests/test_native_*.py             # no-regresión suite native
gga run                                          # lint
```

## Referencias

- PRD: doc/prd/US-NATIVE-BATCH-INGEST_prd.md
- Hallazgo origen: HALLAZGO-v6.9.2-transporte-source-grande.md
- Código reutilizado: native_backend.py:421-604 (create_item/_insert_*), :844-879
  (create_acceptance_criteria transaction), db/pool.py:157-168 (pool), identity.py:400-428
  (auth cached), migration.py:75 (FreeformBackend memory-mode), writer.py:70-171 (write_target).
- No-regresión dogfooding: specbox_cloud 13 US / 89 UC / 466 AC (85 done / 4 backlog),
  backup en `.quality/dogfood-backup/native-project-backup-pre-delete.json` (repo del panel).
```

