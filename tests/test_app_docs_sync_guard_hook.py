"""Subprocess-driven tests for the app-docs-sync-guard.mjs hook (PR-13).

The hook is a Node script meant to run as a Claude Code PostToolUse
trigger. We exercise it via `node` with a controlled CWD so the
behaviour matches what the harness will see in practice.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "app-docs-sync-guard.mjs"


def _run_hook(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(HOOK_PATH)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=15,
    )


def _seed_app_prd(path: Path, body: str = "Vision text") -> str:
    content = (
        "<!-- @specbox:zone start kind=\"manual\" id=\"vision\" -->\n"
        f"{body}\n"
        "<!-- @specbox:zone end -->\n"
    )
    path.write_text(content, encoding="utf-8")
    return content


def _write_lock(project_path: Path, prd_sig: str | None = None, spec_sig: str | None = None) -> None:
    lock_path = project_path / ".quality" / "app_docs_sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    sigs: dict = {}
    if prd_sig:
        sigs["app_prd"] = prd_sig
    if spec_sig:
        sigs["app_spec"] = spec_sig
    lock_path.write_text(json.dumps({"signatures": sigs}), encoding="utf-8")


def _expected_signature_via_python(content: str) -> str:
    """Compute the same signature the hook computes, using the Python
    parser as ground truth so any mismatch surfaces a JS↔Python parity bug."""
    from server.app_docs.zones import compute_signature, parse_document

    doc = parse_document(Path("<inline>"), content=content)
    return compute_signature(doc)


# ── Skip cases ───────────────────────────────────────────────────────


class TestSkipCases:
    def test_no_doc_app_returns_clean(self, tmp_path):
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert "WARNING" not in result.stdout
        assert "ERROR" not in result.stderr

    def test_no_lock_returns_clean(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_prd(app / "app_prd.md")
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert "WARNING" not in result.stdout

    def test_active_uc_defers_enforcement(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        content = _seed_app_prd(app / "app_prd.md")
        _write_lock(tmp_path, prd_sig="0" * 64)  # mismatch on purpose
        # active UC marker present → hook must skip
        active_path = tmp_path / ".quality" / "active_uc.json"
        active_path.parent.mkdir(parents=True, exist_ok=True)
        active_path.write_text(json.dumps({"uc_id": "UC-1", "feature": "demo"}))
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert "WARNING" not in result.stdout


# ── Drift detection ──────────────────────────────────────────────────


class TestDriftDetection:
    def test_matching_signature_clean(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        content = _seed_app_prd(app / "app_prd.md")
        sig = _expected_signature_via_python(content)
        _write_lock(tmp_path, prd_sig=sig)
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert "WARNING" not in result.stdout

    def test_drift_emits_warning_only_in_default_mode(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_prd(app / "app_prd.md")
        _write_lock(tmp_path, prd_sig="abcd" * 16)  # wrong signature
        result = _run_hook(tmp_path)
        assert result.returncode == 0  # warning-only does not block
        assert "WARNING" in result.stdout
        assert "drifted" in result.stdout
        # telemetry was written
        telemetry = tmp_path / ".quality" / "app_docs_drift.jsonl"
        assert telemetry.exists()
        entry = json.loads(telemetry.read_text().strip().splitlines()[0])
        assert entry["document"] == "app_prd"

    def test_drift_blocks_when_block_flag_set(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_prd(app / "app_prd.md")
        _write_lock(tmp_path, prd_sig="abcd" * 16)
        # Enable blocking via settings
        settings_dir = tmp_path / ".claude"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "settings.local.json").write_text(
            json.dumps({"specbox": {"app_docs_sync": {"block_on_drift": True}}})
        )
        result = _run_hook(tmp_path)
        assert result.returncode == 1
        assert "ERROR" in result.stderr
        assert "drifted" in result.stderr


# ── JS↔Python signature parity ───────────────────────────────────────


class TestSignatureParity:
    def test_js_and_python_compute_same_signature(self, tmp_path):
        """The hook's JS signature must equal the server's Python signature
        for the same content. Without parity, drift detection becomes
        non-deterministic across the language boundary."""
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        content = _seed_app_prd(app / "app_prd.md", body="Some content with multiple\nlines\nand markers")
        py_sig = _expected_signature_via_python(content)
        # Write that python sig as the lock — hook should report no drift.
        _write_lock(tmp_path, prd_sig=py_sig)
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert "WARNING" not in result.stdout, result.stdout
