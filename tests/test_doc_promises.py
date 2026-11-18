"""La documentación del engine no promete lo que el código no hace (EP-20 · US-122).

La auditoría «SpecBox frente al SDD» (2026-11-18) halló promesas de la documentación que el
código no cumplía. Mientras el código no las cumpla, la documentación dice lo que pasa de
verdad, y estas pruebas impiden que la promesa vuelva a colarse.

- UC-12201 → UC-12301: el Definition Quality Gate avisa en /prd y lo impone `start_uc` con la medida
  `spec_quality` en «block». Ningún documento dice que bloquea sin decir dónde (`start_uc`) y cuándo
  («block»), ni conserva la nota de que «llegará».
- UC-12202: spec-guard avisa después de escribir; solo bloquea en main o master.
- UC-12204: Spec-Code Sync lista los ficheros tocados; aún no los compara con el plan.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Documentación viva del engine. Fuera: CHANGELOG (histórico) y doc/ salvo las guías
# (PRDs, planes y tracking son registros de su momento).
DOC_GLOBS = (
    "README*.md",
    "CLAUDE.md",
    "rules/*.md",
    "agents/*.md",
    "templates/*.template",
    ".claude/skills/*/SKILL.md",
    ".claude/skills/*/reference/*.md",
    "docs/**/*.md",
    "doc/guides/**/*.md",
)


def _doc_lines() -> list[tuple[str, int, str]]:
    lines: list[tuple[str, int, str]] = []
    seen: set[Path] = set()
    for pattern in DOC_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            rel = path.relative_to(REPO_ROOT).as_posix()
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                lines.append((rel, number, line))
    return lines


DOC_LINES = _doc_lines()


LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s|^\s*\|")


def _doc_paragraphs() -> list[tuple[str, int, str]]:
    """(fichero, primera línea, texto) de cada párrafo: una afirmación puede partirse en líneas.

    Cada elemento de lista y cada fila de tabla empieza un párrafo: son afirmaciones distintas.
    """
    paragraphs: list[tuple[str, int, str]] = []
    current: list[str] = []
    start = 0
    previous = None
    for rel, number, line in DOC_LINES + [("", 0, "")]:
        if rel != previous or not line.strip() or LIST_ITEM.match(line):
            if current:
                paragraphs.append((previous, start, " ".join(current)))
            current = []
        if line.strip():
            if not current:
                start = number
            current.append(line.strip())
        previous = rel
    return paragraphs


DOC_PARAGRAPHS = _doc_paragraphs()


def _offending(subject: re.Pattern[str], claim: re.Pattern[str]) -> list[str]:
    return [
        f"{rel}:{number}: {line.strip()}"
        for rel, number, line in DOC_LINES
        if subject.search(line) and claim.search(line)
    ]


def test_the_docs_are_scanned():
    files = {rel for rel, _, _ in DOC_LINES}
    assert "CLAUDE.md" in files
    assert ".claude/skills/prd/SKILL.md" in files
    assert len(files) > 30


# UC-12201 → UC-12301 ─ el Definition Quality Gate avisa en /prd y lo impone start_uc en «block».
QUALITY_GATE = re.compile(
    r"definition quality gate|calidad de definici[oó]n|validate_ac_quality|\bAC vagos\b|\bvague AC\b",
    re.IGNORECASE,
)
BLOCKS_NOW = re.compile(r"\b(bloquea|bloqueante|blocks|blocking|no arranca|does not start)\b", re.IGNORECASE)
WHERE_AND_WHEN = (re.compile(r"start_uc"), re.compile(r"«block»|\bblock\b"))


def _overpromises(text: str) -> bool:
    return bool(QUALITY_GATE.search(text) and BLOCKS_NOW.search(text)) and not all(
        rule.search(text) for rule in WHERE_AND_WHEN
    )


def test_uc_12301_the_rule_tells_an_overpromise_from_the_truth():
    assert _overpromises("El Definition Quality Gate bloquea las UC con criterios vagos.")
    assert not _overpromises(
        "La medida es validate_ac_quality y la impone start_uc: en «block» la UC no arranca; en «warn» avisa."
    )


def test_uc_12301_a_doc_that_says_the_gate_blocks_says_where_and_when():
    """AC-05: el gate bloquea en start_uc y solo con la medida en «block»; decirlo sin eso es prometer de más."""
    offending = [f"{rel}:{start}: {text[:160]}" for rel, start, text in DOC_PARAGRAPHS if _overpromises(text)]
    assert offending == [], "El gate solo bloquea en start_uc con la medida en «block»:\n" + "\n".join(offending)


def test_uc_12301_the_prd_skill_says_start_uc_enforces_the_gate():
    prd = (REPO_ROOT / ".claude/skills/prd/SKILL.md").read_text(encoding="utf-8")
    step = prd.split("## Paso 2.5:", 1)[1].split("\n## ", 1)[0]
    assert "(se impone en start_uc)" in step.splitlines()[0]
    assert "La medida es `validate_ac_quality`" in step
    assert "AC_QUALITY_BELOW_THRESHOLD" in step and "«warn»" in step
    assert "validate_ac_quality: {passed}/{total}" in step, "el informe del Paso 2.5.7 muestra el resultado"


# AC-05: la nota de UC-12201 («lo impondrá UC-12301», «el servidor no lo impone») se deshace.
UC_12201_NOTE = re.compile(
    r"impondr[aá]|bloqueo real llegar|el servidor no lo impone|no detiene nada en el servidor",
    re.IGNORECASE,
)


def test_uc_12301_the_uc_12201_note_is_gone():
    offending = [f"{rel}:{n}: {line.strip()}" for rel, n, line in DOC_LINES if UC_12201_NOTE.search(line)]
    assert offending == [], "Quedan restos de la nota de UC-12201:\n" + "\n".join(offending)


@pytest.mark.parametrize("claim", ["BLOQUEANTE", "NO se crea hasta que este gate pase"])
def test_uc_12201_old_claims_are_gone_from_the_prd_skill(claim):
    assert claim not in (REPO_ROOT / ".claude/skills/prd/SKILL.md").read_text(encoding="utf-8")


# UC-12202 ─ spec-guard avisa después de escribir; solo bloquea en main o master.
SPEC_GUARD = re.compile(r"spec-guard", re.IGNORECASE)
IMPOSSIBLE = re.compile(r"\bimpossible\b|\bimposible\b", re.IGNORECASE)


def test_uc_12202_no_doc_says_spec_guard_makes_it_impossible():
    offending = [
        f"{rel}:{start}: {text[:160]}"
        for rel, start, text in DOC_PARAGRAPHS
        if SPEC_GUARD.search(text) and IMPOSSIBLE.search(text)
    ]
    assert offending == [], "spec-guard avisa; no hace nada imposible:\n" + "\n".join(offending)


def _row(path: str, hook: str) -> str:
    def first_cell(line: str) -> str:
        return line.split("|")[1].strip().strip("*`").removesuffix(".mjs")

    rows = [line for line in (REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
            if line.startswith("|") and first_cell(line) == hook]
    assert len(rows) == 1, f"{path}: una fila para {hook}"
    return rows[0]


def test_uc_12202_the_hooks_table_describes_what_spec_guard_does():
    claude = _row("CLAUDE.md", "spec-guard")
    assert "after the write" in claude
    assert "main or master" in claude
    # UC-12217: el bloqueo por reserva perdida ya funciona; la tabla lo dice con la tool que lo comprueba.
    assert "get_uc_reservation" in claude and "UC-12217" in claude and "pending" not in claude
    rules = _row("rules/GLOBAL_RULES.md", "spec-guard")
    assert "Despues de Write/Edit" in rules
    assert "main/master" in rules and "get_uc_reservation" in rules and "pendiente" not in rules
    assert "NOTA (UC)" in rules


def test_uc_12202_branch_guard_is_not_sold_as_blocking():
    assert "**BLOQUEANTE**" not in _row("rules/GLOBAL_RULES.md", "branch-guard")


# UC-12204 ─ Spec-Code Sync no compara con el plan (el comparador no recibe sus ficheros).
PLAN_COMPARISON = re.compile(
    r"deltas? vs\.? plan|compara(?:do|da)? con el plan|conforme al plan|compared? (?:with|against) the plan",
    re.IGNORECASE,
)


def test_uc_12204_no_doc_says_spec_code_sync_compares_with_the_plan():
    offending = [
        f"{rel}:{start}: {text[:160]}"
        for rel, start, text in DOC_PARAGRAPHS
        if PLAN_COMPARISON.search(text)
    ]
    assert offending == [], "Spec-Code Sync aún no compara con el plan:\n" + "\n".join(offending)


def test_uc_12204_the_mcp_instructions_do_not_promise_a_plan_comparison():
    # server.py:INSTRUCTIONS es lo que el MCP manda a todos los clientes al conectar.
    server = (REPO_ROOT / "server/server.py").read_text(encoding="utf-8")
    line = next(text for text in server.splitlines() if "Spec-Code Sync" in text)
    assert not PLAN_COMPARISON.search(line), line
    assert "not checked against the plan yet" in line


def test_uc_12204_the_spec_code_sync_section_says_what_it_lists():
    claude = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    section = claude.split("## Spec-Code Sync", 1)[1].split("\n## ", 1)[0]
    assert "The plan is not used yet" in section
    assert "Comparación no disponible" in section
    assert "UC-12601" in section
