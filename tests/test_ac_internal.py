"""US-33 / UC-3301 — la marca `internal` en los criterios de aceptación.

D7 convierte los AC en entregable cara-al-cliente. `internal` es el opt-out:
retira un AC de lo que ve el stakeholder en el portal de negocio sin borrarlo
ni darlo por cumplido.

Los tres AC de la UC:

- **AC-01**: la columna existe con `NOT NULL DEFAULT false` y, tras migrar,
  todos los AC preexistentes quedan **visibles**; ninguno se oculta solo.
- **AC-02**: hay una tool que marca y desmarca, y que devuelve error si el AC
  no existe **en el proyecto de la sesión** (aislamiento por tenant).
- **AC-03**: `mark_ac` / `mark_ac_batch` **preservan** `internal` al mover
  `done`. Se valida **por mutación**: el test debe fallar si el UPDATE deja de
  nombrar columnas. Un test que pasa con y sin el comportamiento no prueba nada.

Postgres-gated: hacen SKIP limpio si no hay DB de dev alcanzable
(``docker compose -f docker-compose.dev.yml up -d``).
"""

from __future__ import annotations

import uuid

import pytest

from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_shared_pool():
    """Deja el pool global a None ANTES y DESPUÉS de cada test de este módulo.

    Sin el reset posterior, este fichero era mal vecino: dejaba en el global un
    pool atado a SU último event loop, y el siguiente módulo de tests que
    llamara a `init_pool` recibía un pool muerto. Medido: la suite conjunta
    pasaba de 13 fallos (línea base de `origin/main`) a 21 solo por el orden.
    """
    import server.db.pool as poolmod

    poolmod._pool = None
    yield
    poolmod._pool = None


async def _pool():
    """Pool NUEVO para cada test, ligado a su propio event loop.

    `init_pool` es un singleton de módulo: devuelve el pool ya creado si existe.
    Con `asyncio_mode="auto"` pytest-asyncio da un loop por test, así que el pool
    del primer test queda atado a un loop muerto y el segundo revienta con
    `Event loop is closed`. Resetear el global antes de crearlo es lo que hace
    que la suite sea ejecutable de corrido y no solo test a test.
    """
    import server.db.pool as poolmod
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    poolmod._pool = None  # el pool anterior pertenece a un loop ya cerrado
    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _seed_project_with_ac(pool, *, n_acs: int = 3):
    """Crea tenant + developer miembro + US + UC + N AC. Devuelve los ids."""
    from server.coordination.identity import (
        add_project_member,
        register_developer,
        register_mcp_token,
    )

    project_id = f"Acme/ac-internal-{uuid.uuid4().hex[:8]}"
    developer_id = f"ai-dev-{uuid.uuid4().hex[:8]}"
    token = f"ai-tok-{uuid.uuid4().hex[:16]}"
    uc_id = "UC-001"

    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="AC Internal Tester")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute(
            "INSERT INTO projects (project_id, name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            project_id,
            "AC Internal",
        )
        await add_project_member(
            conn, project_id=project_id, developer_id=developer_id, role="project_admin"
        )
        await conn.execute(
            "INSERT INTO user_stories (id, project_id, name, state) VALUES ($1,$2,$3,$4)",
            "US-01",
            project_id,
            "US de prueba",
            "backlog",
        )
        await conn.execute(
            "INSERT INTO use_cases (id, project_id, us_id, name, state) VALUES ($1,$2,$3,$4,$5)",
            uc_id,
            project_id,
            "US-01",
            "UC de prueba",
            "backlog",
        )
        for n in range(1, n_acs + 1):
            ac_id = f"AC-{n:02d}"
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text) "
                "VALUES ($1,$2,$3,$4,$5)",
                f"{uc_id}::{ac_id}",
                project_id,
                uc_id,
                ac_id,
                f"Criterio numero {n}",
            )
    return project_id, developer_id, token, uc_id


async def _cleanup(pool, project_id: str, developer_id: str):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)


def _backend(project_id: str, token: str):
    from server.backends.native_backend import NativeBackend

    return NativeBackend(project_id=project_id, dev_token=token)


# ═══════════════════════════════════════════════════════════════════════
# AC-01 — la columna, su default y la no-ocultación
# ═══════════════════════════════════════════════════════════════════════


