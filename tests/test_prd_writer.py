"""Tests for server/prd_writer.py — UC-002 Spec-Code Sync."""

import pytest
from pathlib import Path

from src.prd_writer import find_prd_path, append_implementation_status


@pytest.fixture
def project_dir(tmp_path):
    """Create a temporary project directory with a PRD."""
    prds_dir = tmp_path / "doc" / "prds"
    prds_dir.mkdir(parents=True)
    prd_file = prds_dir / "v5.0_self_evolution_prd.md"
    prd_file.write_text(
        "# PRD: My Feature\n\n## 2. User Stories\n\n### US-01: Something\n\nContent here.\n",
        encoding="utf-8",
    )
    return tmp_path


class TestFindPrdPath:
    """Test PRD file location."""

    def test_find_by_feature_name(self, tmp_path):
        prds_dir = tmp_path / "doc" / "prds"
        prds_dir.mkdir(parents=True)
        prd = prds_dir / "my_feature_prd.md"
        prd.write_text("# PRD", encoding="utf-8")
        result = find_prd_path(tmp_path, feature="my_feature")
        assert result == prd

    def test_find_by_us_id(self, tmp_path):
        prds_dir = tmp_path / "doc" / "prds"
        prds_dir.mkdir(parents=True)
        prd = prds_dir / "us_01_prd.md"
        prd.write_text("# PRD", encoding="utf-8")
        result = find_prd_path(tmp_path, us_id="US-01")
        assert result == prd

    def test_find_single_file(self, project_dir):
        """Single PRD in doc/prds/ is found automatically."""
        result = find_prd_path(project_dir)
        assert result is not None
        assert result.name == "v5.0_self_evolution_prd.md"

    def test_find_legacy_format(self, tmp_path):
        prd_dir = tmp_path / "doc" / "prd"
        prd_dir.mkdir(parents=True)
        prd = prd_dir / "my_feature.md"
        prd.write_text("# PRD", encoding="utf-8")
        result = find_prd_path(tmp_path, feature="my_feature")
        assert result == prd

    def test_not_found(self, tmp_path):
        result = find_prd_path(tmp_path, feature="nonexistent")
        assert result is None

    def test_multiple_files_no_match(self, tmp_path):
        """Multiple PRDs without feature/us_id match → None."""
        prds_dir = tmp_path / "doc" / "prds"
        prds_dir.mkdir(parents=True)
        (prds_dir / "a.md").write_text("# A", encoding="utf-8")
        (prds_dir / "b.md").write_text("# B", encoding="utf-8")
        result = find_prd_path(tmp_path)
        assert result is None


class TestAppendImplementationStatus:
    """Test PRD append-only writing."""

    def test_append_first_status(self, project_dir):
        """AC-06: First Implementation Status creates the section."""
        prd = find_prd_path(project_dir)
        deltas = ["#### Fase 1: DB\n- **Estado:** complete"]
        result = append_implementation_status(prd, "UC-001", "feature/sync", deltas)
        assert result is True

        content = prd.read_text(encoding="utf-8")
        assert "## Implementation Status" in content
        assert "### Implementation Status — UC-001" in content
        assert "**Branch:** feature/sync" in content

    def test_append_only(self, project_dir):
        """AC-07: Existing content is never modified."""
        prd = find_prd_path(project_dir)
        original_content = prd.read_text(encoding="utf-8")
        deltas = ["#### Fase 1: DB\n- **Estado:** complete"]
        append_implementation_status(prd, "UC-001", "feature/sync", deltas)

        content = prd.read_text(encoding="utf-8")
        # Original content must be preserved at the start
        assert content.startswith(original_content.rstrip())

    def test_append_second_uc(self, project_dir):
        """AC-08: Second UC added chronologically after first."""
        prd = find_prd_path(project_dir)
        deltas1 = ["#### Fase 1: DB\n- **Estado:** complete"]
        deltas2 = ["#### Fase 1: Feature\n- **Estado:** complete"]

        append_implementation_status(prd, "UC-001", "feature/sync", deltas1)
        append_implementation_status(prd, "UC-002", "feature/sync", deltas2)

        content = prd.read_text(encoding="utf-8")
        pos1 = content.index("UC-001")
        pos2 = content.index("UC-002")
        assert pos1 < pos2  # Chronological order

    def test_includes_timestamp_and_branch(self, project_dir):
        """AC-10: Timestamp ISO 8601 and branch are included."""
        prd = find_prd_path(project_dir)
        deltas = ["#### Fase 1: DB\n- **Estado:** complete"]
        append_implementation_status(
            prd, "UC-001", "feature/spec-code-sync", deltas,
            timestamp="2026-03-15T14:32:00Z",
        )

        content = prd.read_text(encoding="utf-8")
        assert "2026-03-15T14:32:00Z" in content
        assert "feature/spec-code-sync" in content

    def test_nonexistent_prd(self, tmp_path):
        """Graceful failure for missing PRD."""
        fake_path = tmp_path / "nonexistent.md"
        result = append_implementation_status(fake_path, "UC-001", "main", [])
        assert result is False
