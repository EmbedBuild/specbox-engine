"""Tests for the canonical decisions store (v5.29.0 PR-7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.app_docs.canonical import (
    DEFAULT_PROMOTION_THRESHOLD,
    get_canonical,
    invalidate_canonical,
    list_canonicals,
    record_confirmation,
    revoke_canonical,
)


def _store(project_path: Path) -> dict:
    p = project_path / ".quality" / "canonical_decisions.json"
    return json.loads(p.read_text()) if p.exists() else {"canonicals": [], "counters": []}


# ── record_confirmation: streak + promotion ─────────────────────────


class TestRecordConfirmation:
    def test_first_confirmation_starts_counter(self, tmp_path):
        result = record_confirmation("veg_mode_selection", "per_icp", project_path=tmp_path)
        assert result["promoted"] is False
        assert result["streak"] == 1
        assert result["canonical"] is None
        store = _store(tmp_path)
        assert len(store["counters"]) == 1
        assert store["counters"][0]["streak"] == 1

    def test_three_identical_promotes(self, tmp_path):
        for _ in range(DEFAULT_PROMOTION_THRESHOLD - 1):
            record_confirmation("veg_mode_selection", "per_icp", project_path=tmp_path)
        result = record_confirmation("veg_mode_selection", "per_icp", project_path=tmp_path)
        assert result["promoted"] is True
        assert result["canonical"]["decision_key"] == "veg_mode_selection"
        assert result["canonical"]["value"] == "per_icp"

    def test_different_value_resets_streak(self, tmp_path):
        record_confirmation("veg_mode_selection", "per_icp", project_path=tmp_path)
        record_confirmation("veg_mode_selection", "per_icp", project_path=tmp_path)
        result = record_confirmation("veg_mode_selection", "uniforme", project_path=tmp_path)
        assert result["promoted"] is False
        assert result["streak"] == 1

    def test_promotion_clears_counter(self, tmp_path):
        for _ in range(DEFAULT_PROMOTION_THRESHOLD):
            record_confirmation("tokens_confirmation", "auto", project_path=tmp_path)
        store = _store(tmp_path)
        assert len(store["counters"]) == 0
        assert len(store["canonicals"]) == 1


# ── get_canonical / list_canonicals ──────────────────────────────────


class TestRetrieve:
    def test_returns_none_when_no_canonical(self, tmp_path):
        assert get_canonical("veg_mode_selection", tmp_path) is None

    def test_returns_canonical_after_promotion(self, tmp_path):
        for _ in range(DEFAULT_PROMOTION_THRESHOLD):
            record_confirmation("veg_mode_selection", "per_icp", project_path=tmp_path)
        canonical = get_canonical("veg_mode_selection", tmp_path)
        assert canonical is not None
        assert canonical.value == "per_icp"

    def test_list_includes_invalidated(self, tmp_path):
        for _ in range(DEFAULT_PROMOTION_THRESHOLD):
            record_confirmation("veg_mode_selection", "per_icp", project_path=tmp_path)
        invalidate_canonical("veg_mode_selection", reason="test", project_path=tmp_path)
        all_entries = list_canonicals(tmp_path)
        assert len(all_entries) == 1
        assert all_entries[0]["invalidated_at"]


# ── Invalidation ─────────────────────────────────────────────────────


class TestInvalidation:
    def test_user_picks_different_value_invalidates_existing(self, tmp_path):
        for _ in range(DEFAULT_PROMOTION_THRESHOLD):
            record_confirmation("veg_mode_selection", "per_icp", project_path=tmp_path)
        # Now user picks differently — auto-invalidates and starts new counter.
        result = record_confirmation("veg_mode_selection", "uniforme", project_path=tmp_path)
        assert result["promoted"] is False
        assert get_canonical("veg_mode_selection", tmp_path) is None
        store = _store(tmp_path)
        invalidated = [c for c in store["canonicals"] if c.get("invalidated_at")]
        assert len(invalidated) == 1
        assert invalidated[0]["invalidation_reason"] == "user_chose_different_value"

    def test_invalidate_explicit(self, tmp_path):
        for _ in range(DEFAULT_PROMOTION_THRESHOLD):
            record_confirmation("veg_mode_selection", "per_icp", project_path=tmp_path)
        result = invalidate_canonical(
            "veg_mode_selection", reason="stack_changed", project_path=tmp_path
        )
        assert result["ok"] is True
        assert get_canonical("veg_mode_selection", tmp_path) is None

    def test_invalidate_when_no_canonical(self, tmp_path):
        result = invalidate_canonical("veg_mode_selection", reason="x", project_path=tmp_path)
        assert result["ok"] is False
        assert result["error"] == "no_active_canonical_for_key"


# ── Confirmations after canonical exists ─────────────────────────────


class TestPostPromotion:
    def test_same_value_bumps_confirmations(self, tmp_path):
        for _ in range(DEFAULT_PROMOTION_THRESHOLD):
            record_confirmation("tokens_confirmation", "auto", project_path=tmp_path)
        result = record_confirmation("tokens_confirmation", "auto", project_path=tmp_path)
        assert result["promoted"] is False
        assert result["canonical"]["confirmations"] == DEFAULT_PROMOTION_THRESHOLD + 1


# ── Revoke ───────────────────────────────────────────────────────────


class TestRevoke:
    def test_revokes_active_canonical(self, tmp_path):
        for _ in range(DEFAULT_PROMOTION_THRESHOLD):
            record_confirmation("veg_mode_selection", "per_icp", project_path=tmp_path)
        result = revoke_canonical("veg_mode_selection", tmp_path)
        assert result["ok"] is True
        assert get_canonical("veg_mode_selection", tmp_path) is None
        # Hard-revoke removes the entry entirely
        assert list_canonicals(tmp_path) == []

    def test_revoke_when_missing_returns_error(self, tmp_path):
        result = revoke_canonical("veg_mode_selection", tmp_path)
        assert result["ok"] is False


# ── Custom threshold ─────────────────────────────────────────────────


class TestCustomThreshold:
    def test_threshold_2_promotes_after_two(self, tmp_path):
        record_confirmation("tokens_confirmation", "auto", project_path=tmp_path, promotion_threshold=2)
        result = record_confirmation(
            "tokens_confirmation", "auto", project_path=tmp_path, promotion_threshold=2
        )
        assert result["promoted"] is True

    def test_threshold_5_does_not_promote_at_3(self, tmp_path):
        for _ in range(3):
            r = record_confirmation(
                "tokens_confirmation", "auto", project_path=tmp_path, promotion_threshold=5
            )
        assert r["promoted"] is False
        assert r["streak"] == 3
