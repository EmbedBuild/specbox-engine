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


DESIGN_COMMIT = {
    "subject": "feat(US-49/UC-4901): las herramientas de diseño leen el sistema, no un brand kit aparte",
    "body": "Cuando un proyecto tiene tokens del sistema (design-system.tokens.json), son la única fuente.",
    "files": ["server/design_system/tokens.py"],
}


def test_design_tokens_alone_are_not_a_security_change(tmp_path):
    """US-57/UC-5703 AC-01 — en un mensaje sobre diseño, «tokens» son valores de diseño."""
    code, result, _ = _run(tmp_path, _changelog("### Added\n\n- x\n"), [DESIGN_COMMIT])
    assert code == 0, result
    assert result["security_commits"] == []


def test_bare_token_still_counts_without_design_context(tmp_path):
    commit = {"subject": "fix(cli): el ayudante guarda el token en el Llavero", "body": "", "files": ["packages/x.mjs"]}
    code, result, _ = _run(tmp_path, _changelog("### Fixed\n\n- x\n"), [commit])
    assert code == 1
    assert result["security_commits"][0]["reasons"] == ["mensaje: «token»"]


def test_design_commit_touching_a_sensitive_file_still_counts(tmp_path):
    commit = {**DESIGN_COMMIT, "files": ["vscode-extension/src/oauth.ts"]}
    code, result, _ = _run(tmp_path, _changelog("### Added\n\n- x\n"), [commit])
    assert code == 1
    assert result["security_commits"][0]["reasons"] == ["fichero: vscode-extension/src/oauth.ts"]


@pytest.mark.parametrize(
    "phrase",
    ["token de acceso", "access token", "mcp_token", "dev_token", "Bearer", "service_role", "API key"],
)
def test_access_tokens_always_count_even_in_a_design_message(tmp_path, phrase):
    """US-57/UC-5703 AC-02."""
    commit = {**DESIGN_COMMIT, "body": f"Los tokens del sistema de diseño y, además, el {phrase} de la sesión."}
    code, result, _ = _run(tmp_path, _changelog("### Added\n\n- x\n"), [commit])
    assert code == 1
    assert result["security_commits"][0]["reasons"] == [f"mensaje: «{phrase}»"]


def test_release_6_15_0_flags_only_its_real_security_commits():
    """US-57/UC-5703 AC-01 sobre la historia real: los commits de «Tinta» no son de seguridad."""
    if shutil.which("git") is None:
        pytest.skip("git no está disponible")
    for tag in ("v6.14.2", "v6.15.0"):
        found = subprocess.run(["git", "rev-parse", "-q", "--verify", f"{tag}^{{commit}}"], cwd=ROOT, capture_output=True, check=False)
        if found.returncode != 0:
            pytest.skip(f"clon sin la etiqueta {tag}")
    script = (
        f"import {{ commitsFromGit, classifyCommit }} from {json.dumps(SCRIPT.as_uri())};"
        "const commits = commitsFromGit('v6.14.2..v6.15.0', process.cwd());"
        "console.log(JSON.stringify(commits.filter((c) => classifyCommit(c).length).map((c) => c.subject)));"
    )
    proc = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
    flagged = {subject.rsplit("(#", 1)[-1].rstrip(")") for subject in json.loads(proc.stdout)}
    assert flagged == {"181", "174"}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
         "-c", "tag.gpgsign=false", *args],
        cwd=repo, check=True, capture_output=True,
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="git no está disponible")
def test_a_tagged_version_ends_at_its_tag_and_an_untagged_one_at_head(tmp_path):
    """US-121: un commit de seguridad posterior a la etiqueta es de la versión siguiente."""
    _git(tmp_path, "init", "-q")
    (tmp_path / "CHANGELOG.md").write_text(_changelog("### Fixed\n\n- una errata\n"), encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "release: v6.14.0")
    _git(tmp_path, "tag", "v6.14.0")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "docs: aclara el paso 3 del quickstart")
    (tmp_path / "notas.md").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "fix: los tokens de acceso caducan a los 90 días")

    def run() -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True, check=False)

    # Sin etiqueta v6.14.1 el commit de seguridad es de la 6.14.1 y su entrada no lo cuenta.
    untagged = run()
    assert untagged.returncode == 1, untagged.stderr
    assert "(v6.14.0..HEAD)" in untagged.stderr

    # Con la 6.14.1 ya etiquetada antes de ese commit, ese commit es de la siguiente.
    _git(tmp_path, "tag", "v6.14.1", "HEAD~1")
    tagged = run()
    assert tagged.returncode == 0, tagged.stderr
    assert "(v6.14.0..v6.14.1)" in tagged.stderr


def test_the_published_changelog_passes_against_git_history():
    """El contrato vivo: la entrada superior del CHANGELOG.md real cumple la regla."""
    if shutil.which("git") is None:
        pytest.skip("git no está disponible")
    proc = subprocess.run(["node", str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, check=False)
    if proc.returncode == 2:
        pytest.skip(proc.stderr.strip())  # p. ej. clon sin la etiqueta de la versión anterior
    assert proc.returncode == 0, proc.stderr
