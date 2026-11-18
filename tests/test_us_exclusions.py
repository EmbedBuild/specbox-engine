"""US-123 / UC-12306 — exclusiones y casos límite en la spec y en el tablero.

- **AC-01**: las plantillas de PRD incluyen la sección «Casos límite», con cada caso y el
  comportamiento esperado.
- **AC-02**: ``import_spec`` acepta exclusiones por historia, las guarda en el tablero y ``get_us``
  las devuelve.
- **AC-03**: una historia importada sin exclusiones aparece en la respuesta de ``import_spec`` con el
  aviso ``no_exclusions``.
- **AC-04**: una llamada a ``import_spec`` sin exclusiones, como las de versiones anteriores, deja la
  historia creada igual que antes y la respuesta muestra solo el aviso.
- **AC-05**: en FreeForm las exclusiones quedan en los ficheros del tablero y ``get_us`` las devuelve
  igual que en native.

FreeForm por contenido (el MCP remoto) aquí; native contra Postgres al final (SKIP sin base).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.backends.freeform_backend import FreeformBackend
from server.tools import _mutation_helpers as mh
from server.tools.spec_driven import get_us, import_spec
from server.tools.spec_mutations import update_us
from tests.test_spec_gate_start_uc import CTX, _cleanup, _native_board, pg

ROOT = Path(__file__).resolve().parent.parent

EXCLUSIONS = ["Pagos con criptomoneda", "Devoluciones parciales"]


def _spec(exclusions: list[str] | None = None, us_id: str = "US-09") -> dict:
    story: dict = {"us_id": us_id, "name": "Cobros", "use_cases": [
        {"uc_id": f"UC-{us_id[3:]}01", "name": "Cobrar", "acceptance_criteria": [
            {"text": "El cobro queda registrado con su recibo", "verification": "automated_test"}]}]}
    if exclusions is not None:
        story["exclusions"] = exclusions
    return {"user_stories": [story]}


def _us_meta(items_content: str, us_id: str = "US-09") -> dict:
    return next(i["meta"] for i in json.loads(items_content) if i.get("meta", {}).get("us_id") == us_id
                and "US" in i.get("labels", []))


# ── La parte pura ───────────────────────────────────────────────────


def test_exclusions_are_a_list_of_texts():
    assert mh.normalize_exclusions(None) is None
    assert mh.normalize_exclusions([" Pagos con criptomoneda ", "", "  "]) == ["Pagos con criptomoneda"]
    assert mh.normalize_exclusions("Devoluciones") == ["Devoluciones"]
    assert mh.normalize_exclusions([]) == []
    for bad in ({"a": 1}, [1, 2], 3):
        with pytest.raises(ValueError):
            mh.normalize_exclusions(bad)
    assert mh.exclusions_of({"exclusions": ["a", 2]}) == ["a"]
    assert mh.exclusions_of({}) == [] and mh.exclusions_of(None) == []


def test_the_prd_templates_have_edge_cases():
    """AC-01: las tres plantillas, con cada caso y su comportamiento esperado."""
    skill = (ROOT / ".claude/skills/prd/SKILL.md").read_text(encoding="utf-8")
    assert skill.count("### Casos límite") == 3
    assert skill.count("| Caso | Comportamiento esperado |") == 3
    assert '"exclusions": [' in skill and "update_us(exclusions=[...])" in skill


# ── FreeForm por contenido ──────────────────────────────────────────


async def test_import_spec_keeps_the_exclusions_and_get_us_returns_them():
    """AC-02 y AC-05: quedan en el fichero del tablero."""
    out = await import_spec("ff", _spec(EXCLUSIONS), CTX, items_content="[]")
    assert out["errors"] == [] and "warnings" not in out
    assert _us_meta(out["items_content"])["exclusions"] == EXCLUSIONS
    detail = await get_us("ff", "US-09", CTX, items_content=out["items_content"])
    assert detail["exclusions"] == EXCLUSIONS


async def test_a_story_without_exclusions_is_created_as_before_with_only_the_warning():
    """AC-03 y AC-04: misma historia, mismos recuentos; la respuesta solo añade el aviso."""
    old_style = await import_spec("ff", _spec(), CTX, items_content="[]")
    with_them = await import_spec("ff", _spec(EXCLUSIONS), CTX, items_content="[]")
    assert old_style["warnings"] == [
        {"us_id": "US-09", "code": "no_exclusions", "message": mh.NO_EXCLUSIONS_MESSAGE}
    ]
    assert set(old_style) - set(with_them) == {"warnings"}
    for key in ("created", "updated", "errors"):
        assert old_style[key] == with_them[key]
    old_meta, new_meta = _us_meta(old_style["items_content"]), _us_meta(with_them["items_content"])
    assert {k: v for k, v in new_meta.items() if k != "exclusions"} == old_meta
    detail = await get_us("ff", "US-09", CTX, items_content=old_style["items_content"])
    assert detail["exclusions"] == [] and detail["status"] == "user_stories"


async def test_reimporting_without_exclusions_keeps_the_stored_ones():
    first = await import_spec("ff", _spec(EXCLUSIONS), CTX, items_content="[]")
    again = await import_spec("ff", _spec(), CTX, items_content=first["items_content"])
    assert not [w for w in again.get("warnings", []) if w["code"] == "no_exclusions"]
    assert _us_meta(again["items_content"])["exclusions"] == EXCLUSIONS


async def test_update_us_sets_and_clears_the_exclusions():
    """La forma de corregir el aviso sin reimportar."""
    board = (await import_spec("ff", _spec(), CTX, items_content="[]"))["items_content"]
    out = await update_us("ff", "US-09", CTX, exclusions=EXCLUSIONS, items_content=board)
    assert out["updated_fields"] == ["exclusions"]
    assert (await get_us("ff", "US-09", CTX, items_content=out["items_content"]))["exclusions"] == EXCLUSIONS
    again = await import_spec("ff", _spec(), CTX, items_content=out["items_content"])
    assert not [w for w in again.get("warnings", []) if w["code"] == "no_exclusions"]
    same = await update_us("ff", "US-09", CTX, exclusions=EXCLUSIONS, items_content=out["items_content"])
    assert same["reason"] == "no_change"
    cleared = await update_us("ff", "US-09", CTX, exclusions=[], items_content=out["items_content"])
    assert (await get_us("ff", "US-09", CTX, items_content=cleared["items_content"]))["exclusions"] == []
    bad = await update_us("ff", "US-09", CTX, exclusions=[1], items_content=board)
    assert bad["code"] == "INVALID_EXCLUSIONS"


async def test_a_backend_without_spec_metadata_says_it_did_not_store_them(monkeypatch):
    """Trello y Plane no tienen dónde guardarlas: la respuesta lo dice."""
    monkeypatch.setattr(FreeformBackend, "STORES_SPEC_META", False)
    out = await import_spec("ff", _spec(EXCLUSIONS), CTX, items_content="[]")
    assert out["exclusions_not_stored"] is True and "warnings" not in out
    assert "exclusions" not in _us_meta(out["items_content"])
    updated = await update_us("ff", "US-09", CTX, exclusions=EXCLUSIONS, items_content=out["items_content"])
    assert updated["reason"] == "no_change" and updated["exclusions_not_stored"] is True


# ── Native ──────────────────────────────────────────────────────────


@pg
async def test_native_keeps_the_exclusions_like_freeform(monkeypatch, tmp_path):
    """AC-02 a AC-05 en native: guardar, devolver, avisar y corregir."""
    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria={})
    try:
        out = await import_spec(pid, _spec(EXCLUSIONS, us_id="US-09"), ctx)
        assert out["errors"] == [] and "warnings" not in out
        assert (await get_us(pid, "US-09", ctx))["exclusions"] == EXCLUSIONS
        bare = await import_spec(pid, _spec(us_id="US-08"), ctx)
        assert [(w["us_id"], w["code"]) for w in bare["warnings"]] == [("US-08", "no_exclusions")]
        assert bare["created"]["us"] == 1 and (await get_us(pid, "US-08", ctx))["exclusions"] == []
        await update_us(pid, "US-08", ctx, exclusions=["Exportar a PDF"])
        assert (await get_us(pid, "US-08", ctx))["exclusions"] == ["Exportar a PDF"]
        async with pool.acquire() as conn:
            stored = await conn.fetchval(
                "SELECT meta->'exclusions' FROM user_stories WHERE project_id = $1 AND id = 'US-09'", pid
            )
        assert json.loads(stored) == EXCLUSIONS
    finally:
        await _cleanup(pool, pid, dev)
