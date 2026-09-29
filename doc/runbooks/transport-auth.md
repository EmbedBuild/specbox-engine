# Autenticación de transporte del MCP remoto (UC-3901)

El servidor remoto (`https://mcp-specbox-engine.jpsdeveloper.com/mcp`) comprueba el token de
cada petición HTTP **antes** de que llegue al MCP, inicialización de sesión incluida. La
comprobación de salud (`/health`) sigue siendo pública.

- Un token **presente pero inválido, caducado o revocado** se rechaza siempre con
  `401 invalid_token`.
- Un token válido identifica a la persona durante toda la sesión: las tools, el registro de
  accesos y `set_auth_token(backend_type="native", token="")` usan esa identidad sin que haya que
  volver a pasar el token.
- Qué pasa con una conexión **sin token** lo decide el operador (tabla siguiente).

Código: `server/coordination/transport_auth.py`. Pruebas: `tests/test_transport_auth.py` y
`tests/test_engine_version_contract.py`.

## Modos

| `SPECBOX_TRANSPORT_AUTH` | Conexión sin token |
|---|---|
| `off` (por defecto) | Funciona como hasta ahora, sin aviso. |
| `grace` | Funciona hasta `SPECBOX_TRANSPORT_AUTH_GRACE_UNTIL` (excluida), y cada respuesta de una tool lleva un aviso con esa fecha y las dos formas de conectarse con cuenta. Desde esa fecha, se rechaza con `401 token_required` **y el mismo mensaje**. |
| `enforce` | Se rechaza con `401 token_required`. |

`SPECBOX_TRANSPORT_AUTH_GRACE_UNTIL` es una fecha `AAAA-MM-DD` (UTC): el primer día en que se
rechaza la conexión sin token. Un `grace` sin fecha válida, o un modo desconocido, se comportan
como `enforce` (nunca abren la puerta por error).

La respuesta de rechazo es JSON (`error`, `message`, `docs_url`) con `WWW-Authenticate: Bearer`;
el mensaje sale en español o inglés según `Accept-Language`.

## Antes de empezar la gracia

El periodo de gracia son los 30 días siguientes a activarla, y el aviso que ven todos los clientes
(también los externos) nombra las dos formas de conectarse. Solo se activa cuando se cumplen las dos
condiciones:

1. La contención cross-tenant (US-38) está desplegada — lo está desde el 2026-09-28.
2. Las dos formas de conectarse que nombra el aviso existen de verdad: una versión de la extensión de
   VSCode publicada en el Marketplace que envía el token en el transporte (UC-3901 AC-03) y
   `specbox login` publicado en npm (UC-3904). **A 2026-09-29 ninguna de las dos está publicada**:
   activar la gracia antes pediría a la gente algo que todavía no puede hacer.

Es una decisión del operador: activarla empieza a contar el plazo para todos.

## Activar, comprobar, volver atrás

En EasyPanel (servicio del MCP) → variables de entorno:

```
SPECBOX_TRANSPORT_AUTH=grace
SPECBOX_TRANSPORT_AUTH_GRACE_UNTIL=<hoy + 30 días>
```

y redesplegar. Comprobar:

```bash
URL=https://mcp-specbox-engine.jpsdeveloper.com
curl -s -o /dev/null -w '%{http_code}\n' "$URL/health"                                   # 200
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$URL/mcp" -H 'Authorization: Bearer x' # 401
```

Volver atrás: `SPECBOX_TRANSPORT_AUTH=off` y redesplegar. Pasar a `enforce` al terminar la gracia
no es necesario (desde la fecha límite `grace` ya rechaza), pero deja la configuración explícita.

## Límites y usuario del proceso (UC-3903)

- Una petición de más de 2 MB (`SPECBOX_MAX_REQUEST_BYTES`) se rechaza con `413 request_too_large`.
- Más de 60 llamadas a tools por minuto (`SPECBOX_RATE_LIMIT_PER_MINUTE`) desde la misma identidad se
  rechazan con `429 rate_limited` y `Retry-After`; cada identidad (developer del token, o IP del
  cliente si no hay token) tiene su propio cupo.
- El servidor corre como el usuario `specbox`, no como root. Comprobarlo tras un despliegue:

```bash
ssh specbox-vps 'sh -s -- "$(docker ps -q -f name=mcp_mcp-specbox-engine | head -1)"' < scripts/verify-nonroot.sh
```

## Conectar un cliente con token

El token viaja en la cabecera `Authorization: Bearer <token>` de **cada** petición HTTP (así lo
exige la especificación de autorización de MCP).

**Estado a 2026-09-29: ningún cliente la envía todavía.** Hasta la versión 6.13.0, la extensión de
VSCode escribe su configuración en `~/.claude/settings.local.json`, un fichero del que Claude Code no
lee servidores MCP (solo los lee de `~/.claude.json` y del `.mcp.json` del proyecto), y su lanzador
espera un valor `${secretStorage:…}` que nadie resuelve. Lo que falta está en preparación
(UC-3904, plan en `doc/plans/US-39-conexion-dispositivos_plan.md` del orquestador):

- **Extensión de VSCode**: al iniciar sesión («SpecBox: Iniciar sesión con GitHub») guardará el token
  en el almacén seguro del sistema y configurará Claude Code para enviarlo; al actualizarse, migrará
  las configuraciones existentes sin pasos manuales.
- **Terminal**: `specbox login` mostrará un código de un solo uso que se confirma en el panel con la
  cuenta de GitHub, y hará lo mismo sin que nadie vea ni copie el token.

Mientras tanto, **Claude Code a mano** (`~/.claude.json` o `.mcp.json`): servidor `"type": "http"`
con `"headersHelper"` apuntando a un comando que imprima `{"Authorization": "Bearer <token>"}`
(Claude Code lo ejecuta al conectar, al reconectar y tras un 401, así que una rotación del token no
corta la sesión), o con `"headers": {"Authorization": "Bearer ${SPECBOX_MCP_TOKEN}"}` si el token
está en el entorno. **Otros clientes** que solo hablan stdio:
`npx mcp-remote <URL>/mcp --header "Authorization:Bearer ${SPECBOX_MCP_TOKEN}"` con
`SPECBOX_MCP_TOKEN` en el entorno del proceso.

Nunca hay que pegar un token en un chat ni pasarlo a una tool.

## Caducidad y último uso de los tokens (UC-3904, UC-3902)

- Un token con `expires_at` en el pasado se rechaza igual que uno revocado: `401 invalid_token`, con
  el mensaje que explica cómo volver a conectar. Los tokens anteriores a la migración 0025 no tienen
  caducidad (`expires_at` nulo) hasta que el operador decida su política.
- Cada token pertenece a un dispositivo (persona, ordenador y cliente MCP): como mucho hay uno activo
  por dispositivo, y un nuevo inicio de sesión desde el mismo dispositivo revoca el anterior
  (`revoked_reason = 'replaced'`). Los tokens de dispositivo los emite la API del panel con `public.issue_device_token`, la única vía que lo garantiza en una sola transacción.
- `last_used_at` refleja el uso real del MCP: el servidor lo anota al validar el token, como mucho
  una vez por hora. Antes de la migración 0025 solo lo escribía `/api/whoami` del panel, así que las
  fechas anteriores no sirven para decidir inactividad.
