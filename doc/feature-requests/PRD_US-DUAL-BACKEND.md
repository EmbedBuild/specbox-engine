# PRD — US-DUAL-BACKEND: Espejo Native best-effort (dual-backend)

> **Destino:** ejecutar con Claude desde el proyecto **SpecBox** (repo `EmbedBuild/specbox-engine`).
> **Estado:** listo para `/prd` → `/plan` → `/implement`, o para implementación directa.
> **Autocontenido:** todo el contexto técnico está investigado y embebido aquí. La sesión
> que lo ejecute NO necesita re-descubrir la arquitectura — solo verificar los file:line antes de editar.
> **Versión Engine objetivo:** v6.9.4 (`server/` Python, FastMCP).

---

## 1. Contexto y problema

El Engine modela el *tracking backend* como **single-backend exclusivo**: hay un único
`backend_type` sincronizado en 3 lugares de verdad, y `switch_project_backend` **migra**
de uno a otro (no hay fork/dual-write).

Un patrón de cliente real lo rompe: **necesitan dos backends simultáneos.**

- **Caso disparador — Potencial Digital 2026:** el primario es **Trello** y es *intocable*
  porque alimenta **"Projects Embed"**, una herramienta cliente-final asociada a **hitos de
  pago**. A la vez, el equipo quiere **Native** por su control visual. Hoy hay que elegir uno.
- Es un patrón **recurrente** (otros clientes lo tendrán), así que la solución es una
  **capacidad de producto del Engine**, no una excepción local.

## 2. Objetivo

Permitir que un proyecto **reporte a dos backends a la vez**:

| Rol | Backends válidos | Escritura | Lectura |
|---|---|---|---|
| **Primario** | `trello` · `plane` · `freeform` | Síncrona, bloqueante, fuente de verdad | Sí (única fuente) |
| **Espejo** | `native` (siempre) | **Best-effort + log** | No |

**Regla dura:** primario `native` → dual **prohibido** (fail-fast `MIRROR_ON_NATIVE_FORBIDDEN`).

## 3. No-goals (v1)

- Sin transacción 2-fase entre backends remotos (imposible) → drift posible, resoluble por re-backfill.
- Sin espejo bidireccional (Native nunca propaga al primario).
- Espejo distinto de Native (p. ej. Trello→Plane) — fuera de alcance.
- Sin cola asíncrona de reintentos (queda para v2 si hace falta).

## 4. Métrica de éxito (NSM de la feature)

**El primario nunca se degrada por el espejo.** Operacionalizado: en el test de
inyección de fallo del espejo, el resultado del primario y la latencia del flujo son
idénticos con y sin espejo caído (0 fallos propagados, 0 rollbacks del primario).

## 5. Audiencia / actores

- **Operador del Engine** (tú): activa el espejo en proyectos legacy con `enable_mirror`.
- **Cliente final** (vía Projects Embed): no se entera de nada — Trello sigue igual.
- **Usuario interno** (panel visual): consume Native como réplica.

---

## 6. Arquitectura objetivo (ya investigada — file:line reales)

### 6.1 El chokepoint único
Las ~48 tools de escritura del flujo spec-driven obtienen su backend en **un solo sitio**:

```
server/auth_gateway.py:42   async def get_session_backend(ctx) -> SpecBackend
```

Es el ÚNICO lugar donde se instancian backends concretos (Trello/Plane/Freeform/Native
en líneas 64–96). Insertar aquí un wrapper da dual-write **sin tocar ninguna tool**.

### 6.2 Interfaz a implementar
```
server/spec_backend.py:140   class SpecBackend(ABC)
```
**12 métodos de escritura** a duplicar en el wrapper:
`create_item · update_item · mark_acceptance_criterion · create_acceptance_criteria ·
update_acceptance_criterion · delete_acceptance_criterion · archive_item · add_comment ·
add_attachment · create_module · add_items_to_module · create_label`

