"""UC-12207 — un proyecto nuevo nace con el control de discovery en «warn».

discovery/SKILL.md promete «warn» en proyectos nuevos y «off» en los que ya existían. Hasta
UC-12207 nadie escribía `specbox.discovery.gate_mode` y el hook valía «off» siempre.
"""
from __future__ import annotations

import json
from pathlib import Path

from server.tools.onboarding import (
    NEW_PROJECT_DISCOVERY_GATE_MODE,
    _generate_onboarding_files,
    build_onboard_local_settings,
)
from tests.test_pre_prd_discovery_check_hook import _run_hook

REPO_ROOT = Path(__file__).resolve().parent.parent
PRD_WITHOUT_DISCOVERY = {"tool_input": {"command": "/prd feature_sin_discovery"}}


def _settings(existing: str | None = None, **kwargs) -> dict:
    kwargs.setdefault("backend_type", "native")
    return json.loads(build_onboard_local_settings(existing, **kwargs))


def _project(tmp_path: Path, settings: dict | None) -> Path:
    project = tmp_path / "proyecto"
    (project / ".claude").mkdir(parents=True)
    if settings is not None:
        (project / ".claude/settings.local.json").write_text(json.dumps(settings), encoding="utf-8")
    return project


class TestOnboardWritesTheGate:
    """AC-01: onboard_project deja el control en «warn»."""

    def test_new_project_gets_warn_and_the_onboard_version(self):
        s = _settings(engine_version="6.35.0")
        assert NEW_PROJECT_DISCOVERY_GATE_MODE == "warn"
        assert s["specbox"]["discovery"]["gate_mode"] == "warn"
        assert s["specbox"]["engine_version_at_onboard"] == "6.35.0"
        assert s["specbox"]["backend_type"] == "native"
        assert s["specbox"]["autopilot"]["level"] == "equilibrado"

    def test_freeform_and_trello_keys_still_written(self):
        ff = _settings(backend_type="freeform", freeform_root="/abs/doc/tracking")
        assert ff["specbox"]["freeform_root_absolute"] == "/abs/doc/tracking"
        trello = _settings(backend_type="trello", board_id="b1")
        assert trello["specbox"]["trello_board_id"] == "b1"
        assert ff["specbox"]["discovery"]["gate_mode"] == "warn"

    def test_multirepo_satellite_settings_are_kept(self):
        existing = json.dumps({"multirepo": {"enabled": True, "role": "satellite"}, "boardId": "b"})
        s = _settings(existing)
        assert s["multirepo"] == {"enabled": True, "role": "satellite"}
        assert s["boardId"] == "b"
        assert s["specbox"]["discovery"]["gate_mode"] == "warn"

    def test_a_mode_already_written_is_never_overwritten(self):
        existing = json.dumps({"specbox": {"discovery": {"gate_mode": "block", "pedagogical_mode": "on"}}})
        s = _settings(existing)
        assert s["specbox"]["discovery"] == {"gate_mode": "block", "pedagogical_mode": "on"}

    def test_unreadable_content_starts_from_scratch(self):
        assert _settings("{no es json")["specbox"]["discovery"]["gate_mode"] == "warn"


class TestUpgradeLeavesExistingProjectsAlone:
    """AC-02: un proyecto que ya existía sigue en «off» tras actualizar."""

    def test_upgrade_files_do_not_include_settings_local(self):
        # upgrade_project regenera sus ficheros con _generate_onboarding_files.
        files, _dirs, _warnings = _generate_onboarding_files(REPO_ROOT, "proyecto", "python", [], "Prueba")
        assert ".claude/settings.local.json" not in files
        assert "CLAUDE.md" in files  # la generación funciona: solo falta lo que no debe estar

    def test_existing_project_without_the_key_stays_off(self, tmp_path):
        project = _project(tmp_path, {"specbox": {"backend_type": "native"}})
        rc, stdout, stderr = _run_hook(project, PRD_WITHOUT_DISCOVERY)
        assert (rc, stdout, stderr) == (0, "", "")
        assert not (project / ".quality/discovery_gate_events.jsonl").exists()


class TestFreshProjectWarnsOnce:
    """AC-03: con «warn», /prd sin discovery muestra el aviso una vez y sigue."""

    def test_onboarded_settings_warn_once_and_let_prd_continue(self, tmp_path):
        project = _project(tmp_path, _settings(engine_version="6.35.0"))
        rc, stdout, stderr = _run_hook(project, PRD_WITHOUT_DISCOVERY)
        assert rc == 0
        assert stderr == ""
        # Una sola salida JSON con una sola nota (título y cuerpo llevan la etiqueta del hook).
        assert stdout.count('"additionalContext"') == 1
        note = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        assert note.count("/prd sigue, pero falta el discovery") == 1
        assert "feature_sin_discovery" in note
        assert "gate_mode=warn" in note
        events = (project / ".quality/discovery_gate_events.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(events) == 1
        assert json.loads(events[0])["action"] == "warned"
