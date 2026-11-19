"""UC-12603 (US-126) — un cambio que toca una UC cerrada se avisa.

- AC-01: el tablero guarda, para cada UC cerrada, los ficheros que cambió su PR (complete_uc(files)).
- AC-02: un cambio posterior en uno de esos ficheros, desde otra UC o sin UC, sale con la UC cerrada
  que toca (get_closed_uc_files; la puerta de desviación de UC-12602 lo muestra en su informe).
- AC-03: el aviso propone revisar los criterios de esa UC y la spec queda igual.
- AC-04: las UC cerradas antes de la medida, sin lista de ficheros, no avisan.
"""

from __future__ import annotations

import json

import pytest

from server.closed_files import (
    MAX_CLOSED_FILES,
    ClosedFilesError,
    ClosedUc,
    closed_uc_touches,
    merge_closed_files,
    normalize_closed_files,
)
from server.tools.drift import get_closed_uc_files
from server.tools.spec_driven import complete_uc, get_session_backend, get_uc
from tests.test_spec_gate_start_uc import CTX, US, _cleanup, _native_board, pg

UCS = [
    {"id": f"uc{n}", "name": f"UC-70{n}: Caso {n}", "description": "", "state": "in_progress", "labels": ["UC"],
     "parent_id": "us7", "meta": {"uc_id": f"UC-70{n}", "us_id": "US-07"}}
    for n in (1, 2, 3)
]
ACS = [{"id": f"ac{n}", "name": f"[AC-01] Lo del caso {n} queda registrado", "state": "done", "labels": ["AC"],
        "parent_id": f"uc{n}", "meta": {"ac_id": "AC-01"}} for n in (1, 2, 3)]


def _board(**overrides) -> str:
    items = json.loads(json.dumps([US, *UCS, *ACS]))
    for item in items:
        item.update(overrides.get(item["id"], {}))
    return json.dumps(items)


# ── El módulo puro ──────────────────────────────────────────────────


def test_the_list_of_a_close_is_relative_without_repeats_and_has_a_cap():
    assert normalize_closed_files(["./server/a.py", "server\\a.py", " docs/b.md ", ""]) == ["server/a.py", "docs/b.md"]
    assert normalize_closed_files(None) == []
    for bad in (["../x.py"], ["/abs.py"], "server/a.py", ["a" * 301]):
        with pytest.raises(ClosedFilesError):
            normalize_closed_files(bad)
    assert merge_closed_files(["a.py", "b.py"], ["b.py", "c.py"]) == (["a.py", "b.py", "c.py"], False)
    full = [f"f{i}.py" for i in range(MAX_CLOSED_FILES)]
    kept, truncated = merge_closed_files(full, ["nuevo.py"])
    assert truncated and len(kept) == MAX_CLOSED_FILES and kept[-1] == "nuevo.py" and "f0.py" not in kept


def test_touches_name_the_closed_uc_its_files_and_a_proposal_and_skip_the_branch_and_old_ucs():
    closed = [
        ClosedUc("UC-701", "US-07", "Cobrar", ["server/a.py", "server/b.py"], "2026-11-19T00:00:00Z"),
        ClosedUc("UC-702", "US-07", "Devolver", ["server/b.py"]),
        ClosedUc("UC-703", "US-07", "Anterior a la medida", None),
    ]
    out = closed_uc_touches(closed, ["server/b.py", "./server/a.py", "otra/c.py"], exclude=["uc-702"])
    assert [t["uc_id"] for t in out["touches"]] == ["UC-701"]  # UC-702 es la de la rama
    first = out["touches"][0]
    assert first["files"] == ["server/b.py", "server/a.py"] and first["closed_at"] == "2026-11-19T00:00:00Z"
    assert "revisa si sus criterios siguen valiendo" in first["proposal"] and "lo decide una persona" in first["proposal"]
    assert out["by_path"] == {"server/b.py": ["UC-701"], "server/a.py": ["UC-701"]}
    assert out["closed_without_files"] == 1 and "1 UC cerradas" in out["notice"]  # AC-04: no avisa
    assert "6.46.0" not in out["notice"]  # se pudo cerrar hoy sin lista
    assert closed_uc_touches(closed, ["server/b.py"], exclude="UC-702")["touches_total"] == 1  # texto, no lista


