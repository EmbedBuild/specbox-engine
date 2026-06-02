# PRD: [US-BACKEND-SWITCH-NATIVE] Cambiar de backend como operación única, atómica y completa (hacia/desde Native)

> Origen: FreeForm board `ff-ed0c02f4565a` | Discovery: `doc/discovery/backend_switch_native/icp_jtbd.md` (READY_FOR_PRD)
> Tipo: PRD Técnico (refactor de fondo, no parche)
> Generado: 2026-06-02

## Resumen Ejecutivo

Hoy "cambiar el backend de tracking de un proyecto" está partido en **procesos
separados** que el usuario/agente encadena a mano: `migrate_backend` (copia datos)
+ `seed_native_identity` (asocia developer) + `switch_backend` (cambia el flag de
config) + helpers de salida (`collect_discarded_native_state`…). **Esa separación
es la causa raíz de los estados rotos** reproducidos en dogfooding (2026-06-02):
solo `switch` → config "native" pero BD vacía; solo `migrate` → datos en BD pero
config en freeform; orden equivocado → limbo inconsistente con rollback parcial.

Además, las tools de migración/switch **resuelven `source_id='.'` y `project_path='.'`
contra el filesystem del servidor MCP remoto**, no contra el repo del cliente. Un
`migrate_backend(freeform→native, dry_run=True)` leyó el tracking del *engine* en el
VPS (22 US / 112 UC) o un directorio vacío (0/0), nunca las 11 US / 88 UC del cliente.
Ejecutar el real habría escrito un proyecto vacío en Postgres y apuntado el panel
Cloud a la nada. Este path-bug **no está cubierto** por `US-MCP-PATH-CONTRACT` (que
portó 17 tools cat-A a content-passing pero excluyó migrate/switch).

