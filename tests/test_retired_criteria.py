"""UC-12501 (US-125) — un criterio conserva su id para siempre y el retirado sigue visible.

- AC-01 / AC-03: retirar AC-03 de AC-01..AC-05 deja AC-04 y AC-05 con su id; un criterio nuevo
  toma el siguiente id libre y nunca el de un retirado (tampoco si el retirado era el último).
- AC-02: el retirado queda con su motivo, su fecha, quién y sus recibos, y get_uc lo devuelve
  aparte de los vigentes; marcarlo o reescribirlo responde AC_RETIRED.
- AC-04: import_spec sobre una UC que ya existe no la toca y avisa uc_exists con la diferencia;
  con on_existing_uc="apply" añade los criterios nuevos emparejando por texto.
- AC-05: los retirados no cuentan en los totales que leen el panel, el portal y la app, y la
  migración 0039 no mueve ninguna fila.
- AC-06: las migraciones de backend llevan los retirados (FreeForm → native).
- AC-07: en FreeForm tampoco se renumera y el retirado queda en items.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.spec_backend import ChecklistItemDTO
from server.tools import _mutation_helpers as mh
from server.tools.spec_driven import get_uc, import_spec, mark_ac
from server.tools.spec_mutations import add_ac, delete_ac, update_ac
from tests.test_spec_gate_start_uc import CTX, US, _cleanup, _native_board, pg

ROOT = Path(__file__).resolve().parent.parent
REASON = "La cubre otra historia del tablero"
UC = {"id": "uc701", "name": "UC-701: Cobrar", "description": "# UC-701\n\n## Contexto\nCobro con tarjeta",
      "state": "backlog", "labels": ["UC"], "parent_id": "us7", "meta": {"uc_id": "UC-701", "us_id": "US-07"}}
TEXTS = [
    "El cobro queda registrado con su recibo",
    "El recibo incluye el importe y la fecha",
    "Un cobro rechazado muestra el motivo",
    "El historial muestra los cobros del mes",
    "La exportación incluye todos los cobros",
]


def _acs() -> list[dict]:
    return [
        {"id": f"ac{i}", "name": f"[AC-0{i}] {t}", "state": "backlog", "labels": ["AC"], "parent_id": "uc701",
         "meta": {"ac_id": f"AC-0{i}"}}
        for i, t in enumerate(TEXTS, 1)
    ]


def _board() -> str:
    return json.dumps([US, UC, *_acs()])


def _dto(ac_id: str, text: str, verification: str | None = None) -> ChecklistItemDTO:
    return ChecklistItemDTO(id=ac_id, text=text, done=False, verification=verification)


# ── La regla, sin tablero ───────────────────────────────────────────


def test_next_id_counts_the_retired_ones():
    existing = [_dto("AC-01", "a"), _dto("AC-02", "b")]
    assert mh.next_ac_id(existing) == "AC-03"
    assert mh.next_ac_id(existing, ["AC-03"]) == "AC-04"  # AC-03 retirado: no se reutiliza
    assert mh.next_ac_id([], ["AC-07"]) == "AC-08"


def _plan(spec: list[str], verifs: list[str | None] | None = None, *, retired=(), existing=None, **kw):
    existing = existing if existing is not None else [_dto("AC-01", "Uno queda"), _dto("AC-02", "Dos queda")]
    return mh.plan_existing_uc(
        existing_name=kw.get("name", "Cobrar"), existing_meta={"actor": "Cliente", "horas": 2},
        existing_description="# UC\n\n## Contexto\nCobro", existing_acs=existing, retired_ids=retired,
        spec_name=kw.get("spec_name", "Cobrar"), spec_meta={"actor": kw.get("actor", "Cliente"), "horas": 2.0},
        spec_context=kw.get("context", "Cobro"), spec_criteria=spec, spec_verifications=verifs or [],
        stores_meta=True,
    )


def test_an_identical_spec_changes_nothing():
    plan = _plan(["Uno queda", "Dos  queda"])  # los espacios repetidos no cuentan
    assert plan["identical"] and plan["new"] == [] and plan["differences"]["criteria_missing"] == []


def test_the_differences_name_what_would_change():
    plan = _plan(["Dos queda", "Tres nuevo"], ["review", None], retired=["AC-03"], spec_name="Cobrar bien",
                 actor="Tienda", context="Otro")
    diff = plan["differences"]
    assert diff["name"] == {"from": "Cobrar", "to": "Cobrar bien"}
    assert diff["fields"] == ["actor", "context"]
    assert diff["criteria_added"] == ["Tres nuevo"]
    assert diff["criteria_missing"] == [{"id": "AC-01", "text": "Uno queda"}]
    assert diff["verification_changed"] == [{"id": "AC-02", "from": None, "to": "review"}]
    # El nuevo toma el siguiente id libre contando el retirado; los vigentes conservan el suyo.
    assert plan["new"] == [("AC-04", "Tres nuevo")]
    assert plan["final"] == [("AC-01", "Uno queda"), ("AC-02", "Dos queda"), ("AC-04", "Tres nuevo")]


# ── FreeForm (AC-07) y las herramientas ─────────────────────────────


async def test_freeform_retiring_keeps_the_ids_and_the_retired_one_in_items_json():
    marked = await mark_ac("ff", "UC-701", "AC-04", True, CTX, items_content=_board(), evidence="pytest tests/x.py")
    out = await delete_ac("ff", "UC-701", "AC-03", CTX, reason=REASON, retired_by="Jesús", items_content=marked["items_content"])
    assert out["retired_ac_id"] == "AC-03" and "retired_not_stored" not in out
    items = json.loads(out["items_content"])
    uc = next(i for i in items if i["id"] == "uc701")
    [retired] = uc["meta"]["retired_criteria"]
    assert retired["id"] == "AC-03" and retired["reason"] == REASON and retired["retired_by"] == "Jesús"
    assert retired["text"] == TEXTS[2] and retired["retired_at"]
    ac_names = sorted(i["name"][:7] for i in items if "AC" in i.get("labels", []))
    assert ac_names == ["[AC-01]", "[AC-02]", "[AC-04]", "[AC-05]"]

    detail = await get_uc("ff", "UC-701", CTX, items_content=out["items_content"])
    assert [a["id"] for a in detail["acceptance_criteria"]] == ["AC-01", "AC-02", "AC-04", "AC-05"]
    assert detail["acceptance_criteria"][2]["evidence"]  # AC-04 conserva su recibo
    assert [r["id"] for r in detail["retired_criteria"]] == ["AC-03"]

    added = await add_ac("ff", "UC-701", "El cobro duplicado se rechaza", CTX, items_content=out["items_content"])
    assert added["ac_id"] == "AC-06"


async def test_freeform_the_last_retired_id_is_not_reused_and_retired_cannot_be_marked():
    out = await delete_ac("ff", "UC-701", "AC-05", CTX, reason=REASON, items_content=_board())
    added = await add_ac("ff", "UC-701", "El cobro duplicado se rechaza", CTX, items_content=out["items_content"])
    assert added["ac_id"] == "AC-06"  # no AC-05 otra vez
    marked = await mark_ac("ff", "UC-701", "AC-05", True, CTX, items_content=added["items_content"])
    assert marked["code"] == "AC_RETIRED" and marked["retired"]["reason"] == REASON
    rewritten = await update_ac("ff", "UC-701", "AC-05", CTX, text="Otro texto", items_content=added["items_content"])
    assert rewritten["code"] == "AC_RETIRED"
    again = await delete_ac("ff", "UC-701", "AC-05", CTX, reason=REASON, items_content=added["items_content"])
    assert again["code"] == "AC_RETIRED"


async def test_import_spec_reports_an_existing_uc_and_applies_only_when_asked():
    board = (await delete_ac("ff", "UC-701", "AC-05", CTX, reason=REASON, items_content=_board()))["items_content"]
    spec = {"user_stories": [{"us_id": "US-07", "name": "Pagos", "exclusions": ["Reembolsos"], "use_cases": [{
        "uc_id": "UC-701", "name": "Cobrar", "acceptance_criteria": [
            *TEXTS[:4], {"text": "El cobro duplicado se rechaza", "verification": "automated_test"}]}]}]}

    report = await import_spec("ff", spec, CTX, items_content=board)
    [warning] = [w for w in report["warnings"] if w["code"] == "uc_exists"]
    assert warning["applied"] is False and warning["differences"]["criteria_added"] == ["El cobro duplicado se rechaza"]
    assert report["created"]["ac"] == 0 and report["unchanged"] == {"uc": 1}
    uc_before = next(i for i in json.loads(board) if i["id"] == "uc701")
    uc_after = next(i for i in json.loads(report["items_content"]) if i["id"] == "uc701")
    assert uc_after == uc_before  # nombre, descripción y meta, tal cual
    unchanged = await get_uc("ff", "UC-701", CTX, items_content=report["items_content"])
    assert [a["id"] for a in unchanged["acceptance_criteria"]] == ["AC-01", "AC-02", "AC-03", "AC-04"]

    applied = await import_spec("ff", spec, CTX, items_content=board, on_existing_uc="apply")
    [warning] = [w for w in applied["warnings"] if w["code"] == "uc_exists"]
    assert warning["applied"] is True and applied["created"]["ac"] == 1
    detail = await get_uc("ff", "UC-701", CTX, items_content=applied["items_content"])
    ids = {a["id"]: a for a in detail["acceptance_criteria"]}
    assert list(ids) == ["AC-01", "AC-02", "AC-03", "AC-04", "AC-06"]  # AC-05 está retirado
    assert ids["AC-06"]["verification"] == "automated_test"
    assert "- AC-06: El cobro duplicado se rechaza" in detail["description_raw"]

    bad = await import_spec("ff", spec, CTX, items_content=board, on_existing_uc="overwrite")
    assert bad["code"] == "INVALID_OPTION"


# ── Native (Postgres) ───────────────────────────────────────────────


@pg
async def test_native_retiring_keeps_ids_receipts_and_never_reuses_the_id(monkeypatch, tmp_path):
    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria={"UC-01": TEXTS})
    try:
        await mark_ac(pid, "UC-01", "AC-04", True, ctx, evidence="pytest tests/test_x.py")
        out = await delete_ac(pid, "UC-01", "AC-03", ctx, reason=REASON, retired_by="no-cuenta")
        assert out["retired"]["retired_by"] == dev  # native: quién sale de la sesión
        detail = await get_uc(pid, "UC-01", ctx)
        assert [a["id"] for a in detail["acceptance_criteria"]] == ["AC-01", "AC-02", "AC-04", "AC-05"]
        assert detail["acceptance_criteria"][2]["done"] and detail["acceptance_criteria"][2]["evidence"]
        [retired] = detail["retired_criteria"]
        assert retired["id"] == "AC-03" and retired["reason"] == REASON and retired["retired_at"]
        assert retired["text"] == TEXTS[2]

        # El trigger de 0039 rechaza reutilizar el id, lo escriba quien lo escriba.
        async with pool.acquire() as conn:
            with pytest.raises(Exception, match="retirado"):
                await conn.execute(
                    "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text) "
                    "VALUES ('UC-01::AC-03', $1, 'UC-01', 'AC-03', 'a mano')", pid)
            audit = await conn.fetchval(
                "SELECT metadata FROM audit_log WHERE project_id = $1 AND operation = 'delete_acceptance_criterion'",
                pid)
        assert json.loads(audit)["retired"] is True

        assert (await add_ac(pid, "UC-01", "El cobro duplicado se rechaza", ctx))["ac_id"] == "AC-06"
        await delete_ac(pid, "UC-01", "AC-06", ctx, reason=REASON)
        assert (await add_ac(pid, "UC-01", "El cobro en otra moneda se convierte", ctx))["ac_id"] == "AC-07"
        assert (await mark_ac(pid, "UC-01", "AC-03", True, ctx))["code"] == "AC_RETIRED"
    finally:
        await _cleanup(pool, pid, dev)


@pg
async def test_native_totals_do_not_count_retired_and_the_migration_moves_nothing(monkeypatch, tmp_path):
    """AC-05: lo que cuentan las vistas y la tabla que leen el panel, el portal y la app."""
    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria={"UC-01": TEXTS})

    from server.tools.spec_driven import list_uc

    async def totals() -> tuple[int, int, int]:
        async with pool.acquire() as conn:
            raw = await conn.fetchval("SELECT count(*) FROM acceptance_criteria WHERE project_id = $1", pid)
            kpis = await conn.fetchval("SELECT ac_total FROM project_kpis WHERE project_id = $1", pid)
        listed = await list_uc(pid, ctx, us_id="US-01")
        return raw, int(kpis), sum(u["ac_total"] for u in listed)

    try:
        before = await totals()
        async with pool.acquire() as conn:
            await conn.execute((ROOT / "server/db/migrations/0039_acceptance_criteria_retired.sql").read_text())
        assert await totals() == before == (5, 5, 5)  # aplicar 0039 otra vez no mueve nada
        await delete_ac(pid, "UC-01", "AC-03", ctx, reason=REASON)
        assert await totals() == (4, 4, 4)  # el retirado no cuenta
    finally:
        await _cleanup(pool, pid, dev)


@pg
async def test_native_import_spec_leaves_an_existing_uc_until_asked(monkeypatch, tmp_path):
    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria={"UC-01": TEXTS[:2]})
    spec = {"user_stories": [{"us_id": "US-01", "name": "Pagos", "exclusions": ["Reembolsos"], "use_cases": [{
        "uc_id": "UC-01", "name": "Cobrar otra cosa", "acceptance_criteria": [TEXTS[1], TEXTS[0], TEXTS[2]]}]}]}
    try:
        report = await import_spec(pid, spec, ctx)
        [warning] = [w for w in report["warnings"] if w["code"] == "uc_exists"]
        assert warning["differences"]["name"]["to"] == "Cobrar otra cosa"
        async with pool.acquire() as conn:
            name = await conn.fetchval("SELECT name FROM use_cases WHERE project_id = $1 AND id = 'UC-01'", pid)
            count = await conn.fetchval("SELECT count(*) FROM acceptance_criteria WHERE project_id = $1", pid)
        assert "Cobrar otra cosa" not in name and count == 2

        applied = await import_spec(pid, spec, ctx, on_existing_uc="apply")
        assert applied["created"]["ac"] == 1 and applied["updated"]["uc"] == 1
        detail = await get_uc(pid, "UC-01", ctx)
        # Emparejados por texto: el orden de la spec no cambia los ids.
        assert [(a["id"], a["text"]) for a in detail["acceptance_criteria"]] == [
            ("AC-01", TEXTS[0]), ("AC-02", TEXTS[1]), ("AC-03", TEXTS[2])]
    finally:
        await _cleanup(pool, pid, dev)


@pg
async def test_native_ingest_from_freeform_keeps_the_retired_criteria(monkeypatch, tmp_path):
    """AC-06: una migración FreeForm → native lleva los retirados y su id sigue sin poder usarse."""
    from server.backends.freeform_backend import FreeformBackend
    from server.tools.migration import _read_source
    from server.tools.spec_driven import get_session_backend

    board = (await delete_ac("ff", "UC-701", "AC-03", CTX, reason=REASON, retired_by="Jesús",
                             items_content=_board()))["items_content"]
    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria={})
    try:
        src = FreeformBackend(items_content=board)
        try:
            source = await _read_source(src, ".")
        finally:
            await src.close()
        backend = await get_session_backend(ctx)
        try:
            result = await backend.ingest_atomic(pid, source, source_type="freeform")
        finally:
            await backend.close()
        assert result["migrated"]["ac"] == 4 and result["migrated"]["retired_ac"] == 1
        detail = await get_uc(pid, "UC-701", ctx)
        assert [r["id"] for r in detail["retired_criteria"]] == ["AC-03"]
        assert detail["retired_criteria"][0]["retired_by"] == "Jesús"
        async with pool.acquire() as conn:
            meta = await conn.fetchval("SELECT meta FROM use_cases WHERE project_id = $1 AND id = 'UC-701'", pid)
        assert "retired_criteria" not in json.loads(meta)
        assert (await add_ac(pid, "UC-701", "El cobro duplicado se rechaza", ctx))["ac_id"] == "AC-06"
    finally:
        await _cleanup(pool, pid, dev)
