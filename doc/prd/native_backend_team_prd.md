# PRD: Backend Nativo — SpecBox en equipo (multi-developer)

> Origen: FreeForm backend (ff-2051992d4368) | US-NATIVE-BACKEND
> Generado: 2026-05-21
> Tipo: PRD Técnico (extensión del engine) — alcance v1 = H1+H2+H3

## Resumen Ejecutivo

SpecBox está empezando a usarse por equipos de varios desarrolladores sobre la
misma aplicación. La arquitectura actual está diseñada para **un dev + sus
agentes contra un board**: no hay identidad de persona, ni coordinación
concurrente, ni source-of-truth única cross-proyecto. Dos devs que ejecutan
`find_next_uc` contra el mismo board reciben el mismo UC y se pisan; el marker
`.quality/active_uc.json` es estado per-máquina que ningún otro dev ve.

Este PRD introduce un **4º backend "Nativo"** sobre Postgres interno
auto-hosteado en el VPS, en topología **Modo A**: la BBDD vive en la red interna
del VPS y **solo el MCP server tiene credenciales**; los developers nunca tocan
Postgres directo — hablan con el MCP como ya hacen hoy. El backend Nativo
**convive** con Trello/Plane/FreeForm (no los reemplaza) y es **opt-in por
proyecto**.

El alcance v1 cubre tres hitos: **H1** source-of-truth (NativeBackend sobre el
ABC existente), **H2** identidad de developer, **H3** claims de UC (resuelve el
dolor primario: dos devs sin pisarse). Teams completos, dashboard CRUD,
degradación offline y concurrencia fina de ACs quedan **fuera del v1** (H4-H5).

## Alcance

### Incluye (v1 = H1+H2+H3)

- **NativeBackend** que implementa los ~30 métodos del `SpecBackend` ABC sobre
  Postgres. CRUD completo de US/UC/AC.
- **BBDD una instancia multi-tenant**: tabla `projects`, todas las apps dentro.
  Source-of-truth única + visibilidad cross-proyecto en Sala de Máquinas.
- **Columna `version`** por item (US/UC/AC) para concurrencia optimista.
- **Identidad de developer**: `developer_id` estable + token por dev en su
  `settings.local.json`, mapeado a tabla `developers`. Tool `whoami()`.
- **Dos fronteras de seguridad separadas**: Frontera 1 (autenticación +
  autorización en el MCP) vs Frontera 2 (credencial de servicio de BBDD que
  nunca sale del VPS).
- **Claims de UC**: tabla `uc_claims` con constraint UNIQUE en `uc_id`.
  Tools `claim_uc` / `release_uc`. `start_uc` consulta claims antes de conceder;
  conflicto limpio si otro dev lo tiene. `find_next_uc` excluye UCs reclamados.
- **`branch_registry`** para evitar colisión de nombres de branch entre devs.
- **`.quality/active_uc.json` pasa a cache** de un claim remoto (no la verdad).
- **`spec-guard.mjs` revalida** el claim contra el MCP cuando hay red
  (defense-in-depth; sigue funcionando offline desde el cache).
- **Capa de coordinación** como módulo nuevo `server/coordination/` **fuera del
  `SpecBackend` ABC** — no contamina la abstracción.

### No incluye (fuera del v1 — reservado para H4-H5)

- Teams completos: tablas `teams` / `team_membership`, ACL por team, capacity.
  (En v1, la autorización es por `developer_id ↔ project`, simple.)
- Dashboard web con CRUD humano de US/UC/AC, asignaciones, gestión de personas.
- Degradación offline avanzada con reconciliación de claims hechos sin red.
- Concurrencia fina sobre ACs simultáneos (más allá de la columna `version`).
- Migración de proyectos existentes Trello/Plane/FreeForm → Nativo
  (tool `migrate_to_native`). Reservado para H4.
- Reemplazo de cualquier backend existente. Nativo es aditivo.
- Acceso directo de devs/dashboard a Postgres (Modo B + RLS).

---

## Objetivos

1. **Source-of-truth única opt-in** — Un equipo puede elegir que su app viva en
   una BBDD central en lugar de FreeForm/Trello/Plane, sin cambiar cómo usan los
   skills.
