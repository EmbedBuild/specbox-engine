# Runbook — superficie expuesta de la base de datos (US-40)

Board, panel y portal comparten un único Postgres (Supabase), y PostgREST sirve los
esquemas `public`, `panel` y `business` a quien tenga la clave pública (`anon`) del
proyecto. Una migración descuidada basta para reabrir lo que cerraron US-38 y US-40.
Este runbook explica cómo se vigila y qué hacer cuando la comprobación falla.

## Qué comprueba

`python -m server.db.surface_check` (`server/db/surface_check.py`) falla si encuentra, fuera
de la lista aprobada `server/db/surface_allowlist.yaml`:

| Hallazgo | Qué significa |
|---|---|
| `view_bypasses_rls` | Una vista se evalúa con los privilegios de su dueño (`security_invoker` desactivado) y salta la RLS de sus tablas |
| `table_without_rls` | Una tabla tiene la seguridad por filas desactivada |
| `function_executable_by_anon` | `anon` puede ejecutar una función o procedimiento (no cuentan los triggers ni las funciones de extensiones: no se pueden llamar directamente) |
| `table_writable_by_public_role` | En `public`, `anon` o `authenticated` pueden insertar, modificar, borrar o truncar (UC-4002). `panel` y `business` no se someten a esta regla porque sus usuarios escriben a través de RLS |

Salida: `0` limpio, `1` hallazgos fuera de la lista o lista inválida (una excepción sin
motivo), `2` error de uso o de conexión. El DSN sale de `--dsn` o de `SPECBOX_NATIVE_DSN` y
nunca se imprime.

## Dónde se ejecuta

- **CI del engine** (`.github/workflows/db-surface-check.yml`): en cada PR o push a `main`
  que toque `server/db/**`, `supabase/migrations/**` o las pruebas de superficie. Monta un
  Postgres 16 como lo entrega Supabase (roles `anon`, `authenticated`, `service_role` y
  privilegios por defecto que les dan todo sobre tablas, secuencias y funciones nuevas),
  aplica las migraciones del engine y ejecuta la comprobación sobre `public` y las pruebas
  `tests/test_db_surface_*.py`. Con las migraciones solo hasta la 0022 (el estado previo al
  hotfix del 2026-09-28) la comprobación falla con 36 hallazgos; con la 0023 y la 0024 sale
  limpia.
- **Producción** (board + site + panel + portal): a mano, desde dentro del contenedor del MCP,
  que ya tiene el DSN de producción en su entorno. Así la credencial no sale del servidor ni
  se guarda en GitHub (este repositorio es público):

  ```bash
  ssh specbox-vps
  C=$(docker ps -q -f name=mcp_mcp-specbox-engine | head -1)
  docker exec "$C" python -m server.db.surface_check --schemas public,panel,business
  ```

  Ejecutarla al cerrar cada UC que toque el esquema de cualquier satélite y antes de cada
  release. Los hallazgos abiertos de `panel` y `business` se siguen como UC en el board del
  orquestador (US-41 portal, US-42 panel), no en este repositorio.
- **Local**: `SPECBOX_NATIVE_DSN=<postgres de pruebas> uv run python -m server.db.surface_check`.

## Añadir una excepción

Exponer algo a propósito es una decisión de seguridad: se revisa como código. Añade la
entrada en `server/db/surface_allowlist.yaml` con `kind` (`view`, `table` o `function`), el
`name` tal como lo imprime la comprobación (las funciones como `esquema.nombre(tipos)`) y un
`reason` que diga qué comprueba o devuelve el objeto y por qué es seguro. Una entrada sin
motivo hace fallar la comprobación. Las entradas que no encuentran nada se muestran como
`unused` y no fallan: la misma lista sirve para la base de CI (solo el board) y para
producción.

## Reglas para no reabrir la superficie

- `CREATE OR REPLACE VIEW` borra las opciones de la vista: repite
  `WITH (security_invoker = on)` al redefinir una vista del board.
- `CREATE OR REPLACE FUNCTION` borra sus `SET`: repite `SET search_path = public, pg_temp`.
- Una RPC nueva para `anon` necesita `GRANT EXECUTE` explícito y su entrada con motivo en la
  lista. El resto de funciones: `REVOKE ALL ... FROM PUBLIC, anon, authenticated`.
- Tablas nuevas: activa la RLS en la propia migración. Desde la 0024 las tablas nuevas de
  `public` nacen con solo SELECT para `anon`/`authenticated`, y Supabase activa la RLS por su
  cuenta (event trigger `ensure_rls`), pero la migración no debe depender de ninguno de los
  dos.
