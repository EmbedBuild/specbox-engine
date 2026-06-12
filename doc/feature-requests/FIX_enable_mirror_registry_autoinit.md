# FIX — enable_mirror: auto-init del registry + auto-seed de la entrada del proyecto

> Bug de producción descubierto en dogfooding al activar el espejo Native sobre el
> proyecto cliente **`potencial_digital_2026`** (primario Trello). Cierra el último gap
> de la cadena US-DUAL-BACKEND (US-11) en el despliegue **cloud** del Engine.
> Mapeado contra el código real del Engine v6.10.1 (`server/migration/transactional_switch.py`,
> `server/tools/migration.py`).

---

## Síntoma

`enable_mirror(..., dry_run=False)` ejecuta el backfill correctamente pero falla al
persistir la configuración:

```
status: "CONFIG_FAILED"
failing_place: "registry"
error: "Project registry not found at /data/state/projects.json"
```

El backfill Trello→Native **sí** se ejecuta (aditivo + idempotente; Native queda con
11 US / 36 UC / 111 AC verificados). Pero el bloque `mirror` **no** se persiste en los
3 lugares de verdad → el dual-write automático **no se activa**. El primario (Trello)
queda intacto, read-only, durante todo el flujo (la garantía dura se respeta).

## Causa raíz

`server/migration/transactional_switch.py::_write_registry_mirror` (escritor del primer
lugar de la transacción) hace, antes de escribir nada:

```python
path = _registry_path(state_path)
if not path.exists():
    raise FileNotFoundError(f"Project registry not found at {path}")   # ← (1)
registry = json.loads(path.read_text(encoding="utf-8"))
projects = registry.get("projects") or {}
if project_slug not in projects:
    raise KeyError(f"Project {project_slug!r} not found in registry")  # ← (2)
```

En el filesystem del servidor MCP **cloud** ese `projects.json` (`$STATE_PATH/projects.json`,
default `/data/state/projects.json`) **no existe** — el registry es un artefacto del flujo
de onboarding/migración local que en cloud nunca se materializó para este proyecto. Por
tanto (1) dispara `FileNotFoundError`, la transacción de 3 lugares aborta en el primer
escritor, y el bloque `mirror` nunca se persiste.

Es un bug del **escritor del registry en el path mirror**, no de credenciales, no del
repo cliente, no del backfill. El path de switch primario (`_write_registry`) asume el
mismo invariante, pero ahí siempre lo precede un onboarding que crea la entrada; el path
mirror puede ser la **primera** escritura que el servidor cloud hace sobre ese registry.

## Decisión de diseño

`_write_registry_mirror` debe **auto-inicializar** el `projects.json` cuando falta y
**auto-sembrar** la entrada del proyecto desde los datos del **PRIMARIO** —que ya están
en la sesión (`spec_backend_config`: `backend_type` + `board_id`) y como argumento
(`primary_board_id`) de `enable_mirror`— **antes** de fijar el bloque `mirror`.

Reglas (precisas):

1. **Fichero ausente** → crear el esqueleto `{"projects": {}}`. La rollback debe **borrar**
   el fichero que se acaba de crear (no dejar un `projects.json` vacío huérfano), para que
   un fallo posterior en `app_spec`/`settings` deje el estado byte-idéntico al previo.
2. **Entrada ausente** (al **fijar** un mirror, `mirror_project_id is not None`) → sembrarla
   con `{spec_backend: primary_backend, board_id: primary_board_id}` tomados del primario.
   Si no se conoce el primario (no propagado), se siembra con strings vacíos —degradación
   honesta, nunca un crash.
3. **Entrada presente** → **NUNCA** se tocan `spec_backend` ni `board_id`. El primario es
   sagrado; el mirror solo añade/quita su sub-bloque. (Esto preserva AC-02 de UC-1103.)
4. **Disable** (`mirror_project_id is None`) con entrada o fichero ausente → **no-op**: no
   se fabrica una entrada ni un fichero solo para quitar algo que no existe.

`primary_backend` + `primary_board_id` se propagan `enable_mirror → apply_mirror_transactional
→ _write_registry_mirror` como kwargs opcionales (default vacío → 100% backwards-compatible
con `disable_mirror` y con cualquier caller que no los pase).

### Por qué auto-seed y no exigir onboarding previo

El espejo es **opt-in best-effort sobre un primario ya operativo**. Exigir que el operador
corra un onboarding/migración local solo para materializar `projects.json` en el server
cloud rompe el caso de uso central ("tengo Trello vivo y quiero el panel Native a la vez").
Los datos del primario ya viajan en la sesión y en los argumentos de la tool: sembrarlos es
trivial, atómico y no inventa nada.

