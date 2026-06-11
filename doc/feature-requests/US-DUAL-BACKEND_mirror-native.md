# US-DUAL-BACKEND — Dual-backend (espejo Native best-effort)

> Spec lista para ejecutar en **SpecBox Cloud**. Mapeada contra el código real del
> Engine v6.9.4 (`server/`). Origen: necesidad del cliente *Potencial Digital 2026*
> (primario Trello intocable porque alimenta "Projects Embed" — herramienta
> cliente-final con hitos de pago — + espejo Native para control visual interno).

---

## Resumen ejecutivo

Permitir que **un proyecto reporte a DOS backends a la vez**:

- **Primario** ∈ `{trello, plane, freeform}` — la fuente de verdad. Escritura síncrona y bloqueante.
- **Espejo** = **siempre `native`** — réplica de solo-lectura para el usuario. Escritura **best-effort + log**.

**Regla dura:** si el primario ya es `native` → dual **rechazado** (fail-fast). No se espeja Native sobre Native.

**Garantía crítica (la razón de existir):** el primario **nunca** se bloquea, ralentiza ni revierte por un fallo del espejo. Si Native cae, se loguea el drift y `/implement` continúa. Esto protege el flujo que cobra (Trello → Projects Embed).

---

## Hallazgo arquitectónico clave (ya investigado)

El Engine está **idealmente** preparado: todas las ~48 tools de escritura del flujo
spec-driven pasan por **un único chokepoint**.

| Componente | Archivo | Líneas |
|---|---|---|
| **CHOKEPOINT** `get_session_backend(ctx)` | `server/auth_gateway.py` | 42–113 |
| Interfaz base ABC `SpecBackend` (12 métodos de escritura) | `server/spec_backend.py` | 140–471 |
| Factory `build_backend(backend_type, creds)` | `server/migration/backend_dispatch.py` | 21–71 |
| 4 implementaciones concretas | `server/backends/{freeform,trello,plane,native}_backend.py` | — |
| `set_auth_token` (entrada de credenciales) | `server/tools/spec_driven.py` | 210+ |
| `store_native_credentials` / `store_*_credentials` | `server/auth_gateway.py` | 135–236 |
| Switch atómico 3-lugares `apply_switch_transactional` | `server/migration/transactional_switch.py` | 240–316 |
| Test de conformidad parametrizado | `tests/test_native_backend_conformance.py` | — |

Insertar un wrapper en el chokepoint da dual-write **sin tocar ninguna de las 48 tools**.

### Los 3 lugares de verdad (donde vive `backend_type`, y donde vivirá `mirror`)
1. **Registry** `$STATE_PATH/projects.json` → `projects[slug]` (campos `spec_backend`, `board_id`, `backend_history[]`).
2. **`doc/app/app_spec.md`** → zona `AUTO` id `tracking_backend` (sync vía evento `set_auth_token`).
3. **`.claude/settings.local.json`** → clave `specbox.backend_type`.

### Subtileza no trivial: los `item_id` NO son portables
`create_item` en Trello devuelve un card-id que Native no reconoce. Las tools llaman
p.ej. `mark_acceptance_criterion(board_id, uc_item_id, ...)` con el id **del primario**.
El espejo **no puede** usar ese id → debe resolver el item equivalente en Native por su
**id lógico** (`UC-XXX`/`US-XX`) vía `find_item_by_field`, usando **su** `board_id`
(el `project_id` Native). Si no existe en Native → log "missing mirror item" y continuar.

---

## Los 12 métodos de escritura de `SpecBackend` (a duplicar en el wrapper)
`create_item`, `update_item`, `mark_acceptance_criterion`, `create_acceptance_criteria`,
`update_acceptance_criterion`, `delete_acceptance_criterion`, `archive_item`,
`add_comment`, `add_attachment`, `create_module`, `add_items_to_module`, `create_label`.

Lecturas (delegan SOLO al primario): `validate_auth`, `list_items`, `get_item`,
`find_item_by_field`, `get_item_children`, `get_acceptance_criteria`, `get_comments`,
`get_attachments`, `get_labels`, `get_state_id`, `get_states`, `find_us_items`, `find_uc_items`.

---

## UCs propuestos

