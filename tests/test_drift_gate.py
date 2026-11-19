"""UC-12602 (US-126) — el CI local falla si el código se aparta de la spec.

La parte del servidor: `server/drift.py` (puro) y la tool `get_drift_report`. La orden
`specbox drift` tiene sus pruebas en packages/specbox-cli/test/drift.test.mjs.

- AC-01/AC-02: cada fichero con la UC que lo reclama (por el plan o por los recibos) o «sin UC».
- AC-03: una dependencia nueva que el plan no declara sale con su nombre.
- AC-04: solo las exclusiones del proyecto dejan un fichero fuera, y el informe las muestra.
- AC-08: el modo de la medida drift_gate viene del tablero.
- UC-12603 AC-02/AC-03: un cambio en un fichero de una UC cerrada sale con esa UC y la propuesta.
"""

from __future__ import annotations

import json

import pytest

from server.closed_files import ClosedUc
from server.coordination.enforcement import MEASURES
from server.drift import (
    MAX_DRIFT_PATH,
    ExcludeTooCostly,
    GlobBudget,
    build_drift_report,
    dependency_key,
    glob_matcher,
    plan_owner,
)
from server.plan_contract import parse_plan_contract
from server.tools.drift import get_drift_report
from server.tools.spec_driven import complete_uc, mark_ac
from tests.test_spec_gate_start_uc import CTX, US, _cleanup, _native_board, pg

PLAN = """# Plan
### Fase 1: Base
**Criterios:** UC-701 AC-01
**Ficheros:** server/a.py, server/vistas/
### Fase 2: Otra UC
**Criterios:** UC-702 AC-01
**Ficheros:** server/b.py
## Dependencias nuevas
- pypi: rapidfuzz
- npm: `@scope/kit`
"""
CONTRACTS = [("doc/plans/US-07_plan.md", parse_plan_contract(PLAN))]


def test_each_file_has_its_uc_or_sin_uc():
    out = build_drift_report(
        files=["server/a.py", "server/vistas/lista.py", "server/b.py", "server/c.py", "./server/d.py"],
        uc_ids=["uc-701"], contracts=CONTRACTS, receipts={"UC-701": {"server/d.py"}},
    )
    by = {f["path"]: f for f in out["files"]}
    assert by["server/a.py"]["claimed_by"] == ["UC-701"] and by["server/a.py"]["source"] == "plan"
    assert by["server/vistas/lista.py"]["claimed_by"] == ["UC-701"]  # la carpeta del plan la cubre
    assert by["server/d.py"]["source"] == "receipt"  # reclamado por el recibo de un criterio
    assert by["server/b.py"]["claimed_by"] == [] and by["server/b.py"]["planned_for"] == ["UC-702"]
    assert out["unclaimed"] == ["server/b.py", "server/c.py"] and out["ok"] is False


def test_an_undeclared_dependency_is_named_and_aliases_and_versions_do_not_count():
    out = build_drift_report(files=["pyproject.toml"], uc_ids=["UC-701"], contracts=CONTRACTS, exclude=["pyproject.toml"],
                             dependencies_added=[
                                 {"ecosystem": "pypi", "name": "RapidFuzz>=3", "manifest": "pyproject.toml"},
                                 {"ecosystem": "npm", "name": "@scope/kit", "manifest": "package.json"},
                                 {"ecosystem": "pypi", "name": "httpx", "manifest": "pyproject.toml"},
                             ])
    assert [d["name"] for d in out["dependencies"]["undeclared"]] == ["httpx"] and out["ok"] is False
    assert dependency_key("pip", "Rapid_Fuzz[speedup]==1") == "rapid-fuzz"
    no_section = build_drift_report(files=[], uc_ids=["UC-701"], contracts=[("p.md", parse_plan_contract(PLAN.split("## Dep")[0]))],
                                    dependencies_added=[{"ecosystem": "npm", "name": "zod", "manifest": "package.json"}])
    assert no_section["dependencies"]["plans_without_section"] == ["p.md"] and no_section["dependencies"]["undeclared"]


