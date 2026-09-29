"""US-43/UC-4302 AC-01 — una versión con cambios de seguridad cuenta qué evita.

`.quality/scripts/changelog-security-check.mjs` es la comprobación del release: falla
si la entrada superior del CHANGELOG.md no tiene sección `### Security` cuando los
commits de la versión tocan seguridad, y también si esa sección menciona severidades,
incidentes, reportes o identificadores de vulnerabilidad (decisión del 2026-09-29: la
sección cuenta qué evita la versión, no de dónde vino).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".quality" / "scripts" / "changelog-security-check.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node no está disponible")

SECURITY_COMMIT = {
    "subject": "feat(US-39/UC-3902): los tokens anteriores a la caducidad caducan el 2026-12-28",
    "body": "",
    "files": ["server/db/migrations/0026_legacy_tokens_expire.sql"],
}
PLAIN_COMMIT = {
    "subject": "docs: aclara el paso 3 del quickstart",
    "body": "Sin cambios de comportamiento.\n\nCo-Authored-By: Alguien <x@y.z>",
    "files": ["docs/getting-started.md"],
}
SECTION_OK = "### Security\n\n- **Tokens sin caducidad**: los anteriores a esta versión caducan en 90 días.\n"


def _changelog(body: str) -> str:
    return (
        "# Changelog\n\n"
        '## [6.14.1] - 2026-09-29 — "Forward Only"\n\n'
        f"{body}\n\n"
        '## [6.14.0] - 2026-09-29 — "Front Door"\n\n### Added\n\n- algo anterior\n'
    )


def _run(tmp_path: Path, changelog: str, commits: list[dict]) -> tuple[int, dict, str]:
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    (tmp_path / "commits.json").write_text(json.dumps(commits), encoding="utf-8")
    proc = subprocess.run(
        ["node", str(SCRIPT), "--commits-json", "commits.json", "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, payload, proc.stderr


def test_security_change_with_section_passes(tmp_path):
    code, result, _ = _run(tmp_path, _changelog("### Added\n\n- x\n\n" + SECTION_OK), [SECURITY_COMMIT, PLAIN_COMMIT])
    assert code == 0, result
    assert result["section_present"] is True
    assert [c["subject"] for c in result["security_commits"]] == [SECURITY_COMMIT["subject"]]


def test_security_change_without_section_fails(tmp_path):
    code, result, stderr = _run(tmp_path, _changelog("### Added\n\n- x\n"), [SECURITY_COMMIT])
    assert code == 1
    assert 'no tiene una sección "### Security"' in result["problems"][0]
    assert "FAIL" in stderr


def test_no_security_change_needs_no_section(tmp_path):
    code, result, _ = _run(tmp_path, _changelog("### Fixed\n\n- una errata\n"), [PLAIN_COMMIT])
    assert code == 0
    assert result["security_commits"] == []
    assert result["section_present"] is False


def test_trailers_and_neutral_words_do_not_count_as_security(tmp_path):
    # "Co-Authored-By" contiene "Author", que no es autenticación ni autorización.
    commit = {"subject": "chore: renombra una variable", "body": "Co-Authored-By: X <x@y>", "files": ["server/models.py"]}
    code, result, _ = _run(tmp_path, _changelog("### Changed\n\n- nada\n"), [commit])
    assert code == 0
    assert result["security_commits"] == []


def test_sensitive_file_counts_even_with_a_neutral_message(tmp_path):
    commit = {"subject": "docs: actualiza un fichero", "body": "", "files": ["SECURITY.md"]}
    code, result, _ = _run(tmp_path, _changelog("### Changed\n\n- nada\n"), [commit])
    assert code == 1
    assert result["security_commits"][0]["reasons"] == ["fichero: SECURITY.md"]


def test_section_cannot_mention_severity_incident_or_report(tmp_path):
    bad = "### Security\n\n- Corrige una brecha crítica reportada por un tester (CVE-2026-0001).\n"
    code, result, _ = _run(tmp_path, _changelog(bad), [SECURITY_COMMIT])
    assert code == 1
    assert any("menciona" in p for p in result["problems"])


def test_empty_section_fails(tmp_path):
    code, result, _ = _run(tmp_path, _changelog("### Security\n\n### Tests\n\n- 3 pruebas\n"), [SECURITY_COMMIT])
    assert code == 1
    assert any("vacía" in p for p in result["problems"])


def test_the_published_changelog_passes_against_git_history():
    """El contrato vivo: la entrada superior del CHANGELOG.md real cumple la regla."""
    if shutil.which("git") is None:
        pytest.skip("git no está disponible")
    proc = subprocess.run(["node", str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, check=False)
    if proc.returncode == 2:
        pytest.skip(proc.stderr.strip())  # p. ej. clon sin la etiqueta de la versión anterior
    assert proc.returncode == 0, proc.stderr