### UC-DB-01 — `DualBackendWrapper(SpecBackend)`
**Archivo nuevo:** `server/backends/dual_backend.py`
- Constructor `(primary, mirror, primary_board_id, mirror_board_id)`.
- Lecturas → `primary`.
- Escrituras → `primary` primero (propaga resultado/excepción tal cual). Luego `mirror`
  envuelto en `try/except` que **loguea y traga** (best-effort), resolviendo el item por
  id lógico contra `mirror_board_id`.
- `close()` → cierra ambos (mirror en try/except para no romper el cierre del primario).
- **AC-01** Una escritura con éxito en ambos → ambos backends reflejan el cambio.
- **AC-02** (CRÍTICO) Mirror lanza excepción → la tool devuelve el resultado del primario, NO falla, y se emite un log de drift.
- **AC-03** Lecturas → solo el primario es consultado (mirror nunca).
- **AC-04** item_id del primario ≠ del espejo → el wrapper resuelve por id lógico antes de escribir en el espejo.

### UC-DB-02 — Dispatch en el chokepoint
**Archivo:** `server/auth_gateway.py`
- En `get_session_backend`: tras construir el primario, si `config.get("mirror")` existe
  **y** `backend_type != "native"` → construir `NativeBackend` espejo y devolver
  `DualBackendWrapper`. Si no → comportamiento actual idéntico.
- Nuevo `store_mirror_native_credentials(ctx, project_id, dev_token)` que guarda el sub-dict
  `mirror` dentro de `BACKEND_STATE_KEY`.
- **AC-01** Sin `mirror` en config → devuelve el backend simple de siempre (backward-compat).
- **AC-02** Con `mirror` y primario no-native → devuelve `DualBackendWrapper`.
- **AC-03** Frontier 2: el espejo solo guarda `project_id` + `dev_token`, jamás DSN.

### UC-DB-03 — `enable_mirror` / `disable_mirror` (UX alto nivel)
**Archivo:** `server/tools/migration.py` (+ skill opcional)
- `enable_mirror(project_slug, mirror_project_id, dev_token)`:
  1. validar regla (primario ≠ native);
  2. `validate_auth` del espejo Native;
  3. **backfill inicial**: copiar el estado actual del primario (US/UC/AC) al espejo Native para arrancar sincronizado;
  4. persistir `mirror` en los 3 lugares de verdad vía la transacción atómica.
- `disable_mirror(project_slug)`: quitar `mirror` de los 3 lugares.
- **AC-01** Primario native → `enable_mirror` rechazado con `code=MIRROR_ON_NATIVE_FORBIDDEN`.
- **AC-02** Backfill deja el espejo con el mismo conteo US/UC/AC que el primario.
- **AC-03** `disable_mirror` revierte el proyecto a single-backend sin pérdida en el primario.

### UC-DB-04 — Persistencia transaccional del bloque `mirror`
**Archivo:** `server/migration/transactional_switch.py`
- `apply_switch_transactional` (o función hermana) escribe/borra `mirror` en registry +
  app_spec + settings dentro de la misma transacción todo-o-nada con rollback.
- **AC-01** Fallo al escribir cualquiera de los 3 → rollback total, ninguno queda a medias.
- **AC-02** `detect_project_backend` sigue devolviendo el primario; un nuevo campo expone el espejo.

### UC-DB-05 — Tests
**Archivo nuevo:** `tests/test_dual_backend.py`
- Cubre AC-01..AC-04 de UC-DB-01 (especialmente la garantía crítica AC-02), el rechazo
  primario-native, y la resolución por id lógico. Reusar el patrón parametrizado de
  `test_native_backend_conformance.py`.

---

## Fuera de alcance (v1, consciente)
- Sin transacción 2-fase entre backends remotos → drift posible, resoluble con re-backfill (`enable_mirror`) o un futuro `resync_mirror`.
- Sin espejo bidireccional (Native no propaga al primario).
- Espejo siempre Native (no se soporta Trello-espejando-Plane, etc.).

## Despliegue para Potencial Digital (tras mergear en el Engine)
1. Rebuild/redeploy del MCP server del Engine con la feature.
2. En el repo del cliente: `enable_mirror` con el `project_id` Native (provisionado en `cloud.specbox.build`) + `dev_token`. El backfill copia las US/UC/AC de Trello → Native.
3. Cada `/implement` reporta a Trello (intacto) **y** Native (panel visual). Quedan pocas US → ventana corta.
