"""US-34 / UC-3401 — inventario verificado de aislamiento por tenant.

El hueco (encontrado el 2026-08-24 implementando UC-3301):
`NativeBackend._require_membership_cached()` valida la membresía contra
``self.project_id`` —el proyecto de la SESIÓN— mientras los mutadores reciben
``board_id`` como argumento y lo usan en el ``WHERE``. Como las tools MCP
exponen ``board_id`` al llamante, una sesión autenticada en el proyecto A puede
escribir en el proyecto B.

Este módulo NO arregla nada: **mide**. Produce el inventario que UC-3402 va a
cerrar y que UC-3403 convertirá en red permanente.

Por qué contra Postgres real y no mocks (AC-03): el hueco no vive en ninguna de
las dos piezas por separado —la comprobación de membresía es correcta, el WHERE
es correcto— sino en que hablan de proyectos distintos. Un mock de cualquiera de
las dos reproduce la intención del autor, no el comportamiento del sistema. Con
mocks este fallo es invisible.
"""

from __future__ import annotations

import uuid

import pytest

from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


@pytest.fixture(autouse=True)
def _reset_shared_pool():
    """`init_pool` es singleton de módulo y pytest-asyncio da un loop por test."""
    import server.db.pool as poolmod

    poolmod._pool = None
    yield
    poolmod._pool = None


async def _pool():
    import server.db.pool as poolmod
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    poolmod._pool = None
    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _seed_tenant(pool, tag: str):
    """Tenant completo: developer miembro + US + UC + 3 AC + comentario."""
    from server.coordination.identity import (
        add_project_member,
        register_developer,
        register_mcp_token,
    )

    project_id = f"Acme/{tag}-{uuid.uuid4().hex[:8]}"
    developer_id = f"ti-{tag}-{uuid.uuid4().hex[:8]}"
    token = f"ti-tok-{uuid.uuid4().hex[:16]}"

    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name=f"Tenant {tag}")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute(
            "INSERT INTO projects (project_id, name) VALUES ($1,$2) ON CONFLICT DO NOTHING",
            project_id,
            f"Tenant {tag}",
        )
        await add_project_member(
            conn, project_id=project_id, developer_id=developer_id, role="project_admin"
        )
        await conn.execute(
            "INSERT INTO user_stories (id, project_id, name, state) VALUES ($1,$2,$3,'backlog')",
            "US-01",
            project_id,
            "US victima",
        )
        await conn.execute(
            "INSERT INTO use_cases (id, project_id, us_id, name, state) VALUES ($1,$2,'US-01',$3,'backlog')",
            "UC-001",
            project_id,
            "UC victima",
        )
        for n in (1, 2, 3):
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text) "
                "VALUES ($1,$2,'UC-001',$3,$4)",
                f"UC-001::AC-{n:02d}",
                project_id,
                f"AC-{n:02d}",
                f"Criterio {n} del tenant {tag}",
            )
    return project_id, developer_id, token


async def _snapshot(pool, project_id: str) -> dict:
    """Huella del estado escribible del tenant, para comparar antes/después.

    No basta con mirar la fila que el mutador diría tocar: se comparan TODAS las
    superficies escribibles del tenant, porque un mutador que lanza tras haber
    escrito en OTRO sitio seguiría siendo una fuga.

    El `meta` de US y UC va incluido a propósito: en Native los comentarios y los
    adjuntos NO tienen tabla propia — viven dentro del JSONB del propio ítem. Sin
    capturarlo, `add_comment` y `add_attachment` podrían escribir en el tenant
    ajeno sin que este snapshot lo notara.
    """
    async with pool.acquire() as conn:
        return {
            "us": [
                dict(r)
                for r in await conn.fetch(
                    "SELECT id, name, state, version, meta::text FROM user_stories "
                    "WHERE project_id=$1 ORDER BY id",
                    project_id,
                )
            ],
            "uc": [
                dict(r)
                for r in await conn.fetch(
                    "SELECT id, name, state, version, meta::text FROM use_cases "
                    "WHERE project_id=$1 ORDER BY id",
                    project_id,
                )
            ],
            "ac": [
                dict(r)
                for r in await conn.fetch(
                    "SELECT ac_id, text, done, internal, version FROM acceptance_criteria "
                    "WHERE project_id=$1 ORDER BY ac_id",
                    project_id,
                )
            ],
            "proyecto_meta": await conn.fetchval(
                "SELECT meta::text FROM projects WHERE project_id=$1", project_id
            ),
        }


async def _cleanup(pool, *tenants):
    async with pool.acquire() as conn:
        for project_id, developer_id, _tok in tenants:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)


def _backend(project_id: str, token: str):
    from server.backends.native_backend import NativeBackend

    return NativeBackend(project_id=project_id, dev_token=token)