2. **Identidad de developer** — El sistema sabe *quién* hace cada operación, base
   de toda coordinación y autorización.
3. **Cero pisotones entre devs** — Dos developers sobre la misma app no pueden
   reclamar el mismo UC ni colisionar nombres de branch; el conflicto se detecta
   y se reporta limpio.
4. **Abstracción intacta** — La coordinación vive fuera del `SpecBackend` ABC;
   los 3 backends existentes siguen funcionando sin cambios.

---

## Estado Actual vs Propuesto

### ACTUAL

```
SpecBackend (ABC, ~30 métodos CRUD)
├── TrelloBackend     → Trello API (cloud, reporting cliente)
├── PlaneBackend      → Plane API (cloud/self-hosted)
└── FreeformBackend   → doc/tracking/*.json (local, offline)

Coordinación: NINGUNA
  - find_next_uc: algoritmo determinista, sin saber quién trabaja qué
  - start_uc: escribe .quality/active_uc.json LOCAL (per-máquina)
  - Identidad: auth_gateway per-sesión SIN identidad de persona
  - VPS: telemetría read-only (heartbeat → project_state.json)
```

### PROPUESTO (v1)

```
SpecBackend (ABC, sin cambios)
├── TrelloBackend     (sin cambios)
├── PlaneBackend      (sin cambios)
├── FreeformBackend   (sin cambios)
└── NativeBackend     → Postgres interno (VPS, red interna)  ← NUEVO

server/coordination/ (MÓDULO NUEVO, fuera del ABC)           ← NUEVO
├── identity.py       → developers, tokens, whoami()
├── claims.py         → uc_claims (UNIQUE uc_id), claim/release
└── branches.py       → branch_registry

Topología Modo A:
  Dev (hooks/CLI) ──token──→ MCP (VPS) ──service cred──→ Postgres
                            [Frontera 1]   [Frontera 2, nunca sale del VPS]

  active_uc.json: ahora CACHE de un claim remoto, no la verdad
  spec-guard.mjs: revalida claim contra MCP si hay red
```

---

## User Stories y Use Cases

### US-NATIVE-BACKEND: SpecBox para equipos sobre Postgres nativo

> Como **equipo de desarrolladores que usa SpecBox sobre la misma app**, quiero
> un backend centralizado con identidad y coordinación de UCs, para **trabajar en
> paralelo sin pisarnos las US/UC ni colisionar branches**.

**Actor**: Desarrolladores en equipo
**Hitos**: H1 (UC-101..103), H2 (UC-201..203), H3 (UC-301..304)

---

#### H1 — NativeBackend (source of truth)

##### UC-101: Implementar NativeBackend sobre el SpecBackend ABC
- **Actor**: Engine / dev del engine
- **Horas estimadas**: 16h
- **Estado**: backlog

**Acceptance Criteria:**
- [ ] **AC-01**: `NativeBackend` implementa los ~30 métodos abstractos de
  `SpecBackend` (CRUD de US/UC/AC, comments, attachments, labels, states); un
  test de conformidad ejecuta la misma suite de contrato que pasa
  `FreeformBackend` y termina en verde para `NativeBackend`.
- [ ] **AC-02**: Las operaciones de escritura usan un pool `asyncpg`
  inicializado al arrancar el MCP; ejecutar 50 operaciones CRUD concurrentes no
  agota el pool ni deja conexiones colgadas (verificado contando conexiones
  activas en `pg_stat_activity` antes y después).
- [ ] **AC-03**: Cada fila de US/UC/AC tiene una columna `version` (entero) que
  se incrementa en cada UPDATE; un UPDATE que envía una `version` distinta a la
  almacenada es rechazado con error `STALE_VERSION` y no muta la fila.

##### UC-102: Esquema Postgres multi-tenant
- **Actor**: Engine
- **Horas estimadas**: 8h
- **Estado**: backlog

