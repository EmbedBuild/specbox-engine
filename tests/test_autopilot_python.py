"""Tests for the Python port of the autopilot policy engine (v5.29.0 PR-5).

Mirrors the invariants of `.claude/hooks/lib/autopilot.test.mjs` so any
divergence between the JS and Python implementations surfaces as a
failing test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.app_docs.autopilot import (
    DECISION_KEYS,
    VALID_TIERS,
    evaluate_and_log,
    evaluate_decision,
    load_autopilot_config,
    log_auto_decision,
)


# ── Fixtures ─────────────────────────────────────────────────────────


def _write_settings(project_path: Path, level: str | None, **extra) -> None:
    settings = project_path / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    if level is None and not extra:
        settings.write_text("{}", encoding="utf-8")
        return
    payload: dict = {"specbox": {"autopilot": {}}}
    if level is not None:
        payload["specbox"]["autopilot"]["level"] = level
    payload["specbox"]["autopilot"].update(extra)
    settings.write_text(json.dumps(payload), encoding="utf-8")


def _read_log(project_path: Path) -> list[dict]:
    log = project_path / ".quality" / "autopilot_decisions.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line]


# ── load_autopilot_config ────────────────────────────────────────────


class TestLoadAutopilotConfig:
    def test_returns_low_when_no_settings(self, tmp_path):
        cfg = load_autopilot_config(tmp_path)
        assert cfg["level"] == "low"
        assert cfg["image_budget_eur_per_feature"] == 5
        assert cfg["auto_confirm_overrides"] == []
        assert cfg["always_ask_overrides"] == []
        assert cfg["queue_enabled"] is False

    def test_honors_explicit_level(self, tmp_path):
        _write_settings(tmp_path, "equilibrado")
        assert load_autopilot_config(tmp_path)["level"] == "equilibrado"

    def test_falls_back_on_invalid_level(self, tmp_path):
        _write_settings(tmp_path, "chaotic")
        assert load_autopilot_config(tmp_path)["level"] == "low"

    def test_reads_custom_budget(self, tmp_path):
        _write_settings(tmp_path, "equilibrado", image_budget_eur_per_feature=12)
        assert load_autopilot_config(tmp_path)["image_budget_eur_per_feature"] == 12

    def test_reads_overrides(self, tmp_path):
        _write_settings(
            tmp_path,
            "equilibrado",
            auto_confirm_overrides=["veg_preview"],
            always_ask_overrides=["tokens_confirmation"],
        )
        cfg = load_autopilot_config(tmp_path)
        assert cfg["auto_confirm_overrides"] == ["veg_preview"]
        assert cfg["always_ask_overrides"] == ["tokens_confirmation"]


# ── evaluate_decision: tier defaults ─────────────────────────────────


class TestTierDefaults:
    def test_low_asks_cosmetic(self, tmp_path):
        result = evaluate_decision("tokens_confirmation", {"projectPath": str(tmp_path)})
        assert result["action"] == "ask"
        assert result["autoConfirm"] is False

    def test_equilibrado_auto_confirms_cosmetic(self, tmp_path):
        _write_settings(tmp_path, "equilibrado")
        result = evaluate_decision("tokens_confirmation", {"projectPath": str(tmp_path)})
        assert result["autoConfirm"] is True
        assert result["action"] == "auto"

    def test_conservador_asks_visual_derived(self, tmp_path):
        _write_settings(tmp_path, "conservador")
        result = evaluate_decision("veg_preview", {"projectPath": str(tmp_path), "score": 0.95})
        assert result["autoConfirm"] is False


# ── Score thresholds ─────────────────────────────────────────────────


class TestScoreThresholds:
    def test_equilibrado_auto_when_score_ge_threshold(self, tmp_path):
        _write_settings(tmp_path, "equilibrado")
        result = evaluate_decision("veg_preview", {"projectPath": str(tmp_path), "score": 0.85})
        assert result["autoConfirm"] is True

    def test_equilibrado_asks_below_threshold(self, tmp_path):
        _write_settings(tmp_path, "equilibrado")
        result = evaluate_decision("veg_preview", {"projectPath": str(tmp_path), "score": 0.7})
        assert result["autoConfirm"] is False

    def test_agresivo_lower_threshold(self, tmp_path):
        _write_settings(tmp_path, "agresivo")
        assert evaluate_decision("veg_preview", {"projectPath": str(tmp_path), "score": 0.75})["autoConfirm"] is True
        assert evaluate_decision("veg_preview", {"projectPath": str(tmp_path), "score": 0.65})["autoConfirm"] is False

    def test_missing_score_forces_ask(self, tmp_path):
        _write_settings(tmp_path, "equilibrado")
        result = evaluate_decision("veg_preview", {"projectPath": str(tmp_path)})
        assert result["autoConfirm"] is False
        assert result["reason"] == "missing_score_or_threshold"


# ── Inviolable rules ─────────────────────────────────────────────────


class TestInviolableRules:
    @pytest.mark.parametrize("level", VALID_TIERS)
    def test_image_cost_over_budget_always_asks(self, tmp_path, level):
        _write_settings(tmp_path, level)
        result = evaluate_decision("image_cost_over_budget", {"projectPath": str(tmp_path)})
        assert result["autoConfirm"] is False
        assert result["reason"] == "inviolable_rule"

    @pytest.mark.parametrize("level", VALID_TIERS)
    def test_destructive_action_always_asks(self, tmp_path, level):
        _write_settings(tmp_path, level)
        result = evaluate_decision("destructive_action", {"projectPath": str(tmp_path)})
        assert result["autoConfirm"] is False
        assert result["reason"] == "inviolable_rule"

    @pytest.mark.parametrize("level", VALID_TIERS)
    def test_branch_to_main_push_blocks(self, tmp_path, level):
        _write_settings(tmp_path, level)
        result = evaluate_decision("branch_to_main_push", {"projectPath": str(tmp_path)})
        assert result["action"] == "block"

    def test_inviolable_cannot_be_bypassed_by_override(self, tmp_path):
        _write_settings(tmp_path, "agresivo", auto_confirm_overrides=["image_cost_over_budget"])
        result = evaluate_decision("image_cost_over_budget", {"projectPath": str(tmp_path)})
        assert result["autoConfirm"] is False, "override must not beat inviolable"


# ── User overrides ──────────────────────────────────────────────────


class TestUserOverrides:
    def test_always_ask_forces_ask(self, tmp_path):
        _write_settings(tmp_path, "agresivo", always_ask_overrides=["tokens_confirmation"])
        result = evaluate_decision("tokens_confirmation", {"projectPath": str(tmp_path)})
        assert result["autoConfirm"] is False
        assert result["reason"] == "user_override_always_ask"

    def test_auto_confirm_forces_auto_for_non_inviolable(self, tmp_path):
        _write_settings(tmp_path, "low", auto_confirm_overrides=["veg_preview"])
        result = evaluate_decision("veg_preview", {"projectPath": str(tmp_path)})
        assert result["autoConfirm"] is True
        assert result["reason"] == "user_override_auto_confirm"

    def test_always_ask_wins_when_both_present(self, tmp_path):
        _write_settings(
            tmp_path,
            "agresivo",
            auto_confirm_overrides=["veg_preview"],
            always_ask_overrides=["veg_preview"],
        )
        result = evaluate_decision("veg_preview", {"projectPath": str(tmp_path)})
        assert result["autoConfirm"] is False


# ── App PRD/spec inheritance ─────────────────────────────────────────


class TestAppDocsInheritance:
    def test_aesthetic_auto_when_app_spec_present(self, tmp_path):
        _write_settings(tmp_path, "equilibrado")
        result = evaluate_decision(
            "feature_aesthetic_direction", {"projectPath": str(tmp_path), "hasAppSpec": True}
        )
        assert result["autoConfirm"] is True

    def test_aesthetic_asks_when_app_spec_missing(self, tmp_path):
        _write_settings(tmp_path, "equilibrado")
        result = evaluate_decision(
            "feature_aesthetic_direction", {"projectPath": str(tmp_path), "hasAppSpec": False}
        )
        assert result["autoConfirm"] is False


# ── Backend selection ───────────────────────────────────────────────


class TestBackendSelection:
    def test_equilibrado_defaults_to_freeform(self, tmp_path):
        _write_settings(tmp_path, "equilibrado")
        result = evaluate_decision("backend_selection", {"projectPath": str(tmp_path)})
        assert result["autoConfirm"] is True
        assert result["reason"] == "freeform_default_v5_29"

    @pytest.mark.parametrize("level", ["low", "conservador"])
    def test_low_and_conservador_ask(self, tmp_path, level):
        _write_settings(tmp_path, level)
        result = evaluate_decision("backend_selection", {"projectPath": str(tmp_path)})
        assert result["autoConfirm"] is False


# ── Logging ──────────────────────────────────────────────────────────


class TestLogging:
    def test_log_writes_jsonl_entry(self, tmp_path):
        _write_settings(tmp_path, "equilibrado")
        decision = evaluate_decision("tokens_confirmation", {"projectPath": str(tmp_path)})
        log_auto_decision(decision, project_path=tmp_path, feature="demo", value="derived")

        entries = _read_log(tmp_path)
        assert len(entries) == 1
        assert entries[0]["decision_key"] == "tokens_confirmation"
        assert entries[0]["level"] == "equilibrado"
        assert entries[0]["auto_confirm"] is True
        assert entries[0]["feature"] == "demo"
        assert entries[0]["value"] == "derived"
        assert entries[0]["ts"]

    def test_evaluate_and_log_only_writes_on_auto(self, tmp_path):
        _write_settings(tmp_path, "equilibrado")
        evaluate_and_log("tokens_confirmation", {"projectPath": str(tmp_path)})
        evaluate_and_log("image_cost_over_budget", {"projectPath": str(tmp_path)})

        entries = _read_log(tmp_path)
        assert len(entries) == 1
        assert entries[0]["decision_key"] == "tokens_confirmation"


# ── Catalog completeness ─────────────────────────────────────────────


class TestCatalogCompleteness:
    def test_every_decision_has_all_tiers(self):
        for key, definition in DECISION_KEYS.items():
            for tier in VALID_TIERS:
                assert tier in definition["tiers"], f"{key} missing tier {tier}"

    def test_inviolable_decisions_only_ask_or_block(self):
        for key, definition in DECISION_KEYS.items():
            if not definition.get("inviolable"):
                continue
            for tier in VALID_TIERS:
                assert definition["tiers"][tier] in {"ask", "block"}, (
                    f"{key} at {tier} is {definition['tiers'][tier]} (must be ask/block)"
                )


# ── Cross-language parity ────────────────────────────────────────────


class TestParityWithJsCatalog:
    """Sanity: the Python catalog must match the JS catalog key set."""

    def test_decision_keys_match_js_constants(self):
        # Read the JS file textually and scan for the 19 known keys.
        repo_root = Path(__file__).resolve().parent.parent
        js = (repo_root / ".claude" / "hooks" / "lib" / "autopilot.mjs").read_text()
        for key in DECISION_KEYS:
            assert f"{key}:" in js, (
                f"{key} present in Python catalog but missing in autopilot.mjs"
            )
