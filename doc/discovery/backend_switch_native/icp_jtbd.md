# Discovery: backend_switch_native

**Discovery ID**: disc-558168870723
**Created**: 2026-06-02T19:34:29.156128+00:00
**Status**: READY_FOR_PRD
**Mode**: standard
**Source of inheritance**: doc/app/app_market.md @ 1a9bb8a4e6a524eb

> Discovery honesto del caso de uso **"cambiar el backend de tracking de un
> proyecto"** hacia/desde el backend `native` (SpecBox Cloud / Postgres),
> partiendo del PRINCIPIO RECTOR: una **operación única, atómica y completa**,
> con **matriz origen×destino** como contrato y el **path-bug de MCP remoto
> resuelto dentro** de esa operación (el source nunca se lee del filesystem del
> servidor). Basado en reproducción real en dogfooding (2026-06-02), no teoría.

---

## ICPs involucrados

Heredados de `doc/app/app_market.md` (sin ICPs nuevos → ver "Drift").

### ICP-1: Owner-operator del engine (JPS, dogfooding) — **PRIMARIO de esta feature**
- **Por qué aplica**: el bug se reprodujo operando SpecBox **como cliente real**
  sobre SpecBox Cloud. El owner tiene un proyecto en freeform local cuyo panel
  Cloud lee de Postgres native; las dos fuentes no se reconcilian. Es quien sufre
  el limbo de estados rotos y quien lo va a arreglar.
- **Estado**: canónico.

### ICP-3: Equipo/agencia que sube su proyecto a Cloud
- **Por qué aplica**: el caso de uso "tengo mi proyecto en local (freeform/trello/
  plane) y quiero subirlo a SpecBox Cloud para colaboración multi-dev / reporting"
  es exactamente el flujo destino=native. La salida de native (volver a un backend
  local/externo) también es su caso.
- **Estado**: tentative (real esperado v2 con Native multi-dev), pero la
  infraestructura del switch debe estar correcta ya en v1 porque el owner la usa.

### No involucra
- **ICP-2 (dev solo que adopta SpecBox)**: típicamente se queda en freeform; no
  necesita native salvo que quiera Cloud. No es el driver de esta feature.

---

## JTBDs racionales

- **JR-Fbsn.1 [ICP-1, ICP-3]**: Cuando decido subir mi proyecto local a SpecBox
  Cloud, quiero emitir **una sola orden** ("pasa mi proyecto a Cloud") y que el
  sistema ejecute **toda la cadena** (auth → leer source del cliente → crear
  proyecto en Postgres → copiar US/UC/AC preservando estados → asociar developer →
  conmutar el backend activo) de forma transaccional, para no tener que encadenar
  a mano `migrate_backend` + `seed_native_identity` + `switch_backend` y arriesgar
  un estado a medias.

- **JR-Fbsn.2 [ICP-1]**: Cuando hago un dry-run de la migración con el MCP remoto,
  quiero que el preview lea el source **de mi repo local** (no del filesystem del
  servidor VPS) y me afirme **"N US / M UC leídas del cliente"**, para confirmar
  ese conteo antes de tocar la base productiva y no escribir un proyecto vacío (o
  el del engine) en Postgres.

- **JR-Fbsn.3 [ICP-1, ICP-3]**: Cuando la migración a native preserva los estados
  de mis US/UC, quiero que el panel Cloud muestre el progreso real (no todo en
  `backlog`), para que la migración refleje el avance verdadero y no degrade el
  trabajo a "todo por empezar".

- **JR-Fbsn.4 [ICP-3]**: Cuando saco un proyecto de Cloud hacia un backend local,
  quiero un **reporte auditable de lo que se descarta** (reservas, membresías,
  audit log, coordinación multi-dev que no tiene destino en freeform/trello/plane),
  para saber exactamente qué pierdo antes de confirmar y no descubrirlo después.

- **JR-Fbsn.5 [ICP-1]**: Cuando falta el `dev_token` que exige native, quiero que
  la operación **falle pronto y con mensaje claro** (antes de leer/escribir nada),
  para no quedar a mitad de una escritura parcial en Postgres.

