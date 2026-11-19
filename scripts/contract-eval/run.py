#!/usr/bin/env python3
"""¿Detectan más fallos las pruebas generadas con contrato? (US-128 · UC-12801 AC-04).

Mide con fallos sembrados: por cada UC, unos mutantes (cambios de comportamiento escritos a partir
de sus criterios, registrados antes de generar ninguna prueba) y las pruebas generadas en dos brazos,
A (desde los criterios) y B (contrato primero), dos pasadas cada uno. Una prueba vale si pasa sobre el
código bueno; un mutante queda detectado si alguna prueba que vale falla con él.

Uso:
    python scripts/contract-eval/run.py --check-mutants [--uc UC-12604]
        Comprueba cada mutante (se aplica una sola vez, el módulo importa) y si lo detectan las
        pruebas que ya existen: ayuda a revisar los equivalentes, que se marcan a mano en mutants.json.
    python scripts/contract-eval/run.py [--uc UC-12604] [--arm A|B|both] [--passes 2]
        Mide las pruebas generadas y escribe results.jsonl y report.md.

Los mutantes: scripts/contract-eval/mutants/<UC>/mutants.json. Las pruebas generadas y su coste:
.quality/evidence/UC-12801/contract-eval/generated/<UC>/<A|B>-p<N>/ (test_generated.py, meta.json y,
en B, contract.json). La regla, fijada antes de empezar: el contrato gana si, sumando las 5 UC y las
dos pasadas, B detecta más mutantes que A sin más falsos positivos.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MUTANTS = ROOT / "scripts" / "contract-eval" / "mutants"
EVIDENCE = ROOT / ".quality" / "evidence" / "UC-12801" / "contract-eval"
GENERATED = EVIDENCE / "generated"
PYTHON = ROOT / ".venv" / "bin" / "python"

#: Las 5 UC: el módulo que se muta y las pruebas que ya tenía (solo para revisar los mutantes).
UCS: dict[str, dict] = {
    "UC-12604": {"module": "server/plan_contract.py", "tests": ["tests/test_plan_contract.py"]},
    "UC-12603": {"module": "server/closed_files.py", "tests": ["tests/test_closed_files.py"]},
    "UC-12502": {"module": "server/approval.py", "tests": ["tests/test_criteria_approval.py"]},
    "UC-12305": {"module": "server/coordination/enforcement.py", "tests": ["tests/test_pending_decisions.py"]},
    "UC-12606": {"module": "server/impact_radius.py", "tests": ["tests/test_impact_radius.py"]},
}
TIMEOUT = 180


def load_mutants(uc: str) -> list[dict]:
    path = MUTANTS / uc / "mutants.json"
    return json.loads(path.read_text(encoding="utf-8"))["mutants"] if path.exists() else []


def workspace(with_tests: bool = False) -> Path:
    """Una copia del paquete server (y, si se pide, de tests/) donde aplicar un mutante."""
    tmp = Path(tempfile.mkdtemp(prefix="contract-eval-"))
    shutil.copytree(ROOT / "server", tmp / "server", ignore=shutil.ignore_patterns("__pycache__"))
    for extra in ("pyproject.toml",):
        shutil.copy(ROOT / extra, tmp / extra)
    if with_tests:
        # Las pruebas que ya existían, y los hooks con los que algunas comparan (paridad Python/JS).
        shutil.copytree(ROOT / "tests", tmp / "tests", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / ".claude" / "hooks", tmp / ".claude" / "hooks", ignore=shutil.ignore_patterns("node_modules"))
    return tmp


def apply(tmp: Path, mutant: dict) -> str | None:
    """Aplica el mutante en la copia; devuelve el motivo si no se puede."""
    target = tmp / mutant["file"]
    text = target.read_text(encoding="utf-8")
    count = text.count(mutant["find"])
    if count != 1:
        return f"«find» aparece {count} veces en {mutant['file']}"
    target.write_text(text.replace(mutant["find"], mutant["replace"]), encoding="utf-8")
    return None


def pytest(tmp: Path, test_paths: list[Path | str], extra: list[str] | None = None) -> dict[str, str]:
    """Ejecuta pytest en la copia y devuelve {prueba: passed|failed|error|skipped}."""
    report = tmp / f"junit-{abs(hash(tuple(map(str, test_paths))))}.xml"
    cmd = [str(PYTHON), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header", f"--junitxml={report}",
           "-o", "addopts=", "--timeout=60", *(extra or []), *map(str, test_paths)]
    try:
        subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=TIMEOUT,
                       env={"PYTHONPATH": str(tmp), "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp)})
    except subprocess.TimeoutExpired:
        return {"<timeout>": "error"}
    if not report.exists():
        return {"<no-report>": "error"}
    outcomes: dict[str, str] = {}
    for case in ET.parse(report).getroot().iter("testcase"):
        name = f"{case.get('classname')}::{case.get('name')}"
        if case.find("failure") is not None:
            outcomes[name] = "failed"
        elif case.find("error") is not None:
            outcomes[name] = "error"
        elif case.find("skipped") is not None:
            outcomes[name] = "skipped"
        else:
            outcomes[name] = "passed"
    report.unlink()
    return outcomes


def check_mutants(uc: str) -> list[dict]:
    """Cada mutante: ¿se aplica, importa y lo detectan las pruebas que ya existían?"""
    spec = UCS[uc]
    # Lo que ya pasa en la copia sin mutar: una prueba que falla también sin mutante (le falta algo del
    # repositorio) no dice nada del mutante.
    base = workspace(with_tests=True)
    try:
        baseline = pytest(base, spec["tests"])
    finally:
        shutil.rmtree(base, ignore_errors=True)
    passing = {n for n, o in baseline.items() if o == "passed"}

    def one(mutant: dict) -> dict:
        tmp = workspace(with_tests=True)
        try:
            why = apply(tmp, mutant)
            if why:
                return {"id": mutant["id"], "ok": False, "why": why}
            module = spec["module"].removesuffix(".py").replace("/", ".")
            imp = subprocess.run([str(PYTHON), "-c", f"import {module}"], cwd=tmp, capture_output=True, text=True,
                                 env={"PYTHONPATH": str(tmp), "PATH": "/usr/bin:/bin"})
            if imp.returncode:
                return {"id": mutant["id"], "ok": False, "why": imp.stderr.strip().splitlines()[-1][:200]}
            # Sin Postgres, las pruebas de la base no pasan ni sin mutante: solo cuenta lo que pasaba.
            outcomes = pytest(tmp, spec["tests"])
            failed = sorted(n for n, o in outcomes.items() if n in passing and o in ("failed", "error"))
            return {"id": mutant["id"], "ok": True, "killed_by_existing": bool(failed), "failing": failed[:5]}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(one, load_mutants(uc)))


def generated_runs(uc: str, arms: list[str], passes: int) -> list[tuple[str, int, Path]]:
    runs = []
    for arm in arms:
        for n in range(1, passes + 1):
            path = GENERATED / uc / f"{arm}-p{n}" / "test_generated.py"
            if path.exists():
                runs.append((arm, n, path))
    return runs


def measure(uc: str, arms: list[str], passes: int) -> list[dict]:
    """Falsos positivos sobre el código bueno y mutantes detectados, por brazo y pasada."""
    mutants = [m for m in load_mutants(uc) if not m.get("equivalent")]
    runs = generated_runs(uc, arms, passes)
    rows = []
    base = workspace()
    try:
        baseline: dict[tuple[str, int], dict[str, str]] = {}
        for arm, n, path in runs:
            shutil.copy(path, base / f"test_{arm}_p{n}.py")
            baseline[(arm, n)] = pytest(base, [f"test_{arm}_p{n}.py"])
    finally:
        shutil.rmtree(base, ignore_errors=True)

    def against(mutant: dict) -> dict[tuple[str, int], bool]:
        tmp = workspace()
        try:
            if apply(tmp, mutant):
                return {}
            killed = {}
            for arm, n, path in runs:
                shutil.copy(path, tmp / f"test_{arm}_p{n}.py")
                valid = {t for t, o in baseline[(arm, n)].items() if o == "passed"}
                outcomes = pytest(tmp, [f"test_{arm}_p{n}.py"])
                killed[(arm, n)] = any(outcomes.get(t) in ("failed", "error") for t in valid) or (
                    bool(valid) and any(k.startswith("<") for k in outcomes))
            return killed
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    with ThreadPoolExecutor(max_workers=6) as pool:
        per_mutant = dict(zip([m["id"] for m in mutants], pool.map(against, mutants)))

    for arm, n, path in runs:
        outcomes = baseline[(arm, n)]
        meta_path = path.parent / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        killed = sorted(mid for mid, res in per_mutant.items() if res.get((arm, n)))
        rows.append({
            "uc_id": uc, "arm": arm, "pass": n,
            "tests": len(outcomes),
            "false_positives": sum(1 for o in outcomes.values() if o in ("failed", "error")),
            "mutants": len(mutants), "killed": len(killed), "killed_ids": killed,
            "survivors": sorted(set(per_mutant) - set(killed)),
            "tokens": meta.get("tokens"), "seconds": meta.get("seconds"),
        })
    return rows


def report(rows: list[dict]) -> str:
    def total(arm: str, key: str) -> int:
        return sum(r[key] for r in rows if r["arm"] == arm)

    a_k, b_k = total("A", "killed"), total("B", "killed")
    a_fp, b_fp = total("A", "false_positives"), total("B", "false_positives")
    a_m, b_m = total("A", "mutants"), total("B", "mutants")
    wins = b_k > a_k and b_fp <= a_fp
    lines = [
        "# Contrato antes de las pruebas: la medición (UC-12801 AC-04)",
        "",
        "Regla fijada antes de empezar: el contrato gana si, sumando las 5 UC y las dos pasadas, el brazo B "
        "(contrato primero) detecta más mutantes que el A (desde los criterios) sin más falsos positivos.",
        "",
        "| UC | Brazo | Pasada | Pruebas | Falsos positivos | Mutantes detectados | Tokens | Segundos |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: (r["uc_id"], r["arm"], r["pass"])):
        lines.append(f"| {r['uc_id']} | {r['arm']} | {r['pass']} | {r['tests']} | {r['false_positives']} | "
                     f"{r['killed']}/{r['mutants']} | {r['tokens'] or '—'} | {r['seconds'] or '—'} |")
    lines += [
        "",
        f"**Total A**: {a_k}/{a_m} mutantes detectados, {a_fp} falsos positivos.",
        f"**Total B**: {b_k}/{b_m} mutantes detectados, {b_fp} falsos positivos.",
        "",
        f"**Resultado**: {'el contrato gana' if wins else 'el contrato no gana'} "
        f"({'B detecta más sin más falsos positivos' if wins else 'B no detecta más, o lo hace con más falsos positivos'}).",
        "",
        "## Coste medio por pasada",
        "",
        "| Brazo | Pruebas | Tokens del subagente | Segundos |",
        "|---|---|---|---|",
    ]
    for arm in ("A", "B"):
        own = [r for r in rows if r["arm"] == arm]
        if own:
            mean = lambda key: sum(r[key] or 0 for r in own) / len(own)  # noqa: E731
            lines.append(f"| {arm} | {mean('tests'):.1f} | {mean('tokens'):,.0f} | {mean('seconds'):.1f} |")
    lines += ["", "## Mutantes que no detectó una pasada", "", "| UC | Brazo | Pasada | Mutantes |", "|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["uc_id"], r["arm"], r["pass"])):
        if r["survivors"]:
            lines.append(f"| {r['uc_id']} | {r['arm']} | {r['pass']} | {', '.join(r['survivors'])} |")
    lines += [
        "",
        "## Límites",
        "",
        "- El aislamiento de los subagentes es una instrucción, no una barrera; cada informe lo confirma.",
        "- Los tokens son los del subagente entero (incluye el contexto que recibe al empezar), no solo los "
        "de escribir las pruebas.",
        "- Cinco UC del propio engine, de lógica pura en Python; 10 mutantes por UC escritos por agentes "
        "aislados (ver `scripts/contract-eval/README.md`).",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--uc", choices=sorted(UCS), action="append")
    parser.add_argument("--arm", choices=["A", "B", "both"], default="both")
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--check-mutants", action="store_true")
    args = parser.parse_args(argv)
    ucs = args.uc or sorted(UCS)
    if args.check_mutants:
        for uc in ucs:
            print(json.dumps({"uc_id": uc, "mutants": check_mutants(uc)}, ensure_ascii=False))
        return 0
    arms = ["A", "B"] if args.arm == "both" else [args.arm]
    rows = [row for uc in ucs for row in measure(uc, arms, args.passes)]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                            encoding="utf-8")
    (EVIDENCE / "report.md").write_text(report(rows), encoding="utf-8")
    print(report(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
