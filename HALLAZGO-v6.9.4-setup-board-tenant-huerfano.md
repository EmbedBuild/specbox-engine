# Hallazgo para v6.9.4 — `setup_board` crea un tenant huérfano que envenena la auto-provisión

> Encontrado en dogfooding el 2026-06-03, **probando v6.9.3 "Tenant Provisioning"** sobre el
> caso real (`specbox_cloud` → native, BD vacía). v6.9.3 **no cierra el gap de provisión en el
> camino real**: su lógica de auto-provisión es correcta, pero otra ruta (`setup_board`) crea un
> tenant sin membresía que la desactiva. Es un bug de orden/atomicidad, confirmado con file:line.

## Síntoma

`start_migration_session(target='EmbedBuild/specbox_cloud', dev_token=<válido>)` sobre una BD
**verificada vacía** (`SELECT count(*) FROM projects = 0` segundos antes) devolvió:

```
Developer 'jesusperezdeveloper' is not a member of project 'EmbedBuild/specbox_cloud'
code: FORBIDDEN
```

Estado de Postgres **tras** el fallo (verificado por SQL directo):
- `public.projects` → **1 fila** `EmbedBuild/specbox_cloud` (`name` genérico = project_id,
  `backend_type=native`, `created_at` = momento del intento).
- `public.project_members` → **0** (sin membresía).
- `public.audit_log` → **0** (sin registro de provisión).

Esa firma (projects sí, members no, audit no) es de **`setup_board`**, NO de
`provision_native_project` (que crearía membresía + audit en la misma transacción).

## Causa raíz (file:line)

El flujo de `start_migration_session` está **bien escrito**:
- `server/tools/migration.py:1199-1213` — llama `_maybe_auto_provision()` **antes** del gate de
  membresía. Correcto.

`_maybe_auto_provision` (`server/tools/migration.py:1436`) provisiona **solo si el proyecto no
existe**:
```python
exists = bool(await conn.fetchval("SELECT 1 FROM projects WHERE project_id = $1", canonical))
if exists:
    return False        # no provisiona → el gate decide → FORBIDDEN si no hay membresía
await provision_native_project(pool, project_id=canonical, developer_id=..., role="project_admin")
```

`provision_native_project` (`server/migration/native_handling.py:284-312`) **es atómico y
correcto**: crea `projects` (UPSERT) + `project_members` en una sola `conn.transaction()`.

**El problema:** `setup_board` (`server/backends/native_backend.py:336-354`) hace
`INSERT INTO projects ... ON CONFLICT` **sin crear membresía**, **fuera** de
`provision_native_project`. Se invoca desde `migration.py:337,630,1009` y
`spec_driven.py:276,460` (`start_uc`, `import_spec`). Cualquiera de esas operaciones —ejecutada
antes del `start_migration_session`— crea un **tenant huérfano** (proyecto sin ningún miembro).

**La cadena del fallo:**
1. Una operación previa (un `setup_board` vía spec/migración, o el MCP tocando el proyecto) crea
   la fila de `projects` **sin membresía**.
2. `start_migration_session` → `_maybe_auto_provision` ve `exists = True` → `return False` (no
   provisiona, porque cree que es un tenant legítimo preexistente).
3. El gate de membresía corre → no hay miembro → **FORBIDDEN**.

El ecosistema **se sabotea a sí mismo**: `setup_board` envenena el estado limpio que la
auto-provisión de v6.9.3 necesitaba.

## Por qué el test de v6.9.3 no lo detecta

El E2E de UC-822 ejerce el camino **limpio**: BD vacía → `start_migration_session` → provisión.
Nunca hay un `setup_board` previo creando la fila huérfana. Por eso pasa en test y falla en real
— el mismo patrón que en v6.9.2 (test con fixture en memoria, no el transporte real).

## Fix de raíz (a decidir en el discovery)

1. **Eliminar la creación de tenant fuera de la provisión atómica.** Toda creación de tenant
   native debe pasar por `provision_native_project` (tenant + membresía juntos). `setup_board`
   para native no debería poder dejar un proyecto sin ningún miembro.
2. **O** que `_maybe_auto_provision` trate **"proyecto existe pero con CERO miembros"** como caso
   provisionable: un tenant sin **ningún** `project_members` es un fantasma, no un proyecto real
   del que el guard AC-13 deba proteger. El guard "no auto-unir a tenant preexistente" debe
   distinguir *tenant con miembros* (proteger) de *tenant huérfano* (provisionar/adoptar).
3. **Test E2E que reproduzca el camino real:** un `setup_board` previo crea la fila huérfana,
   y LUEGO `start_migration_session` debe recuperarse (provisionar la membresía o adoptar el
   tenant huérfano), no devolver FORBIDDEN.

## Síntoma recurrente relacionado (mismo origen)

Durante todo el dogfooding, la fila de `projects` "fantasma" reaparece sola cada vez que el MCP
toca el proyecto (la borras y vuelve). Es el mismo `setup_board` huérfano. Mientras exista esa
puerta (crear tenant sin membresía), el estado se ensucia repetidamente.

## Datos de reproducción / no-regresión

- Proyecto `specbox_cloud`: `doc/tracking/items.json` reconciliado (186 KB, 13 US / 89 UC /
  466 AC, 85 done / 4 backlog).
- BD Cloud: tras el fallo quedó **1 fila huérfana** `EmbedBuild/specbox_cloud` sin membresía
  (creada durante el intento). Hay que limpiarla antes del próximo intento.
- Identidad `jesusperezdeveloper` válida (dev_token autentica, whoami OK).
- Repro: con una fila de `projects` sin membresía presente, `start_migration_session` →
  FORBIDDEN en vez de auto-provisionar.

## Cadena de hallazgos de este dogfooding

1. v6.9.1 "Atomic Switch" — switch atómico + path bug remoto (cerrado).
2. v6.9.2 "Batch Ingest" — transporte de sources grandes por lotes (cerrado).
3. v6.9.3 "Tenant Provisioning" — provisión + contrato project_id (cierra la LÓGICA, pero...).
4. **v6.9.4 (este)** — `setup_board` deja tenant huérfano que desactiva la auto-provisión de
   v6.9.3 en el camino real. El test no lo ve por no reproducir el `setup_board` previo.

Patrón recurrente en los 4: **el test pasa con el camino ideal; el dogfooding encuentra el camino
real.** Sugerencia transversal: los E2E de migración deben partir de estados "sucios" realistas,
no solo de BD/fixtures vírgenes.