- **JR-Fbsn.6 [ICP-1]**: Cuando el proyecto ya existe en native (idempotencia /
  colisión de project_id), quiero que la operación lo detecte y me diga qué va a
  pasar (re-usar / fallar / merge), para no duplicar ni pisar datos productivos.

## JTBDs emocionales

- **JE-Fbsn.1 [ICP-1]**: Confianza de que la operación es **todo-o-nada**. Tras
  reproducir el limbo (config dice "native" pero la BD vacía / datos en BD pero
  config en freeform), quiero la certeza de que al terminar **o queda todo bien o
  no queda nada a medias** — sin estados huérfanos que el panel muestre rotos.
  (Materializa JE-G.1: "nada se pierde / nada queda inconsistente".)

- **JE-Fbsn.2 [ICP-1]**: Sentir que el sistema **no me deja dispararme en el pie**
  con datos productivos. El dry-run que lee el source equivocado y me dejaría
  ejecutar el real es justo el tipo de improvisación bajo presión que los guard
  rails deben impedir mecánicamente. (Materializa JE-G.2.)

---

## Validation evidence

**[d] Datapoint / reproducción real (2026-06-02, dogfooding sobre SpecBox Cloud):**

1. Proyecto en **freeform** (tracking en `doc/tracking/*.md` del cliente) cuyo
   panel Cloud lee de **Postgres native**. Dos fuentes sin reconciliar: una US
   creada por `/prd` en freeform **nunca llega a la BD** → el panel no la ve. La
   BD se pobló **una vez a mano** vía `import_spec` en un smoke-test.

2. `migrate_backend(source_type='freeform', source_id='.', target_type='native',
   dry_run=True)` leyó el filesystem del **servidor MCP remoto** (`/app/...`):
   - Una sesión → **22 US / 112 UC** (el tracking del *engine*, que vive en el
     disco del servidor), no las 11 US / 88 UC del panel.
   - Otra sesión con `.` → **0 / 0** (directorio vacío del servidor).
   - En ambos: **`source_id='.'` se resolvió contra el CWD del servidor remoto.**
     `dry_run=False` habría escrito un proyecto vacío (o el del engine) en native,
     y luego `switch_backend` habría apuntado el panel a la nada.

3. La skill `/switch-backend` tiene hoy una **precondición BLOQUEANTE "MCP local"**
   (`.claude/skills/switch-backend/SKILL.md:25-38`): en vez de soportar el
   escenario MCP remoto, **se rinde ante él**. El modo de despliegue por defecto
   (online-first, v6.7+) es precisamente MCP remoto → la skill no cubre el caso real.

**Backup de no-regresión disponible**: el proyecto dogfood `EmbedBuild/specbox_cloud`
está vacío en Supabase (borrado en diagnóstico, backup en
`specbox_cloud/.quality/dogfood-backup/native-project-backup-pre-delete.json`:
10 US / 84 UC / 440 AC / 8 audit / 1 membership). Su tracking freeform local tiene
**11 US / 88 UC** (incluye US-13 nueva). Un `migrate freeform→native` correcto DEBE
leer **11 US / 88 UC del cliente** y reconstruir el proyecto con developer
`jesusperezdeveloper` como project_admin y estados preservados.

No waiver: es feature interna del engine con evidencia reproducible de primera mano.

---

## Drift from app_market

- **Nuevos ICPs introducidos**: ninguno. Hereda ICP-1 (primario) e ICP-3.
- **Nuevos JTBDs introducidos**: JR-Fbsn.1..6 y JE-Fbsn.1..2 son **especializaciones**
  de los globales (JR-G.1 trazabilidad, JR-G.2 recuperar contexto sin perder estado,
  JR-G.3 enforcement mecánico, JE-G.1 nada se pierde, JE-G.2 agente con disciplina).
  No abren mercado nuevo ni contradicen los no-ICPs.
- **Resolución**: **no_drift**. La feature es infraestructura interna que sirve a
  los ICPs y JTBDs canónicos ya documentados.

---

## Restricciones del discovery (constraints duros)

1. **MCP remoto + cliente local es el modo por defecto** (online-first, v6.7+).
   Cualquier resolución de `source_id='.'` o `project_path='.'` contra el servidor
   es un bug. El source freeform/trello/plane DEBE llegar por **content-passing** o
   por **path absoluto resuelto en cliente** (reusar `detect_local_root_path`).
