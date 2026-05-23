# Runbook — Credencial del Native Backend sobre Supabase (UC-404)

> Frontera 2: la credencial de Postgres es la "joya de la corona". Vive **solo**
> en la variable de entorno `SPECBOX_NATIVE_DSN`, nunca en config de sesión MCP,
> nunca como argumento de tool, nunca en logs ni en el repo.

Este runbook cubre cómo obtener, instalar, rotar y retirar la credencial del
Native Backend cuando la base de datos es una instancia **Supabase
gestionada** (Postgres 17+, región a elección del operador). Cada operador
del MCP es responsable de su propia instancia Supabase: el repo es público
y no documenta refs ni credenciales de ninguna instancia concreta.

---

## (a) Obtener el DSN del Pooler transaction-mode

El Native Backend se conecta a través del **Supabase Pooler en modo
transaction** (PgBouncer), no por conexión directa. Esto importa: el código de
[`server/db/pool.py`](../../server/db/pool.py) desactiva el cache de prepared
statements (`statement_cache_size=0`) precisamente porque el pooler en modo
transaction no mantiene estado entre sentencias. [AC-24]

1. Dashboard de Supabase → tu proyecto → **Project Settings → Database →
   Connection string**.
2. Pestaña **Connection pooling** → **Transaction** mode.
3. Copiar el URI. Tiene esta forma (host `...pooler.supabase.com`, **puerto
   6543**):

   ```
   postgresql://postgres.<PROJECT_REF>:<DB_PASSWORD>@aws-0-<REGION>.pooler.supabase.com:6543/postgres
   ```

4. Sustituir `<PROJECT_REF>`, `<REGION>` y `<DB_PASSWORD>` por los valores de
   tu instancia (la password vive en **Database → Database password**; si no
   se recuerda, se puede **resetear** ahí — ver sección de rotación).

> TLS: el código fuerza `ssl=require` automáticamente cuando el host es
> `*.supabase.co` / `*.supabase.com` (ver `_resolve_ssl`), así que el DSN no
> necesita llevar `?sslmode=require`. [AC-25]

> Pooler vs directo: usar **siempre** el Pooler transaction-mode (6543) para el
> MCP. La conexión directa (5432) tiene un límite de conexiones más bajo y, en
> planes pequeños, requiere IPv6 o el add-on IPv4.

---

## (b) Dónde vive `SPECBOX_NATIVE_DSN`

| Entorno | Ubicación del secreto | Notas |
|---------|-----------------------|-------|
| **VPS (producción, MCP remoto)** | Variable de entorno del proceso del MCP server (p. ej. unit de systemd `Environment=`, o el `.env` del servicio fuera del repo). | Nunca commitear. Permisos `600`. El proceso del MCP es el único que la lee, vía `server/db/pool.py`. |
| **CI** | Secreto del repositorio/organización (GitHub Actions → *Secrets*) inyectado como env `SPECBOX_NATIVE_DSN` solo en los jobs que corren la suite native. | Si el secreto no está, los tests native **skipean limpio** (ver UC-405). No exponer el secreto a PRs de forks. |
| **Dev local** | Export en la shell o `.env` local NO versionado. Apunta a la branch DB de Supabase o al Postgres docker (`docker-compose.dev.yml`). | Para Supabase local/branch ver UC-405. |

El override opcional `SPECBOX_NATIVE_SSL` (`require`/`disable`) permite forzar
TLS on/off independientemente del host — útil para un proxy local.

---

## (c) Rotación sin downtime

La credencial es la DB password de Supabase. Para rotarla:

1. **Generar la nueva password**: Dashboard → Database → **Reset database
   password**. Supabase la cambia de inmediato (las conexiones abiertas siguen
   vivas hasta que se reciclan).
2. **Componer el nuevo DSN** del Pooler con la nueva password (sección a).
3. **Actualizar el secreto** en VPS y CI (sección b).
4. **Reiniciar el proceso del MCP** (o recargar el servicio) para que
   `init_pool` tome el nuevo DSN. El pool antiguo se cierra con `close_pool` en
   el shutdown graceful.
5. **Verificar** con `get_setup_status` / un round-trip (`whoami` sobre un
   proyecto native) que el MCP opera con la credencial nueva.

> Ventana sin downtime: como el reset de password no corta las conexiones
> establecidas instantáneamente, hay un breve solape en el que el pool viejo
> sigue sirviendo. Reinicia el MCP en cuanto el secreto esté propagado.

---

## (d) Retirada del Postgres-VPS antiguo

Antes de v-Supabase, el Native Backend corría contra un Postgres self-hosted
(`docker-compose.dev.yml`, usuario `specbox`, password `specbox_dev_only`,
puerto host 55432). Esa credencial y esa instancia se retiran así:

