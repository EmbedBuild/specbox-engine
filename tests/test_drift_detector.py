"""Tests for the multi-source drift detector (v5.29.0 PR-15)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.app_docs.drift_detector import (
    heartbeat_payload,
    run_drift_detection,
)


def _seed_app_spec(path: Path, *, stack: str = "", brand_ref: str = "", canonicals_zone: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stack_body = stack or "## 1. Stack\n(autoinferido)"
    brand_body = brand_ref or "## 3. Brand\nVEG arquetipo: Startup"
    canonicals_body = canonicals_zone or "## 6. Decisiones canónicas\n<!-- engine-entries-below -->"
    path.write_text(
        f"<!-- @specbox:zone start kind=\"auto\" id=\"stack\" -->\n{stack_body}\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"auto\" id=\"tracking_backend\" -->\n## 2.\n<!-- @specbox:zone end -->\n"
        f"<!-- @specbox:zone start kind=\"manual\" id=\"brand_visual\" -->\n{brand_body}\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"conventions\" -->\nc\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"auto\" id=\"autopilot\" -->\n## 5.\n<!-- @specbox:zone end -->\n"
        f"<!-- @specbox:zone start kind=\"hybrid\" id=\"canonical_decisions\" -->\n{canonicals_body}\n<!-- @specbox:zone end -->\n",
        encoding="utf-8",
    )


def _seed_app_prd(path: Path, *, roadmap: str = "## 5. Roadmap\n(empty)") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "<!-- @specbox:zone start kind=\"manual\" id=\"vision\" -->\nv\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"audience\" -->\na\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"scope\" -->\ns\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"hybrid\" id=\"success_metrics\" -->\nm\n<!-- @specbox:zone end -->\n"
        f"<!-- @specbox:zone start kind=\"auto\" id=\"roadmap\" -->\n{roadmap}\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"stakeholders\" -->\np\n<!-- @specbox:zone end -->\n",
        encoding="utf-8",
    )


# ── Empty project ────────────────────────────────────────────────────


class TestNoDrift:
    def test_empty_project_returns_in_sync(self, tmp_path):
        report = run_drift_detection(tmp_path)
        assert report["in_sync"] is True
        assert report["signal_count"] == 0


# ── S1 — Stack drift ─────────────────────────────────────────────────


class TestStackDrift:
    def test_lockfile_present_but_undeclared_emits_warning(self, tmp_path):
        _seed_app_spec(tmp_path / "doc" / "app" / "app_spec.md", stack="## 1. Stack\nFlutter declared")
        (tmp_path / "package-lock.json").write_text("{}")
        report = run_drift_detection(tmp_path)
        codes = [s["code"] for s in report["signals"]]
        assert "S1" in codes
        assert any("package-lock.json" in s["message"] for s in report["signals"])

    def test_lockfile_mentioned_explicitly_no_signal(self, tmp_path):
        _seed_app_spec(tmp_path / "doc" / "app" / "app_spec.md", stack="## 1. Stack\nNode.js (package-lock.json)")
        (tmp_path / "package-lock.json").write_text("{}")
        report = run_drift_detection(tmp_path)
        codes = [s["code"] for s in report["signals"]]
        assert "S1" not in codes


# ── S2 — Brand kit dangling reference ───────────────────────────────


class TestBrandKitDrift:
    def test_dangling_reference_detected(self, tmp_path):
        _seed_app_spec(
            tmp_path / "doc" / "app" / "app_spec.md",
            brand_ref="## 3. Brand\nBrand kit: `doc/design/brand_kit.md`",
        )
        report = run_drift_detection(tmp_path)
        codes = [s["code"] for s in report["signals"]]
        assert "S2" in codes

    def test_existing_reference_no_signal(self, tmp_path):
        kit_path = tmp_path / "doc" / "design" / "brand_kit.md"
        kit_path.parent.mkdir(parents=True, exist_ok=True)
        kit_path.write_text("# Brand Kit\n")
        _seed_app_spec(
            tmp_path / "doc" / "app" / "app_spec.md",
            brand_ref="## 3. Brand\nBrand kit: `doc/design/brand_kit.md`",
        )
        report = run_drift_detection(tmp_path)
        codes = [s["code"] for s in report["signals"]]
        assert "S2" not in codes


# ── S3 — Roadmap vs tracking mismatch (FreeForm) ─────────────────────


class TestRoadmapDrift:
    def test_us_marked_done_in_prd_but_no_uc_done(self, tmp_path):
        _seed_app_prd(
            tmp_path / "doc" / "app" / "app_prd.md",
            roadmap="## 5. Roadmap\n\n| US | Title | State | UCs | Updated |\n"
            "|----|-------|-------|-----|---------|\n| US-99 | Demo | done | 3 | 2026-05-02 |",
        )
        # Tracking has no UCs done for US-99.
        items_path = tmp_path / "doc" / "tracking" / "items.json"
        items_path.parent.mkdir(parents=True, exist_ok=True)
        items_path.write_text(json.dumps([
            {"id": "1", "name": "UC-001", "state": "in_progress", "meta": {"us_id": "US-99"}}
        ]))
        report = run_drift_detection(tmp_path)
        codes = [s["code"] for s in report["signals"]]
        assert "S3" in codes

    def test_us_done_with_matching_uc_done_no_signal(self, tmp_path):
        _seed_app_prd(
            tmp_path / "doc" / "app" / "app_prd.md",
            roadmap="## 5. Roadmap\n\n| US | Title | State | UCs | Updated |\n"
            "|----|-------|-------|-----|---------|\n| US-01 | Demo | done | 1 | 2026-05-02 |",
        )
        items_path = tmp_path / "doc" / "tracking" / "items.json"
        items_path.parent.mkdir(parents=True, exist_ok=True)
        items_path.write_text(json.dumps([
            {"id": "1", "name": "UC-001", "state": "done", "meta": {"us_id": "US-01"}}
        ]))
        report = run_drift_detection(tmp_path)
        codes = [s["code"] for s in report["signals"]]
        assert "S3" not in codes


# ── S4 — Canonical decision undocumented ────────────────────────────


class TestCanonicalDrift:
    def test_active_canonical_missing_from_zone(self, tmp_path):
        _seed_app_spec(
            tmp_path / "doc" / "app" / "app_spec.md",
            canonicals_zone="## 6. Decisiones canónicas\n<!-- engine-entries-below -->",
        )
        canon = tmp_path / ".quality" / "canonical_decisions.json"
        canon.parent.mkdir(parents=True, exist_ok=True)
        canon.write_text(json.dumps({
            "canonicals": [
                {
                    "decision_key": "veg_mode_selection",
                    "value": "per_icp",
                    "promoted_at": "2026-05-02",
                    "confirmations": 3,
                    "last_seen": "2026-05-02",
                    "invalidated_at": None,
                }
            ],
            "counters": [],
        }))
        report = run_drift_detection(tmp_path)
        codes = [s["code"] for s in report["signals"]]
        assert "S4" in codes

    def test_documented_canonical_no_signal(self, tmp_path):
        _seed_app_spec(
            tmp_path / "doc" / "app" / "app_spec.md",
            canonicals_zone="## 6. Decisiones canónicas\n- veg_mode_selection = per_icp",
        )
        canon = tmp_path / ".quality" / "canonical_decisions.json"
        canon.parent.mkdir(parents=True, exist_ok=True)
        canon.write_text(json.dumps({
            "canonicals": [
                {
                    "decision_key": "veg_mode_selection",
                    "value": "per_icp",
                    "promoted_at": "2026-05-02",
                    "confirmations": 3,
                    "last_seen": "2026-05-02",
                    "invalidated_at": None,
                }
            ],
            "counters": [],
        }))
        report = run_drift_detection(tmp_path)
        codes = [s["code"] for s in report["signals"]]
        assert "S4" not in codes


# ── Telemetry + heartbeat ───────────────────────────────────────────


class TestTelemetry:
    def test_signals_appended_to_jsonl(self, tmp_path):
        _seed_app_spec(tmp_path / "doc" / "app" / "app_spec.md", stack="## 1. Stack\nFlutter")
        (tmp_path / "package-lock.json").write_text("{}")
        run_drift_detection(tmp_path)
        log = tmp_path / ".quality" / "app_docs_drift.jsonl"
        assert log.exists()
        first_line = log.read_text().splitlines()[0]
        entry = json.loads(first_line)
        assert entry["code"] == "S1"

    def test_no_signals_no_log(self, tmp_path):
        run_drift_detection(tmp_path)
        log = tmp_path / ".quality" / "app_docs_drift.jsonl"
        assert not log.exists()

    def test_heartbeat_payload_compact(self, tmp_path):
        _seed_app_spec(tmp_path / "doc" / "app" / "app_spec.md", stack="## 1. Stack\nFlutter")
        (tmp_path / "package-lock.json").write_text("{}")
        payload = heartbeat_payload(tmp_path)
        assert "in_sync" in payload
        assert "signal_count" in payload
        assert "summary_by_code" in payload
        assert payload["summary_by_code"]["S1"] == 1
