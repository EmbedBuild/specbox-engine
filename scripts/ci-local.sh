#!/usr/bin/env bash
# shellcheck disable=SC2034,SC2329  # CI_NOMBRE, CI_BLOQUES… y los bloques los usa scripts/ci-local/lib.sh (ci_correr)
# scripts/ci-local.sh [bloques…] [--lista]
# CI local de SpecBox Engine, estándar ci-local v1 (US-121 · UC-12101): la prueba de verdad antes de cada PR.
# Hace lo que hacían los workflows de GitHub, que desde ahora solo se lanzan a mano (workflow_dispatch):
#   secretos      gitleaks sobre el árbol y el historial
#   dependencias  uv sync --extra dev (lo necesitan python, native, migraciones e inventario)
#   python        la suite de pytest sin las pruebas de Postgres
#   native        pruebas native_db contra un Postgres 16 desechable (Docker)              ← native-tests.yml
#   migraciones   una versión por migración y la superficie de la base en un Postgres limpio ← db-surface-check.yml
#   inventario    el inventario que publica el site, contra el tools/list real              ← site-inventory.yml
#   extension     extensión de VS Code: dependencias, compilar, textos y pruebas            ← oauth-e2e.yml
#   cli           CLI specbox: espera de npm, pruebas y contenido del paquete               ← specbox-cli.yml
#   hooks         hooks, documentos, design-review, visual-setup y comprobaciones del MCP   ← hooks.yml, mcp-hosts.yml
#   contenedor    la imagen del servidor arranca sana y su proceso no es root (Docker)     ← container-nonroot.yml
# Requisitos: uv, node ≥ 22, npm, docker y gitleaks. Las pruebas en Windows (extension-windows.yml) y la
# comprobación semanal de los dos nombres del MCP (mcp-hosts.yml) siguen en GitHub, a mano o programadas.
# Cada bloque con Postgres o con la imagen usa sus propios contenedores, con nombre y puerto propios, y los borra al acabar.
# Avance: bash scripts/ci-local/lib.sh estado · registros en $TMPDIR/ci-local/<copia>/ (CI_LOCAL_LOGS lo cambia)
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$ROOT/scripts/ci-local/lib.sh"

CI_NOMBRE="SpecBox Engine"
CI_BLOQUES="secretos dependencias python native migraciones inventario extension cli hooks contenedor"
CI_DOCKER="native migraciones contenedor"
CI_NECESITA_python="dependencias"
CI_NECESITA_native="dependencias"
CI_NECESITA_migraciones="dependencias"
CI_NECESITA_inventario="dependencias"
CI_LIMITE_python=1800
CI_LIMITE_native=1800
CI_LIMITE_contenedor=1500

# ── Postgres desechable: el mismo servicio que levantaban los workflows ───────────────────────────
PG_CONTENEDOR=""
pg_arrancar() { # $1 = sufijo del contenedor → exporta SPECBOX_NATIVE_DSN
  PG_CONTENEDOR="ci-engine-$1-$$"
  docker rm -f "$PG_CONTENEDOR" >/dev/null 2>&1
  docker run -d --rm --name "$PG_CONTENEDOR" \
    -e POSTGRES_DB=specbox_native -e POSTGRES_USER=specbox -e POSTGRES_PASSWORD=specbox_dev_only \
    -p 127.0.0.1::5432 postgres:16-alpine >/dev/null || return 1
  local i
  for i in $(seq 1 60); do
    # Por TCP: durante la inicialización el servidor temporal solo escucha en el socket local.
    docker exec "$PG_CONTENEDOR" pg_isready -h 127.0.0.1 -U specbox -d specbox_native >/dev/null 2>&1 && break
    sleep 1
  done
  local puerto
  puerto="$(docker port "$PG_CONTENEDOR" 5432/tcp | head -1 | sed 's/.*://')"
  [ -n "$puerto" ] || return 1
  export SPECBOX_NATIVE_DSN="postgresql://specbox:specbox_dev_only@127.0.0.1:$puerto/specbox_native"
  echo "Postgres desechable $PG_CONTENEDOR en el puerto $puerto"
}
pg_parar() { [ -n "$PG_CONTENEDOR" ] && docker rm -f "$PG_CONTENEDOR" >/dev/null 2>&1; true; }

