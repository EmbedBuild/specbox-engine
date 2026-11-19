"""El contrato de cada criterio antes de las pruebas de aceptación (US-128 · UC-12801).

AG-09a escribe, antes de generar ninguna prueba, ``.quality/evidence/<feature>/acceptance/contract.json``
con las precondiciones (``pre``), las postcondiciones (``post``) y el comportamiento no definido
(``undefined``) de cada criterio vigente de la UC::

    {"schema": 1, "uc_id": "UC-12801", "criteria": {"AC-01": {
        "pre": [{"id": "AC-01.pre1", "text": "…"}],
        "post": [{"id": "AC-01.post1", "text": "…"}],
        "undefined": ["…"]}}}

Cada prueba cita en ``results[].contract`` (``{"pre": [...], "post": [...]}``) las condiciones que
comprueba. Este módulo es puro (no lee ni escribe nada) y tiene su espejo en
``.claude/hooks/lib/acceptance-contract.mjs``; ``tests/test_acceptance_contract.py`` comprueba que
los dos dicen lo mismo.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA = 1
#: Lo que cabe en una llamada: un contrato o unos resultados más grandes no son de una UC.
MAX_CONTRACT_BYTES = 512_000
MAX_RESULTS_BYTES = 5_000_000
MAX_CRITERIA = 200
MAX_CONDITIONS = 50
MAX_TEXT = 2000
KINDS = ("pre", "post")

_AC = re.compile(r"^\s*AC-(\d{1,4})\s*$", re.IGNORECASE | re.ASCII)
_CONDITION = re.compile(r"^\s*AC-(\d{1,4})\.(pre|post)(\d{1,4})\s*$", re.IGNORECASE | re.ASCII)


class ContractError(ValueError):
    """El contrato no se puede leer (no es JSON, no es un objeto o no es del esquema 1)."""


class ResultsError(ValueError):
    """Los resultados de las pruebas no se pueden leer."""


def _ac(raw: object) -> str | None:
    match = _AC.match(str(raw)) if isinstance(raw, str) else None
    return f"AC-{int(match[1]):02d}" if match else None


def normalize_condition(raw: object) -> tuple[str, str, str] | None:
    """``ac-1.PRE01`` es ``AC-01.pre1``: devuelve (id, criterio, clase) o None si no es una condición."""
    match = _CONDITION.match(raw) if isinstance(raw, str) else None
    if not match:
        return None
    ac, kind = f"AC-{int(match[1]):02d}", match[2].lower()
    return f"{ac}.{kind}{int(match[3])}", ac, kind


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


def _show(raw: object) -> str:
    """Un valor del cliente para un mensaje: el texto tal cual y lo demás en JSON (igual que el hook)."""
    if isinstance(raw, str):
        return raw
    try:
        return json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return "?"


def parse_contract(content: str | None) -> dict[str, Any]:
    """Lee el contrato y lo deja normalizado, con lo que no vale en ``invalid``.

    Devuelve ``{"uc_id", "criteria": {AC: {"pre", "post", "undefined"}}, "invalid": [...]}``.
    ``undefined`` es None cuando el criterio no lo escribe (vacío vale: se escribe aunque no haya
    nada). Un contenido que no es un contrato es un ``ContractError``.
    """
    if content is None or not str(content).strip():
        raise ContractError("está vacío")
    if _size(content) > MAX_CONTRACT_BYTES:
        raise ContractError(f"pasa de {MAX_CONTRACT_BYTES} bytes")
    try:
        data = json.loads(content)
    except (TypeError, ValueError) as e:
        raise ContractError(f"no es JSON ({e})") from e
    if not isinstance(data, dict):
        raise ContractError("no es un objeto JSON")
    schema = data.get("schema")
    if isinstance(schema, bool) or schema != SCHEMA:
        raise ContractError(f"su «schema» es {_show(schema)}; este engine lee el {SCHEMA}")
    raw_criteria = data.get("criteria")
    if not isinstance(raw_criteria, dict):
        raise ContractError("no tiene «criteria» como objeto")
    if len(raw_criteria) > MAX_CRITERIA:
        raise ContractError(f"tiene más de {MAX_CRITERIA} criterios")

    invalid: list[dict[str, str]] = []
    uc_id = data.get("uc_id")
    if not isinstance(uc_id, str) or not uc_id.strip():
        invalid.append({"ac_id": "", "problem": "falta «uc_id»"})
        uc_id = ""
    criteria: dict[str, dict[str, Any]] = {}
    for key, entry in raw_criteria.items():
        ac = _ac(key)
        if ac is None:
            invalid.append({"ac_id": str(key), "problem": "no es el id de un criterio (AC-NN)"})
            continue
        if ac in criteria:
            invalid.append({"ac_id": ac, "problem": "el criterio aparece dos veces"})
            continue
        if not isinstance(entry, dict):
            invalid.append({"ac_id": ac, "problem": "no es un objeto con «pre», «post» y «undefined»"})
            continue
        parsed: dict[str, Any] = {"pre": [], "post": [], "undefined": None}
        for kind in KINDS:
            items = entry.get(kind, [])
            if not isinstance(items, list):
                invalid.append({"ac_id": ac, "problem": f"«{kind}» no es una lista"})
                continue
            if len(items) > MAX_CONDITIONS:
                invalid.append({"ac_id": ac, "problem": f"«{kind}» tiene más de {MAX_CONDITIONS} condiciones"})
                items = items[:MAX_CONDITIONS]
            seen: set[str] = set()
            for item in items:
                raw_id = item.get("id") if isinstance(item, dict) else None
                text = item.get("text") if isinstance(item, dict) else None
                cond = normalize_condition(raw_id)
                if cond is None:
                    invalid.append({"ac_id": ac, "problem": f"«{kind}» tiene una condición sin id válido "
                                                            f"(AC-NN.{kind}N): {_show(raw_id)}"[:300]})
                    continue
                cond_id, cond_ac, cond_kind = cond
                if cond_ac != ac or cond_kind != kind:
                    invalid.append({"ac_id": ac, "problem": f"«{cond_id}» no es una {kind} de {ac}"})
                    continue
                if cond_id in seen:
                    invalid.append({"ac_id": ac, "problem": f"«{cond_id}» aparece dos veces"})
                    continue
                if not isinstance(text, str) or not text.strip():
                    invalid.append({"ac_id": ac, "problem": f"«{cond_id}» no tiene texto"})
                    continue
                if len(text) > MAX_TEXT:
                    invalid.append({"ac_id": ac, "problem": f"«{cond_id}» pasa de {MAX_TEXT} caracteres"})
                    continue
                seen.add(cond_id)
                parsed[kind].append({"id": cond_id, "text": text.strip()})
        undefined = entry.get("undefined")
        if undefined is not None:
            if not isinstance(undefined, list) or not all(isinstance(u, str) and u.strip() for u in undefined):
                invalid.append({"ac_id": ac, "problem": "«undefined» no es una lista de textos"})
            elif len(undefined) > MAX_CONDITIONS or any(len(u) > MAX_TEXT for u in undefined):
                invalid.append({"ac_id": ac, "problem": "«undefined» es demasiado largo"})
            else:
                parsed["undefined"] = [u.strip() for u in undefined]
        criteria[ac] = parsed
    return {"uc_id": uc_id.strip().upper(), "criteria": criteria, "invalid": invalid}


def check_contract(contract: dict[str, Any], criteria_ids: list[str], uc_id: str | None = None) -> dict[str, Any]:
    """Qué falta en el contrato para los criterios vigentes de la UC (UC-12801 AC-01).

    ``missing``: criterios sin entrada; ``incomplete``: criterios sin ``pre``, sin ``post`` o sin
    ``undefined`` escrito; ``extra``: entradas de criterios que la UC ya no tiene (solo aviso);
    ``uc_mismatch``: el contrato es de otra UC.
    """
    wanted: list[str] = []
    for raw in criteria_ids or []:
        ac = _ac(raw)
        if ac and ac not in wanted:
            wanted.append(ac)
    entries = contract["criteria"]
    missing = [ac for ac in wanted if ac not in entries]
    incomplete = []
    for ac in wanted:
        entry = entries.get(ac)
        if entry is None:
            continue
        lacks = [kind for kind in KINDS if not entry[kind]]
        if entry["undefined"] is None:
            lacks.append("undefined")
        if lacks:
            incomplete.append({"ac_id": ac, "missing": lacks})
    extra = [ac for ac in entries if ac not in wanted] if wanted else []
    out: dict[str, Any] = {"missing": missing, "incomplete": incomplete, "extra": extra}
    expected = (uc_id or "").strip().upper()
    if expected and contract["uc_id"] and contract["uc_id"] != expected:
        out["uc_mismatch"] = {"expected": expected, "found": contract["uc_id"]}
    return out


def parse_results(content: str | None) -> list[dict[str, Any]]:
    """Las ejecuciones de ``results.json`` (una o una lista), en orden: la más reciente, la última."""
    if content is None or not str(content).strip():
        raise ResultsError("está vacío")
    if _size(content) > MAX_RESULTS_BYTES:
        raise ResultsError(f"pasa de {MAX_RESULTS_BYTES} bytes")
    try:
        data = json.loads(content)
    except (TypeError, ValueError) as e:
        raise ResultsError(f"no es JSON ({e})") from e
    runs = data if isinstance(data, list) else [data]
    if not runs:
        raise ResultsError("no trae ninguna ejecución")
    for n, run in enumerate(runs, 1):
        if not isinstance(run, dict) or not isinstance(run.get("results"), list):
            raise ResultsError(f"la ejecución {n} no tiene una lista «results»")
    if all(isinstance(r.get("timestamp"), str) and r["timestamp"] for r in runs):
        runs = sorted(runs, key=lambda r: r["timestamp"])
    return runs


def _latest_tests(runs: list[dict[str, Any]], uc_id: str) -> dict[str, list[dict[str, Any]]]:
    """Las pruebas de cada criterio en la ejecución más reciente que lo trae (como run_acceptance_check)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        run_uc = str(run.get("uc_id") or "").strip().upper()
        if uc_id and run_uc and run_uc != uc_id:
            continue
        this_run: dict[str, list[dict[str, Any]]] = {}
        for result in run["results"]:
            ac = _ac(result.get("id")) if isinstance(result, dict) else None
            if ac:
                this_run.setdefault(ac, []).append(result)
        out.update(this_run)
    return out


