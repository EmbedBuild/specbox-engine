# Prueba de humo de FreeForm en el MCP de producción (UC-11012)

Fusionar en `main` redespliega el MCP alojado en uno o dos minutos. `scripts/check-mcp-hosts.mjs` solo
comprueba que los dos nombres abren sesión; esta prueba recorre además lo que hace un proyecto
FreeForm nuevo con el MCP remoto, que es el camino de quien usa SpecBox gratis.

## Cuándo

- Después de **cada despliegue del MCP**, es decir, de cada fusión en `main` del engine. Esperar a
  que `/health` sirva la versión nueva y a que solo quede una réplica sana.
- En cada `/release`, en el Paso 6.7, junto a `check-mcp-hosts`.

## Cómo

```bash
node scripts/smoke-freeform-remote.mjs --with-device-token
```

En los dos nombres (`mcp.specbox.build` y `mcp-specbox-engine.jpsdeveloper.com`) abre una sesión
FreeForm sin disco y llama a `set_auth_token`, `setup_board`, `import_spec`, `find_next_uc`,
`start_uc`, `mark_ac` y `get_uc`. Pasa el `items.json` de una llamada a la siguiente, como el
cliente, y comprueba que la UC queda en curso con su criterio marcado. El servidor no guarda nada.

- Sale con 0 si todo responde y con 1 si algo falla. Imprime el nombre del MCP, la tool y su error.
- `--with-device-token` envía el token de este ordenador (el ayudante `~/.specbox/bin/mcp-headers.mjs`
  que instala `specbox login`). El token no aparece nunca en la salida.
- Sin `--with-device-token` solo sirve hasta el fin de la gracia de UC-3901 (2026-10-30). Después, el
  MCP rechaza la sesión sin token y la prueba falla en `initialize` con `HTTP 401`.
- `--json` da el resultado entero, paso a paso.

## Si falla

1. Mirar qué tool falla y con qué error, y en qué nombre.
2. Si el despliegue es la causa, revertir la PR (`gh pr revert`) y fusionar la reversión: el MCP se
   redespliega solo con la versión anterior.
3. Volver a pasar la prueba hasta que salga con 0.

Pruebas del propio script, sin red: `node --test scripts/smoke-freeform-remote.test.mjs`. Las ejecuta el
workflow `mcp-hosts.yml` cuando cambia el script.
