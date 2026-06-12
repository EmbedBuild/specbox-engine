"""UC-404 tests: transactional switch_backend (AC-12 coherent, AC-13 rollback).

AC-12: after a switch, the three sources of truth — registry (projects.json),
app_spec.md tracking_backend zone, settings.local.json specbox.backend_type —
are all coherent, and ``detect_backend`` reports the new backend.

AC-13: if writing any of the three places fails (here we inject a
settings_writer that raises), the already-written places are rolled back and a
TransactionalSwitchError naming the failing place is raised, leaving the project
on its original backend.

Everything runs against tmp_path: STATE_PATH is monkeypatched for the registry,
and a minimal app_spec.md with the tracking_backend auto-zone is written into
the project tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.app_docs.discovery import detect_backend
from server.migration import transactional_switch as ts
from server.migration.transactional_switch import (
    TransactionalSwitchError,
    apply_switch_transactional,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures: a tmp project (registry + app_spec + settings) on freeform
# ═══════════════════════════════════════════════════════════════════════


_APP_SPEC = """# App Spec — demo

<!-- @specbox:zone start kind="auto" id="tracking_backend" auto_sync_on="set_auth_token" -->
## 2. Tracking backend

- **Tipo:** freeform
- **Path absoluto:** /tmp/demo/doc/tracking
- **Reporting externo:** no

