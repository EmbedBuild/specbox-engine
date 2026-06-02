# PRD: [US-NATIVE-BATCH-INGEST] Ingesta por lotes de sources grandes a Native

> Origen: FreeForm board `ff-ed0c02f4565a` (specbox-engine) | US-NATIVE-BATCH-INGEST
> Discovery: doc/discovery/native_batch_ingestion/icp_jtbd.md (disc-9409945c825b, READY_FOR_PRD)
> Generado: 2026-06-02

## Resumen

Migrar un proyecto freeform real a Native (SpecBox Cloud) se bloquea en el **transporte**:
`switch_project_backend` con `source_type='freeform'` exige el `items.json` completo como **un
único string** (`source_content`), y un board no trivial (`specbox_cloud`: 133 KB / 568 ítems)
no cabe fiablemente en un parámetro de tool sin riesgo de truncado/corrupción silenciosa. El MCP
es **siempre remoto** desde v6.7.0 (no ve el filesystem del cliente). La **lógica** del switch
v6.9.1 funciona (lee el source del cliente, detecta drift, preserva estados); el **transporte**
no escala a sources reales. Es el **modo por defecto** del producto: cliente local + MCP remoto
+ board de tamaño real.

Esta US resuelve el transporte como **ingesta por lotes server-side**: una sesión de migración
multi-llamada (`start → append_chunk × N → commit`) donde el cliente envía el `items.json` en
chunks pequeños y verificables, el servidor los acumula en una zona de staging server-side, y al
commit verifica integridad global (hash + conteo declarado) **antes** de ingestar en **una
transacción atómica** reutilizando los INSERT item-por-item que el engine ya tiene. El chunking
es solo del **transporte**; la **escritura** sigue siendo todo-o-nada (commit al final, rollback
total ante fallo a mitad). No relaja el blindaje de seguridad (identidad validada server-side,
escritura solo en el tenant, audit).

## Alcance

