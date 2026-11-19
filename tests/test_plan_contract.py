"""UC-12604 (US-126) — cada criterio enlaza con su fase del plan, sus ficheros y su prueba.

- AC-01: el plan de /plan dice en cada fase los criterios que cubre, y check_plan_contract avisa del
  criterio que ninguna fase cubre.
- AC-02: al marcar un criterio, el recibo guarda los ficheros que lo implementan y la prueba.
- AC-03: get_uc devuelve, por criterio, su fase, sus ficheros y su prueba.
- AC-04: con un plan anterior (sin esas líneas) todo sigue funcionando y el informe dice que falta
  la relación.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from server.ac_evidence import EvidenceError, normalize_evidence
from server.plan_contract import CONTRACT_NOTICE_OLD_PLAN, parse_plan_contract, phase_of, uncovered_criteria
from server.tools.plan_contract import check_plan_contract
from server.tools.spec_driven import get_uc, mark_ac
from tests.test_spec_gate_start_uc import CTX, US, _cleanup, _native_board, pg

ROOT = Path(__file__).resolve().parent.parent
PLAN = """# Plan: Cobros
## 5. Fases
### Fase 1: Registro del cobro
**Criterios:** UC-701 AC-01, AC-02
**Ficheros:** `server/cobros.py`, server/recibos.py