@pytestmark_pg
class TestColumnAndDefault:
    async def test_column_exists_not_null_default_false(self):
        """AC-01: `internal boolean not null default false`."""
        pool = await _pool()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'acceptance_criteria' AND column_name = 'internal'
                    """
                )
            assert row is not None, "la columna internal no existe tras migrar"
            assert row["data_type"] == "boolean"
            assert row["is_nullable"] == "NO"
            assert "false" in (row["column_default"] or "").lower()
        finally:
            pass  # `init_pool` devuelve un pool COMPARTIDO a nivel de módulo:
            # cerrarlo aquí lo dejaría inservible para el resto de la sesión de
            # pytest. Los tests native del engine nunca lo cierran, por eso.

    async def test_existing_acs_stay_visible(self):
        """AC-01: ningún AC preexistente queda oculto — todos `internal=false`."""
        pool = await _pool()
        project_id, developer_id, _token, _uc = await _seed_project_with_ac(pool, n_acs=5)
        try:
            async with pool.acquire() as conn:
                total = await conn.fetchval(
                    "SELECT count(*) FROM acceptance_criteria WHERE project_id = $1", project_id
                )
                ocultos = await conn.fetchval(
                    "SELECT count(*) FROM acceptance_criteria WHERE project_id = $1 AND internal",
                    project_id,
                )
            assert total == 5
            assert ocultos == 0, "la migración ocultó AC que debían quedar visibles"
        finally:
            await _cleanup(pool, project_id, developer_id)

    async def test_migration_is_idempotent(self):
        """Re-aplicar el ledger no falla ni cambia el estado (runner local + tests)."""
        from server.db.migrate import apply_migrations

        pool = await _pool()
        try:
            await apply_migrations(pool)  # segunda pasada
            async with pool.acquire() as conn:
                n = await conn.fetchval(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name='acceptance_criteria' AND column_name='internal'"
                )
            assert n == 1
        finally:
            pass  # `init_pool` devuelve un pool COMPARTIDO a nivel de módulo:
            # cerrarlo aquí lo dejaría inservible para el resto de la sesión de
            # pytest. Los tests native del engine nunca lo cierran, por eso.


# ═══════════════════════════════════════════════════════════════════════
# AC-02 — marcar, desmarcar y aislamiento por tenant
# ═══════════════════════════════════════════════════════════════════════


@pytestmark_pg
class TestSetAcInternal:
    async def test_mark_and_unmark(self):
        """AC-02: marca y desmarca, y el valor viaja en el DTO."""
        pool = await _pool()
        project_id, developer_id, token, uc_id = await _seed_project_with_ac(pool)
        backend = _backend(project_id, token)
        try:
            marcado = await backend.set_ac_internal(project_id, uc_id, "AC-01", True)
            assert marcado.internal is True

            leidos = await backend.get_acceptance_criteria(project_id, uc_id)
            por_id = {a.id: a for a in leidos}
            assert por_id["AC-01"].internal is True
            assert por_id["AC-02"].internal is False, "marcar uno no debe arrastrar a los demás"

            desmarcado = await backend.set_ac_internal(project_id, uc_id, "AC-01", False)
            assert desmarcado.internal is False
        finally:
            await backend.close()
            await _cleanup(pool, project_id, developer_id)

    async def test_unknown_ac_raises(self):
        """AC-02: un AC inexistente da error, no un no-op silencioso."""
        pool = await _pool()
        project_id, developer_id, token, uc_id = await _seed_project_with_ac(pool)
        backend = _backend(project_id, token)
        try:
            with pytest.raises(ValueError):
                await backend.set_ac_internal(project_id, uc_id, "AC-99", True)
        finally:
            await backend.close()
            await _cleanup(pool, project_id, developer_id)

    async def test_ac_of_another_tenant_is_not_found(self):
        """AC-02: un AC de OTRO proyecto es, desde esta sesión, inexistente.

        ESTE TEST ENCONTRÓ UN FALLO REAL. Escrito como "un AC inexistente da
        error" habría pasado en verde; escrito como "un AC de otro tenant es
        inexistente" falló con DID NOT RAISE y destapó que
        `_require_membership_cached()` valida contra `self.project_id` mientras
        el WHERE usa el `board_id` recibido — es decir, la sesión de A escribía
        en el proyecto de B. Verificado también sobre `mark_acceptance_criterion`,
        que es preexistente y comparte el hueco (se aborda en UC aparte).

        Aquí se fija el contrato del método nuevo: cruzar de tenant es
        indistinguible de que el AC no exista.
        """
        pool = await _pool()
        p_a, dev_a, tok_a, uc = await _seed_project_with_ac(pool)
        p_b, dev_b, _tok_b, _ = await _seed_project_with_ac(pool)
        backend_a = _backend(p_a, tok_a)
        try:
            # La sesión de A intenta tocar el AC de B usando el board_id de B.
            with pytest.raises(ValueError):
                await backend_a.set_ac_internal(p_b, uc, "AC-01", True)

            async with pool.acquire() as conn:
                oculto_en_b = await conn.fetchval(
                    "SELECT internal FROM acceptance_criteria "
                    "WHERE project_id=$1 AND uc_id=$2 AND ac_id=$3",
                    p_b,
                    uc,
                    "AC-01",
                )
            assert oculto_en_b is False, "una sesión ajena ocultó un AC de otro tenant"
        finally:
            await backend_a.close()
            await _cleanup(pool, p_a, dev_a)
            await _cleanup(pool, p_b, dev_b)


# ═══════════════════════════════════════════════════════════════════════
# AC-03 — `mark_ac` preserva `internal` (validado por mutación)
# ═══════════════════════════════════════════════════════════════════════


@pytestmark_pg
class TestMarkAcPreservesInternal:
    async def test_closing_an_internal_ac_keeps_it_internal(self):
        """AC-03: cerrar un AC marcado como interno NO lo vuelve visible.

        Mutación que debe hacer fallar este test: cambiar el UPDATE de
        `mark_acceptance_criterion` por uno que reescriba la fila entera (o que
        añada `internal = false`). Si el test sigue pasando tras esa mutación,
        no está probando nada.
        """
        pool = await _pool()
        project_id, developer_id, token, uc_id = await _seed_project_with_ac(pool)
        backend = _backend(project_id, token)
        try:
            await backend.set_ac_internal(project_id, uc_id, "AC-01", True)

            cerrado = await backend.mark_acceptance_criterion(project_id, uc_id, "AC-01", True)
            assert cerrado.done is True
            assert cerrado.internal is True, "cerrar el AC borró su marca de interno"

            reabierto = await backend.mark_acceptance_criterion(project_id, uc_id, "AC-01", False)
            assert reabierto.done is False
            assert reabierto.internal is True, "reabrir el AC borró su marca de interno"
        finally:
            await backend.close()
            await _cleanup(pool, project_id, developer_id)

    async def test_set_internal_does_not_move_done(self):
        """La simétrica: ocultar un AC no lo da por cumplido.

        `internal` y `done` son decisiones distintas. El UPDATE de
        `set_ac_internal` nombra `internal` y nada más, igual que el de
        `mark_ac` nombra `done` y nada más.
        """
        pool = await _pool()
        project_id, developer_id, token, uc_id = await _seed_project_with_ac(pool)
        backend = _backend(project_id, token)
        try:
            await backend.mark_acceptance_criterion(project_id, uc_id, "AC-02", True)
            tras_ocultar = await backend.set_ac_internal(project_id, uc_id, "AC-02", True)
            assert tras_ocultar.done is True, "ocultar el AC movió su estado de cumplimiento"

            visible_no_hecho = await backend.set_ac_internal(project_id, uc_id, "AC-03", True)
            assert visible_no_hecho.done is False
        finally:
            await backend.close()
            await _cleanup(pool, project_id, developer_id)


# ═══════════════════════════════════════════════════════════════════════
# Backends sin soporte — fallan con motivo, no en silencio
# ═══════════════════════════════════════════════════════════════════════


class TestUnsupportedBackends:
    """El default del ABC lanza: un no-op silencioso dejaría al operador
    creyendo que ocultó un AC que sigue proyectándose en la reunión."""

    def test_abc_default_raises_not_implemented(self):
        import asyncio
        import inspect

        from server.spec_backend import SpecBackend

        assert inspect.iscoroutinefunction(SpecBackend.set_ac_internal)

        class _Dummy(SpecBackend):
            pass

        # No se instancia (SpecBackend es abstracta): se invoca el default sin
        # ligarlo a una instancia concreta.
        with pytest.raises(NotImplementedError):
            asyncio.run(SpecBackend.set_ac_internal(object(), "b", "UC-001", "AC-01", True))