def test_only_the_project_exclusions_leave_a_file_out_and_the_report_lists_them():
    assert glob_matcher("docs/**")("docs/a/b.md") and glob_matcher("*.lock")("sub/uv.lock")
    assert not glob_matcher("docs/*.md")("docs/a/b.md")
    assert glob_matcher("docs")("docs/a/b.md") and glob_matcher("/CHANGELOG.md")("CHANGELOG.md")
    assert not glob_matcher("/CHANGELOG.md")("a/CHANGELOG.md")
    out = build_drift_report(files=["CHANGELOG.md", "docs/x.md", "server/c.py"], uc_ids=["UC-701"], contracts=CONTRACTS,
                             exclude=["CHANGELOG.md", "docs/**"])
    assert out["exclude"] == ["CHANGELOG.md", "docs/**"] and out["excluded"] == ["CHANGELOG.md", "docs/x.md"]
    assert out["unclaimed"] == ["server/c.py"]


def test_a_change_in_a_closed_uc_file_comes_with_that_uc_and_the_proposal():
    closed = [ClosedUc("UC-650", "US-06", "Cobrar", ["server/c.py"], "2026-11-01",
                       by_repo={"EmbedBuild/specbox-engine": ["server/c.py"]})]
    out = build_drift_report(files=["server/c.py", "docs/x.md"], uc_ids=["UC-701"], contracts=CONTRACTS, closed=closed,
                             exclude=["docs/**"], repo="EmbedBuild/specbox-engine")
    [touch] = out["closed_touches"]
    assert touch["uc_id"] == "UC-650" and "revisa si sus criterios siguen valiendo" in touch["proposal"]
    other_repo = build_drift_report(files=["server/c.py"], uc_ids=[], contracts=[], closed=closed, repo="EmbedBuild/specbox_cloud")
    assert other_repo["closed_touches"] == [] and other_repo["notes"]  # sin UC ni plan: lo dice


def test_drift_gate_is_active_since_6_46():
    assert MEASURES["drift_gate"].since == "6.46.0"


# ── La tool ─────────────────────────────────────────────────────────

UC = {"id": "uc701", "name": "UC-701: Cobrar", "description": "", "state": "in_progress", "labels": ["UC"],
      "parent_id": "us7", "meta": {"uc_id": "UC-701", "us_id": "US-07"}}
UC_CLOSED = {"id": "uc650", "name": "UC-650: Devolver", "description": "", "state": "review", "labels": ["UC"],
             "parent_id": "us7", "meta": {"uc_id": "UC-650", "us_id": "US-07"}}
ACS = [{"id": "ac1", "name": "[AC-01] El cobro queda registrado", "state": "backlog", "labels": ["AC"],
        "parent_id": "uc701", "meta": {"ac_id": "AC-01"}}]


async def test_the_tool_reads_receipts_closed_ucs_and_the_mode_from_a_freeform_board():
    board = json.dumps([US, UC, UC_CLOSED, *ACS])
    board = (await mark_ac("ff", "UC-701", "AC-01", True, CTX, items_content=board, evidence={
        "type": "test", "label": "t.py::x", "files": ["server/recibo.py"], "test": "t.py::x"}))["items_content"]
    board = (await complete_uc("ff", "UC-650", CTX, items_content=board, files=["server/cerrado.py"]))["items_content"]
    before = board
    policy = json.dumps({"measures": {"drift_gate": {"mode": "block"}}})
    out = await get_drift_report("ff", ["server/recibo.py", "server/cerrado.py", "server/a.py"], CTX, uc_ids=["UC-701"],
                                 plan_contents={"doc/plans/p.md": PLAN}, items_content=board, policy_content=policy,
                                 backend_type="freeform")
    assert out["success"] and out["board"] == "leído" and out["mode"] == "block"
    by = {f["path"]: f for f in out["files"]}
    assert by["server/recibo.py"]["source"] == "receipt" and by["server/a.py"]["source"] == "plan"
    assert out["unclaimed"] == ["server/cerrado.py"]
    assert [t["uc_id"] for t in out["closed_touches"]] == ["UC-650"]
    assert "items_content" not in out and board == before  # solo lee


async def test_without_a_readable_board_the_report_uses_the_plan_and_says_why():
    out = await get_drift_report("tablero-trello", ["server/a.py"], CTX, uc_ids=["UC-701"],
                                 plan_contents={"doc/plans/p.md": PLAN}, backend_type="trello")
    assert out["success"] and "trello" in out["board"] and out["unclaimed"] == [] and out["mode"] == "warn"
    bad = await get_drift_report("x", "server/a.py", CTX)  # type: ignore[arg-type]
    assert bad["code"] == "INVALID_FILES"


