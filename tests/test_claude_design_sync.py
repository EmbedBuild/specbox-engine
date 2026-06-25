"""Tests for the Claude Design sync engine (US-29 · UC-2905).

Covers AC-01 (.design-sync/config.json prepared with projectId), AC-02
(idempotency via _ds_sync.json), AC-03 (localDir = gate site's dist/).
"""

from __future__ import annotations

import json
from pathlib import Path

from server.veg.claude_design_sync import (
    evaluate_sync,
    is_up_to_date,
    prepare_config,
    write_anchor,
    _fingerprint_dist,
)
from server.veg.design_system_gate import resolve_site


def _write_settings(repo: Path, multirepo: dict | None) -> None:
    claude = repo / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    data = {"multirepo": multirepo} if multirepo is not None else {}
    (claude / "settings.local.json").write_text(json.dumps(data), encoding="utf-8")


def _make_ds(repo: Path, files: dict[str, str] | None = None) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "package.json").write_text("{}", encoding="utf-8")
    dist = repo / "dist"
    dist.mkdir(exist_ok=True)
    for name, content in (files or {"index.js": "x"}).items():
        (dist / name).write_text(content, encoding="utf-8")


# --------------------------------------------------------------------------
# AC-01 — .design-sync/config.json prepared with the anchored projectId
# --------------------------------------------------------------------------

def test_prepare_config_writes_projectid_and_localdir(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)
    _make_ds(repo)
    site = resolve_site(repo)
    cfg = prepare_config(site, "uuid-1")
    assert cfg.exists()
    data = json.loads(cfg.read_text())
    assert data["projectId"] == "uuid-1"
    assert data["localDir"] == str(repo.resolve() / "dist")
    assert data["role"] == "monorepo"


def test_prepare_config_merges_existing(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)
    _make_ds(repo)
    cfgdir = repo / ".design-sync"
    cfgdir.mkdir()
    (cfgdir / "config.json").write_text(json.dumps({"custom": "keep"}))
    site = resolve_site(repo)
    prepare_config(site, "uuid-2")
    data = json.loads((cfgdir / "config.json").read_text())
    assert data["custom"] == "keep"
    assert data["projectId"] == "uuid-2"


def test_evaluate_sync_delegates_not_reimplements(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)
    _make_ds(repo)
    decision = evaluate_sync(repo, "uuid-1")
    assert decision.action == "sync"
    assert "design-sync" in decision.reason  # delegates to the skill
    assert decision.config_path is not None


# --------------------------------------------------------------------------
# AC-02 — idempotency via _ds_sync.json
# --------------------------------------------------------------------------

def test_second_sync_skips_when_anchor_matches(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)
    _make_ds(repo)
    # First sync prepares config; record the anchor as if it succeeded.
    first = evaluate_sync(repo, "uuid-1")
    assert first.action == "sync"
    fp = _fingerprint_dist(repo / "dist")
    write_anchor(repo.resolve(), fp, "uuid-1")
    # Second sync with unchanged dist/ must skip (no writes).
    second = evaluate_sync(repo, "uuid-1")
    assert second.action == "skip"
    assert "_ds_sync.json" in second.reason


def test_changed_dist_triggers_resync(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)
    _make_ds(repo)
    fp = _fingerprint_dist(repo / "dist")
    write_anchor(repo.resolve(), fp, "uuid-1")
    assert is_up_to_date(repo.resolve(), "uuid-1") is True
    # Mutate dist/ → fingerprint changes → not up to date.
    (repo / "dist" / "new.js").write_text("new", encoding="utf-8")
    assert is_up_to_date(repo.resolve(), "uuid-1") is False
    assert evaluate_sync(repo, "uuid-1").action == "sync"


def test_different_projectid_is_not_up_to_date(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)
    _make_ds(repo)
    fp = _fingerprint_dist(repo / "dist")
    write_anchor(repo.resolve(), fp, "uuid-1")
    # Same dist/ but a different anchored project ⇒ must re-sync.
    assert is_up_to_date(repo.resolve(), "uuid-OTHER") is False


# --------------------------------------------------------------------------
# AC-03 — localDir = the gate site's dist/ (orchestrator in multirepo)
# --------------------------------------------------------------------------

def test_sync_targets_orchestrator_dist_for_satellite(tmp_path: Path) -> None:
    orch = tmp_path / "orchestrator"
    sat = orch / "repositorios" / "salacal-web"
    _write_settings(orch, {"role": "orchestrator"})
    _make_ds(orch)  # design-system + dist/ live in the orchestrator
    _write_settings(sat, {"role": "satellite", "orchestrator": "../.."})

    decision = evaluate_sync(sat, "uuid-1")
    assert decision.action == "sync"
    # localDir must be the ORCHESTRATOR's dist/, not the satellite's.
    assert decision.local_dir == str(orch.resolve() / "dist")
    # config.json is written at the orchestrator (the site that owns the DS).
    assert decision.config_path == str(orch.resolve() / ".design-sync" / "config.json")


def test_sync_targets_repo_dist_for_monorepo(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)
    _make_ds(repo)
    decision = evaluate_sync(repo, "uuid-1")
    assert decision.local_dir == str(repo.resolve() / "dist")


def test_pending_when_no_design_system(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "package.json").write_text("{}", encoding="utf-8")  # no dist/
    decision = evaluate_sync(repo, "uuid-1")
    assert decision.action == "pending"
    assert "dist/" in decision.reason
