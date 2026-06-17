"""Tests del parser de site_publish (UC-1601, US-16).

Cubren AC-01 (ENGINE_VERSION.yaml), AC-02 (CHANGELOG.md, verificado contra v6.11.0
"Self Update") y AC-03 (derivación determinista de public_highlights).
"""

from pathlib import Path

import pytest

from server.site_publish.parser import (
    build_engine_state,
    derive_public_highlights,
    parse_changelog_md,
    parse_engine_version,
)

ENGINE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def engine_version_text() -> str:
    return (ENGINE_ROOT / "ENGINE_VERSION.yaml").read_text(encoding="utf-8")


@pytest.fixture
def changelog_text() -> str:
    return (ENGINE_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-01 — ENGINE_VERSION.yaml
# ---------------------------------------------------------------------------

def test_parse_engine_version_release_fields(engine_version_text):
    state = parse_engine_version(engine_version_text)
    assert state.release.version == "6.11.0"
    assert state.release.codename == "Self Update"
    assert state.release.release_date == "2026-06-14"
    assert state.release.min_claude_code == "1.0.0"


def test_parse_engine_version_features_with_since(engine_version_text):
    state = parse_engine_version(engine_version_text)
    keys = {f.feature_key for f in state.features}
    # Features conocidas presentes.
    assert "agent-skills" in keys
    assert "multi-backend-abstraction" in keys
    by_key = {f.feature_key: f for f in state.features}
    # since_version derivado de los comentarios "# Existing/New (vX)".
    assert by_key["agent-skills"].since_version == "3.9.1"
    assert by_key["multi-backend-abstraction"].since_version == "4.1.0"


def test_parse_engine_version_stacks_services_pms(engine_version_text):
    state = parse_engine_version(engine_version_text)
    assert state.stacks.get("python") == "3.12+"
    assert "supabase" in state.services
    assert "trello" in state.project_managers
    assert "freeform" in state.project_managers


def test_parse_engine_version_handles_empty():
    state = parse_engine_version("")
    assert state.release.version == ""
    assert state.features == []


# ---------------------------------------------------------------------------
# AC-02 — CHANGELOG.md
# ---------------------------------------------------------------------------

def test_parse_changelog_latest_version(changelog_text):
    entries = parse_changelog_md(changelog_text)
    assert entries, "debe parsear al menos una versión"
    latest = entries[0]
    assert latest.version == "6.11.0"
    assert latest.codename == "Self Update"
    assert latest.release_date == "2026-06-14"
    # Tiene las secciones canónicas de Keep a Changelog.
    assert "Added" in latest.sections
    assert len(latest.sections["Added"]) >= 1


def test_parse_changelog_multiple_versions(changelog_text):
    entries = parse_changelog_md(changelog_text)
    versions = [e.version for e in entries]
    assert "6.11.0" in versions
    assert "6.10.2" in versions
    # Orden descendente: la más reciente primero (como el fichero).
    assert versions.index("6.11.0") < versions.index("6.10.2")


def test_changelog_items_are_plain_text(changelog_text):
    entries = parse_changelog_md(changelog_text)
    latest = entries[0]
    for item in latest.sections.get("Added", []):
        # Sin markdown de enlaces ni énfasis residual.
        assert "](" not in item
        assert "**" not in item


# ---------------------------------------------------------------------------
# AC-03 — public_highlights deterministas
# ---------------------------------------------------------------------------

def test_derive_highlights_deterministic(engine_version_text, changelog_text):
    md = parse_changelog_md(changelog_text)
    state = parse_engine_version(engine_version_text)
    a = derive_public_highlights("6.11.0", md, state.changelog)
    b = derive_public_highlights("6.11.0", md, state.changelog)
    assert a == b, "misma entrada -> misma salida"


def test_derive_highlights_count_and_length(engine_version_text, changelog_text):
    md = parse_changelog_md(changelog_text)
    state = parse_engine_version(engine_version_text)
    highlights = derive_public_highlights("6.11.0", md, state.changelog)
    assert 1 <= len(highlights) <= 4
    for h in highlights:
        assert h, "ningún highlight vacío"
        assert len(h) <= 180
        assert "](" not in h and "**" not in h
        # Sin prefijo de commit ni sufijo (UC-XXXX).
        assert not h.lower().startswith("feat:")
        assert not h.rstrip().endswith(")")  # heurística: no termina en (UC-...)


def test_build_engine_state_end_to_end(engine_version_text, changelog_text):
    state = build_engine_state(engine_version_text, changelog_text)
    assert state.release.version == "6.11.0"
    assert state.features
    # El changelog enriquecido tiene highlights para la versión actual.
    current = next((e for e in state.changelog if e.version == "6.11.0"), None)
    assert current is not None
    assert 1 <= len(current.public_highlights) <= 4


def test_build_engine_state_without_changelog_md(engine_version_text):
    # Sin CHANGELOG.md, los highlights caen al bloque changelog: del YAML.
    state = build_engine_state(engine_version_text, None)
    current = next((e for e in state.changelog if e.version == "6.11.0"), None)
    assert current is not None
    assert len(current.public_highlights) >= 1