> Esta zona la mantiene el engine.
<!-- @specbox:zone end -->
"""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Build a tmp project on freeform and point STATE_PATH at it.

    Returns (project_path, state_path, project_slug).
    """
    project_path = tmp_path / "proj"
    project_path.mkdir()

    # app_spec.md with the tracking_backend zone.
    app_dir = project_path / "doc" / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "app_spec.md").write_text(_APP_SPEC, encoding="utf-8")

    # settings.local.json on freeform.
    claude_dir = project_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.local.json").write_text(
        json.dumps({"specbox": {"backend_type": "freeform"}}, indent=2),
        encoding="utf-8",
    )

    # registry projects.json on freeform.
    state_path = tmp_path / "state"
    state_path.mkdir()
    slug = "demo"
    (state_path / "projects.json").write_text(
        json.dumps(
            {"projects": {slug: {"spec_backend": "freeform", "board_id": "ff-1"}}},
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("STATE_PATH", str(state_path))

    return project_path, state_path, slug


# ═══════════════════════════════════════════════════════════════════════
# AC-12 — the three places are coherent after the switch
# ═══════════════════════════════════════════════════════════════════════


def test_switch_updates_all_three_places(project) -> None:
    project_path, state_path, slug = project

    outcome = apply_switch_transactional(
        project_slug=slug,
        new_backend="native",
        new_board_id="proj-native-1",
        project_path=str(project_path),
        state_path=str(state_path),
    )

    assert outcome["updated"] == ["registry", "app_spec", "settings"]

    # 1. Registry.
    registry = json.loads((state_path / "projects.json").read_text())
    entry = registry["projects"][slug]
    assert entry["spec_backend"] == "native"
    assert entry["board_id"] == "proj-native-1"
    assert entry["backend_history"][-1]["backend"] == "freeform"

    # 2. settings.local.json.
    settings = json.loads((project_path / ".claude" / "settings.local.json").read_text())
    assert settings["specbox"]["backend_type"] == "native"

    # 3. app_spec.md tracking_backend zone.
    spec = (project_path / "doc" / "app" / "app_spec.md").read_text()
    assert "- **Tipo:** native" in spec
    assert "- **Native project id:** proj-native-1" in spec


def test_detect_backend_reports_new_backend_after_switch(project) -> None:
    """AC-12: detect_backend resolves to the new backend (settings level-1)."""
    project_path, state_path, slug = project

    apply_switch_transactional(
        project_slug=slug,
        new_backend="native",
        new_board_id="proj-native-1",
        project_path=str(project_path),
        state_path=str(state_path),
    )

    detected = detect_backend(str(project_path))
    assert detected["backend_type"] == "native"
    assert detected["source"] == "settings_specbox"


def test_switch_to_plane_renders_plane_id(project) -> None:
    project_path, state_path, slug = project

    apply_switch_transactional(
        project_slug=slug,
        new_backend="plane",
        new_board_id="plane-proj-9",
        project_path=str(project_path),
        state_path=str(state_path),
    )
    spec = (project_path / "doc" / "app" / "app_spec.md").read_text()
    assert "- **Tipo:** plane" in spec
    assert "- **Plane project id:** plane-proj-9" in spec


# ═══════════════════════════════════════════════════════════════════════
# AC-13 — rollback on failure of any place
# ═══════════════════════════════════════════════════════════════════════


def test_settings_failure_rolls_back_registry_and_app_spec(project) -> None:
    """AC-13: a failing settings write rolls back registry + app_spec."""
    project_path, state_path, slug = project

    registry_before = (state_path / "projects.json").read_text()
    spec_before = (project_path / "doc" / "app" / "app_spec.md").read_text()
    settings_before = (project_path / ".claude" / "settings.local.json").read_text()

    def _boom() -> None:
        raise RuntimeError("disk full writing settings")

    with pytest.raises(TransactionalSwitchError) as exc_info:
        apply_switch_transactional(
            project_slug=slug,
            new_backend="native",
            new_board_id="proj-native-1",
            project_path=str(project_path),
            state_path=str(state_path),
            settings_writer=_boom,
        )

    err = exc_info.value
    assert err.place == "settings"
    # registry and app_spec were applied then rolled back.
    assert set(err.rolled_back) == {"registry", "app_spec"}

    # All three files are byte-for-byte back to their pre-switch state.
    assert (state_path / "projects.json").read_text() == registry_before
    assert (project_path / "doc" / "app" / "app_spec.md").read_text() == spec_before
    assert (project_path / ".claude" / "settings.local.json").read_text() == settings_before


def test_rollback_leaves_project_on_original_backend(project) -> None:
    """AC-13: after rollback, detect_backend still reports the original."""
    project_path, state_path, slug = project

    def _boom() -> None:
        raise RuntimeError("settings write failed")

    with pytest.raises(TransactionalSwitchError):
        apply_switch_transactional(
            project_slug=slug,
            new_backend="native",
            new_board_id="proj-native-1",
            project_path=str(project_path),
            state_path=str(state_path),
            settings_writer=_boom,
        )

    detected = detect_backend(str(project_path))
    assert detected["backend_type"] == "freeform"

    registry = json.loads((state_path / "projects.json").read_text())
    assert registry["projects"][slug]["spec_backend"] == "freeform"


def test_app_spec_failure_rolls_back_registry_only(project) -> None:
    """AC-13: a failure on the 2nd place rolls back only the 1st (registry)."""
    project_path, state_path, slug = project
    registry_before = (state_path / "projects.json").read_text()

    def _boom() -> None:
        raise RuntimeError("app_spec write failed")

    with pytest.raises(TransactionalSwitchError) as exc_info:
        apply_switch_transactional(
            project_slug=slug,
            new_backend="native",
            new_board_id="proj-native-1",
            project_path=str(project_path),
            state_path=str(state_path),
            app_spec_writer=_boom,
        )

    err = exc_info.value
    assert err.place == "app_spec"
    assert err.rolled_back == ["registry"]
    assert (state_path / "projects.json").read_text() == registry_before


# ═══════════════════════════════════════════════════════════════════════
# Helper-level edge cases (snapshots, restore branches, missing files)
# ═══════════════════════════════════════════════════════════════════════


def test_switch_to_freeform_defaults_root_and_renders(project) -> None:
    """Freeform target without an explicit root falls back to <project>/doc/tracking."""
    project_path, state_path, slug = project

    apply_switch_transactional(
        project_slug=slug,
        new_backend="trello",
        new_board_id="b1",
        project_path=str(project_path),
        state_path=str(state_path),
    )
    # Now switch back to freeform with no freeform_root_absolute → default path.
    apply_switch_transactional(
        project_slug=slug,
        new_backend="freeform",
        new_board_id="ff-2",
        project_path=str(project_path),
        state_path=str(state_path),
    )
    spec = (project_path / "doc" / "app" / "app_spec.md").read_text()
    assert "- **Tipo:** freeform" in spec
    assert str(project_path / "doc" / "tracking") in spec


def test_registry_snapshot_absent_when_no_registry(tmp_path: Path) -> None:
    snap = ts._read_registry_snapshot("nope", str(tmp_path / "missing"))
    assert snap == {"present": False, "entry": None, "file_present": False}


def test_write_registry_raises_when_registry_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ts._write_registry("demo", "native", "x", str(tmp_path / "missing"))


def test_write_registry_raises_when_project_absent(tmp_path: Path) -> None:
    sp = tmp_path / "state"
    sp.mkdir()
    (sp / "projects.json").write_text(json.dumps({"projects": {}}))
    with pytest.raises(KeyError):
        ts._write_registry("ghost", "native", "x", str(sp))


def test_restore_registry_deletes_when_snapshot_absent(tmp_path: Path) -> None:
    sp = tmp_path / "state"
    sp.mkdir()
    (sp / "projects.json").write_text(json.dumps({"projects": {"demo": {"spec_backend": "x"}}}))
    ts._restore_registry("demo", {"present": False, "entry": None}, str(sp))
    registry = json.loads((sp / "projects.json").read_text())
    assert "demo" not in registry["projects"]


def test_restore_registry_noop_when_registry_missing(tmp_path: Path) -> None:
    # No file → restore is a silent no-op (does not raise).
    ts._restore_registry("demo", {"present": True, "entry": {}}, str(tmp_path / "missing"))


def test_settings_writer_creates_specbox_when_absent(tmp_path: Path) -> None:
    project_path = tmp_path / "p"
    (project_path / ".claude").mkdir(parents=True)
    (project_path / ".claude" / "settings.local.json").write_text(json.dumps({"other": 1}))
    ts._write_settings(str(project_path), "native")
    settings = json.loads((project_path / ".claude" / "settings.local.json").read_text())
    assert settings["specbox"]["backend_type"] == "native"
    assert settings["other"] == 1


def test_settings_writer_creates_file_when_absent(tmp_path: Path) -> None:
    project_path = tmp_path / "p"
    project_path.mkdir()
    ts._write_settings(str(project_path), "plane")
    settings = json.loads((project_path / ".claude" / "settings.local.json").read_text())
    assert settings["specbox"]["backend_type"] == "plane"


def test_settings_writer_handles_corrupt_json(tmp_path: Path) -> None:
    project_path = tmp_path / "p"
    (project_path / ".claude").mkdir(parents=True)
    (project_path / ".claude" / "settings.local.json").write_text("{not json")
    ts._write_settings(str(project_path), "native")
    settings = json.loads((project_path / ".claude" / "settings.local.json").read_text())
    assert settings["specbox"]["backend_type"] == "native"


def test_restore_settings_deletes_when_was_absent(tmp_path: Path) -> None:
    project_path = tmp_path / "p"
    (project_path / ".claude").mkdir(parents=True)
    sp = project_path / ".claude" / "settings.local.json"
    sp.write_text("{}")
    ts._restore_settings(str(project_path), {"present": False, "content": None})
    assert not sp.exists()


def test_restore_app_spec_deletes_when_was_absent(tmp_path: Path) -> None:
    project_path = tmp_path / "p"
    app = project_path / "doc" / "app"
    app.mkdir(parents=True)
    spec = app / "app_spec.md"
    spec.write_text("x")
    ts._restore_app_spec(str(project_path), {"present": False, "content": None})
    assert not spec.exists()


def test_write_app_spec_noop_when_doc_absent(tmp_path: Path) -> None:
    """No app_spec.md → sync reports skipped but ok=True, so no error raised."""
    project_path = tmp_path / "p"
    project_path.mkdir()
    # Should not raise even though the document does not exist.
    ts._write_app_spec("native", "x", str(project_path), None)


def test_switch_no_app_spec_still_updates_registry_and_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project without canonical docs still switches registry + settings."""
    project_path = tmp_path / "p"
    (project_path / ".claude").mkdir(parents=True)
    (project_path / ".claude" / "settings.local.json").write_text(json.dumps({"specbox": {"backend_type": "freeform"}}))
    sp = tmp_path / "state"
    sp.mkdir()
    (sp / "projects.json").write_text(
        json.dumps({"projects": {"demo": {"spec_backend": "freeform", "board_id": "ff"}}})
    )
    monkeypatch.setenv("STATE_PATH", str(sp))

    outcome = apply_switch_transactional(
        project_slug="demo",
        new_backend="native",
        new_board_id="n1",
        project_path=str(project_path),
        state_path=str(sp),
    )
    assert outcome["updated"] == ["registry", "app_spec", "settings"]
    settings = json.loads((project_path / ".claude" / "settings.local.json").read_text())
    assert settings["specbox"]["backend_type"] == "native"


def test_rollback_best_effort_when_restorer_also_fails(project, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing restorer during rollback is logged, not raised (lines 306-307)."""
    project_path, state_path, slug = project

    def _settings_boom() -> None:
        raise RuntimeError("settings write failed")

    def _restore_boom(*_a, **_k) -> None:
        raise RuntimeError("rollback failed too")

    # Make the app_spec restorer blow up during rollback.
    monkeypatch.setattr(ts, "_restore_app_spec", _restore_boom)

    with pytest.raises(TransactionalSwitchError) as exc_info:
        apply_switch_transactional(
            project_slug=slug,
            new_backend="native",
            new_board_id="n1",
            project_path=str(project_path),
            state_path=str(state_path),
            settings_writer=_settings_boom,
        )
    # The original failing place is still surfaced despite the rollback hiccup.
    assert exc_info.value.place == "settings"