**Acceptance Criteria:**
- [ ] **AC-04**: Existe una migración SQL versionada que crea las tablas
  `projects`, `user_stories`, `use_cases`, `acceptance_criteria` con `project_id`
  como FK en cada tabla de spec; aplicar la migración sobre una BBDD vacía y
  re-aplicarla (idempotente) no produce error.
- [ ] **AC-05**: Una consulta de los UCs de `project_id=A` nunca devuelve filas
  de `project_id=B` (verificado con un test que inserta specs en dos proyectos
  distintos y comprueba aislamiento por `project_id` en cada método de lectura).
- [ ] **AC-06**: La Sala de Máquinas (`get_sala_de_maquinas` /
  `get_all_projects_overview`) lista los proyectos almacenados en Postgres junto
  a los de otros backends, sin requerir escanear el filesystem.

##### UC-103: Selección de backend Nativo opt-in por proyecto
- **Actor**: Dev configurando un proyecto
- **Horas estimadas**: 6h
- **Estado**: backlog

**Acceptance Criteria:**
- [ ] **AC-07**: `set_auth_token(backend_type="native", ...)` registra el
  proyecto contra Postgres; `detect_project_backend` devuelve `native` cuando
  `specbox.backend_type="native"` está en `settings.local.json`, con prioridad
  por encima de las señales de filesystem.
- [ ] **AC-08**: Con backend Nativo configurado, `import_spec` persiste la
  estructura US/UC/AC en Postgres y `list_us`/`list_uc` la recuperan idéntica
  (round-trip verificado campo a campo).
- [ ] **AC-09**: Un proyecto con backend Trello/Plane/FreeForm sigue funcionando
  sin cambios cuando `NativeBackend` está disponible en el server (la suite de
  regresión de los 3 backends pasa en verde).

---

#### H2 — Identidad de developer

##### UC-201: Modelo de developer y token
- **Actor**: Engine / admin
- **Horas estimadas**: 8h
- **Estado**: backlog

**Acceptance Criteria:**
- [ ] **AC-10**: Existe tabla `developers` con `developer_id` (estable, PK),
  `display_name` y `token_hash`; los tokens se almacenan hasheados, nunca en
  claro (verificado: la columna no contiene el token literal tras crear un dev).
- [ ] **AC-11**: Un dev declara su token en `settings.local.json`
  (`specbox.native.token`); el cliente MCP lo adjunta en cada llamada y el token
  nunca se escribe en logs del server (verificado grepeando los logs tras una
  operación autenticada).

##### UC-202: Autenticación y autorización en el MCP (Frontera 1)
- **Actor**: MCP server
- **Horas estimadas**: 10h
- **Estado**: backlog

**Acceptance Criteria:**
- [ ] **AC-12**: Una llamada a una tool del backend Nativo sin token válido es
  rechazada con `UNAUTHENTICATED` y no toca Postgres.
- [ ] **AC-13**: Una llamada con token válido pero a un proyecto al que el dev no
  está asociado es rechazada con `FORBIDDEN`; una llamada al proyecto correcto
  procede.
- [ ] **AC-14**: La credencial de servicio de Postgres (Frontera 2) se lee solo
  de la env del VPS; no aparece en ninguna respuesta de tool ni en
  `settings.local.json` de ningún dev (verificado por inspección de las
  respuestas de todas las tools del backend Nativo).

##### UC-203: Tool whoami
- **Actor**: Dev
- **Horas estimadas**: 3h
- **Estado**: backlog

**Acceptance Criteria:**
- [ ] **AC-15**: `whoami()` devuelve el `developer_id` y `display_name`
  resueltos desde el token presentado; con token inválido devuelve
  `UNAUTHENTICATED` sin filtrar si el dev existe o no.

---

#### H3 — Claims de UC (coordinación)

##### UC-301: Tabla de claims con exclusión mutua
- **Actor**: Engine
- **Horas estimadas**: 8h
- **Estado**: backlog

**Acceptance Criteria:**
- [ ] **AC-16**: Existe tabla `uc_claims` con constraint `UNIQUE(uc_id)`; dos
  `claim_uc(uc_id)` concurrentes sobre el mismo UC resultan en exactamente un
  claim concedido y uno rechazado con `ALREADY_CLAIMED` (verificado lanzando dos
  claims en paralelo).
