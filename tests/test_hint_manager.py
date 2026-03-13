"""Tests for the hint manager module (UC-005).

Validates:
- AC-21/AC-22: Hint texts exist for prd, implement, and other skills
- AC-23: Hints disappear after MAX_HINT_COUNT (3) uses
- AC-24: No hints if project has > 5 completed UCs
- AC-25: Hints don't require confirmation (tested implicitly by API design)
"""

import json
from pathlib import Path

import pytest

from src.hint_manager import (
    MAX_HINT_COUNT,
    COMPLETED_UC_THRESHOLD,
    get_hint_text,
    get_available_hints,
    should_show_hint,
    record_hint_shown,
    _read_counters,
    _write_counters,
    _count_completed_ucs,
)


@pytest.fixture
def demo_project(tmp_path: Path) -> Path:
    """Create a minimal project directory with .quality/ structure."""
    quality_dir = tmp_path / ".quality"
    quality_dir.mkdir()
    (quality_dir / "evidence").mkdir()
    return tmp_path


class TestGetHintText:
    """AC-21, AC-22: Hint texts exist for key skills."""

    def test_prd_hint_exists(self):
        text = get_hint_text("prd")
        assert text
        assert "PRD" in text
        assert "US" in text or "User Stor" in text
        assert "Quality Gate" in text or "quality" in text.lower()

    def test_implement_hint_exists(self):
        text = get_hint_text("implement")
        assert text
        assert "Orchestrator" in text or "autopilot" in text.lower()
        assert "GO/NO-GO" in text or "quality gate" in text.lower()

    def test_plan_hint_exists(self):
        text = get_hint_text("plan")
        assert text
        assert "plan" in text.lower()

    def test_unknown_skill_returns_empty(self):
        assert get_hint_text("nonexistent-skill") == ""

    def test_available_hints_includes_core_skills(self):
        hints = get_available_hints()
        assert "prd" in hints
        assert "implement" in hints
        assert "plan" in hints


class TestShouldShowHint:
    """AC-23, AC-24: Counter logic and UC threshold."""

    def test_shows_hint_for_new_project(self, demo_project: Path):
        """First time should show hint."""
        assert should_show_hint(str(demo_project), "prd") is True

    def test_shows_hint_up_to_max_count(self, demo_project: Path):
        """Hint shown MAX_HINT_COUNT times, then stops."""
        for i in range(MAX_HINT_COUNT):
            assert should_show_hint(str(demo_project), "prd") is True
            record_hint_shown(str(demo_project), "prd")

        # After MAX_HINT_COUNT, should not show
        assert should_show_hint(str(demo_project), "prd") is False

    def test_different_skills_have_separate_counters(self, demo_project: Path):
        """Each skill has its own counter."""
        record_hint_shown(str(demo_project), "prd")
        record_hint_shown(str(demo_project), "prd")
        record_hint_shown(str(demo_project), "prd")

        # prd exhausted, but implement should still show
        assert should_show_hint(str(demo_project), "prd") is False
        assert should_show_hint(str(demo_project), "implement") is True

    def test_no_hint_for_unknown_skill(self, demo_project: Path):
        """Skills without hint text never show hints."""
        assert should_show_hint(str(demo_project), "nonexistent") is False

    def test_no_hint_for_nonexistent_path(self):
        """Non-existent project path returns False."""
        assert should_show_hint("/nonexistent/path/xyz", "prd") is False

    def test_no_hint_when_many_completed_ucs(self, demo_project: Path):
        """AC-24: No hints if project has > 5 completed UCs."""
        evidence_dir = demo_project / ".quality" / "evidence"
        for i in range(COMPLETED_UC_THRESHOLD + 1):
            uc_dir = evidence_dir / f"UC-{i:03d}"
            uc_dir.mkdir()
            checkpoint = uc_dir / "checkpoint.json"
            checkpoint.write_text(json.dumps({
                "phase": 3,
                "status": "complete",
            }))

        assert should_show_hint(str(demo_project), "prd") is False

    def test_hint_shown_with_few_completed_ucs(self, demo_project: Path):
        """Hints still show when completed UCs <= threshold."""
        evidence_dir = demo_project / ".quality" / "evidence"
        for i in range(3):  # 3 < COMPLETED_UC_THRESHOLD
            uc_dir = evidence_dir / f"UC-{i:03d}"
            uc_dir.mkdir()
            checkpoint = uc_dir / "checkpoint.json"
            checkpoint.write_text(json.dumps({
                "phase": 3,
                "status": "complete",
            }))

        assert should_show_hint(str(demo_project), "prd") is True


class TestRecordHintShown:
    """Test counter persistence."""

    def test_counter_increments(self, demo_project: Path):
        counters = _read_counters(demo_project)
        assert counters.get("prd", 0) == 0

        record_hint_shown(str(demo_project), "prd")
        counters = _read_counters(demo_project)
        assert counters["prd"] == 1

        record_hint_shown(str(demo_project), "prd")
        counters = _read_counters(demo_project)
        assert counters["prd"] == 2

    def test_creates_quality_dir_if_missing(self, tmp_path: Path):
        """Should create .quality/ directory if it doesn't exist."""
        record_hint_shown(str(tmp_path), "prd")
        assert (tmp_path / ".quality" / "hint_counters.json").exists()

    def test_handles_corrupted_counters_file(self, demo_project: Path):
        """Should handle malformed JSON gracefully."""
        counters_file = demo_project / ".quality" / "hint_counters.json"
        counters_file.write_text("not valid json!!!")

        # Should not raise, returns empty
        counters = _read_counters(demo_project)
        assert counters == {}

        # Should still be able to write
        record_hint_shown(str(demo_project), "prd")
        counters = _read_counters(demo_project)
        assert counters["prd"] == 1


class TestCountCompletedUCs:
    """Test UC completion counting logic."""

    def test_no_evidence_dir(self, tmp_path: Path):
        assert _count_completed_ucs(tmp_path) == 0

    def test_counts_only_complete_status(self, demo_project: Path):
        evidence_dir = demo_project / ".quality" / "evidence"

        # Complete UC
        uc1 = evidence_dir / "UC-001"
        uc1.mkdir()
        (uc1 / "checkpoint.json").write_text(json.dumps({"status": "complete"}))

        # Failed UC (should not count)
        uc2 = evidence_dir / "UC-002"
        uc2.mkdir()
        (uc2 / "checkpoint.json").write_text(json.dumps({"status": "failed"}))

        # In-progress UC (should not count)
        uc3 = evidence_dir / "UC-003"
        uc3.mkdir()
        (uc3 / "checkpoint.json").write_text(json.dumps({"status": "in_progress"}))

        assert _count_completed_ucs(demo_project) == 1

    def test_ignores_directories_without_checkpoint(self, demo_project: Path):
        evidence_dir = demo_project / ".quality" / "evidence"
        uc1 = evidence_dir / "UC-001"
        uc1.mkdir()
        # No checkpoint.json

        assert _count_completed_ucs(demo_project) == 0