def test_in_multirepo_only_closed_ucs_of_the_same_repo_count_and_the_most_shared_come_first():
    closed = [
        ClosedUc("UC-1", "US-1", "Del engine", ["CLAUDE.md", "package.json"], "2026-11-01",
                 by_repo={"EmbedBuild/specbox-engine": ["CLAUDE.md", "package.json"]}),
        ClosedUc("UC-2", "US-1", "Del panel", ["CLAUDE.md"], "2026-11-02", by_repo={"EmbedBuild/specbox_cloud": ["CLAUDE.md"]}),
        ClosedUc("UC-3", "US-1", "Sin repo, satélite cloud", ["package.json", "CLAUDE.md"], "2026-11-03", satellite="cloud"),
        ClosedUc("UC-4", "US-1", "Sin nada", ["CLAUDE.md"], "2026-11-04"),
    ]
    out = closed_uc_touches(closed, ["CLAUDE.md", "package.json"], repo="EmbedBuild/specbox_cloud", satellite="cloud")
    # Ni UC-1 (otro repositorio); primero la que más ficheros comparte y, a igualdad, la más reciente.
    assert [t["uc_id"] for t in out["touches"]] == ["UC-3", "UC-4", "UC-2"]
    capped = closed_uc_touches(closed, ["CLAUDE.md"], limit=2)
    assert len(capped["touches"]) == 2 and capped["touches_total"] == 4


# ── FreeForm (AC-01 a AC-04) ────────────────────────────────────────


async def test_freeform_keeps_the_files_of_the_close_and_reports_a_later_change():
    closed = await complete_uc("ff", "UC-701", CTX, items_content=_board(), files=["server/cobros.py", "doc/x.md"])
    assert closed["closed_files"] == 2, closed
    board = closed["items_content"]
    uc = next(i for i in json.loads(board) if i["id"] == "uc1")
    assert uc["state"] == "done" and uc["meta"]["closed_files"] == ["server/cobros.py", "doc/x.md"]
    detail = await get_uc("ff", "UC-701", CTX, items_content=board)
    assert detail["closed_files"] == ["server/cobros.py", "doc/x.md"]

    # Otra UC (UC-702) toca un fichero de la cerrada: sale con la propuesta, y el tablero no cambia.
    out = await get_closed_uc_files("ff", ["server/cobros.py", "server/nuevo.py"], CTX,
                                    exclude_uc_ids=["UC-702"], items_content=board)
    assert out["supported"] is True and [t["uc_id"] for t in out["touches"]] == ["UC-701"]
    assert out["touches"][0]["files"] == ["server/cobros.py"] and "UC-701" in out["touches"][0]["proposal"]
    assert "items_content" not in out  # solo lee: no devuelve un tablero cambiado
    again = await get_uc("ff", "UC-701", CTX, items_content=board)
    assert again["acceptance_criteria"] == detail["acceptance_criteria"] and again["status"] == "done"

    # Sin UC (ninguna excluida) también sale; la propia UC de la rama, no.
    assert [t["uc_id"] for t in (await get_closed_uc_files("ff", ["doc/x.md"], CTX, items_content=board))["touches"]] == ["UC-701"]
    own = await get_closed_uc_files("ff", ["doc/x.md"], CTX, exclude_uc_ids=["UC-701"], items_content=board)
    assert own["touches"] == []


async def test_a_reclosed_uc_adds_its_new_files_and_an_old_close_does_not_warn():
    first = await complete_uc("ff", "UC-701", CTX, items_content=_board(), files=["a.py"])
    reopened = json.loads(first["items_content"])
    for item in reopened:
        if item["id"] == "uc1":
            item["state"] = "in_progress"
    second = await complete_uc("ff", "UC-701", CTX, items_content=json.dumps(reopened), files=["b.py", "a.py"])
    assert second["closed_files"] == 2
    # UC-702 cerrada antes de la medida: hecha, sin lista. No avisa y se cuenta.
    board = json.loads(second["items_content"])
    for item in board:
        if item["id"] == "uc2":
            item["state"] = "done"
    out = await get_closed_uc_files("ff", ["a.py", "b.py"], CTX, items_content=json.dumps(board))
    assert [t["uc_id"] for t in out["touches"]] == ["UC-701"] and out["touches"][0]["files"] == ["a.py", "b.py"]
    assert out["closed_without_files"] == 1 and out["notice"]


async def test_an_invalid_list_closes_nothing_and_no_list_closes_with_a_warning():
    bad = await complete_uc("ff", "UC-701", CTX, items_content=_board(), files=["../fuera.py"])
    assert bad["code"] == "INVALID_FILES" and "items_content" not in bad
    assert (await complete_uc("ff", "UC-701", CTX, items_content=_board(), files=["a.py"], repo="no es repo"))["code"] == "INVALID_FILES"
    plain = await complete_uc("ff", "UC-701", CTX, items_content=_board())
    uc = next(i for i in json.loads(plain["items_content"]) if i["id"] == "uc1")
    assert uc["state"] == "done" and "closed_files" not in uc["meta"] and "closed_files" not in plain
    assert "no avisará" in plain["closed_files_missing"]  # cerrar sin lista lo dice
    # La lista se puede añadir después a la UC ya cerrada, con su repositorio.
    later = await complete_uc("ff", "UC-701", CTX, items_content=plain["items_content"], files=["a.py"],
                              repo="EmbedBuild/specbox-engine")
    uc = next(i for i in json.loads(later["items_content"]) if i["id"] == "uc1")
    assert uc["meta"]["closed_files"] == ["a.py"] and uc["meta"]["closed_files_by_repo"] == {"EmbedBuild/specbox-engine": ["a.py"]}
    out = await get_closed_uc_files("ff", "server/a.py", CTX, items_content=_board())  # type: ignore[arg-type]
    assert out["code"] == "INVALID_PATHS"


