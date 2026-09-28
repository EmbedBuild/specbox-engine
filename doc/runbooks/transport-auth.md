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
(también los externos) nombra las dos formas de conectarse. Solo se activa cuando:

1. La contención cross-tenant (US-38) está desplegada — lo está desde el 2026-09-28.
2. Las dos formas de conectarse existen: la extensión de VSCode envía el token en el transporte
   (UC-3901 AC-03, publicada en el Marketplace) y `specbox login` está disponible (UC-3904).

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

## Conectar un cliente con token

El token viaja en la cabecera `Authorization: Bearer <token>` de **cada** petición HTTP (así lo
exige la especificación de autorización de MCP); los clientes la envían solos.

- **Extensión de VSCode**: al iniciar sesión («SpecBox: Iniciar sesión con GitHub») configura la
  conexión para enviar el token de la persona; no hay que copiar nada.
- **Terminal**: `specbox login` (UC-3904) guarda el token en el almacén seguro del sistema.
- **Claude Code a mano** (`~/.claude.json` o `.mcp.json`): servidor `"type": "http"` con
  `"headersHelper"` apuntando a un comando que imprima `{"Authorization": "Bearer <token>"}`, o con
  `"headers": {"Authorization": "Bearer ${SPECBOX_MCP_TOKEN}"}` si el token está en el entorno.
- **Otros clientes** que solo hablan stdio: `npx mcp-remote <URL>/mcp --header "Authorization:Bearer ${SPECBOX_MCP_TOKEN}"`
  con `SPECBOX_MCP_TOKEN` en el entorno del proceso.

Nunca hay que pegar un token en un chat ni pasarlo a una tool.