- [ ] **AC-17**: `release_uc(uc_id)` solo lo puede ejecutar el dev dueño del
  claim; un `release_uc` de otro dev es rechazado con `NOT_CLAIM_OWNER` y el
  claim permanece.

##### UC-302: start_uc consulta claims
- **Actor**: Dev / skill /implement
- **Horas estimadas**: 6h
- **Estado**: backlog

**Acceptance Criteria:**
- [ ] **AC-18**: `start_uc(uc_id)` sobre un UC sin claim crea el claim a nombre
  del dev y devuelve éxito; el UC pasa a estado "in_progress" en Postgres en la
  misma transacción (sin claim huérfano si falla el cambio de estado).
- [ ] **AC-19**: `start_uc(uc_id)` sobre un UC ya reclamado por otro dev devuelve
  un conflicto que incluye **quién** lo tiene, **desde cuándo** y **qué branch**
  (verificado: la respuesta contiene `owner`, `claimed_at`, `branch`).

##### UC-303: find_next_uc excluye reclamados
- **Actor**: Dev / skill /implement
- **Horas estimadas**: 4h
- **Estado**: backlog

**Acceptance Criteria:**
- [ ] **AC-20**: `find_next_uc` sobre un backend Nativo no devuelve UCs que ya
  tienen un claim activo de otro dev; con dos devs y dos UCs disponibles, cada
  `find_next_uc` simultáneo devuelve UCs distintos.

##### UC-304: active_uc.json como cache + branch_registry
- **Actor**: Dev / hooks
- **Horas estimadas**: 8h
- **Estado**: backlog

**Acceptance Criteria:**
- [ ] **AC-21**: Tras `start_uc`, `.quality/active_uc.json` se escribe local con
  una referencia al claim remoto (`uc_id`, `developer_id`, `claimed_at`); el
  fichero se trata como cache y `spec-guard.mjs` lo acepta offline.
- [ ] **AC-22**: Cuando hay red, `spec-guard.mjs` revalida el claim contra el
  MCP antes de permitir escribir código; si el claim ya no es del dev (lo liberó
  o lo tiene otro), el hook bloquea con un mensaje que indica el conflicto.
- [ ] **AC-23**: `branch_registry` registra `(project_id, uc_id, branch, dev)`;
  intentar registrar un branch con nombre ya usado por otro dev para otro UC es
  rechazado, y el naming sugerido incluye el `uc_id` para evitar colisión
  (`feature/{uc_id}-{slug}`).

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medición |
|-----|----------|----------|
| Concurrencia | Claim de UC es atómico bajo carrera | Test de 2 claims paralelos → 1 OK, 1 rechazado |
| Seguridad | Credencial de BBDD nunca sale del VPS | Inspección de respuestas + logs |
| Seguridad | Tokens de dev hasheados, nunca en logs | grep de logs tras operación autenticada |
| Aislamiento | Sin fuga de datos entre proyectos | Test de aislamiento por `project_id` |
| Compatibilidad | 3 backends existentes sin regresión | Suite de regresión en verde |
| Rendimiento | 50 ops CRUD concurrentes sin agotar pool | `pg_stat_activity` antes/después |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| MCP pasa a ser punto crítico de escritura; si cae, devs bloqueados | Media | Alto | active_uc.json cache permite trabajo offline; degradación offline completa en H5 |
| Credencial de servicio de Postgres se filtra → acceso total | Baja | Crítico | Solo en env del VPS, nunca cerca de repo (historial de Secret Scanning); rotable |
| Fuga de conexiones del pool tumba a todos los devs a la vez | Media | Alto | Pool dimensionado + AC-02 verifica no-leak; timeouts por conexión |
| Claim huérfano si falla la transacción claim+estado | Media | Medio | AC-18 exige atomicidad transaccional |
| Scope creep hacia "otro Jira" (teams/capacity/permisos) | Alta | Medio | Teams completos explícitamente fuera del v1 (H4); en v1 autorización simple dev↔project |
| Contaminar el SpecBackend ABC con métodos de coordinación | Media | Alto | Coordinación en módulo separado `server/coordination/`; otros backends devuelven "no soportado" |