Lecturas (delegan SOLO al primario): `validate_auth, list_items, get_item,
find_item_by_field, get_item_children, get_acceptance_criteria, get_comments,
get_attachments, get_labels, get_state_id, get_states` + convenience `find_us_items/find_uc_items`.

### 6.3 Credenciales de sesión
```
server/auth_gateway.py:37    BACKEND_STATE_KEY = "spec_backend_config"
server/auth_gateway.py:169   async def store_native_credentials(ctx, project_id, dev_token)
server/tools/spec_driven.py:210  async def set_auth_token(...)
```
El espejo Native guarda SOLO `project_id` + `dev_token` (Frontier 2 — nunca DSN; el DSN
vive en `SPECBOX_NATIVE_DSN`, leído por el pool).

### 6.4 Los 3 lugares de verdad + transacción atómica
```
server/migration/transactional_switch.py:240  apply_switch_transactional(...)
   WRITE_ORDER = registry → app_spec → settings, con rollback total
```
1. Registry `$STATE_PATH/projects.json` → `projects[slug]` (`spec_backend`, `board_id`, `backend_history[]`).
2. `doc/app/app_spec.md` zona AUTO `tracking_backend`.
3. `.claude/settings.local.json` → `specbox.backend_type`.
El bloque nuevo `mirror` se persiste en los mismos 3, misma transacción.

### 6.5 Factory y tests existentes
```
server/migration/backend_dispatch.py:21   build_backend(backend_type, creds) -> SpecBackend
tests/test_native_backend_conformance.py   conformance parametrizado (freeform/native)
```

### 6.6 ⚠️ Subtileza obligatoria: item_id NO portables
`create_item` (Trello) devuelve un card-id que Native no reconoce. Las tools llaman
`mark_acceptance_criterion(board_id, uc_item_id, ...)` con el id **del primario**.
El espejo debe resolver el item equivalente en Native por su **id lógico** (`UC-XXX`/`US-XX`)
con `find_item_by_field`, usando **su** `board_id` (= `project_id` Native). Item ausente en
Native → log "missing mirror item" y continuar (best-effort).

---

## 7. User Story

> **US-DUAL-BACKEND** — Como operador del Engine, quiero poder añadir un **espejo Native
> best-effort** a un proyecto cuyo primario es Trello/Plane/FreeForm, para tener una réplica
> visual sin poner en riesgo el backend primario que el cliente consume y que está asociado
> a hitos de pago.

### Casos de uso y criterios de aceptación

#### UC-DB-01 — `DualBackendWrapper(SpecBackend)`  ·  *nuevo* `server/backends/dual_backend.py`
- **AC-01** Escritura con éxito en ambos → ambos backends reflejan el cambio.
- **AC-02** *(CRÍTICO)* El espejo lanza excepción en una escritura → la tool devuelve el
  resultado del **primario**, NO falla, y se emite un log estructurado de drift.
- **AC-03** Cualquier lectura → solo el primario es consultado; el espejo nunca.
- **AC-04** item_id primario ≠ espejo → el wrapper resuelve por id lógico antes de escribir en el espejo; si no existe, loguea y sigue.
- **AC-05** `close()` cierra ambos; un fallo cerrando el espejo no impide cerrar el primario.

#### UC-DB-02 — Dispatch dual en el chokepoint  ·  `server/auth_gateway.py`
- **AC-01** Sin `mirror` en `BACKEND_STATE_KEY` → devuelve el backend simple actual (backward-compat exacto).
- **AC-02** Con `mirror` y primario ≠ native → devuelve `DualBackendWrapper(primary, NativeBackend(...))`.
- **AC-03** Frontier 2: el sub-dict `mirror` solo contiene `project_id` + `dev_token`; nunca DSN.
- **AC-04** Nuevo `store_mirror_native_credentials(ctx, project_id, dev_token)` persiste el sub-dict `mirror`.