# ═══════════════════════════════════════════════════════════════════════
# El catálogo de mutadores a probar
# ═══════════════════════════════════════════════════════════════════════
#
# Cada entrada es (nombre, callable(backend, board_id_ajeno)). El callable
# intenta UNA escritura sobre el proyecto ajeno. Si retorna sin excepción, el
# mutador es vulnerable.
#
# `set_ac_internal` va incluido a propósito aunque ya lleva guard desde
# UC-3301: es el control positivo del inventario. Si apareciera como vulnerable,
# el propio inventario estaría mal construido.

MUTATORS = [
    # OJO con este: con un nombre sin prefijo `US-`/`UC-`, create_item lanza por
    # una validación de NOMBRE y nunca llega a la escritura — parecía protegido
    # y no lo estaba. La sonda tiene que atravesar las validaciones previas para
    # que lo que se mida sea el aislamiento y no otra cosa.
    ("create_item", lambda b, p: b.create_item(p, "US-99: inyectada por otro tenant", labels=["US"])),
    ("update_item", lambda b, p: b.update_item(p, "UC-001", name="renombrada por otro tenant")),
    ("mark_acceptance_criterion", lambda b, p: b.mark_acceptance_criterion(p, "UC-001", "AC-01", True)),
    ("set_ac_internal", lambda b, p: b.set_ac_internal(p, "UC-001", "AC-01", True)),
    ("create_acceptance_criteria", lambda b, p: b.create_acceptance_criteria(p, "UC-001", [("AC-09", "AC inyectado")])),
    ("update_acceptance_criterion", lambda b, p: b.update_acceptance_criterion(p, "UC-001", "AC-02", text="reescrito por otro tenant")),
    ("delete_acceptance_criterion", lambda b, p: b.delete_acceptance_criterion(p, "UC-001", "AC-03")),
    ("archive_item", lambda b, p: b.archive_item(p, "UC-001", reason="archivada por otro tenant")),
    ("add_comment", lambda b, p: b.add_comment(p, "UC-001", "comentario de otro tenant")),
    ("add_attachment", lambda b, p: b.add_attachment(p, "UC-001", "ajeno.pdf", b"%PDF-1.4 ajeno")),
    ("create_label", lambda b, p: b.create_label(p, "etiqueta-ajena", "#ff0000")),
]

#: Métodos que reciben `board_id` y llevan verbo de escritura en el nombre pero
#: NO tocan la base: en Native los módulos son implícitos (la jerarquía va por
#: la FK `us_id`), así que estos dos son stubs del ABC. No hay nada que aislar,
#: pero tienen que estar clasificados: si algún día pasan a escribir de verdad,
#: `test_stubs_write_nothing` falla y obliga a moverlos a MUTATORS.
STUB_METHODS = ["create_module", "add_items_to_module"]

# ═══════════════════════════════════════════════════════════════════════
# EL INVENTARIO — cerrado por UC-3402 el 2026-08-24
# ═══════════════════════════════════════════════════════════════════════
#
#   VULNERABLES: 0  ·  PROTEGIDOS: 11  ·  STUBS: 2  ·  sin clasificar: 0
#
# Estado medido por UC-3401 (2026-08-24): 10 vulnerables de 11 mutadores. Los
# diez completaban la escritura sobre un proyecto ajeno sin error.
#
# UC-3402 los cerró de una vez llevando la validación al punto donde se cruzan
# las dos piezas: `_require_membership_cached(board_id)` valida contra el
# proyecto QUE SE VA A ESCRIBIR, no contra el de la sesión.
#
# El `strict=True` hizo su trabajo: al aplicar el arreglo, los diez pasaron a
# XPASS y la suite se puso ROJA, obligando a vaciar esta lista en el mismo PR.
# Se conserva el mecanismo —no la lista— porque un mutador nuevo mal escrito
# volverá a aparecer aquí, y `test_catalog_covers_every_mutator` obliga a
# clasificarlo.
VULNERABLE: set[str] = set()


def _caso(nombre, operacion):
    """Envuelve el caso con xfail(strict) si el mutador está inventariado como vulnerable."""
    if nombre in VULNERABLE:
        return pytest.param(
            nombre,
            operacion,
            id=nombre,
            marks=pytest.mark.xfail(
                strict=True,
                reason=f"UC-3401: {nombre} completa la escritura cross-tenant. Lo cierra UC-3402.",
            ),
        )
    return pytest.param(nombre, operacion, id=nombre)


CASOS = [_caso(n, op) for n, op in MUTATORS]


