"""US-122 / UC-12217 — get_uc_reservation: quién tiene la reserva de una UC (solo lectura).

La usa spec-guard para revisar la reserva al escribir código. Modelo de amenazas §8: sin
identidad, otro developer (lo ajeno no existe) y la lectura de un miembro. SKIP limpio sin base de
datos (``docker compose -f docker-compose.dev.yml up -d``).
"""

from __future__ import annotations

import uuid

import pytest

from server.tools.coordination import get_uc_reservation
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


async def _pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _developer(conn, *, member_of: str | None = None):
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token

    developer_id = f"res-dev-{uuid.uuid4().hex[:8]}"
    token = f"res-tok-{uuid.uuid4().hex[:16]}"
    await register_developer(conn, developer_id=developer_id, display_name=developer_id)
    await register_mcp_token(conn, developer_id=developer_id, token=token)
    if member_of:
        await add_project_member(conn, project_id=member_of, developer_id=developer_id, role="member")
    return developer_id, token


async def test_get_uc_reservation_tells_who_holds_it_only_to_members():
    from server.coordination.reservations import release_uc, reserve_uc

    pool = await _pool()
    project_id = f"Acme/res-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'Reservas')", project_id)
        ana = await _developer(conn, member_of=project_id)
        luis = await _developer(conn, member_of=project_id)
        ajena = await _developer(conn)
    try:
        sin = await get_uc_reservation(None, "UC-7", project_id=project_id, dev_token="")
        assert sin["code"] == "UNAUTHENTICATED" and "reservation" not in sin
        fuera = await get_uc_reservation(None, "UC-7", project_id=project_id, dev_token=ajena[1])
        assert fuera["code"] == "PROJECT_NOT_VISIBLE" and "reservation" not in fuera
        mala = await get_uc_reservation(None, "lo-que-sea", project_id=project_id, dev_token=ana[1])
        assert mala["code"] == "INVALID_UC_ID"

        libre = await get_uc_reservation(None, "UC-7", project_id=project_id, dev_token=luis[1])
        assert libre == {"success": True, "project_id": project_id, "uc_id": "UC-7", "reservation": None}

        async with pool.acquire() as conn:
            await reserve_uc(conn, project_id=project_id, uc_id="UC-7", developer_id=ana[0], branch="feature/UC-7-x")
        tomada = await get_uc_reservation(None, "UC-7", project_id=project_id, dev_token=luis[1])
        assert tomada["reservation"]["developer_id"] == ana[0]
        assert tomada["reservation"]["branch"] == "feature/UC-7-x" and tomada["reservation"]["reserved_at"]

        async with pool.acquire() as conn:
            await release_uc(conn, project_id=project_id, uc_id="UC-7", developer_id=ana[0])
        assert (await get_uc_reservation(None, "UC-7", project_id=project_id, dev_token=ana[1]))["reservation"] is None
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
            for developer_id, _ in (ana, luis, ajena):
                await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)