Este refactor **rediseña "cambiar de backend" como UNA sola operación atómica y
completa**: el usuario emite una orden ("pasa mi proyecto a Cloud" / "saca mi
proyecto de Cloud") y el sistema ejecuta **internamente toda la cadena de
propagación** que ese origen×destino requiera, de forma transaccional, con
preview/dry-run fiable (que lee el source del **cliente**) y rollback total: o queda
todo bien, o no queda nada a medias. `migrate_backend` / `seed_native_identity` /
`switch` / helpers de salida pasan a ser **piezas internas**, no tools que el usuario
invoca por separado y puede olvidar. El path-bug se arregla **dentro** de esa
operación unificada vía content-passing.

## Objetivos

1. **Operación única atómica** — una sola entrada pública (`switch_project_backend` +
   skill `/switch-backend`) que orquesta migrate→seed→switch→exit-report como pasos
   internos, todo-o-nada con rollback end-to-end.
2. **Content-passing en migrate/switch** — el source freeform/trello/plane se lee del
   CONTENIDO que pasa el cliente, nunca del filesystem del servidor. `_read_source`,
   `migrate_preview`, `migrate_backend`, `switch_backend` refactorizados.
3. **Dry-run fiable con guard rail de conteo** — el preview afirma "N US / M UC leídas
   del cliente" y exige confirmación antes de `dry_run=False`; bloquea si lee 0 o un
   conteo inesperado.
4. **Flujo destino native end-to-end** — auth dev_token (fail-fast) → preview → crear
   proyecto + copiar US/UC/AC preservando estados → asociar developer → switch atómico,
   con idempotencia/colisión resueltas.
5. **Flujo origen native end-to-end** — leer Postgres como source vía DTO, manejar
   reservas/membresías/audit/coordination al salir (descartar + reporte auditable).
6. **E2E que reproduce el bug original** — migrar freeform-local → native con MCP
   remoto y confirmar que lee el conteo del CLIENTE, no del servidor.

---

## Estado Actual vs Propuesto

### ACTUAL (procesos separados, path-bug)

```
Usuario/agente encadena a mano:
  set_migration_target(...)
  migrate_backend(source_id='.', dry_run=True)   ← lee FS del servidor remoto (BUG)
  migrate_backend(source_id='.', dry_run=False)  ← escribe vacío/engine a Postgres
  [seed_native_identity interno solo si target=native]
  switch_backend(project_path='.')               ← escribe app_spec/settings en el servidor (BUG)
Resultado posible: limbo (config≠datos), rollback parcial, panel apuntando a la nada.
Skill /switch-backend: precondición BLOQUEANTE "MCP local" → se rinde ante MCP remoto.
```

### PROPUESTO (operación única atómica, content-passing)

```
Cliente (skill /switch-backend) lee su source local y llama UNA tool:
  switch_project_backend(
    project_slug, source_type, target_type,
    source_content=<items.json del cliente | DTO>,   ← content-passing
    app_spec_content=..., settings_content=...,       ← para el write-back de los 3 lugares
    dev_token=<si target/source native>,
    dry_run=True,
  )
  → preview fiable: "Leí 11 US / 88 UC del cliente" + degradaciones + exit-report (si native source)
Cliente confirma el conteo → switch_project_backend(..., dry_run=False, confirmed_count={us:11,uc:88})
  Internamente y transaccional:
    1. (target native) verificar dev_token → fail-fast si falta
    2. migrar datos (write_target, preserva estados) a Postgres / target
    3. (target native) seed_native_identity → developer como project_admin
    4. (source native) collect_discarded + build_native_exit_report
    5. switch transaccional de los 3 lugares (registry/app_spec/settings) — write-back al cliente
    6. rollback TOTAL si cualquier paso falla (incluida la migración de datos)
  → resultado: o todo bien, o nada a medias.
Skill /switch-backend: SIN precondición "MCP local" — online-first, lee/escribe el cliente.
```

---

## Matriz origen × destino (CONTRATO)

Cada celda define los pasos de propagación internos requeridos. `freeform/trello/plane`
son "locales/externos single-user"; `native` es Cloud/Postgres multi-dev.

| Origen \ Destino | freeform | trello | plane | **native** |
|------------------|----------|--------|-------|------------|
| **freeform** | (no-op) | leer source cliente → write_target | leer source cliente → write_target (degrada review/user_stories) | **auth dev_token → leer source cliente → setup_board Postgres → write_target (preserva estados) → seed developer → switch** |
| **trello** | leer Trello API → write_target → switch (freeform path absoluto cliente) | (no-op) | API→API | **auth dev_token → leer Trello API → Postgres → seed → switch** |
| **plane** | leer Plane API → write_target → switch | API→API | (no-op) | **auth dev_token → leer Plane API → Postgres → seed → switch** |
| **native** | leer Postgres DTO → write_target → **exit-report (descarta reservas/membresías/audit)** → switch | idem + exit-report | idem + exit-report | (no-op) |

**Pasos comunes a TODA celda no-trivial**: (a) source nunca del FS del servidor; (b)
dry-run con conteo confirmable; (c) switch transaccional de los 3 lugares con rollback;
(d) atomicidad end-to-end (datos + flags).

**Pasos específicos "→ native"**: auth dev_token (fail-fast), `setup_board` (UPSERT
`ON CONFLICT`), preservación de estados vía `write_target` (NO `import_spec`), seed del
developer como project_admin, idempotencia a nivel items.

**Pasos específicos "native →"**: lectura desde Postgres como source (DTO), volcado de
reservas/membresías/audit/coordination decidiendo qué se preserva (nada → single-user)
y qué se reporta (`build_native_exit_report`), mostrado ANTES de confirmar.

---

## A Eliminar / Cambiar

- [ ] Precondición BLOQUEANTE "MCP local" de `.claude/skills/switch-backend/SKILL.md:25-38` — contradice la decisión canónica "Transporte único MCP remoto + content-passing" (UC-668).
- [ ] Resolución de `source_id='.'` / `project_path='.'` contra el FS del servidor en `_read_source` / `apply_switch_transactional`.
- [ ] Encadenamiento manual de `migrate_backend` + `switch_backend` como interfaz pública (pasan a internos).

## A Mantener (reusar, NO duplicar)

- `write_target` (`server/migration/writer.py`) — ya preserva `state=item.state`.
- `state_mapping.py` — freeform/native/trello identidad, Plane lossy.
- `setup_board` native (UPSERT `ON CONFLICT`), `seed_native_identity`, `collect_discarded_native_state`, `build_native_exit_report`.
- `apply_switch_transactional` — atomicidad de los 3 lugares + rollback (extender para abarcar datos).
- `detect_local_root_path()` — handshake v6.0.1 para resolver path en cliente.
- `NativeBackend.list_items` / `get_acceptance_criteria` / `get_item_children` — native como source.

---

## User Story

**ID**: US-BACKEND-SWITCH-NATIVE
**Nombre**: Cambiar de backend como operación única, atómica y completa (hacia/desde Native)
**Actor**: Owner-operator (ICP-1, dogfooding) + Equipo/agencia que sube a Cloud (ICP-3)
**Horas estimadas**: 40h
**Pantallas**: (ninguna — infra del engine, sin UI de producto)

> Como owner-operator (y equipo que sube su proyecto a Cloud), quiero cambiar el
> backend de tracking de mi proyecto con **una sola orden atómica** que lea mi source
> local correctamente (no el del servidor), preserve mi avance y deje todo coherente
> o nada a medias, para no quedar en un limbo donde la config dice una cosa y la base
> de datos otra.

---

## Use Cases

### UC-810: Content-passing en `_read_source` + `migrate_preview`
- **Actor**: Engine (MCP server)
- **Horas**: 6h
- **Estado**: backlog

`_read_source` y `migrate_preview` dejan de leer el filesystem del servidor. Aceptan
el CONTENIDO del source (items.json freeform serializado, o un DTO normalizado) que el
cliente lee localmente y pasa como parámetro. Para trello/plane el source se lee de la
API (que sí vive server-side legítimamente). El preview reporta el conteo leído.

#### Acceptance Criteria
- [ ] **AC-01**: Dado un MCP remoto y `source_type="freeform"`, cuando se llama `migrate_preview` con `source_content=<items.json del cliente como string>`, entonces el preview reporta exactamente el conteo de US/UC/AC presente en ese contenido (p.ej. 11 US / 88 UC / N AC) y NO ejecuta ningún `Path.resolve()` ni `list_items` contra el filesystem del servidor (verificable: con `SPECBOX_ENGINE_MCP_URL` seteado y un items.json de 11/88 pasado, el resultado es 11/88, nunca 22/112 ni 0/0).
- [ ] **AC-02**: Dado `source_content=None` y `source_type="freeform"`, cuando se llama `migrate_preview`, entonces retorna un error explícito `"freeform source requires source_content (read items.json on the client)"` en vez de leer el FS del servidor.
- [ ] **AC-03**: Dado `source_type ∈ {trello, plane}`, cuando se llama `migrate_preview` sin `source_content`, entonces el source se lee de la API del backend (comportamiento legítimo server-side) y el preview reporta el conteo de la API.

### UC-811: Guard rail de conteo confirmable en el dry-run
- **Actor**: Engine + Cliente (skill)
- **Horas**: 4h
- **Estado**: backlog

El preview incluye un `read_counts` explícito y un `confirmation_token` que el execute
exige. Si el conteo es 0 o el cliente no confirma el conteo exacto, el execute se bloquea.

#### Acceptance Criteria
- [ ] **AC-04**: Dado un dry-run que lee 0 US / 0 UC del source, cuando el cliente intenta `dry_run=False`, entonces la operación retorna error `"refusing to execute: dry-run read 0 items — source path/content likely wrong"` y no escribe nada en el target.
- [ ] **AC-05**: Dado un dry-run que reporta `read_counts={us:11, uc:88}`, cuando el cliente llama el execute con `confirmed_count={us:11, uc:88}`, entonces la operación procede; cuando llama con `confirmed_count` distinto (p.ej. `{us:22, uc:112}`) o ausente, entonces retorna error `"count mismatch: preview read 11/88, execute confirmed 22/112"` y no escribe nada.

### UC-812: Operación única atómica `switch_project_backend` (orquestador)
- **Actor**: Engine (MCP server)
- **Horas**: 8h
- **Estado**: backlog

Nueva tool pública `switch_project_backend` que orquesta internamente
migrate→seed→switch→exit-report como una transacción todo-o-nada. `migrate_backend` y
`switch_backend` quedan como funciones internas (o tools deprecadas marcadas "internal").

#### Acceptance Criteria
- [ ] **AC-06**: Dado un proyecto freeform y `switch_project_backend(target_type="native", source_content=<11/88>, dev_token=<válido>, dry_run=False, confirmed_count={us:11,uc:88})`, cuando se ejecuta, entonces en una sola llamada: (1) se crea el proyecto en Postgres, (2) se copian las 11 US / 88 UC / AC, (3) se asocia el developer como project_admin, (4) se actualizan los 3 lugares de config — y el resultado lista los 4 sub-pasos como `completed`.
- [ ] **AC-07**: Dado que el paso de switch transaccional (escritura de los 3 lugares) falla tras haber escrito Postgres, cuando ocurre el fallo, entonces se hace rollback de la migración de datos (el proyecto Postgres queda en su estado previo: vacío si no existía) y el resultado reporta `rolled_back=true` con `failing_step` nombrado, dejando el proyecto en su backend original.
- [ ] **AC-08**: Dado que `switch_project_backend` se ejecuta con éxito, cuando se inspeccionan las tools MCP públicas, entonces `migrate_backend` y `switch_backend` o bien no figuran como interfaz pública recomendada o bien emiten una nota `"prefer switch_project_backend for atomic switches"` en su respuesta.

### UC-813: Flujo destino native — auth fail-fast + preservación de estados + idempotencia
- **Actor**: Engine
- **Horas**: 6h
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-09**: Dado `target_type="native"` y `dev_token` ausente o vacío, cuando se llama `switch_project_backend` (incluso con `dry_run=True`), entonces retorna error `"native target requires dev_token from the Cloud panel"` ANTES de leer el source o escribir nada (fail-fast verificable: ningún INSERT en Postgres, ningún read del source).
- [ ] **AC-10**: Dado un source con US/UC en estados mixtos (p.ej. una US `done`, una UC `in_progress`, otra `review`), cuando se migra a native con `switch_project_backend`, entonces los estados se preservan exactamente en Postgres (la US queda `done`, la UC `in_progress`, la otra `review`) — NO se usa `import_spec` (que degradaría a `backlog`), sino `write_target`.
- [ ] **AC-11**: Dado un `project_id` que ya existe en native con items, cuando se llama `switch_project_backend(target_type="native")` apuntando a ese project_id, entonces el preview reporta la colisión (`project_exists=true`, item_count actual) y exige una resolución explícita (`on_collision ∈ {reuse, skip, fail}`); sin ella, el execute falla con `"project already exists in native — specify on_collision"`.

### UC-814: Flujo origen native — lectura DTO + exit-report de coordinación
- **Actor**: Engine
- **Horas**: 6h
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-12**: Dado `source_type="native"`, cuando se llama `switch_project_backend(target_type="freeform", dry_run=True)`, entonces el source se lee desde Postgres vía `NativeBackend.list_items` / `get_acceptance_criteria` (DTO, no filesystem) y el preview reporta el conteo de US/UC/AC de la BD.
- [ ] **AC-13**: Dado `source_type="native"` con reservas/membresías/audit en la BD, cuando se ejecuta el preview de salida, entonces el resultado incluye un `native_exit_report` que lista cuántas reservas, membresías y filas de audit se descartarán (no tienen destino en el backend single-user), y ese reporte se muestra ANTES de la confirmación del execute.
- [ ] **AC-14**: Dado `source_type="native"` y `dry_run=False` confirmado, cuando se ejecuta la salida, entonces los datos US/UC/AC se escriben en el target preservando estados, la coordinación se descarta, y el resultado final incluye el `native_exit_report` con lo efectivamente descartado.

### UC-815: Skill `/switch-backend` online-first + write-back de los 3 lugares
- **Actor**: Cliente (skill)
- **Horas**: 5h
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-15**: Dado el MCP corriendo en modo remoto (`SPECBOX_ENGINE_MCP_URL` seteado), cuando se ejecuta `/switch-backend`, entonces la skill NO aborta con la precondición "MCP local": lee el source local del cliente (con `Read`), lo pasa por content-passing, y al confirmar escribe el contenido devuelto de `app_spec.md` y `settings.local.json` en el filesystem del CLIENTE (verificable: tras el switch, `.claude/settings.local.json` del repo cliente tiene el nuevo `backend_type`).
- [ ] **AC-16**: Dado un switch hacia native, cuando la skill `/switch-backend` corre, entonces presenta al usuario el conteo "N US / M UC leídas del cliente" y exige confirmación literal del conteo antes de invocar el execute (`dry_run=False`).

### UC-816: `onboard_project --backend native` — cerrar el caso "registry sin BD"
- **Actor**: Engine
- **Horas**: 3h
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-17**: Dado `onboard_project(backend_type="native")` sin migración previa, cuando se completa el onboard, entonces el resultado documenta explícitamente el estado `"project registered, native DB empty — run switch_project_backend or import_spec to populate"` y NO deja al usuario creyendo que el panel mostrará datos que no existen.

### UC-817: E2E de no-regresión — reproduce el bug original
- **Actor**: Engine (tests)
- **Horas**: 6h
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-18**: Dado un test que simula MCP remoto (`SPECBOX_ENGINE_MCP_URL` seteado) y un items.json de cliente con 11 US / 88 UC, cuando se ejecuta `migrate_preview`/`switch_project_backend(dry_run=True)` con `source_content` = ese items.json, entonces el conteo reportado es 11/88 (del cliente) y un assert verifica que NO se accedió a ningún path del servidor (mock del FS del servidor con 22/112 que debe quedar intacto/no leído).
- [ ] **AC-19**: Dado el backup de no-regresión (`native-project-backup-pre-delete.json`: 10 US / 84 UC / 440 AC), cuando un test migra freeform→native con estados preservados, entonces el proyecto reconstruido en Postgres (test contra instancia native de test) tiene los conteos esperados, el developer asociado como project_admin, y los estados NO degradados a backlog.

---

## Interacciones UI

> N/A — feature de infraestructura del engine. Sin UI de producto. La "interacción" es
> vía tools MCP + skill `/switch-backend` (texto en chat de Claude Code).

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medición |
|-----|----------|----------|
| Seguridad de datos | Ningún `dry_run=False` puede ejecutarse sin conteo confirmado | Test AC-05 |
| Atomicidad | Rollback total si cualquier paso falla (datos + 3 flags) | Test AC-07 |
| Fail-fast | dev_token ausente falla antes de cualquier I/O | Test AC-09 |
| Aislamiento de FS | El server nunca lee/escribe el FS del cliente en migrate/switch | Test AC-18 |
| Idempotencia | Colisión de project_id resuelta explícitamente | Test AC-11 |
| Coherencia Cloud | El sync lo hace el engine/MCP, no la app; service_role solo en API | Revisión de diseño |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Rollback de datos en Postgres es complejo (no hay "undo" trivial de un setup_board+writes) | Alta | Alto | Estrategia: en target native crear el proyecto en una transacción; si el switch posterior falla, DELETE del proyecto recién creado (solo si no preexistía). Snapshot del estado previo antes de tocar. Cubierto por AC-07. |
| El DTO de source unificado (freeform content vs trello/plane API vs native DB) diverge | Media | Medio | Normalizar a la estructura que `_read_source` ya devuelve (`{board_name, items, classified, ac_data, comments_data, labels, states}`). Una sola forma interna. |
| Romper callers existentes de `migrate_backend`/`switch_backend` (tests, scripts) | Media | Medio | Mantener las firmas como wrappers internos compatibles; añadir `source_content` opcional sin quitar params. Deprecar, no eliminar, en esta US. |
| Test contra instancia native real requiere Postgres | Media | Bajo | Reusar `docker-compose.dev.yml` (postgres:16 puerto 55432) que ya existe para la suite native. AC-19 corre ahí. |

---

## Stack Técnico (estimado)

- **Lenguaje**: Python (FastMCP) — `server/`
- **Módulos tocados**: `server/tools/migration.py`, `server/migration/{writer,state_mapping,native_handling,transactional_switch,backend_dispatch}.py`, `server/backends/native_backend.py`, `server/tools/onboarding.py` (reuso `detect_local_root_path`), `server/tools/spec_driven.py` (doc de import_spec).
- **Cliente**: `.claude/skills/switch-backend/SKILL.md` + bridge `.claude/hooks/lib/mcp-client-io.mjs` (reuso content-passing helpers).
- **Tests**: `tests/test_native_*.py`, nuevo `tests/test_backend_switch_native.py`. Postgres dev vía `docker-compose.dev.yml`.

## Dependencias

- Decisión canónica "Transporte único MCP remoto + content-passing" (UC-668) — ya vigente.
- Patrón content-passing v6.0.1 (US-MCP-PATH-CONTRACT) — reuso de `mcp-client-io.mjs`.
- Instancia native de test (Supabase gestionada / Postgres local docker-compose.dev.yml).

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)
- [ ] **AC-01**: migrate_preview freeform remoto lee `source_content` del cliente (11/88), nunca el FS del servidor (22/112 ni 0/0).
- [ ] **AC-02**: freeform sin `source_content` → error explícito, no lee FS del servidor.
- [ ] **AC-03**: trello/plane sin `source_content` → lee de la API (legítimo server-side).
- [ ] **AC-04**: dry-run lee 0 items → execute bloqueado con error.
- [ ] **AC-05**: execute exige `confirmed_count` == conteo del preview; mismatch → error, no escribe.
- [ ] **AC-06**: `switch_project_backend` freeform→native ejecuta los 4 sub-pasos en una llamada.
- [ ] **AC-07**: fallo en switch tras escribir Postgres → rollback de datos + `rolled_back=true`.
- [ ] **AC-08**: migrate_backend/switch_backend dejan de ser interfaz pública recomendada (nota/deprecación).
- [ ] **AC-09**: target native sin dev_token → fail-fast antes de cualquier I/O.
- [ ] **AC-10**: estados de US/UC preservados en native (write_target, no import_spec).
- [ ] **AC-11**: colisión de project_id en native → resolución explícita `on_collision`.
- [ ] **AC-12**: source native leído vía DTO (NativeBackend), no filesystem.
- [ ] **AC-13**: `native_exit_report` con reservas/membresías/audit descartadas, mostrado antes de confirmar.
- [ ] **AC-14**: salida de native preserva estados, descarta coordinación, reporta lo descartado.
- [ ] **AC-15**: `/switch-backend` online-first: no aborta con MCP remoto, escribe los 3 lugares en el cliente.
- [ ] **AC-16**: `/switch-backend` muestra "N US / M UC del cliente" y exige confirmación literal del conteo.
- [ ] **AC-17**: `onboard_project --backend native` documenta el estado "registry sin BD poblada".
- [ ] **AC-18**: E2E reproduce el bug: MCP remoto + source_content 11/88 → conteo 11/88, FS del servidor no leído.
- [ ] **AC-19**: E2E migra freeform→native preservando estados + developer project_admin (contra Postgres de test).

### Técnicos (no validados por AG-09)
- [ ] Proyecto compila / suite pytest verde.
- [ ] Sin regresión en la suite native existente (`tests/test_native_*.py`).
- [ ] Lint GGA limpio.

---
**Prioridad**: high
**Complejidad**: Alta
**VEG Readiness**: DISABLED (sin targets de UI — feature de infra)
*Generado: 2026-06-02*
