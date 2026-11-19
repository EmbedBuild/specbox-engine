"""UC-12801 (US-128) — el contrato de cada criterio antes de las pruebas de aceptación.

- AC-01: el contrato tiene, por cada criterio vigente, sus precondiciones, sus postcondiciones y el
  comportamiento no definido; la tool dice qué falta.
- AC-02: cada prueba cita la precondición y la postcondición de su criterio que comprueba; la tool y
  el validador de results.json dicen qué prueba no lo hace o cita algo que no existe.

Las reglas viven en `server/acceptance_contract.py` y en su espejo
`.claude/hooks/lib/acceptance-contract.mjs`: la prueba de paridad pasa los mismos casos por los dos.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from server.acceptance_contract import (
    MAX_CONTRACT_BYTES,
    ContractError,
    check_citations,
    check_contract,
    contract_report,
    normalize_condition,
    parse_contract,
    parse_results,
)
from server.tools.acceptance_contract import check_acceptance_contract

ROOT = Path(__file__).resolve().parent.parent

GOOD = {
    "schema": 1,
    "uc_id": "UC-900",
    "criteria": {
        "AC-01": {
            "pre": [{"id": "AC-01.pre1", "text": "Hay una factura con dos líneas de 60,00 €"}],
            "post": [{"id": "AC-01.post1", "text": "El total queda en 120,00 €"}],
            "undefined": [],
        },
        "AC-02": {
            "pre": [{"id": "AC-02.pre1", "text": "La factura no tiene líneas"}],
            "post": [
                {"id": "AC-02.post1", "text": "El total queda en 0,00 €"},
                {"id": "AC-02.post2", "text": "No aparece ningún aviso"},
            ],
            "undefined": ["Qué pasa con una línea de importe negativo"],
        },
    },
}

BAD = {
    "schema": 1,
    "criteria": {
        "AC-01": {"pre": [
            {"id": "AC-01.pre1", "text": "Hay una factura"},
            {"id": "AC-02.pre1", "text": "De otro criterio"},
            {"id": "AC-01.pre1", "text": "Repetida"},
            {"id": "AC-01.pre2", "text": "   "},
            {"text": "Sin id"},
        ]},
        "AC-1": {},
        "foo": {},
        "AC-03": "un texto",
        "AC-04": {"pre": "no", "post": [], "undefined": [1]},
    },
}


def _result(ac: str, scenario: str, contract: dict | None = None, status: str = "PASS") -> dict:
    out = {"id": ac, "scenario": scenario, "status": status, "duration_ms": 10, "evidence": None, "error": None}
    if contract is not None:
        out["contract"] = contract
    return out


def _run(results: list[dict], uc: str = "UC-900", ts: str = "2026-11-19T10:00:00Z") -> dict:
    passed = sum(r["status"] == "PASS" for r in results)
    return {"feature": "facturas", "uc_id": uc, "us_id": "US-09", "timestamp": ts, "source": "pytest-bdd",
            "stack": "python", "evidence_type": "response-log", "tests_total": len(results),
            "tests_passed": passed, "tests_failed": len(results) - passed, "results": results}


GOOD_RESULTS = _run([
    _result("AC-01", "Total con dos líneas", {"pre": ["AC-01.pre1"], "post": ["AC-01.post1"]}),
    _result("AC-02", "Factura sin líneas", {"pre": ["ac-2.PRE1"], "post": ["AC-02.post1"]}),
])

BAD_RESULTS = _run([
    _result("AC-01", "Sin citas"),
    _result("AC-02", "Citas que no valen", {"pre": ["AC-01.pre1", "AC-02.post1"], "post": ["AC-02.post9", 7]}),
])


def test_condition_ids_are_normalized():
    assert normalize_condition("ac-1.PRE01") == ("AC-01.pre1", "AC-01", "pre")
    assert normalize_condition(" AC-12.post3 ") == ("AC-12.post3", "AC-12", "post")
    assert normalize_condition("AC-01.pre") is None and normalize_condition("AC-01") is None
    assert normalize_condition(None) is None and normalize_condition("AC-١.pre1") is None  # solo cifras ASCII


def test_ac01_a_complete_contract_passes():
    report = contract_report(json.dumps(GOOD), ["AC-01", "AC-2"], "uc-900")
    assert report["success"] and report["ok"], report
    assert report["missing"] == [] and report["incomplete"] == [] and report["invalid"] == []
    assert "warnings" not in report


def test_ac01_the_contract_says_what_is_missing_incomplete_or_invalid():
    report = contract_report(json.dumps(BAD), ["AC-01", "AC-02", "AC-03"], "UC-900")
    assert report["success"] and not report["ok"]
    assert report["missing"] == ["AC-02", "AC-03"]
    assert report["incomplete"] == [{"ac_id": "AC-01", "missing": ["post", "undefined"]}]
    assert report["extra"] == ["AC-04"]
    problems = [(i["ac_id"], i["problem"]) for i in report["invalid"]]
    assert problems[0] == ("", "falta «uc_id»")
    assert ("AC-01", "«AC-02.pre1» no es una pre de AC-01") in problems
    assert ("AC-01", "«AC-01.pre1» aparece dos veces") in problems
    assert ("AC-01", "«AC-01.pre2» no tiene texto") in problems
    assert ("AC-01", "«pre» tiene una condición sin id válido (AC-NN.preN): null") in problems
    assert ("AC-01", "el criterio aparece dos veces") in problems  # «AC-1» es AC-01
    assert ("foo", "no es el id de un criterio (AC-NN)") in problems
    assert ("AC-03", "no es un objeto con «pre», «post» y «undefined»") in problems
    assert ("AC-04", "«pre» no es una lista") in problems and ("AC-04", "«undefined» no es una lista de textos") in problems
    assert any("Criterios sin contrato: AC-02, AC-03" in w for w in report["warnings"])


def test_ac01_undefined_may_be_empty_but_is_written():
    contract = json.loads(json.dumps(GOOD))
    del contract["criteria"]["AC-01"]["undefined"]
    report = contract_report(json.dumps(contract), ["AC-01", "AC-02"])
    assert report["incomplete"] == [{"ac_id": "AC-01", "missing": ["undefined"]}] and not report["ok"]


def test_ac01_a_contract_of_another_uc_does_not_pass():
    report = contract_report(json.dumps(GOOD), ["AC-01", "AC-02"], "UC-901")
    assert report["uc_mismatch"] == {"expected": "UC-901", "found": "UC-900"} and not report["ok"]


def test_without_criteria_only_the_shape_is_checked_and_it_says_so():
    report = contract_report(json.dumps(GOOD), None)
    assert report["ok"] and "Sin uc_criteria" in report["notice"]


@pytest.mark.parametrize("content, why", [
    ("", "está vacío"),
    ("[]", "no es un objeto JSON"),
    (json.dumps({"schema": 2, "criteria": {}}), "su «schema» es 2; este engine lee el 1"),
    (json.dumps({"schema": True, "criteria": {}}), "su «schema» es true"),
    (json.dumps({"schema": 1}), "no tiene «criteria» como objeto"),
    ("{" + " " * MAX_CONTRACT_BYTES + "}", "pasa de 512000 bytes"),
])
def test_a_content_that_is_not_a_contract_answers_invalid_contract(content, why):
    with pytest.raises(ContractError):
        parse_contract(content)
    report = contract_report(content, ["AC-01"])
    assert report["success"] is False and report["code"] == "INVALID_CONTRACT" and why in report["error"]


def test_ac02_every_test_cites_a_pre_and_a_post_of_its_criterion():
    report = contract_report(json.dumps(GOOD), ["AC-01", "AC-02"], "UC-900", json.dumps(GOOD_RESULTS))
    assert report["ok"], report
    citations = report["citations"]
    assert citations["tests_checked"] == 2 and citations["uncited"] == [] and citations["unknown"] == []
    # Una postcondición que ninguna prueba comprueba es un aviso, no un fallo.
    assert citations["not_cited"] == ["AC-02.post2"]
    assert any("AC-02.post2" in w for w in report["warnings"])


def test_ac02_tests_without_citations_or_with_wrong_ones_do_not_pass():
    report = contract_report(json.dumps(GOOD), ["AC-01", "AC-02"], "UC-900", json.dumps(BAD_RESULTS))
    assert not report["ok"]
    citations = report["citations"]
    assert citations["uncited"] == [
        {"ac_id": "AC-01", "test": "Sin citas", "missing": ["pre", "post"]},
        {"ac_id": "AC-02", "test": "Citas que no valen", "missing": ["pre", "post"]},
    ]
    assert [(u["condition"], u["problem"]) for u in citations["unknown"]] == [
        ("AC-01.pre1", "es de otro criterio (AC-01)"),
        ("AC-02.post1", "es una post, no una pre"),
        ("AC-02.post9", "no existe en el contrato"),
        ("7", "no existe en el contrato"),
    ]


def test_ac02_the_latest_run_of_each_criterion_counts_and_other_ucs_are_ignored():
    old = _run([_result("AC-01", "Antigua sin citas")], ts="2026-11-19T09:00:00Z")
    other_uc = _run([_result("AC-02", "De otra UC")], uc="UC-777", ts="2026-11-19T11:00:00Z")
    runs = parse_results(json.dumps([GOOD_RESULTS, old, other_uc]))  # ordenadas por su timestamp
    citations = check_citations(parse_contract(json.dumps(GOOD)), runs)
    assert citations["uncited"] == [] and citations["tests_checked"] == 2


def test_results_that_cannot_be_read_answer_invalid_results():
    report = contract_report(json.dumps(GOOD), ["AC-01"], None, '{"results": "no"}')
    assert report["code"] == "INVALID_RESULTS" and "no tiene una lista «results»" in report["error"]
    assert contract_report(json.dumps(GOOD), ["AC-01"], None, "")["code"] == "INVALID_RESULTS"


def test_check_contract_keeps_the_criteria_order_and_ignores_ids_that_are_not_criteria():
    contract = parse_contract(json.dumps(GOOD))
    assert check_contract(contract, ["AC-03", "x", "AC-01", "ac-01"])["missing"] == ["AC-03"]


def test_the_tool_is_pure_and_registered():
    report = asyncio.run(check_acceptance_contract(json.dumps(GOOD), ["AC-01", "AC-02"], "UC-900",
                                                   json.dumps(GOOD_RESULTS)))
    assert report["ok"]
    from server.server import mcp

    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    assert "check_acceptance_contract" in tools
    template = (ROOT / "templates/settings.json.template").read_text(encoding="utf-8")
    assert "mcp__SpecBox-MCP__check_acceptance_contract" in template


# ── Paridad con el hook ────────────────────────────────────────────────────────────────────────

CASES = [
    {"contract": json.dumps(GOOD), "criteria": ["AC-01", "AC-02"], "uc": "UC-900", "results": json.dumps(GOOD_RESULTS)},
    {"contract": json.dumps(GOOD), "criteria": ["AC-01", "AC-02"], "uc": "UC-900", "results": json.dumps(BAD_RESULTS)},
    {"contract": json.dumps(BAD), "criteria": ["AC-01", "AC-02", "AC-03"], "uc": "UC-900", "results": None},
    {"contract": json.dumps(GOOD), "criteria": None, "uc": "UC-901", "results": None},
    {"contract": json.dumps(GOOD), "criteria": ["AC-01"], "uc": None,
     "results": json.dumps([GOOD_RESULTS, _run([_result("AC-01", "Antigua")], ts="2026-01-01T00:00:00Z")])},
    {"contract": json.dumps({"schema": 2, "criteria": {}}), "criteria": None, "uc": None, "results": None},
    {"contract": json.dumps({"schema": "1", "criteria": {}}), "criteria": None, "uc": None, "results": None},
    {"contract": json.dumps({"schema": 1.0, "uc_id": "UC-1", "criteria": {"AC-01": {"pre": [{"id": {"a": [1]}}]}}}),
     "criteria": ["AC-01"], "uc": None, "results": None},
    {"contract": json.dumps(GOOD), "criteria": ["AC-01"], "uc": None, "results": '{"results": 3}'},
    {"contract": "", "criteria": None, "uc": None, "results": None},
]


def test_the_server_and_the_hook_say_the_same():
    if not shutil.which("node"):
        pytest.skip("sin node")
    py = [contract_report(c["contract"], c["criteria"], c["uc"], c["results"]) for c in CASES]
    script = (
        "import { contractReport } from './.claude/hooks/lib/acceptance-contract.mjs';"
        "import { readFileSync } from 'node:fs';"
        "const cases = JSON.parse(readFileSync(0, 'utf8'));"
        "console.log(JSON.stringify(cases.map((c) => contractReport({contractContent: c.contract, "
        "criteriaIds: c.criteria, ucId: c.uc, resultsContent: c.results}))));"
    )
    js = json.loads(subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, input=json.dumps(CASES),
                                   capture_output=True, text=True, check=True).stdout)
    assert js == py


# ── AC-03 / AC-06: el informe de aceptación enseña el contrato junto al resultado ──────────────

PRD = """# Facturas