#### UC-DB-03 — `enable_mirror` / `disable_mirror`  ·  `server/tools/migration.py`
- **AC-01** `enable_mirror` con primario native → rechazo `MIRROR_ON_NATIVE_FORBIDDEN`.
- **AC-02** `enable_mirror` hace `validate_auth` del espejo + **backfill inicial**: el espejo Native arranca con el mismo conteo US/UC/AC que el primario.
- **AC-03** `enable_mirror` persiste `mirror` en los 3 lugares de verdad vía la transacción atómica.
- **AC-04** `disable_mirror` revierte a single-backend sin pérdida en el primario.

#### UC-DB-04 — Persistencia transaccional del bloque `mirror`  ·  `server/migration/transactional_switch.py`
- **AC-01** Fallo escribiendo cualquiera de los 3 lugares → rollback total, ninguno a medias.
- **AC-02** `detect_project_backend` sigue devolviendo el primario; nuevo campo `mirror` expone el espejo.

#### UC-DB-05 — Tests  ·  *nuevo* `tests/test_dual_backend.py`
- **AC-01** Cubre UC-DB-01 AC-01..AC-05 (con foco en la garantía crítica AC-02 vía fallo inyectado en el espejo).
- **AC-02** Cubre el rechazo primario-native y la resolución por id lógico.
- **AC-03** Verifica backward-compat: sin `mirror`, el comportamiento es idéntico al baseline.

---

## 8. Plan de implementación (orden sugerido)

1. **UC-DB-01** wrapper + su test de garantía crítica (fallo del espejo) — valida el corazón antes de cablear nada.
2. **UC-DB-02** dispatch en `get_session_backend` + `store_mirror_native_credentials`.
3. **UC-DB-04** persistencia transaccional del bloque `mirror`.
4. **UC-DB-03** `enable_mirror`/`disable_mirror` + backfill.
5. **UC-DB-05** suite completa + actualizar `test_native_backend_conformance` si procede.
6. Doc: CHANGELOG + nota en README sobre dual-backend; bump de versión del Engine.

## 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Drift Trello↔Native si el espejo falla repetidamente | best-effort + log + `enable_mirror` re-backfill (idempotente); futuro `resync_mirror` |
| Latencia extra por la doble escritura | el espejo se escribe DESPUÉS del primario; si molesta, v2 lo hace fire-and-forget |
| Romper backward-compat de los 48 call-sites | wrapper implementa `SpecBackend` completo; sin `mirror` el path es idéntico → test AC-03 de UC-DB-05 lo blinda |
| Fuga de DSN | Frontier 2: solo `project_id`+`dev_token` en sesión; test AC-03 de UC-DB-02 |

## 10. Definición de "hecho"

- Los 5 UCs con todos sus AC en verde.
- `tests/test_dual_backend.py` pasando + suite existente sin regresión.
- Backward-compat probada (proyecto sin espejo = comportamiento baseline).
- CHANGELOG + bump de versión + nota de despliegue.
- Validado end-to-end con el caso real: Potencial Digital con primario Trello + espejo Native, Trello intacto.
```
```

---

## Apéndice A — Prompt de arranque para Claude en SpecBox Cloud

Pega esto como primer mensaje en la sesión del proyecto SpecBox:

> Voy a implementar la feature **US-DUAL-BACKEND** (espejo Native best-effort / dual-backend).
> El PRD completo está en `doc/feature-requests/PRD_US-DUAL-BACKEND.md` con la arquitectura
> ya investigada (file:line reales contra v6.9.4). El chokepoint es
> `server/auth_gateway.py:42 get_session_backend`. Empieza por **UC-DB-01**
> (`server/backends/dual_backend.py` + su test de la garantía crítica: el espejo falla → el
> primario NO se degrada). Lee cada archivo antes de editar (quality-first guard). Regla dura:
> primario native → dual prohibido. Frontier 2: el espejo solo guarda project_id+dev_token,
> nunca DSN. No toques las 48 tools de escritura — todo pasa por el chokepoint.