- [ ] tarea
### Fase 2: Historial
**Criterios:** AC-03
**Ficheros:** server/historial.py
## Dependencias nuevas
- pypi: rapidfuzz
- npm: zod
"""
OLD_PLAN = "# Plan viejo\n## Fases\n### Fase 1: Todo\n- [ ] hacer cosas\n## Archivos a Crear/Modificar\n```\nserver/x.py\n```\n"
UC = {"id": "uc701", "name": "UC-701: Cobrar", "description": "Cobrar con tarjeta", "state": "in_progress",
      "labels": ["UC"], "parent_id": "us7", "meta": {"uc_id": "UC-701", "us_id": "US-07"}}
ACS = [{"id": f"ac{i}", "name": f"[AC-0{i}] Criterio {i} queda registrado", "state": "backlog", "labels": ["AC"],
        "parent_id": "uc701", "meta": {"ac_id": f"AC-0{i}"}} for i in (1, 2, 3)]


# ── El contrato del plan (AC-01, AC-04) ─────────────────────────────


def test_a_plan_declares_criteria_files_and_dependencies_per_phase():
    contract = parse_plan_contract(PLAN, default_uc="UC-701")
    assert contract.contract_version == 1
    assert [p.title for p in contract.phases] == ["Fase 1: Registro del cobro", "Fase 2: Historial"]
    assert contract.phases[0].criteria == [("UC-701", "AC-01"), ("UC-701", "AC-02")]
    assert contract.phases[0].files == ["server/cobros.py", "server/recibos.py"]
    assert contract.phases[1].criteria == [("UC-701", "AC-03")]  # sin UC: la del plan
    assert contract.dependencies == [{"ecosystem": "pypi", "name": "rapidfuzz"}, {"ecosystem": "npm", "name": "zod"}]
    assert phase_of(contract, "UC-701", "AC-03").title == "Fase 2: Historial"
    assert uncovered_criteria(contract, {"UC-701": ["AC-01", "AC-02", "AC-03", "AC-04"]}) == {"UC-701": ["AC-04"]}


async def test_check_plan_contract_names_what_no_phase_covers():
    out = await check_plan_contract(PLAN, {"UC-701": ["AC-01", "AC-02", "AC-03", "AC-04"]}, "UC-701")
    assert out["contract_version"] == 1 and out["ok"] is False and out["uncovered"] == {"UC-701": ["AC-04"]}
    assert "AC-04" in out["warnings"][0]
    full = await check_plan_contract(PLAN, {"UC-701": ["AC-01", "AC-02", "AC-03"]}, "UC-701")
    assert full["ok"] is True and "warnings" not in full
    no_deps = await check_plan_contract(PLAN.split("## Dependencias")[0], {"UC-701": ["AC-01"]}, "UC-701")
    assert "Dependencias nuevas" in no_deps["warnings"][0]


async def test_an_older_plan_is_not_guessed_and_says_what_is_missing():
    """AC-04: contrato 0, con el aviso que /implement copia en su informe."""
    out = await check_plan_contract(OLD_PLAN, {"UC-701": ["AC-01"]}, "UC-701")
    assert out["contract_version"] == 0 and out["ok"] is False and out["notice"] == CONTRACT_NOTICE_OLD_PLAN
    assert out["phases"] == [] and out["dependencies"] is None


def test_the_plan_template_follows_the_contract():
    """AC-01: la plantilla de /plan lleva criterios y ficheros en cada fase y la sección de dependencias."""
    skill = (ROOT / ".claude/skills/plan/SKILL.md").read_text()
    template = skill[skill.index("## Fases de Implementación"):skill.index("## Comandos Finales")]
    template += skill[skill.index("## Dependencias nuevas"):skill.index("## Alternativas y Tradeoffs")]
    contract = parse_plan_contract(template, default_uc="UC-XXX")
    assert contract.contract_version == 1 and len(contract.phases) == 5
    assert all(p.criteria and p.files for p in contract.phases)
    assert contract.dependencies == []
    assert "check_plan_contract(" in skill
    implement = (ROOT / ".claude/skills/implement/SKILL.md").read_text()
    assert "check_plan_contract(" in implement and re.search(r'"test": "\{fichero de la prueba\}', implement)


# ── El recibo (AC-02) ───────────────────────────────────────────────


def test_a_receipt_keeps_files_test_and_phase_only_when_given():
    receipt = normalize_evidence({"type": "test", "label": "tests/test_cobros.py::test_registra",
                                  "files": ["server/cobros.py", "server/cobros.py", "server\\recibos.py"],
                                  "test": "tests/test_cobros.py::test_registra", "phase": "Fase 1: Registro"})
    assert receipt["files"] == ["server/cobros.py", "server/recibos.py"]
    assert receipt["test"] == "tests/test_cobros.py::test_registra" and receipt["phase"] == "Fase 1: Registro"
    plain = normalize_evidence({"type": "url", "label": "x"})
    assert set(plain) == {"type", "label", "link", "detail", "commit", "repo"}  # los de siempre, sin cambios
    for bad in (["../etc/passwd"], ["/abs/path"], "server/x.py", [f"f{i}.py" for i in range(51)]):
        with pytest.raises(EvidenceError):
            normalize_evidence({"type": "test", "label": "x", "files": bad})


# ── get_uc (AC-03) ──────────────────────────────────────────────────


async def test_freeform_get_uc_returns_phase_files_and_test_per_criterion():
    board = json.dumps([US, UC, *ACS])
    marked = await mark_ac("ff", "UC-701", "AC-01", True, CTX, items_content=board, evidence={
        "type": "test", "label": "tests/test_cobros.py::test_registra", "files": ["server/cobros.py"],
        "test": "tests/test_cobros.py::test_registra", "phase": "Fase 1: Registro del cobro"})
    detail = await get_uc("ff", "UC-701", CTX, items_content=marked["items_content"], plan_content=PLAN)
    by_id = {a["id"]: a for a in detail["acceptance_criteria"]}
    assert by_id["AC-01"]["phase"] == "Fase 1: Registro del cobro"
    assert by_id["AC-01"]["files"] == ["server/cobros.py"]
    assert by_id["AC-01"]["test"] == "tests/test_cobros.py::test_registra"
    # Sin recibo, la fase y sus ficheros salen del plan; la prueba, no.
    assert by_id["AC-03"]["phase"] == "Fase 2: Historial" and by_id["AC-03"]["files"] == ["server/historial.py"]
    assert by_id["AC-03"]["test"] is None
    # Con un plan anterior, nada se rompe y no hay fase (AC-04).
    old = await get_uc("ff", "UC-701", CTX, items_content=marked["items_content"], plan_content=OLD_PLAN)
    assert {a["id"]: a["phase"] for a in old["acceptance_criteria"]}["AC-02"] is None


@pg
async def test_native_keeps_files_and_test_with_the_receipt(monkeypatch, tmp_path):
    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria={"UC-01": ["El cobro queda registrado"]})
    try:
        out = await mark_ac(pid, "UC-01", "AC-01", True, ctx, evidence={
            "type": "test", "label": "tests/test_cobros.py::test_registra", "files": ["server/cobros.py"],
            "test": "tests/test_cobros.py::test_registra", "phase": "Fase 1",
            "commit": "185231f5828d64db74c5fedfc0be80da72a91983", "repo": "EmbedBuild/specbox-engine"})
        assert "error" not in out, out
        [ac] = (await get_uc(pid, "UC-01", ctx))["acceptance_criteria"]
        assert (ac["phase"], ac["files"], ac["test"]) == ("Fase 1", ["server/cobros.py"], "tests/test_cobros.py::test_registra")
    finally:
        await _cleanup(pool, pid, dev)
