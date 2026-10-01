"""UC-5901 — una prueba que deja la pool abierta no bloquea a las siguientes.

La suite completa contra Postgres se colgaba: una prueba terminaba con la pool
compartida (``server.db.pool``, un singleton por proceso) todavía abierta y una
conexión a medias —dentro de una transacción, con bloqueos—. El event loop de
esa prueba se cerraba, nadie cerraba la pool y otras pruebas la soltaban con
``_pool = None``: la sesión seguía viva en el servidor con sus bloqueos, y el
siguiente ``apply_migrations`` esperaba esos bloqueos para siempre.

``tests/conftest.py`` cierra ahora la pool al terminar la prueba que la abrió,
en su propio loop. Estas dos pruebas reproducen el caso, en orden: la primera
deja una conexión retenida con un bloqueo; la segunda comprueba que empieza sin
pool heredada y que nadie retiene ya ese bloqueo.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

import server.db.pool as native_pool
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)

#: Bloqueo consultivo que la primera prueba deja retenido.
_LOCK_KEY = uuid.uuid4().int % 2**62
_left_behind: dict[str, int] = {}


async def test_a_test_ends_holding_a_pool_connection_and_a_lock():
    pool = await native_pool.init_pool(dsn=DSN)
    conn = await pool.acquire()  # nunca se devuelve: así acababa la prueba culpable
    await conn.execute("BEGIN")
    assert await conn.fetchval("SELECT pg_try_advisory_lock($1)", _LOCK_KEY)
    _left_behind["pid"] = await conn.fetchval("SELECT pg_backend_pid()")


async def test_the_next_test_starts_without_that_pool_nor_its_lock():
    assert "pid" in _left_behind, "la prueba anterior debe ejecutarse primero"
    assert native_pool._pool is None, "una pool de otra prueba (y de otro loop) seguía viva"

    pool = await native_pool.init_pool(dsn=DSN)
    async with pool.acquire() as conn:
        # El servidor cierra la sesión en cuanto el cliente corta; se da un margen.
        for _ in range(50):
            alive = await conn.fetchval("SELECT count(*) FROM pg_stat_activity WHERE pid = $1", _left_behind["pid"])
            if not alive:
                break
            await asyncio.sleep(0.1)
        assert not alive, "la sesión de la prueba anterior sigue abierta en el servidor"
        assert await conn.fetchval("SELECT pg_try_advisory_lock($1)", _LOCK_KEY), (
            "el bloqueo de la prueba anterior sigue retenido"
        )
        await conn.execute("SELECT pg_advisory_unlock($1)", _LOCK_KEY)
