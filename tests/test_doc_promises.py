"""La documentación del engine no promete lo que el código no hace (EP-20 · US-122).

La auditoría «SpecBox frente al SDD» (2026-11-18) halló promesas de la documentación que el
código no cumplía. Mientras el código no las cumpla, la documentación dice lo que pasa de
verdad, y estas pruebas impiden que la promesa vuelva a colarse.

- UC-12201: el Definition Quality Gate avisa; no bloquea (lo impondrá `start_uc`, UC-12301).
- UC-12202: spec-guard avisa después de escribir; solo bloquea en main o master.
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


def _doc_paragraphs() -> list[tuple[str, int, str]]:
    """(fichero, primera línea, texto) de cada párrafo: una afirmación puede partirse en líneas."""
    paragraphs: list[tuple[str, int, str]] = []
    current: list[str] = []
    start = 0
    previous = None
    for rel, number, line in DOC_LINES + [("", 0, "")]:
        if rel != previous or not line.strip():
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


# UC-12201 ─ el Definition Quality Gate es un aviso.
QUALITY_GATE = re.compile(
    r"definition quality gate|calidad de definici[oó]n|validate_ac_quality|\bAC vagos\b|\bvague AC\b",
    re.IGNORECASE,
)
# Afirmación de bloqueo en presente. «bloquear»/«bloqueará» (futuro, UC-12301) no cuentan.
BLOCKS_NOW = re.compile(r"\b(bloquea|bloqueante|blocks|blocking)\b", re.IGNORECASE)


def test_uc_12201_no_doc_says_the_quality_gate_blocks():
    offending = _offending(QUALITY_GATE, BLOCKS_NOW)
    assert offending == [], "El Definition Quality Gate avisa; no bloquea:\n" + "\n".join(offending)


def test_uc_12201_the_prd_skill_names_validate_ac_quality_as_the_measure():
    prd = (REPO_ROOT / ".claude/skills/prd/SKILL.md").read_text(encoding="utf-8")
    step = prd.split("## Paso 2.5:", 1)[1].split("\n## ", 1)[0]
    assert "(aviso)" in step.splitlines()[0]
    assert "La medida es `validate_ac_quality`" in step
    assert "validate_ac_quality: {passed}/{total}" in step, "el informe del Paso 2.5.7 muestra el resultado"


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
    assert "pending" in claude and "UC-12217" in claude, "la reserva perdida figura como pendiente"
    rules = _row("rules/GLOBAL_RULES.md", "spec-guard")
    assert "Despues de Write/Edit" in rules
    assert "main/master" in rules and "pendiente (UC-12217)" in rules
    assert "NOTA (UC)" in rules


def test_uc_12202_branch_guard_is_not_sold_as_blocking():
    assert "**BLOQUEANTE**" not in _row("rules/GLOBAL_RULES.md", "branch-guard")
