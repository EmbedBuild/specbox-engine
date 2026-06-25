"""Tests for the design-system precondition gate (US-29 · UC-2903).

Covers AC-01 (orchestrator anchor), AC-02 (satellite consumes orchestrator),
AC-03 (monorepo), AC-04 (compiled detection), AC-05 (not-ready ⇒ reason, no
raise).
"""

from __future__ import annotations

import json
from pathlib import Path

from server.veg.design_system_gate import evaluate_gate, resolve_site


def _write_settings(repo: Path, multirepo: dict | None) -> None:
    claude = repo / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    data = {}
    if multirepo is not None:
        data["multirepo"] = multirepo
    (claude / "settings.local.json").write_text(json.dumps(data), encoding="utf-8")


def _make_compiled_ds(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "package.json").write_text('{"name":"ds"}', encoding="utf-8")
    (repo / "dist").mkdir(exist_ok=True)


# --------------------------------------------------------------------------
# AC-01 — orchestrator: site is the orchestrator itself
# --------------------------------------------------------------------------

def test_orchestrator_resolves_site_to_itself(tmp_path: Path) -> None:
    orch = tmp_path / "orchestrator"
    _write_settings(orch, {"role": "orchestrator"})
    res = resolve_site(orch)
    assert res.role == "orchestrator"
    assert res.site_path == orch.resolve()
    assert res.consumes_from_orchestrator is False
    assert res.anchor_settings_path == orch.resolve() / ".claude" / "settings.local.json"


# --------------------------------------------------------------------------
# AC-02 — satellite consumes the orchestrator (nested ../.. layout)
# --------------------------------------------------------------------------

def test_satellite_resolves_site_to_orchestrator(tmp_path: Path) -> None:
    # Nested layout: <orch>/repositorios/<satellite>, orchestrator = "../.."
    orch = tmp_path / "orchestrator"
    sat = orch / "repositorios" / "salacal-web"
    _write_settings(orch, {"role": "orchestrator"})
    _write_settings(sat, {"role": "satellite", "orchestrator": "../.."})

    res = resolve_site(sat)
    assert res.role == "satellite"
    # Site must be the orchestrator, NOT the satellite.
    assert res.site_path == orch.resolve()
    assert res.site_path != sat.resolve()
    assert res.consumes_from_orchestrator is True
    # The projectId anchors in the orchestrator's settings.
    assert res.anchor_settings_path == orch.resolve() / ".claude" / "settings.local.json"


def test_satellite_without_orchestrator_field_falls_back_to_self(tmp_path: Path) -> None:
    sat = tmp_path / "sat"
    _write_settings(sat, {"role": "satellite"})  # no "orchestrator" key
    res = resolve_site(sat)
    assert res.role == "satellite"
    assert res.site_path == sat.resolve()


# --------------------------------------------------------------------------
# AC-03 — monorepo: site is the repo itself
# --------------------------------------------------------------------------

def test_monorepo_no_multirepo_block(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)  # settings without multirepo
    res = resolve_site(repo)
    assert res.role == "monorepo"
    assert res.site_path == repo.resolve()
    assert res.consumes_from_orchestrator is False


def test_monorepo_no_settings_file(tmp_path: Path) -> None:
    repo = tmp_path / "bare"
    repo.mkdir()
    res = resolve_site(repo)
    assert res.role == "monorepo"
    assert res.site_path == repo.resolve()


# --------------------------------------------------------------------------
# AC-04 — compiled design-system detection at the resolved site
# --------------------------------------------------------------------------

def test_gate_ready_when_package_and_dist_present(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)
    _make_compiled_ds(repo)
    gate, site = evaluate_gate(repo)
    assert gate.ready is True
    assert gate.reason == ""
    assert site.role == "monorepo"


def test_gate_ready_with_storybook_instead_of_dist(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "package.json").write_text("{}", encoding="utf-8")
    (repo / ".storybook").mkdir()
    gate, _ = evaluate_gate(repo)
    assert gate.ready is True


def test_gate_not_ready_when_dist_missing(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "package.json").write_text("{}", encoding="utf-8")
    # no dist/, no storybook
    gate, _ = evaluate_gate(repo)
    assert gate.ready is False
    assert "dist/" in gate.reason


def test_gate_not_ready_when_package_missing(tmp_path: Path) -> None:
    repo = tmp_path / "mono"
    _write_settings(repo, None)
    gate, _ = evaluate_gate(repo)
    assert gate.ready is False
    assert "package.json" in gate.reason


# --------------------------------------------------------------------------
# AC-05 — not-ready yields a legible reason and never raises
# --------------------------------------------------------------------------

def test_gate_evaluates_at_orchestrator_site_for_satellite(tmp_path: Path) -> None:
    # The compiled design-system lives in the orchestrator; the satellite has
    # none of its own. The gate must evaluate the ORCHESTRATOR, so it's ready.
    orch = tmp_path / "orchestrator"
    sat = orch / "repositorios" / "salacal-web"
    _write_settings(orch, {"role": "orchestrator"})
    _make_compiled_ds(orch)
    _write_settings(sat, {"role": "satellite", "orchestrator": "../.."})
    sat.mkdir(parents=True, exist_ok=True)  # satellite has no dist/

    gate, site = evaluate_gate(sat)
    assert site.site_path == orch.resolve()
    assert gate.ready is True  # because the orchestrator has the design-system


def test_gate_never_raises_and_reason_is_legible(tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()
    # Must not raise even with nothing present.
    gate, _ = evaluate_gate(repo)
    assert gate.ready is False
    assert isinstance(gate.reason, str) and gate.reason