@pg
async def test_native_reads_the_board_with_the_session(monkeypatch, tmp_path):
    pool, pid, dev, _token, ctx = await _native_board(monkeypatch, tmp_path, criteria={"UC-01": ["El cobro queda registrado"]})
    try:
        await mark_ac(pid, "UC-01", "AC-01", True, ctx, evidence={
            "type": "test", "label": "t.py::x", "files": ["server/cobros.py"], "test": "t.py::x"})
        out = await get_drift_report(pid, ["server/cobros.py", "server/otro.py"], ctx, uc_ids=["UC-01", "UC-99"])
        assert out["board"] == "leído" and out["mode"] == "warn"
        assert out["unclaimed"] == ["server/otro.py"] and out["unknown_ucs"] == ["UC-99"]
    finally:
        await _cleanup(pool, pid, dev)


@pytest.mark.parametrize("exclude", [None, []])
def test_no_exclusions_means_nothing_is_left_out(exclude):
    out = build_drift_report(files=["a.md"], uc_ids=[], contracts=[], exclude=exclude)
    assert out["excluded"] == [] and out["exclude"] == [] and out["unclaimed"] == ["a.md"]


# ── Revisión de la PR #401 ───────────────────────────────────────────


def test_a_pathological_exclusion_does_not_hang_the_server():
    import time

    start = time.perf_counter()
    assert not glob_matcher("*" * 40 + "z")("a" * 300)
    assert not glob_matcher("**/" * 20 + "x")("a/" * 100 + "y")
    assert time.perf_counter() - start < 0.5


async def test_the_tool_caps_the_exclusions_and_only_opens_native_when_declared():
    too_many = await get_drift_report("x", ["a.py"], CTX, exclude=["*.md"] * 201)
    assert too_many["code"] == "INVALID_EXCLUDE"
    too_long = await get_drift_report("x", ["a.py"], CTX, exclude=["a" * 201])
    assert too_long["code"] == "INVALID_EXCLUDE"
    undeclared = await get_drift_report("tablero", ["a.py"], CTX, uc_ids=["UC-1"])  # sin backend_type
    assert "sin tipo declarado" in undeclared["board"]


OLD_PLAN = "# Plan de la US-126\n### Fase 1: Todo (UC-12602)\n- [ ] hacer\n"


def test_an_existing_uc_with_an_old_plan_and_no_receipt_files_is_not_judged():
    old = [("doc/plans/US-126_plan.md", parse_plan_contract(OLD_PLAN), OLD_PLAN)]
    out = build_drift_report(files=["server/a.py", "CLAUDE.md"], uc_ids=["UC-12602"], contracts=old,
                             known_ucs={"UC-12602"})
    assert out["ok"] is True and out["unclaimed"] == [] and out["not_judged"] == ["server/a.py", "CLAUDE.md"]
    assert out["judgeable"] is False and out["old_plan_ucs"] == ["UC-12602"]
    assert "no juzga 2 fichero(s)" in " ".join(out["notes"])
    # Sin ninguna UC sí cuenta todo como «sin UC».
    assert build_drift_report(files=["a.py"], uc_ids=[], contracts=old)["unclaimed"] == ["a.py"]


def test_a_made_up_uc_or_one_without_a_plan_does_not_switch_the_gate_off():
    old = [("doc/plans/US-126_plan.md", parse_plan_contract(OLD_PLAN), OLD_PLAN)]
    made_up = build_drift_report(files=["server/a.py"], uc_ids=["UC-99999"], contracts=old, known_ucs={"UC-12602"})
    assert made_up["unknown_ucs"] == ["UC-99999"] and made_up["unclaimed"] == ["server/a.py"] and made_up["ok"] is False
    no_plan = build_drift_report(files=["server/a.py"], uc_ids=["UC-7"], contracts=[], known_ucs={"UC-7"})
    assert no_plan["unclaimed"] == ["server/a.py"] and no_plan["judgeable"] is True
    # Con el tablero sin leer no se sabe si la UC existe: se juzga, y lo dice.
    blind = build_drift_report(files=["server/a.py"], uc_ids=["UC-12602"], contracts=old)
    assert blind["unclaimed"] == ["server/a.py"] and "No se pudo leer el tablero" in " ".join(blind["notes"])