## Alcance

**Toca** (mínimo):

- `server/migration/transactional_switch.py`
  - `_write_registry_mirror(...)`: nuevos params `primary_backend`, `primary_board_id`;
    auto-init + auto-seed según las reglas de arriba.
  - `_read_registry_snapshot(...)`: registrar `created_file`/`file_present` para que la
    rollback distinga "el fichero existía" de "lo creó el writer".
  - `_restore_registry(...)`: si el snapshot dice que el fichero **no** existía, borrarlo
    en rollback (no solo `pop` del slug).
  - `apply_mirror_transactional(...)`: nuevos params `primary_backend`, `primary_board_id`;
    bind del writer real con esos valores.
- `server/tools/migration.py`
  - `enable_mirror(...)`: pasar `primary_backend=primary_type` y
    `primary_board_id=primary_board_id` (ya disponibles) a `apply_mirror_transactional`.
  - `disable_mirror(...)`: sin cambios funcionales (no propaga primario — para quitar el
    bloque la entrada ya existe; si no existiera, la regla 4 lo hace no-op seguro).

**No toca:** el wrapper dual, el dispatch, el backfill, las credenciales, el primario, ni
ninguna de las ~48 tools de escritura.

## Tests obligatorios (5)

En `tests/test_dual_backend.py`, sección UC-1103. La fixture existente `trello_project`
**siempre** pre-siembra `projects.json` con la entrada presente — por eso la suite previa
no detectó el bug. Los nuevos tests ejercen explícitamente el path de fichero/entrada
ausentes (patrón UC-827: el test debe partir del estado sucio real, no del ideal).

1. **`test_mirror_autoinits_registry_when_file_missing`** — sin `projects.json`,
   `apply_mirror_transactional(..., primary_backend="trello", primary_board_id="board-1")`
   crea el fichero, siembra la entrada desde el primario, y fija el bloque `mirror`. Verifica
   `spec_backend=="trello"`, `board_id=="board-1"`, `mirror.project_id` correcto, y
   `updated == ["registry","app_spec","settings"]`.
2. **`test_mirror_autoseeds_entry_when_slug_absent`** — `projects.json` existe pero **sin** el
   slug; se siembra la entrada desde el primario y se fija el mirror, sin tocar otros proyectos
   ya presentes en el registry.
3. **`test_mirror_does_not_overwrite_existing_primary`** — entrada presente con
   `spec_backend`/`board_id` propios; pasar `primary_backend`/`primary_board_id` **distintos**
   NO los pisa (el primario en disco gana). Solo se añade el sub-bloque `mirror`.
4. **`test_rollback_deletes_registry_created_by_writer`** — sin `projects.json`; forzar fallo
   en el escritor de `settings` (último lugar). La rollback debe **borrar** el `projects.json`
   recién creado → el directorio de estado queda como antes (sin fichero). Verifica
   `TransactionalSwitchError.place == "settings"` y `not (state/projects.json).exists()`.
5. **`test_enable_mirror_e2e_seeds_registry_from_session`** — vía `enable_mirror` con
   `mirror_seams` + un `trello_project` cuyo `projects.json` se borra antes de ejecutar:
   `status=="enabled"`, `config_updated` con los 3 lugares, y la entrada del registry
   sembrada desde la sesión (`spec_backend=="trello"`).

## Verificación e2e contra el proyecto real

Tras el merge + redeploy cloud, re-ejecutar contra `potencial_digital_2026`:

1. `set_auth_token(backend_type="trello", ...)` como primario.
2. `enable_mirror(project_slug="potencial_digital_2026",
   mirror_project_id="jesusperezdeveloper/potencial_digital_2026",
   dev_token=<token>, primary_board_id="69cd517b0a0bde849084a262", dry_run=True)` → preview OK.
3. Re-ejecutar con `dry_run=False` + `confirmed_count` → esperado `status: "enabled"`,
   `config_updated: ["registry","app_spec","settings"]`, **sin** `CONFIG_FAILED`.
4. Confirmar que una escritura spec-driven posterior (p.ej. `mark_ac`) se replica
   best-effort al espejo Native sin bloquear el primario Trello.

> Nota de identidad (de la sesión origen): el `mirror_project_id` canónico debe ir en
> formato `owner/repo` (`jesusperezdeveloper/potencial_digital_2026`, guiones **bajos**);
> `validate_project_id` rechaza un slug sin owner. El `dev_token` Native es session-only
> (Frontier 2), nunca se persiste.

---

*Origen: dogfooding US-11 / UC-1104, 2026-06-11. Satélite: `engine`. Board: `EmbedBuild/specbox-manager`.*