2. **Datos productivos**: la operación toca una BD real. Necesita dry-run fiable
   (que lea el source correcto), preview con conteo confirmable, idempotencia y
   rollback total.
3. **Identidad**: native exige `dev_token` (lo emite el panel Cloud). El flujo
   falla pronto y con mensaje claro si falta, no a mitad de escritura.
4. **Coherencia con decisiones canónicas del Cloud**: el panel NO hace CRUD de
   specs; el `service_role` solo vive en la API; el front nunca escribe Postgres.
   El sync lo hace el **engine/MCP**, no la app.

---

## Decisiones de producto cerradas con el owner (2026-06-02)

| # | Decisión | Resolución |
|---|----------|-----------|
| D1 | Interfaz pública del switch | **Una sola operación atómica**: la skill `/switch-backend` (o una tool nueva) ejecuta `migrate` + `seed` + `switch` + `exit-report` como **pasos internos**. Dejan de ser interfaz pública que el usuario encadena y puede olvidar. |
| D2 | Qué hacer con coordinación al salir de native | **Descartar + reporte auditable**: reservas/membresías/audit/coordination se descartan (no hay destino en backends single-user), pero se vuelca el `native_exit_report` con todo lo descartado y el usuario lo ve antes de confirmar. |
| D3 | Guard rail del dry-run | **Confirmación de conteo obligatoria**: el dry-run reporta "N US / M UC leídas del cliente"; el usuario DEBE confirmar ese conteo antes de permitir `dry_run=False`. Si lee 0 o un conteo inesperado → avisar y bloquear el real. |

---

## Casos límite (edge cases a cubrir en el PRD/plan)

| EC | Escenario | Comportamiento esperado |
|----|-----------|-------------------------|
| EC-1 | MCP remoto + `source_id='.'` (freeform) | El source se lee del **cliente** (content-passing o path absoluto resuelto en cliente vía `detect_local_root_path`), nunca del FS del servidor. |
| EC-2 | Dry-run lee 0 US / 0 UC | Bloquear el execute. "Leí 0 items del source — probablemente el path no es el de tu repo. No ejecuto el real." |
| EC-3 | Dry-run lee un conteo inesperado (p.ej. el del engine, 22/112) | Mostrar el conteo y exigir confirmación literal; si el usuario lo rechaza, abortar. |
| EC-4 | Falta `dev_token` (destino native) | Fallar **antes** de leer/escribir: "native requiere dev_token del panel Cloud." |
| EC-5 | project_id ya existe en native | Idempotencia: detectar colisión y decidir explícitamente (re-usar UPSERT `ON CONFLICT` ya existe en `setup_board`, pero los items podrían duplicarse → resolver merge vs skip vs fail). |
| EC-6 | Estados de US/UC en migración a native | **Preservar** (no degradar a backlog). `write_target` ya preserva `state=item.state`; el "G11" es de `import_spec` (hardcodea `state="user_stories"/"backlog"`), no de `migrate_backend`. La operación unificada usa `write_target`, no `import_spec`. |
| EC-7 | Salida de native con reservas activas | Por D2 se descartan con reporte. (Considerar en PRD si conviene un warning extra cuando hay reservas vivas — pero la decisión cerrada es descartar+reporte, no bloquear.) |
| EC-8 | Fallo a mitad del switch transaccional (3 lugares) | Rollback total ya implementado en `apply_switch_transactional`; debe extenderse para que el **rollback abarque también la migración de datos** si el switch falla tras escribir Postgres (atomicidad end-to-end, no solo de los 3 flags). |
| EC-9 | `project_path='.'` en `switch_backend` con MCP remoto | Mismo bug que EC-1 en el lado de escritura de `app_spec.md` / `settings.local.json`: deben escribirse en el **cliente** (content-passing / write-back), no en el servidor. |
| EC-10 | Onboard directo a native | `onboard_project --backend native` deja "registry tiene el proyecto pero BD vacía". Cerrar el caso: o popula explícitamente, o documenta que requiere migrate/populate posterior. |

---

## Mapa "estado actual vs estado deseado" por pieza