# ── Bloques ────────────────────────────────────────────────────────────────────────────────────────
secretos() { ci_secretos; }

dependencias() { cd "$ROOT" && ci_paso "uv sync" uv sync --extra dev; }

python() { cd "$ROOT" && ci_paso "pytest" uv run pytest -q -m "not native_db" tests; }

native() {
  cd "$ROOT" || return 1
  pg_arrancar native || { pg_parar; return 1; }
  ci_paso "Postgres accesible" uv run python -c "from tests._native_db import reachable; ok, why = reachable(); assert ok, why; print('Postgres reachable')" &&
    ci_paso "pytest native_db" uv run pytest -m native_db -rs --durations=15 tests
  local rc=$?
  pg_parar
  return "$rc"
}

superficie_base() { # la base como la entrega Supabase y después las migraciones del engine (db-surface-check.yml)
  uv run python - <<'EOF'
import asyncio
import os

import asyncpg

from server.db.migrate import apply_migrations

SUPABASE_DEFAULTS = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN CREATE ROLE service_role NOLOGIN BYPASSRLS; END IF;
END $$;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon, authenticated, service_role;
"""


async def main() -> None:
    conn = await asyncpg.connect(os.environ["SPECBOX_NATIVE_DSN"])
    try:
        await conn.execute(SUPABASE_DEFAULTS)
        applied = await apply_migrations(conn)
        print(f"{len(applied)} migrations applied, last {applied[-1]}")
    finally:
        await conn.close()


asyncio.run(main())
EOF
}

migraciones() {
  cd "$ROOT" || return 1
  ci_paso "Una versión por migración" uv run python -m server.db.migration_twins || return 1
  pg_arrancar superficie || { pg_parar; return 1; }
  ci_paso "Base de Supabase y migraciones" superficie_base &&
    ci_paso "Superficie" uv run python -m server.db.surface_check --schemas public &&
    ci_paso "Pruebas de superficie" uv run pytest -q tests/test_db_surface_views.py tests/test_db_surface_tables.py \
      tests/test_db_surface_check.py tests/test_migration_twins.py
  local rc=$?
  pg_parar
  return "$rc"
}

inventario() { cd "$ROOT" && ci_paso "pytest" uv run pytest -rs tests/test_site_publish_*.py; }

textos_extension() ( cd "$ROOT" && node scripts/lint-extension-strings.mjs ) # se lanza desde la raíz, como en oauth-e2e.yml

extension() {
  cd "$ROOT/vscode-extension" || return 1
  ci_paso "npm ci" npm ci --no-audit --no-fund &&
    ci_paso "Compilar" npm run compile &&
    ci_paso "Textos de la extensión" textos_extension &&
    ci_paso "Pruebas" node --test tests/*.test.mjs
}

paquete_cli() { # el paquete publica solo bin, lib, hooks y README (specbox-cli.yml)
  npm pack --dry-run --json > "$CI_DIR/cli-pack.json" || return 1
  PACK_JSON="$CI_DIR/cli-pack.json" node -e "
    // npm ≤ 11 prints an array; npm ≥ 12 prints an object keyed by package name.
    const out = require(process.env.PACK_JSON);
    const pkg = Array.isArray(out) ? out[0] : (out.files ? out : Object.values(out)[0]);
    const files = (pkg.files || []).map(f => f.path);
    if (!files.length) { console.error('npm pack no devolvió ficheros:', JSON.stringify(out).slice(0, 300)); process.exit(1); }
    // UC-11201: hooks/ lo genera prepack (scripts/pack-hooks.mjs) con su manifest.
    const bad = files.filter(p => !/^(bin|lib|hooks)\//.test(p) && !['README.md', 'package.json'].includes(p));
    if (bad.length) { console.error('Ficheros inesperados en el paquete:', bad); process.exit(1); }
    if (!files.includes('hooks/hooks-manifest.json')) { console.error('Falta hooks/hooks-manifest.json (prepack)'); process.exit(1); }
    console.log(files.join('\n'));
  "
}

cli() {
  cd "$ROOT" || return 1
  ci_paso "Publicar y esperar a npm" bash scripts/tests/test-npm-publish-and-wait.sh &&
    cd "$ROOT/packages/specbox-cli" &&
    ci_paso "Pruebas" node --test test/*.test.mjs &&
    ci_paso "Contenido del paquete" paquete_cli
}

hooks() {
  cd "$ROOT" || return 1
  ci_paso "Hooks, documentos y diseño" node --test tests/hooks/*.test.mjs tests/docs/*.test.mjs \
    tests/design-review/*.test.mjs tests/visual-setup/*.test.mjs .claude/hooks/lib/*.test.mjs &&
    ci_paso "test-hooks" node .claude/hooks/test-hooks.mjs &&
    ci_paso "Comprobaciones del MCP" node --test scripts/check-mcp-hosts.test.mjs scripts/smoke-freeform-remote.test.mjs
}

esperar_salud() { # $1 = contenedor
  local i
  for i in $(seq 1 30); do
    docker exec "$1" curl -sf http://localhost:8000/health && return 0
    sleep 2
  done
  docker logs "$1"
  return 1
}

contenedor() {
  cd "$ROOT" || return 1
  local tag="specbox-engine:ci-local-$$" nombre="ci-engine-servidor-$$" vol="ci-engine-estado-$$"
  ci_paso "Imagen" docker build -t "$tag" . || { docker rmi "$tag" >/dev/null 2>&1; return 1; }
  docker volume create "$vol" >/dev/null &&
    docker run --rm -v "$vol":/data/state --entrypoint sh "$tag" \
      -c 'mkdir -p /data/state/projects && echo "{}" > /data/state/registry.json && chown -R root:root /data/state' &&
    docker run -d --name "$nombre" -e SPECBOX_TRANSPORT_AUTH=enforce -v "$vol":/data/state "$tag" >/dev/null &&
    ci_paso "Arranca sano" esperar_salud "$nombre" &&
    ci_paso "El proceso no es root" sh scripts/verify-nonroot.sh "$nombre"
  local rc=$?
  docker rm -f "$nombre" >/dev/null 2>&1
  docker volume rm "$vol" >/dev/null 2>&1
  docker rmi "$tag" >/dev/null 2>&1
  return "$rc"
}

# ── Orden ──────────────────────────────────────────────────────────────────────────────────────────
ci_abrir "$@"
command -v uv >/dev/null 2>&1 || ci_abortar "falta uv (https://docs.astral.sh/uv/)"
command -v node >/dev/null 2>&1 || ci_abortar "falta node ≥ 22"
if ci_elegido native || ci_elegido migraciones || ci_elegido contenedor; then
  docker info >/dev/null 2>&1 || ci_abortar "Docker no responde: arranca Docker Desktop o elige bloques sin Docker"
fi

ci_correr secretos & P_SECRETOS=$!
ci_correr extension & P_EXTENSION=$!
ci_correr cli & P_CLI=$!
ci_correr hooks & P_HOOKS=$!
ci_correr contenedor & P_CONTENEDOR=$!
if ci_correr dependencias; then
  ci_correr python & P_PYTHON=$!
  ci_correr native & P_NATIVE=$!
  ci_correr migraciones & P_MIGRACIONES=$!
  ci_correr inventario & P_INVENTARIO=$!
  wait "$P_PYTHON" "$P_NATIVE" "$P_MIGRACIONES" "$P_INVENTARIO"
else
  for b in python native migraciones inventario; do ci_saltar "$b" "falló dependencias"; done
fi
wait "$P_SECRETOS" "$P_EXTENSION" "$P_CLI" "$P_HOOKS" "$P_CONTENEDOR"
ci_cerrar