### Incluye
- Orquestador de **sesión de migración multi-llamada** server-side que mantiene el `dev_token`
  validado (caché TTL) y acumula chunks entre requests (gap #1).
- **Zona de staging server-side** (dict en memoria por `session_id`, efímera con TTL) donde se
  acumulan los chunks hasta el commit (gap #2).
- **Transacción envolvente en `write_target`**: las 3 fases (US, UC+AC, comments) dentro de
  `async with pool.acquire() as conn: async with conn.transaction():` para atomicidad real —
  hoy un fallo de item hace `continue`, no rollback (gap #3). Solo aplica al target Native.
- **Commit diferido**: reensamblar el staging, verificar hash + conteo declarado, alimentar
  `FreeformBackend(items_content=reensamblado)` → `_read_source` → `write_target` atómico;
  rollback total + limpieza de staging ante cualquier fallo (gap #4).
- **Pre-flight**: el cliente declara al `start` cuántos ítems/bytes y un hash del `items.json`
  completo; el commit verifica conteo y hash recibidos == declarados antes de escribir nada.
- **Integración con `switch_project_backend`**: la ingesta por lotes es el paso "write_target"
  de la operación atómica; el switch de los 3 lugares de config sigue al final, sin cambios.
- **E2E de tamaño real**: un test que cruza un `items.json` ≥100 KB por lotes por el camino
  real cliente→servidor (no fixture en memoria), verificando resultado Postgres == source,
  estados preservados, atómico.

### No incluye
- **Reanudación** de una sesión cortada a medias (gap explícito): el staging es efímero; una
  sesión incompleta se descarta y el cliente reinicia desde `start`. (Decisión de discovery:
  YAGNI para v1; el commit es el único punto que toca Postgres.)
- **Streaming / upload a tabla temporal Postgres** (Opción A del hallazgo): se descartó por más
  infraestructura; el staging en memoria reutiliza más de lo existente.
- **Compresión gzip+base64** (Opción C): paliativo, reintroduce el blob no verificable.
- Cambios en el transporte de sources **trello/plane/native** (esos viven detrás de una API que
  el server alcanza directamente — solo `freeform` cruza por `source_content`).
- Migración del skill `/switch-backend` UX más allá de cablear la nueva sesión por lotes para
  sources freeform grandes.

---

## User Story

**ID**: US-NATIVE-BATCH-INGEST
**Nombre**: Ingesta por lotes de sources grandes a Native
**Actor**: Owner-operator (ICP-1) y equipo/agencia migrando a Native Cloud (ICP-3)
**Horas estimadas**: 14h
**Pantallas**: ninguna (feature de backend / MCP server, sin UI)

> Como dev que migra su proyecto freeform a SpecBox Cloud (Native), quiero subir un `items.json`
> de tamaño real por lotes verificables sin transcribirlo a mano, para que el board en Postgres
> sea byte-fiel a mi source, con escritura atómica y rollback total ante fallo.

---

## Use Cases

### UC-680: Sesión de migración multi-llamada con dev_token cacheado
- **Actor**: Owner-operator / equipo (ICP-1, ICP-3)
- **Horas**: 3h
- **Estado**: backlog
- **JTBD**: JR-FNBI.1, JR-FNBI.3
- **Gap cubierto**: #1 (orquestador de sesión multi-llamada)

Tool MCP `start_migration_session(target_project_id, source_type, declared_items, declared_bytes,
source_sha256, chunk_count)` que abre una sesión server-side: valida el `dev_token` UNA vez vía
`authenticate_and_authorize_cached` (reúsa caché TTL 30s para los N appends siguientes sin
re-consultar Postgres), registra el pre-flight declarado, devuelve un `session_id`. La sesión
queda asociada al developer autenticado y al `target_project_id` (tenant).

#### Acceptance Criteria
- [ ] **AC-01**: `start_migration_session` con `source_type='freeform'`, `declared_items=568`,
  `chunk_count=6` y un `dev_token` válido devuelve `{session_id, status:'open', declared_items:568,
  chunks_expected:6, chunks_received:0}` y NO escribe nada en la tabla `user_stories`/`use_cases`/
  `acceptance_criteria` del proyecto (verificable con `SELECT count(*)` == estado previo).
- [ ] **AC-02**: `start_migration_session` con un `dev_token` ausente o inválido devuelve un
  envelope `{status:'UNAUTHENTICATED', code, message}` sin abrir sesión (fail-fast antes de
  cualquier I/O de staging), reutilizando el contrato `require_dev_token` existente.
- [ ] **AC-03**: tras un `start` exitoso, una segunda tool de la misma sesión (`append_chunk`)
  reutiliza la identidad cacheada sin re-consultar `mcp_tokens` JOIN `developers` (verificable
  por conteo de queries de identidad: 1 en el `start`, 0 en los appends dentro del TTL).

### UC-681: Staging server-side de chunks con verificación por chunk
- **Actor**: Owner-operator / equipo (ICP-1, ICP-3)
- **Horas**: 3h
- **Estado**: backlog
- **JTBD**: JR-FNBI.3, JE-FNBI.1
- **Gap cubierto**: #2 (zona de staging server-side)

Tool MCP `append_migration_chunk(session_id, chunk_index, chunk_data, chunk_sha256)` que acumula
el fragmento en una zona de staging en memoria indexada por `session_id`. Verifica el hash del
chunk recibido contra `chunk_sha256` declarado; rechaza con error claro si no coincide (transporte
corrupto detectado en el chunk, no a mitad de la escritura). El staging es efímero (TTL); no
persiste en Postgres.

#### Acceptance Criteria
- [ ] **AC-04**: `append_migration_chunk` con `chunk_index=0`, `chunk_data` cuyo SHA-256 == el
  `chunk_sha256` declarado devuelve `{status:'accepted', chunks_received:1, chunks_expected:N}` y
  acumula el fragmento en el staging de esa `session_id`.
- [ ] **AC-05**: `append_migration_chunk` cuyo SHA-256 calculado del `chunk_data` NO coincide con
  el `chunk_sha256` declarado devuelve `{status:'CHUNK_HASH_MISMATCH', chunk_index, expected,
  actual}` y NO incrementa `chunks_received` ni acumula ese fragmento corrupto.
- [ ] **AC-06**: `append_migration_chunk` con un `session_id` inexistente o ya cerrado devuelve
  `{status:'SESSION_NOT_FOUND'}` sin crear staging implícito.
- [ ] **AC-07**: enviar dos chunks distintos con el mismo `chunk_index` en la misma sesión hace
  que el segundo devuelva `{status:'DUPLICATE_CHUNK_INDEX', chunk_index}` sin sobrescribir el
  primero (el orden y unicidad de los N chunks queda garantizado para el reensamblado).

### UC-682: Commit diferido con pre-flight global y escritura atómica
- **Actor**: Owner-operator / equipo (ICP-1, ICP-3)
- **Horas**: 5h
- **Estado**: backlog
- **JTBD**: JR-FNBI.1, JR-FNBI.2, JR-FNBI.3, JE-FNBI.1, JE-FNBI.2
- **Gap cubierto**: #3 (transacción envolvente) + #4 (commit diferido + rollback)

Tool MCP `commit_migration_session(session_id, confirmed_count)` que: (1) reensambla los N chunks
en orden; (2) verifica que `chunks_received == chunks_expected` y que el SHA-256 del reensamblado
== `source_sha256` declarado al `start` y que el conteo de ítems parseados == `declared_items` y
== `confirmed_count` — **antes de escribir nada**; (3) construye `FreeformBackend(items_content=
reensamblado)`, lee con `_read_source`, y llama un `write_target` **transaccional** (las 3 fases
dentro de una sola `conn.transaction()` del pool asyncpg) → atomicidad real; (4) limpia el staging.
Cualquier fallo en (2)-(3) aborta sin escritura parcial (rollback de la transacción) y deja un
mensaje accionable.

#### Acceptance Criteria
- [ ] **AC-08**: con todos los chunks de un `items.json` real recibidos y el SHA-256 reensamblado
  == `source_sha256` declarado y conteo == `declared_items`, `commit_migration_session` devuelve
  `{status:'committed', migrated:{us,uc,ac}, skipped, target_id}` y Postgres contiene exactamente
  los US/UC/AC del source (conteo igual al source).
- [ ] **AC-09**: si `chunks_received < chunks_expected` o el SHA-256 reensamblado != `source_sha256`
  o el conteo parseado != `declared_items`/`confirmed_count`, `commit_migration_session` devuelve
  `{status:'PREFLIGHT_FAILED', reason}` y NO ejecuta ningún INSERT (verificable: el conteo de
  filas en Postgres es idéntico al previo al commit).
- [ ] **AC-10**: si un INSERT de la fase UC+AC falla a mitad (p.ej. violación de constraint
  inyectada en el test), la transacción envolvente hace **rollback total**: Postgres queda sin
  ninguna fila del proyecto migrado (ni siquiera las US de la fase 1 que ya se habían insertado),
  y la tool devuelve `{status:'COMMIT_FAILED', failing_phase, error}`.
- [ ] **AC-11**: tras un `commit` exitoso, el staging de esa `session_id` se libera (un segundo
  `append_migration_chunk` o `commit` sobre la misma sesión devuelve `{status:'SESSION_NOT_FOUND'}`).
- [ ] **AC-12**: los estados de los UC se preservan en el commit (un UC `done` en el source queda
  `done` en Postgres, un UC `backlog` queda `backlog`) — `write_target` no degrada estados a
  backlog.

### UC-683: Integración con switch_project_backend y skill /switch-backend
- **Actor**: Owner-operator / equipo (ICP-1, ICP-3)
- **Horas**: 2h
- **Estado**: backlog
- **JTBD**: JR-FNBI.2, JE-FNBI.2
- **Gap cubierto**: encaje con el switch atómico existente

`switch_project_backend` (target native, source freeform grande) usa la sesión por lotes como su
paso `write_target` dentro del orquestador atómico (`run_switch`): la ingesta sustituye al
`write_target` directo cuando el source excede el techo de `source_content`; el switch de los 3
lugares de config y el `native_exit_report` siguen al final sin cambios. El skill `/switch-backend`
detecta el tamaño del source y, si excede el umbral, trocea el `items.json` del cliente en chunks,
ejecuta `start → append × N → commit`, y luego completa el switch.

#### Acceptance Criteria
- [ ] **AC-13**: `switch_project_backend(source_type='freeform', target_type='native')` con un
  source que excede el umbral de transporte usa la ruta de ingesta por lotes (sesión start/append/
  commit) como paso de escritura, y el orquestador atómico completa el switch de los 3 lugares de
  config solo si el commit fue `committed` (verificable: config destino == native solo cuando la
  ingesta tuvo éxito).
- [ ] **AC-14**: si la ingesta por lotes falla (PREFLIGHT_FAILED o COMMIT_FAILED), el orquestador
  NO cambia ningún lugar de config (la operación atómica se mantiene: o todo, o nada) y reporta el
  fallo de la ingesta como `failing_step`.
- [ ] **AC-15**: el skill `/switch-backend`, ante un `items.json` de tamaño real, reporta al
  usuario un plan de transporte por lotes (nº de chunks, tamaño, hash) antes de ejecutar, y un
  resumen post-commit (US/UC/AC migrados, estados preservados) — sin pedir al usuario que pegue el
  blob de 133 KB.

### UC-684: E2E de transporte con items.json de tamaño real
- **Actor**: Owner-operator (ICP-1)
- **Horas**: 1h
- **Estado**: backlog
- **JTBD**: JR-FNBI.1, JE-FNBI.1
- **Gap cubierto**: cierra el agujero de test que ocultó el gap

Test E2E en `tests/test_native_batch_ingestion.py` que reproduce el caso real: un `items.json`
≥100 KB (cientos de ítems con estados mixtos done/backlog) troceado en chunks reales, cruzando el
camino completo `start_migration_session → append_migration_chunk × N → commit_migration_session`
contra Postgres real (docker-compose.dev), verificando que el resultado en Postgres == source del
cliente. NO usa fixtures pequeñas en memoria (`CLIENT_11_88`) — usa un source de tamaño real, que
es lo que faltaba y por lo que el gap no se detectó.

#### Acceptance Criteria
- [ ] **AC-16**: existe un test que genera (o carga) un `items.json` ≥100 KB con ≥100 UC de
  estados mixtos, lo trocea en ≥4 chunks, los envía por la sesión por lotes, y asserta que el
  conteo de US/UC/AC en Postgres == el del source y que los estados done/backlog se preservan
  uno-a-uno.
- [ ] **AC-17**: el mismo test asserta atomicidad inyectando un fallo a mitad del commit
  (constraint o chunk corrupto) y verificando que Postgres queda sin filas del proyecto (rollback
  total), y que un reintento limpio (nueva sesión) reconstruye el proyecto completo.

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medición |
|-----|----------|----------|
| Integridad de transporte | Cero corrupción silenciosa: todo chunk y el reensamblado se verifican por SHA-256 antes de escribir | Test AC-05, AC-09 |
| Atomicidad | Escritura todo-o-nada: fallo a mitad → 0 filas | Test AC-10, AC-17 |
| Seguridad | dev_token validado server-side al start; escritura solo en el tenant del developer; no se relaja `deny_anon` ni se expone `service_role` | Test AC-02; revisión de que no hay nuevos paths anónimos |
| Tamaño de chunk | Chunk recomendado ≤ ~16 KB (margen amplio bajo el techo de un parámetro de tool); documentado | Doc en el plan + default del skill |
| Caché de identidad | 1 sola consulta de identidad por sesión (reúso TTL para N appends) | Test AC-03 |
| Auditoría | El commit registra fila en `audit_log` como cualquier mutación native | Verificación post-commit |

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Staging en memoria se pierde si el proceso MCP reinicia a mitad | Media | Bajo | Staging efímero por diseño: la sesión se descarta y el cliente reinicia (no hay estado parcial en Postgres). Documentado como decisión. |
| Transacción larga sobre Supabase Pooler con cientos de INSERT | Media | Medio | Reusar el patrón `conn.transaction()` ya probado (native_backend.py:854); medir con el E2E de 100 KB; si hay timeout, el rollback es limpio. |
| Colisión de `project_id` destino entre sesiones concurrentes | Baja | Medio | El commit verifica idempotencia (write_target ya hace skip por us_id/uc_id); colisión de proyecto ya existente se resuelve vía `on_collision` del switch existente. |
| TTL de identidad (30s) expira en una migración lenta multi-chunk | Baja | Bajo | Re-validar identidad en el commit (no solo en el start); el TTL solo evita re-consultas en appends rápidos. |

## Stack Técnico (estimado)

- **Lenguaje**: Python (FastMCP), tests pytest contra Postgres real (docker-compose.dev.yml).
- **Módulos nuevos**: `server/migration/batch_session.py` (orquestador de sesión + staging),
  tools en `server/tools/migration.py` (`start_migration_session`, `append_migration_chunk`,
  `commit_migration_session`).
- **Módulos modificados**: `server/migration/writer.py` (write_target transaccional opcional para
  native), `server/tools/migration.py` (switch_project_backend usa la ruta por lotes), skill
  `.claude/skills/switch-backend/SKILL.md`.
- **Reutiliza**: `native_backend.create_item`/`_insert_*` (421-604), `asyncpg.Pool`
  (db/pool.py:157-168), `create_acceptance_criteria` transaction pattern (854),
  `FreeformBackend(items_content=)` (migration.py:75), `authenticate_and_authorize_cached`
  (identity.py:400-428), `write_target` (writer.py:70-171).

## Dependencias
- Postgres dev local (`docker compose -f docker-compose.dev.yml up`) para el E2E AC-16/AC-17.
- Backend Native ya existente (NativeBackend ABC + schema multi-tenant).

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)
- [ ] **AC-01**: `start_migration_session` abre sesión sin escribir, devuelve session_id + pre-flight.
- [ ] **AC-02**: `start_migration_session` fail-fast con dev_token inválido (UNAUTHENTICATED).
- [ ] **AC-03**: identidad cacheada — 1 consulta en start, 0 en appends dentro del TTL.
- [ ] **AC-04**: `append_migration_chunk` con hash correcto acumula y devuelve chunks_received.
- [ ] **AC-05**: `append_migration_chunk` con hash incorrecto → CHUNK_HASH_MISMATCH, no acumula.
- [ ] **AC-06**: `append_migration_chunk` con session_id inexistente → SESSION_NOT_FOUND.
- [ ] **AC-07**: chunk_index duplicado → DUPLICATE_CHUNK_INDEX, no sobrescribe.
- [ ] **AC-08**: `commit_migration_session` con integridad OK escribe US/UC/AC == source.
- [ ] **AC-09**: commit con pre-flight fallido → PREFLIGHT_FAILED, 0 INSERT.
- [ ] **AC-10**: fallo a mitad del commit → rollback total (0 filas), COMMIT_FAILED.
- [ ] **AC-11**: tras commit exitoso, staging liberado (SESSION_NOT_FOUND en reuso).
- [ ] **AC-12**: estados UC preservados (done queda done, backlog queda backlog).
- [ ] **AC-13**: switch_project_backend usa la ruta por lotes cuando el source excede el umbral.
- [ ] **AC-14**: ingesta fallida → 0 cambios de config (operación atómica).
- [ ] **AC-15**: skill /switch-backend reporta plan de transporte y resumen sin pedir el blob.
- [ ] **AC-16**: E2E con items.json ≥100 KB / ≥100 UC mixtos → Postgres == source, estados 1:1.
- [ ] **AC-17**: E2E de atomicidad — fallo a mitad → 0 filas; reintento limpio reconstruye todo.

### Técnicos (no validados por AG-09)
- [ ] Proyecto pasa la suite native (`tests/test_native_*.py`) sin regresión.
- [ ] Tests nuevos con cobertura del orquestador de sesión y el commit transaccional.
- [ ] Lint GGA verde.

---
**Prioridad**: high
**Complejidad**: Media
*Generado: 2026-06-02*
**VEG Readiness**: DISABLED (feature de backend, sin UI)
