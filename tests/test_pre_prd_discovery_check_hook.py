"""Tests for the pre-prd-discovery-check hook (UC-D003).

Runs the Node.js hook as a subprocess with different gate modes and
verifies exit codes + behavior.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / ".claude/hooks/pre-prd-discovery-check.mjs"


def _run_hook(project_dir: Path, stdin_payload: dict | None) -> tuple[int, str, str]:
    """Run the hook in project_dir; return (rc, stdout, stderr)."""
    stdin_str = json.dumps(stdin_payload) if stdin_payload is not None else ""
    result = subprocess.run(
        ["node", str(HOOK_PATH)],
        cwd=str(project_dir),
        input=stdin_str,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture
def project_with_settings(tmp_path: Path):
    """Factory for projects with a given gate_mode."""

    def _make(gate_mode: str) -> Path:
        project = tmp_path / f"project_{gate_mode}"
        project.mkdir()
        (project / ".claude").mkdir()
        settings = {"specbox": {"discovery": {"gate_mode": gate_mode}}}
        (project / ".claude/settings.local.json").write_text(
            json.dumps(settings, indent=2), encoding="utf-8"
        )
        return project

    return _make


# ─── Gate mode behavior ──────────────────────────────────────────────


class TestGateMode:
    def test_off_mode_exits_0_silently(self, project_with_settings):
        project = project_with_settings("off")
        rc, stdout, stderr = _run_hook(
            project, {"tool_input": {"command": "/prd new_feature"}}
        )
        assert rc == 0
        assert stdout == ""
        assert stderr == ""

    def test_warn_mode_exits_0_with_warning_when_missing(
        self, project_with_settings
    ):
        project = project_with_settings("warn")
        rc, stdout, stderr = _run_hook(
            project, {"tool_input": {"command": "/prd new_feature"}}
        )
        assert rc == 0  # warn doesn't block
        # Output goes to stderr via printWarning
        combined = stdout + stderr
        assert "WARNING" in combined or "WARNED" in combined
        assert "new_feature" in combined
        assert "/discovery" in combined  # the suggestion

    def test_block_mode_exits_1_when_missing(self, project_with_settings):
        project = project_with_settings("block")
        rc, stdout, stderr = _run_hook(
            project, {"tool_input": {"command": "/prd new_feature"}}
        )
        assert rc == 1
        combined = stdout + stderr
        assert "BLOCKED" in combined
        assert "new_feature" in combined

    def test_default_off_when_no_settings(self, tmp_path: Path):
        """Project with no settings.local.json should default to gate_mode=off."""
        project = tmp_path / "no_settings"
        project.mkdir()
        rc, _, _ = _run_hook(
            project, {"tool_input": {"command": "/prd new_feature"}}
        )
        assert rc == 0


# ─── Feature name extraction ─────────────────────────────────────────


class TestFeatureNameExtraction:
    def test_spec_driven_us_id_bypasses_check(self, project_with_settings):
        """`/prd US-01` is Trello/Plane spec-driven mode → skip Discovery."""
        project = project_with_settings("block")
        rc, stdout, stderr = _run_hook(
            project, {"tool_input": {"command": "/prd US-01"}}
        )
        # Bypass: exits 0 even though gate=block
        assert rc == 0
        # No warning emitted
        assert (stdout + stderr).strip() == ""

    def test_spec_driven_uc_id_bypasses_check(self, project_with_settings):
        project = project_with_settings("block")
        rc, _, _ = _run_hook(project, {"tool_input": {"command": "/prd UC-123"}})
        assert rc == 0

    def test_spec_driven_board_id_bypasses_check(self, project_with_settings):
        project = project_with_settings("block")
        rc, _, _ = _run_hook(
            project, {"tool_input": {"command": "/prd board:xyz789"}}
        )
        assert rc == 0

    def test_no_feature_name_in_input_exits_0(self, project_with_settings):
        """If we can't extract feature_name, don't block."""
        project = project_with_settings("block")
        rc, _, _ = _run_hook(project, {"tool_input": {"command": "/prd"}})
        assert rc == 0

    def test_invalid_feature_name_chars_treated_as_unextractable(
        self, project_with_settings
    ):
        """Names with spaces or special chars → can't extract → no block."""
        project = project_with_settings("block")
        rc, _, _ = _run_hook(
            project,
            {"tool_input": {"command": '/prd "has spaces"'}},
        )
        # Either bypasses or treats as unextractable; either way doesn't block
        # cleanly extracted names.
        assert rc == 0


# ─── Happy path: artifact exists and is READY_FOR_PRD ───────────────


class TestHappyPath:
    def test_complete_artifact_bypasses_block(self, project_with_settings):
        """If icp_jtbd.md exists AND validates as READY_FOR_PRD → /prd proceeds."""
        project = project_with_settings("block")
        # Write a minimally-complete artifact
        feature_dir = project / "doc/discovery/ready_feature"
        feature_dir.mkdir(parents=True)
        artifact_content = """# Discovery: ready_feature

## ICPs involucrados

### ICP-1: Real ICP name with content here.

## JTBDs racionales

- JR-F1.1: Cuando X, quiero Y, para Z. Real content.

## JTBDs emocionales

- JE-F1.1: Real emotional content here.

## Validation evidence

- Type: waiver. Real waiver justification here.

## Drift from app_market

- Resolución: no drift detected

## Verdict

READY_FOR_PRD
"""
        (feature_dir / "icp_jtbd.md").write_text(artifact_content, encoding="utf-8")

        # The hook runs the Python validator as subprocess; ensure the
        # cwd has access to the engine modules (we add the engine repo to
        # PYTHONPATH via env). For this test, since the hook tries to
        # import `server.tools.discovery`, we set PYTHONPATH to REPO_ROOT.
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

        result = subprocess.run(
            ["node", str(HOOK_PATH)],
            cwd=str(project),
            input=json.dumps({"tool_input": {"command": "/prd ready_feature"}}),
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        # Either passes (exit 0) because validator confirmed READY,
        # or falls back to existence check (exit 0 because artifact exists).
        # Both outcomes count as "don't block the happy path".
        assert result.returncode == 0


# ─── Telemetry ───────────────────────────────────────────────────────


class TestTelemetry:
    def test_event_recorded_on_block(self, project_with_settings):
        project = project_with_settings("block")
        _run_hook(project, {"tool_input": {"command": "/prd test_telemetry"}})

        telemetry_path = project / ".quality/discovery_gate_events.jsonl"
        assert telemetry_path.exists()
        lines = telemetry_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["type"] == "discovery_gate"
        assert entry["feature_name"] == "test_telemetry"
        assert entry["gate_mode"] == "block"
        assert entry["action"] == "blocked"
        assert "detected_at" in entry

    def test_event_recorded_on_warn(self, project_with_settings):
        project = project_with_settings("warn")
        _run_hook(project, {"tool_input": {"command": "/prd test_warn_telemetry"}})

        telemetry_path = project / ".quality/discovery_gate_events.jsonl"
        assert telemetry_path.exists()
        entry = json.loads(telemetry_path.read_text(encoding="utf-8").strip().splitlines()[0])
        assert entry["action"] == "warned"
        assert entry["gate_mode"] == "warn"

    def test_no_telemetry_in_off_mode(self, project_with_settings):
        project = project_with_settings("off")
        _run_hook(project, {"tool_input": {"command": "/prd test_off"}})
        telemetry_path = project / ".quality/discovery_gate_events.jsonl"
        # In "off" mode the hook exits before writing telemetry
        assert not telemetry_path.exists()