def check_citations(contract: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Qué pruebas no citan su precondición y su postcondición, o citan una que no existe (AC-02).

    Cada resultado lleva ``contract: {"pre": [...], "post": [...]}`` con condiciones de su criterio.
    ``uncited``: pruebas sin ``pre`` o sin ``post``; ``unknown``: citas de condiciones que el
    contrato no tiene, de otro criterio o de la otra clase; ``not_cited``: condiciones del contrato
    que ninguna prueba cita (solo aviso).
    """
    conditions: dict[str, tuple[str, str]] = {}
    for ac, entry in contract["criteria"].items():
        for kind in KINDS:
            for cond in entry[kind]:
                conditions[cond["id"]] = (ac, kind)
    tests = _latest_tests(runs, contract["uc_id"])
    uncited: list[dict[str, Any]] = []
    unknown: list[dict[str, str]] = []
    cited: set[str] = set()
    checked = 0
    for ac, results in tests.items():
        for n, result in enumerate(results, 1):
            checked += 1
            scenario = result.get("scenario")
            label = (scenario if isinstance(scenario, str) and scenario else f"{ac} #{n}")[:200]
            citation = result.get("contract")
            citation = citation if isinstance(citation, dict) else {}
            lacks: list[str] = []
            for kind in KINDS:
                values = citation.get(kind)
                values = values if isinstance(values, list) else []
                found = False
                for raw in values:
                    cond = normalize_condition(raw)
                    if cond is None or cond[0] not in conditions:
                        unknown.append({"ac_id": ac, "test": label, "condition": _show(raw)[:100],
                                        "problem": "no existe en el contrato"})
                        continue
                    cond_ac, cond_kind = conditions[cond[0]]
                    if cond_ac != ac:
                        unknown.append({"ac_id": ac, "test": label, "condition": cond[0],
                                        "problem": f"es de otro criterio ({cond_ac})"})
                        continue
                    if cond_kind != kind:
                        unknown.append({"ac_id": ac, "test": label, "condition": cond[0],
                                        "problem": f"es una {cond_kind}, no una {kind}"})
                        continue
                    found = True
                    cited.add(cond[0])
                if not found:
                    lacks.append(kind)
            if lacks:
                uncited.append({"ac_id": ac, "test": label, "missing": lacks})
    not_cited = [cid for cid, (ac, _) in conditions.items() if ac in tests and cid not in cited]
    return {"tests_checked": checked, "uncited": uncited, "unknown": unknown, "not_cited": not_cited}


def contract_report(
    contract_content: str | None,
    criteria_ids: list[str] | None,
    uc_id: str | None = None,
    results_content: str | None = None,
) -> dict[str, Any]:
    """El informe completo de ``check_acceptance_contract`` (el hook calcula lo mismo en JS)."""
    try:
        contract = parse_contract(contract_content)
    except ContractError as e:
        return {"success": False, "code": "INVALID_CONTRACT",
                "error": f"contract_content no es un contrato válido: {e}. Escríbelo como dice "
                         "doc/specs/results-json-spec.md («Contrato de cada criterio»)."}
    out: dict[str, Any] = {"success": True, "uc_id": contract["uc_id"], "invalid": contract["invalid"]}
    out.update(check_contract(contract, criteria_ids or [], uc_id))
    if not criteria_ids:
        out["notice"] = ("Sin uc_criteria solo se comprueba la forma del contrato: pasa los criterios vigentes "
                         "de la UC para saber si falta alguno.")
    ok = not (out["missing"] or out["incomplete"] or out["invalid"] or out.get("uc_mismatch"))
    warnings: list[str] = []
    if out["missing"]:
        warnings.append(f"Criterios sin contrato: {', '.join(out['missing'])}. Escribe su pre, su post y su "
                        "undefined antes de generar sus pruebas.")
    if out["incomplete"]:
        listed = "; ".join(f"{i['ac_id']} (sin {' ni '.join(i['missing'])})" for i in out["incomplete"])
        warnings.append(f"Criterios con el contrato incompleto: {listed}.")
    if out["invalid"]:
        warnings.append(f"El contrato tiene {len(out['invalid'])} entradas que no valen: corrígelas.")
    if out.get("uc_mismatch"):
        warnings.append(f"El contrato es de {out['uc_mismatch']['found']}, no de {out['uc_mismatch']['expected']}.")
    if out["extra"]:
        warnings.append(f"El contrato trae criterios que la UC no tiene: {', '.join(out['extra'])}.")
    if results_content is not None:
        try:
            runs = parse_results(results_content)
        except ResultsError as e:
            return {"success": False, "code": "INVALID_RESULTS",
                    "error": f"results_content no es un results.json válido: {e}"}
        citations = check_citations(contract, runs)
        out["citations"] = citations
        ok = ok and not (citations["uncited"] or citations["unknown"])
        if citations["uncited"]:
            warnings.append(f"{len(citations['uncited'])} pruebas no citan su precondición y su postcondición: "
                            "etiquétalas con @pre:AC-NN.preN y @post:AC-NN.postN.")
        if citations["unknown"]:
            warnings.append(f"{len(citations['unknown'])} citas no corresponden a una condición de su criterio.")
        if citations["not_cited"]:
            warnings.append(f"Condiciones que ninguna prueba comprueba: {', '.join(citations['not_cited'][:20])}.")
    out["ok"] = ok
    if warnings:
        out["warnings"] = warnings
    return out