1. **Verificar que no quedan datos sin migrar**: el proyecto Supabase es la
   nueva fuente de verdad. Si el Postgres VPS tenía datos de producción,
   exportarlos (`pg_dump`) y cargarlos en Supabase **antes** de seguir. En el
   estado actual la instancia Supabase arrancó vacía y el schema se aplicó vía
   migraciones (UC-402), así que confirmar que producción no escribió aún al
   Postgres viejo.
2. **Repuntar la config de producción**: cambiar `SPECBOX_NATIVE_DSN` del VPS al
   DSN del Pooler de Supabase (secciones a–b). Reiniciar el MCP.
3. **Smoke test** contra Supabase (round-trip de un proyecto native).
4. **Teardown del contenedor/instancia VPS**:
   ```bash
   docker compose -f docker-compose.dev.yml down -v   # -v borra el volumen
   ```
   `docker-compose.dev.yml` permanece en el repo: sigue siendo útil como
   Postgres efímero **local** para tests (UC-405). Lo que se retira es la
   instancia de **producción** del VPS y su credencial.
5. **Invalidar la credencial vieja**: borrar `specbox_dev_only` de cualquier
   `.env`/secreto de producción. Al ser un contenedor efímero local, no hay
   rotación que hacer más allá de destruirlo.

---

## (e) Higiene de secretos [AC-37]

- Ningún secreto de Supabase (DB password, service_role key, DSN completo) se
  commitea al repo ni se imprime en logs. `pool.py` nunca loguea el DSN
  resuelto y los errores de config no incluyen material de credencial.
- Verificación rápida en el árbol git (no debe encontrar coincidencias reales):
  ```bash
  git grep -nE 'postgresql://postgres\.[a-z]{20}:' || echo "OK: sin DSN commiteado"
  git grep -nE 'service_role|sb_secret|sbp_[A-Za-z0-9]{20,}' || echo "OK: sin keys"
  ```
- Tras aplicar las migraciones (UC-403) el advisor de seguridad de Supabase
  queda **limpio**: RLS + policies activas y función `rls_auto_enable` con
  `EXECUTE` revocado a `anon`/`authenticated`.

---

## (f) Correr la suite de conformidad contra Supabase (UC-405) [AC-40]

La suite native (`tests/test_native_schema.py`,
`tests/test_native_backend_conformance.py`, `tests/test_native_dispatch.py`)
lee el DSN de `SPECBOX_NATIVE_DSN` (helper compartido `tests/_native_db.py`,
TLS-aware) y **skipea limpio** cuando no hay DB alcanzable — el path no-DB de CI
queda verde. [AC-39]

Tres formas de darle una DB a los tests:

1. **Postgres local efímero** (el más rápido para dev):
   ```bash
   docker compose -f docker-compose.dev.yml up -d
   .venv/bin/pytest tests/test_native_*.py -q       # usa el DSN dev por defecto
   ```

2. **Branch DB de Supabase** (verifica contra el motor real, aislado de prod):
   crear una *branch* del proyecto en el dashboard de Supabase (o vía el
   Supabase MCP `create_branch`), tomar su DSN del Pooler transaction-mode y:
   ```bash
   export SPECBOX_NATIVE_DSN='postgresql://postgres.<BRANCH_REF>:<DB_PASSWORD>@aws-0-<REGION>.pooler.supabase.com:6543/postgres'
   .venv/bin/pytest tests/test_native_*.py -q       # native corre, no skipea [AC-38]
   ```
   La rama se descarta al terminar (`delete_branch`) sin tocar producción.

3. **Supabase local** (`supabase start`): levanta el stack completo en docker y
   exporta su DSN local a `SPECBOX_NATIVE_DSN`.

> El runner casero `apply_migrations` (`server/db/migrate.py`) lleva el schema a
> esa DB de test — está permitido para dev/tests, NO para producción (la prod
> usa el ledger Supabase, ver UC-402 / sección de migraciones).

> TLS: contra cualquier host Supabase la suite negocia `ssl=require`
> automáticamente (mismo `_resolve_ssl` que `pool.py`), así que un DSN de branch
> DB no necesita `?sslmode=require` para que el probe lo alcance. [AC-38]

## Referencias

- Conexión / SSL / pooling: [`server/db/pool.py`](../../server/db/pool.py) (UC-401)
- Migraciones (ledger Supabase): [`supabase/migrations/`](../../supabase/migrations/) (UC-402)
- RLS + policies: `supabase/migrations/20260522000004_rls_policies.sql` (UC-403)
- Plan del Native Backend: [`doc/plans/native_backend_team_plan.md`](../plans/native_backend_team_plan.md)