---

## Stack Técnico (estimado)

- **Lenguaje**: Python 3.12 + FastMCP (mismo runtime del engine)
- **BBDD**: Postgres en VPS, red interna (sin puerto expuesto)
- **Driver**: `asyncpg` con connection pool
- **Migraciones**: SQL versionado (esquema multi-tenant)
- **Módulos nuevos**:
  - `server/backends/native_backend.py` — `NativeBackend(SpecBackend)`
  - `server/coordination/identity.py` — developers, tokens, whoami
  - `server/coordination/claims.py` — uc_claims, claim/release
  - `server/coordination/branches.py` — branch_registry
  - `server/db/migrations/` — esquema Postgres
- **Modificados**:
  - `server/auth_gateway.py` — identidad de persona (Frontera 1)
  - `server/spec_backend.py` — registrar NativeBackend (sin nuevos métodos ABC)
  - `server/tools/spec_driven.py` — start_uc/find_next_uc consultan claims
  - `.claude/hooks/spec-guard.mjs` — revalidación de claim contra MCP

## Dependencias

- Postgres operativo en el VPS (provisión de instancia + backups).
- Variable de entorno con la credencial de servicio en el VPS.

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)

- [ ] **AC-01**: NativeBackend implementa los ~30 métodos del ABC; suite de contrato en verde.
- [ ] **AC-02**: Pool asyncpg; 50 ops concurrentes sin agotar ni dejar conexiones colgadas.
- [ ] **AC-03**: Columna `version`; UPDATE con versión stale → `STALE_VERSION`, no muta.
- [ ] **AC-04**: Migración SQL idempotente crea tablas multi-tenant con `project_id` FK.
- [ ] **AC-05**: Aislamiento por `project_id`; lecturas de A nunca devuelven filas de B.
- [ ] **AC-06**: Sala de Máquinas lista proyectos Postgres junto a otros backends.
- [ ] **AC-07**: `backend_type="native"` opt-in; `detect_project_backend` lo prioriza.
- [ ] **AC-08**: `import_spec` round-trip US/UC/AC en Postgres campo a campo.
- [ ] **AC-09**: 3 backends existentes sin regresión.
- [ ] **AC-10**: Tabla `developers` con token hasheado, nunca en claro.
- [ ] **AC-11**: Token en settings.local.json; nunca en logs del server.
- [ ] **AC-12**: Sin token válido → `UNAUTHENTICATED`, no toca Postgres.
- [ ] **AC-13**: Token válido a proyecto ajeno → `FORBIDDEN`; al propio procede.
- [ ] **AC-14**: Credencial de BBDD solo en env del VPS, nunca en respuestas ni settings.
- [ ] **AC-15**: `whoami()` resuelve developer desde token; inválido → `UNAUTHENTICATED`.
- [ ] **AC-16**: `UNIQUE(uc_id)`; 2 claims concurrentes → 1 OK, 1 `ALREADY_CLAIMED`.
- [ ] **AC-17**: `release_uc` solo por el dueño; ajeno → `NOT_CLAIM_OWNER`.
- [ ] **AC-18**: `start_uc` crea claim + estado in_progress atómico (sin huérfano).
- [ ] **AC-19**: `start_uc` sobre UC reclamado → conflicto con owner/claimed_at/branch.
- [ ] **AC-20**: `find_next_uc` excluye UCs reclamados; 2 devs → UCs distintos.
- [ ] **AC-21**: active_uc.json como cache del claim; aceptado offline por spec-guard.
- [ ] **AC-22**: spec-guard revalida claim contra MCP con red; bloquea si ya no es del dev.
- [ ] **AC-23**: branch_registry rechaza colisión; naming sugerido incluye uc_id.

### Técnicos (no validados por AG-09)

- [ ] Proyecto compila / importa sin errores.
- [ ] Tests con 85%+ coverage en módulos nuevos.
- [ ] Migraciones SQL aplican limpio sobre BBDD vacía.

---

**Prioridad**: high
**Complejidad**: Alta
*Generado: 2026-05-21*