## US-09: Totales

#### UC-900: Total de la factura
- [ ] **AC-01**: El total queda en 120,00 € con dos líneas de 60,00 €
- [ ] **AC-02**: El total queda en 0,00 € sin líneas
"""


def _check(**kwargs):
    from server.tools.acceptance import run_acceptance_check_from_content

    return run_acceptance_check_from_content(prd_content=PRD, item_id="UC-900", results_content=json.dumps(GOOD_RESULTS),
                                             **kwargs)


def test_ac03_the_report_shows_the_contract_next_to_each_result():
    contract = json.loads(json.dumps(GOOD))
    del contract["criteria"]["AC-02"]
    out = _check(contract_content=json.dumps(contract))
    [uc] = out["uc_results"]
    ac01, ac02 = uc["criteria"]
    assert ac01["verdict"] == "ACCEPTED" and [c["id"] for c in ac01["contract"]["post"]] == ["AC-01.post1"]
    assert ac01["contract"]["undefined"] == [] and "contract_warning" not in ac01
    # AC-06: sin contrato, el informe lo dice en ese criterio.
    assert ac02["contract"] is None and ac02["contract_warning"].startswith("Sin contrato")
    report = json.loads(out["reports"][".quality/acceptance-check/UC-900/report.json"])
    assert report["criteria_without_contract"] == ["AC-02"]
    md = out["reports"][".quality/acceptance-check/UC-900/report.md"]
    assert "- Pre `AC-01.pre1`: Hay una factura con dos líneas de 60,00 €" in md
    assert "- Sin definir: nada" in md and "**Contrato**: Sin contrato" in md


def test_ac06_an_empty_contract_means_the_uc_has_none_and_omitted_keeps_the_old_report():
    empty = _check(contract_content="")
    assert all(c["contract"] is None for c in empty["uc_results"][0]["criteria"])
    old = _check()
    assert all("contract" not in c for c in old["uc_results"][0]["criteria"])
    assert "Contrato" not in old["reports"][".quality/acceptance-check/UC-900/report.md"]


def test_an_unreadable_contract_answers_invalid_contract():
    out = _check(contract_content='{"schema": 3}')
    assert out["code"] == "INVALID_CONTRACT" and "schema" in out["error"]


# ── AC-04 / AC-05: la medición decide el valor por defecto ─────────────────────────────────────

EVAL = ROOT / ".quality" / "evidence" / "UC-12801" / "contract-eval"


def test_ac04_the_measurement_is_in_the_evidence_with_its_rule():
    rows = [json.loads(line) for line in (EVAL / "results.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert {r["uc_id"] for r in rows} == {"UC-12604", "UC-12603", "UC-12502", "UC-12305", "UC-12606"}
    assert sorted((r["arm"], r["pass"]) for r in rows if r["uc_id"] == "UC-12604") == [("A", 1), ("A", 2), ("B", 1), ("B", 2)]
    assert all(r["mutants"] >= 8 for r in rows)  # al menos 8 fallos sembrados por UC
    assert "Regla fijada antes de empezar" in (EVAL / "report.md").read_text(encoding="utf-8")


def test_ac05_the_default_follows_the_measurement():
    from server.coordination.enforcement import MEASURES

    rows = [json.loads(line) for line in (EVAL / "results.jsonl").read_text(encoding="utf-8").splitlines() if line]
    total = lambda arm, key: sum(r[key] for r in rows if r["arm"] == arm)  # noqa: E731
    wins = total("B", "killed") > total("A", "killed") and total("B", "false_positives") <= total("A", "false_positives")
    template = json.loads((ROOT / "templates/settings.json.template").read_text(encoding="utf-8"))
    implement = (ROOT / ".claude/skills/implement/SKILL.md").read_text(encoding="utf-8")
    if wins:
        assert template["acceptance"]["contract"] is True
        assert MEASURES["contract_first"].new_default == "warn"
        assert "**Por defecto, siempre** (`acceptance.contract: true`" in implement
    else:
        assert template["acceptance"]["contract"] is False
        assert MEASURES["contract_first"].new_default == "off"
