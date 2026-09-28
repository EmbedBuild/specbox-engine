# Runbook — Registro de accesos por tool del MCP remoto (UC-3803)

> Para el **operador del ecosistema** (SuperAdmin del panel). Responde a la pregunta que el
> reporte del tester dejó sin respuesta: *¿quién llamó a qué tool, cuándo y con qué resultado?*

## Qué se registra

Cada llamada a una tool del servidor, en cualquier transporte, deja una fila en
`tool_access_log` (Postgres del board native) con:

| Campo | Contenido |
|---|---|
| `occurred_at` | fecha y hora UTC |
| `tool` | nombre de la tool |
| `identity_kind` / `developer_id` | `developer` + su id; o `anonymous` (sin sesión native), `invalid_token` (token que no resuelve a nadie), `unresolved` (BD de identidad no disponible en ese momento). En consultas, sin developer la identidad se muestra como `anónimo` |
| `outcome` / `error_code` | `ok`, `error` (la tool devolvió un sobre de error: `UNAUTHENTICATED`, `PROJECT_NOT_VISIBLE`, `FREEFORM_REMOTE_DISK_MODE_REJECTED`…) o `exception` (nombre de la excepción) |
| `duration_ms`, `transport`, `client`, `remote_addr`, `session_id` | contexto de la llamada |
| `arg_keys` | **solo los nombres** de los argumentos |

Nunca se guarda un token, un valor de argumento, el contenido devuelto ni un mensaje de error.

## Qué NO se puede hacer con el registro

La tabla es append-only: un trigger rechaza `UPDATE`, `DELETE` y `TRUNCATE` para cualquier rol,
incluido el dueño. La retención es una decisión explícita del operador (eliminar el trigger,
archivar, volver a crearlo), nunca un accidente. PostgREST no la ve: privilegios revocados a
`anon` y `authenticated` y RLS activo sin políticas.

## Consultar

Con una sesión identificada del MCP (o pasando `dev_token`):

```
get_tool_access_log(developer_id="<id>", date_from="2026-09-24", date_to="2026-09-25")
get_tool_access_log(developer_id="anónimo", date_from="2026-09-24", date_to="2026-09-24", tool="list_onboarded_projects")
get_tool_access_log(date_from="2026-09-28T16:00:00Z", limit=500)
```

- `date_from` / `date_to` aceptan `YYYY-MM-DD` (día completo, inclusive) o fecha-hora ISO.
- Sin `developer_id` se devuelven todas las identidades; `anónimo` selecciona las llamadas sin
  identidad.
- Máximo 1000 entradas por consulta, las más recientes primero; `truncated: true` avisa de que
  hay más.

Quien no sea operador recibe `FORBIDDEN` y `entries: []`; sin identidad, `UNAUTHENTICATED`.

## Reinicios de estado (UC-3804)

`reset_project` y `reset_all_state` solo los ejecuta el operador, y cada ejecución deja su
propio evento en el registro: `tool = state_reset`, `developer_id` = quien lo ejecutó,
`project_id` = el proyecto reiniciado (`*` en el reinicio global). La llamada en sí también
queda registrada por el middleware, denegada o no, así que un intento de reinicio por parte de
otra identidad aparece como `reset_project` con `outcome = error` y `error_code = FORBIDDEN`.

```
get_tool_access_log(tool="state_reset", date_from="2026-09-01")
get_tool_access_log(tool="reset_project", date_from="2026-09-01")   # intentos, incluidos los denegados
```

## Quién es operador

- El SuperAdmin del panel: `panel.profiles.role = 'superadmin'` en la fila cuyo `developer_id`
  es el del token que usa el MCP.
- Override explícito (bootstrap, servidores sin panel): variable de entorno
  `SPECBOX_OPERATOR_DEVELOPER_IDS=id1,id2` en el servicio del MCP.

Comprobación rápida de que tu identidad cuenta como operador: `whoami` devuelve tu
`developer_id`; `get_tool_access_log(limit=1)` debe responder con `operator` = ese id.

## Si la base de datos falla

El middleware nunca bloquea una tool. Si el INSERT falla, la entrada se encola en
`$STATE_PATH/tool_access_log.spool.jsonl` y se reproduce en la siguiente escritura correcta. Si
ese fichero crece en el VPS, la BD está fallando: mira los logs del contenedor
(`access_log_db_write_failed`).

## Despliegue

1. Aplicar la migración `0022_tool_access_log.sql` (espejo `supabase/migrations/20260928000022_…`)
   en el Postgres del board **antes** del deploy del engine. Es aditiva e idempotente.
2. Deploy del servicio del MCP. Desde ese momento todas las llamadas quedan registradas.
3. Verificar: una llamada anónima (por ejemplo `get_engine_version` desde una sesión nueva) y
   después `get_tool_access_log(developer_id="anónimo", date_from=<hoy>)` como operador.