def test_a_single_uc_plan_whose_criteria_do_not_say_their_uc_claims_for_that_uc():
    single = (
        "# Plan\n| UC | Qué |\n|---|---|\n| UC-701 | Cobrar |\n"
        "### Fase 1: Base\n**Criterios:**\n- AC-01\n- AC-02\n**Ficheros:** server/cobros.py\n"
    )
    out = build_drift_report(files=["server/cobros.py"], uc_ids=["UC-701"],
                             contracts=[("doc/plans/cobros.md", parse_plan_contract(single), single)])
    assert out["unclaimed"] == [] and out["files"][0]["claimed_by"] == ["UC-701"]
    assert out["plans"][0]["owner"] == "UC-701"


def test_a_plan_of_another_uc_that_mentions_the_branch_uc_in_a_heading_claims_nothing_for_it():
    foreign = (
        "# Plan UC-998: Avisos\n## Relación con UC-701\nUsa lo de UC-701.\n"
        "### Fase 1: Avisos\n**Criterios:** AC-01\n**Ficheros:** server/avisos.py\n"
    )
    out = build_drift_report(files=["server/avisos.py"], uc_ids=["UC-701"],
                             contracts=[("doc/plans/avisos.md", parse_plan_contract(foreign), foreign)])
    assert out["unclaimed"] == ["server/avisos.py"] and out["files"][0]["planned_for"] == ["UC-998"]
    assert plan_owner("doc/plans/x.md", "# Plan\nUC-1 y UC-2") is None


def test_costly_exclusions_stop_within_budget():
    import time

    start = time.perf_counter()
    with pytest.raises(ExcludeTooCostly):
        build_drift_report(files=["a" * 1019 + f"{i:05d}" for i in range(19_999)], uc_ids=[], contracts=[],
                           exclude=["a*" * 19 + "x*"] * 200)
    assert time.perf_counter() - start < 3
    # El caso normal no gasta casi nada: los trozos literales descartan antes.
    budget = GlobBudget()
    matcher = glob_matcher("docs/**")
    assert not any(matcher(f"server/m{i}.py", budget) for i in range(20_000)) and budget.spent < 2_000_000


async def test_the_tool_rejects_long_paths_and_costly_exclusions():
    long_path = await get_drift_report("x", ["a" * (MAX_DRIFT_PATH + 1)], CTX)
    assert long_path["code"] == "INVALID_FILES"
    wild = await get_drift_report("x", ["a.py"], CTX, exclude=["*" * 21])
    assert wild["code"] == "INVALID_EXCLUDE"
    costly = await get_drift_report("x", ["a" * 1019 + f"{i:05d}" for i in range(19_999)], CTX,
                                    exclude=["a*" * 19 + "x*"] * 200)
    assert costly["code"] == "EXCLUDE_TOO_COSTLY" and costly["mode"] == "warn"


def test_a_closed_uc_with_an_old_plan_does_not_switch_the_gate_off():
    old = [("doc/plans/US-126_plan.md", parse_plan_contract(OLD_PLAN), OLD_PLAN)]
    out = build_drift_report(files=["server/a.py"], uc_ids=["UC-12602"], contracts=old, known_ucs={"UC-12602"},
                             done_ucs={"UC-12602"})
    assert out["unclaimed"] == ["server/a.py"] and out["not_judged"] == [] and out["ok"] is False


def test_an_open_old_plan_uc_named_in_a_commit_does_not_hide_the_other_ucs_drift():
    old = [("doc/plans/US-126_plan.md", parse_plan_contract(OLD_PLAN), OLD_PLAN), *CONTRACTS]
    out = build_drift_report(files=["server/a.py", "server/b.py"], uc_ids=["UC-701", "UC-12602"], contracts=old,
                             known_ucs={"UC-701", "UC-12602"})
    by = {f["path"]: f for f in out["files"]}
    assert by["server/a.py"]["claimed_by"] == ["UC-701"]
    assert out["unclaimed"] == ["server/b.py"] and out["not_judged"] == [] and out["ok"] is False


def test_the_plan_of_another_uc_does_not_claim_the_branch_files():
    foreign = parse_plan_contract("### Fase 1\n**Criterios:** UC-999 AC-01\n**Ficheros:** server/a.py\n"
                                  "### Fase 2\n**Criterios:** AC-02\n**Ficheros:** server/b.py\n")
    out = build_drift_report(files=["server/a.py", "server/b.py"], uc_ids=["UC-701"], contracts=[("p.md", foreign)],
                             receipts={"UC-701": {"server/otro.py"}})
    assert out["unclaimed"] == ["server/a.py", "server/b.py"]  # ni la fase de UC-999 ni la que no dice UC