@pytestmark_pg
class TestMutatorInventory:
    """AC-01/02/03: cada mutador se prueba desde otro tenant y se clasifica."""

    @pytest.mark.parametrize("nombre,operacion", CASOS)
    async def test_mutator_rejects_cross_tenant_write(self, nombre, operacion):
        """Un mutador NO debe completar una escritura sobre un proyecto ajeno.

        US-34/UC-3403 endurece el aserto. Hasta UC-3402 bastaba con `raises
        (Exception)`, porque lo que se medía era *si* la escritura se completaba.
        Como red permanente eso es débil: un `TypeError` por refactor, un fallo
        de conexión o una validación de nombre —el caso real que estuvo a punto
        de colar un falso negativo en el inventario— darían el test por bueno sin
        que exista aislamiento alguno.

        Ahora se exigen las tres cosas que definen "rechazar":

        1. la excepción es **`ForbiddenError`**, el vocabulario de no-membresía;
        2. la fila de la víctima queda **sin tocar**;
        3. el intento queda **registrado** en `audit_log` contra la víctima.

        La 2 es la que de verdad importa: una excepción con la escritura ya
        aplicada sería el peor de los mundos, y sin comprobarla el test no
        distingue ese caso.
        """
        from server.coordination.audit import OP_CROSS_TENANT_DENIED
        from server.coordination.identity import ForbiddenError

        pool = await _pool()
        atacante = await _seed_tenant(pool, "a")
        victima = await _seed_tenant(pool, "b")
        backend = _backend(atacante[0], atacante[2])
        try:
            antes = await _snapshot(pool, victima[0])

            with pytest.raises(ForbiddenError):
                await operacion(backend, victima[0])

            despues = await _snapshot(pool, victima[0])
            assert antes == despues, (
                f"{nombre} lanzó, pero la escritura sobre el tenant ajeno se aplicó igual. "
                f"antes={antes} después={despues}"
            )

            async with pool.acquire() as conn:
                registrado = await conn.fetchval(
                    "SELECT count(*) FROM audit_log "
                    "WHERE project_id = $1 AND operation = $2 AND developer_id = $3",
                    victima[0],
                    OP_CROSS_TENANT_DENIED,
                    atacante[1],
                )
            assert registrado >= 1, (
                f"{nombre} rechazó el intento pero no dejó rastro en audit_log: "
                "la víctima no tiene forma de saber que alguien lo intentó."
            )
        finally:
            await backend.close()
            await _cleanup(pool, atacante, victima)

    async def test_catalog_covers_every_mutator(self):
        """AC-02: ningún mutador queda sin clasificar.

        Compara el catálogo contra los métodos públicos del backend que reciben
        `board_id` y escriben. Si alguien añade un mutador nuevo y no lo mete en
        MUTATORS, este test falla — que es lo que impide que el inventario
        envejezca en silencio.
        """
        import inspect

        from server.backends.native_backend import NativeBackend

        # Verbos de escritura. `set_`/`emit_` incluidos; los `get_`/`list_` no.
        prefijos_escritura = ("create_", "update_", "mark_", "set_", "delete_", "archive_", "add_")
        descubiertos = set()
        for nombre, miembro in inspect.getmembers(NativeBackend, inspect.isfunction):
            if nombre.startswith("_"):
                continue
            if not nombre.startswith(prefijos_escritura):
                continue
            params = inspect.signature(miembro).parameters
            if "board_id" not in params:
                continue
            descubiertos.add(nombre)

        catalogados = {m[0] for m in MUTATORS} | set(STUB_METHODS)
        sin_clasificar = descubiertos - catalogados
        assert not sin_clasificar, (
            "mutadores que reciben board_id y no están en el inventario: "
            f"{sorted(sin_clasificar)}. Añádelos a MUTATORS (si escriben) o a "
            "STUB_METHODS (si no tocan la base), o el hueco vuelve a crecer sin "
            "que nadie se entere."
        )

    @pytest.mark.parametrize("nombre", STUB_METHODS)
    async def test_stubs_write_nothing(self, nombre):
        """Los stubs no escriben, así que no hay tenant que aislar.

        Se comprueba ejecutando, no leyendo el código: se invoca el método sobre
        el proyecto ajeno y se verifica que el `updated_at` de ese proyecto no se
        mueve. Si alguien los implementa de verdad, este test falla y obliga a
        reclasificarlos como mutadores.
        """
        pool = await _pool()
        atacante = await _seed_tenant(pool, "a")
        victima = await _seed_tenant(pool, "b")
        backend = _backend(atacante[0], atacante[2])
        try:
            async with pool.acquire() as conn:
                antes = await conn.fetchval(
                    "SELECT updated_at FROM projects WHERE project_id = $1", victima[0]
                )
            metodo = getattr(backend, nombre)
            if nombre == "create_module":
                await metodo(victima[0], "modulo-ajeno")
            else:
                await metodo(victima[0], "mod-x", ["UC-001"])
            async with pool.acquire() as conn:
                despues = await conn.fetchval(
                    "SELECT updated_at FROM projects WHERE project_id = $1", victima[0]
                )
            assert antes == despues, f"{nombre} ya no es un stub: escribió en el proyecto ajeno"
        finally:
            await backend.close()
            await _cleanup(pool, atacante, victima)