async def test_move_uc_to_done_says_the_list_is_missing():
    from server.tools.spec_driven import move_uc

    out = await move_uc("ff", "UC-701", "done", CTX, items_content=_board())
    assert "no avisará" in out["closed_files_missing"]


async def test_a_board_without_meta_says_it_does_not_keep_the_list(monkeypatch):
    class _NoMeta:
        STORES_SPEC_META = False

        async def close(self):
            return None

    async def _backend(ctx, items_content=None):
        return _NoMeta()

    monkeypatch.setattr("server.tools.drift.get_session_backend", _backend)
    out = await get_closed_uc_files("trello-board", ["a.py"], CTX)
    assert out["supported"] is False and out["touches"] == [] and "Trello y Plane" in out["notice"]


# ── Native ──────────────────────────────────────────────────────────


@pg
async def test_native_keeps_the_files_and_reports_them(monkeypatch, tmp_path):
    pool, pid, dev, token, ctx = await _native_board(
        monkeypatch, tmp_path, criteria={"UC-01": ["El cobro queda registrado"], "UC-02": ["La devolución queda registrada"]},
    )
    try:
        out = await complete_uc(pid, "UC-01", ctx, files=["server/cobros.py", "server/recibos.py"])
        assert out.get("closed_files") == 2, out
        assert (await get_uc(pid, "UC-01", ctx))["closed_files"] == ["server/cobros.py", "server/recibos.py"]
        report = await get_closed_uc_files(pid, ["server/recibos.py"], ctx, exclude_uc_ids=["UC-02"])
        assert [t["uc_id"] for t in report["touches"]] == ["UC-01"] and report["closed_without_files"] == 0
        await complete_uc(pid, "UC-02", ctx)  # cerrada sin lista: no avisa
        later = await get_closed_uc_files(pid, ["server/recibos.py"], ctx)
        assert [t["uc_id"] for t in later["touches"]] == ["UC-01"] and later["closed_without_files"] == 1
        # Las lecturas de tablero entero no cargan la lista; list_done_ucs sí.
        backend = await get_session_backend(ctx)
        try:
            summary = {i.name: i.meta for i in await backend.list_board_summary(pid)}
            assert all("closed_files" not in m for m in summary.values())
            done = [i for i in await backend.list_done_ucs(pid) if i.meta.get("closed_files")]
            assert [i.meta["closed_files"] for i in done] == [["server/cobros.py", "server/recibos.py"]]
        finally:
            await backend.close()
    finally:
        await _cleanup(pool, pid, dev)


async def test_a_uc_with_prs_in_two_repos_keeps_one_list_per_repo():
    from server.tools.drift import closed_ucs_of
    from server.backends.freeform_backend import FreeformBackend

    first = await complete_uc("ff", "UC-701", CTX, items_content=_board(), files=["server/solo_engine.py"],
                              repo="EmbedBuild/specbox-engine")
    second = await complete_uc("ff", "UC-701", CTX, items_content=first["items_content"], files=["apps/web/x.tsx"],
                               repo="EmbedBuild/specbox_cloud")
    uc = next(i for i in json.loads(second["items_content"]) if i["id"] == "uc1")
    assert uc["meta"]["closed_files_by_repo"] == {"EmbedBuild/specbox-engine": ["server/solo_engine.py"],
                                                  "EmbedBuild/specbox_cloud": ["apps/web/x.tsx"]}
    closed = closed_ucs_of(await FreeformBackend(items_content=second["items_content"]).list_done_ucs("ff"))
    engine = closed_uc_touches(closed, ["server/solo_engine.py"], repo="EmbedBuild/specbox-engine")
    cloud = closed_uc_touches(closed, ["server/solo_engine.py"], repo="EmbedBuild/specbox_cloud")
    assert [t["uc_id"] for t in engine["touches"]] == ["UC-701"] and cloud["touches"] == []


async def test_a_pr_over_the_cap_still_closes_and_keeps_the_most_recent():
    big = [f"f{i}.py" for i in range(MAX_CLOSED_FILES + 5)]
    out = await complete_uc("ff", "UC-701", CTX, items_content=_board(), files=big)
    uc = next(i for i in json.loads(out["items_content"]) if i["id"] == "uc1")
    assert uc["state"] == "done" and out["closed_files_truncated"] is True
    assert len(uc["meta"]["closed_files"]) == MAX_CLOSED_FILES and uc["meta"]["closed_files"][-1] == big[-1]