| Pieza | Archivo:línea | Estado actual | Estado deseado |
|-------|---------------|---------------|----------------|
| `migrate_preview` | `server/tools/migration.py:110` | Lee vía `_read_source(get_session_backend(ctx), source_id)`. Source freeform/trello/plane se resuelve **en el servidor**. Solo trella↔plane semánticamente. | Acepta `source_content` (content-passing) **o** path absoluto resuelto en cliente. Reporta conteo confirmable del **cliente**. Cubre los 4 backends. |
| `migrate_backend` | `server/tools/migration.py:463` | N×N pero `source = _read_source(source_backend, source_id)` lee del **servidor**. dry_run/execute encadenados a mano con `switch_backend`. | Pasa a **paso interno** de la operación atómica. Source por content-passing. Execute solo tras confirmación de conteo. |
| `migrate_project` | `server/tools/migration.py:190` | Trello↔Plane legacy, mismo `_read_source`. | Reusar el writer content-passing; mantener compat o deprecar. |
| `_read_source` | `server/tools/migration.py:56` | `backend.list_items(board_id)` — para freeform el `board_id`/`'.'` es FS del servidor. **Raíz del bug.** | Refactor: recibe el **contenido** del source (items/AC/comments ya leídos por el cliente) o un backend cuyo root sea absoluto del cliente. Nunca FS del servidor. |
| `switch_backend` | `server/tools/migration.py:722` | `project_path='.'` → `apply_switch_transactional` escribe `app_spec.md`+`settings.local.json` **en el servidor**. Tool separada de migrate. | Paso interno. Escritura de los 3 lugares en el **cliente** (content-passing / write-back). Rollback que abarque también la migración de datos (EC-8). |
| `apply_switch_transactional` | `server/migration/transactional_switch.py` | Actualiza 3 lugares (registry/app_spec/settings) con rollback. Ya contempla native. Pero escribe FS del servidor. | Mantener la atomicidad de los 3 lugares; cliente provee/recibe el contenido de app_spec+settings. |
| `seed_native_identity` | `server/migration/native_handling.py:154` | Crea `developers` row + `add_project_member` (membership). Invocado solo en execute si target=native. | Paso interno de "→ native". Fallar pronto si falta dev_token (EC-4). |
| `collect_discarded_native_state` / `build_native_exit_report` | `server/migration/native_handling.py:40,131` | Leen reservas/developers/branches y producen exit-report. Invocados si source=native. | Paso interno de "native →". El reporte se muestra **antes** de confirmar (D2). |
| `setup_board` (native) | `server/backends/native_backend.py:~336` | UPSERT `ON CONFLICT` (idempotente a nivel proyecto). | Reusar. Resolver idempotencia a nivel **items** (EC-5). |
| `import_spec` | `server/tools/spec_driven.py:609,618,676` | Hardcodea `state="user_stories"/"backlog"` → **degrada estados** ("G11"). | **No** usar en la operación de switch (usar `write_target` que preserva estado). Documentar que `import_spec` es para bootstrap inicial, no para migración con avance. |
| `detect_local_root_path` | `server/tools/onboarding.py:478` | Handshake v6.0.1: `{is_remote_mcp, requires_absolute_path, default_relative_path, client_resolution_recipe, hook_helper}`. | **Reusar tal cual** como mecanismo de resolución de path en cliente cuando el source/target sea filesystem y el MCP remoto. |
| Skill `/switch-backend` | `.claude/skills/switch-backend/SKILL.md:25` | **Precondición BLOQUEANTE "MCP local"** → se rinde ante MCP remoto. | Soportar MCP remoto: leer source del cliente, escribir los 3 lugares en el cliente. La precondición desaparece o se invierte (online-first). |

---

## Verdict

**READY_FOR_PRD**

- ICPs identificados (ICP-1 primario, ICP-3) heredados de app_market, sin drift.
- JTBDs racionales (6) y emocionales (2) en formato canónico, trazables a globales.
- Validation evidence = datapoint reproducido de primera mano + backup de no-regresión.
- Drift resuelto como `no_drift`.
- Decisiones de producto cerradas (D1/D2/D3), 10 edge cases, mapa estado-actual-vs-deseado.

**Next step recomendado**: `/prd backend_switch_native`
