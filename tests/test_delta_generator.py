"""Tests for server/delta_generator.py — UC-001 Spec-Code Sync."""

import pytest

from src.delta_generator import generate_phase_delta, compile_uc_status


class TestGeneratePhaseDelta:
    """Test phase delta block generation."""

    def test_basic_complete_phase(self):
        """AC-01: Generates Markdown block with phase, files, deltas, decisions."""
        result = generate_phase_delta(
            phase_number=1,
            phase_name="DB Schema",
            phase_status="complete",
            files_created=["server/delta_generator.py"],
            files_modified=["server/server.py"],
            plan_files_expected=["server/delta_generator.py", "server/server.py"],
            decisions=["Separated delta logic into own module"],
        )
        assert "#### Fase 1: DB Schema" in result
        assert "**Estado:** complete" in result
        assert "`server/delta_generator.py`" in result
        assert "`server/server.py`" in result
        assert "Sin deltas — implementación conforme al plan" in result
        assert "Separated delta logic into own module" in result

    def test_no_changes_conforme_al_plan(self):
        """AC-03: When files match plan exactly → 'Sin deltas'."""
        result = generate_phase_delta(
            phase_number=2,
            phase_name="Feature Logic",
            phase_status="complete",
            files_created=["a.py"],
            files_modified=["b.py"],
            plan_files_expected=["a.py", "b.py"],
        )
        assert "Sin deltas — implementación conforme al plan" in result

    def test_with_deltas(self):
        """AC-01: When files differ from plan → shows deltas."""
        result = generate_phase_delta(
            phase_number=3,
            phase_name="UI",
            phase_status="complete",
            files_created=["a.py", "extra.py"],
            files_modified=[],
            plan_files_expected=["a.py"],
        )
        assert "Archivos adicionales" in result
        assert "`extra.py`" in result

    def test_no_plan_available(self):
        """When plan_files_expected is None → comparison not available."""
        result = generate_phase_delta(
            phase_number=1,
            phase_name="Feature",
            phase_status="complete",
            files_created=["a.py"],
        )
        assert "Comparación no disponible" in result

    def test_self_healing_event(self):
        """AC-04: Self-healing events are included."""
        result = generate_phase_delta(
            phase_number=2,
            phase_name="Feature",
            phase_status="needs_healing",
            healing_events=[{"type": "auto-fix", "resolved": True}],
        )
        assert "**Self-healing:** auto-fix — resuelto" in result

    def test_self_healing_unresolved(self):
        """AC-04: Unresolved healing shows 'no resuelto'."""
        result = generate_phase_delta(
            phase_number=2,
            phase_name="Feature",
            phase_status="needs_healing",
            healing_events=[{"type": "diagnóstico", "resolved": False}],
        )
        assert "diagnóstico — no resuelto" in result

    def test_failed_phase(self):
        """AC-05: Failed phase includes error summary."""
        result = generate_phase_delta(
            phase_number=4,
            phase_name="QA",
            phase_status="failed",
            error_summary="Test suite failed: 3 tests broken in auth module",
        )
        assert "**Estado:** failed" in result
        assert "**Error:** Test suite failed" in result

    def test_failed_phase_no_error(self):
        """AC-05: Failed phase without explicit error → default message."""
        result = generate_phase_delta(
            phase_number=4,
            phase_name="QA",
            phase_status="failed",
        )
        assert "Error no especificado" in result

    def test_error_truncation(self):
        """AC-05: Long errors are truncated."""
        long_error = "x" * 200
        result = generate_phase_delta(
            phase_number=1,
            phase_name="DB",
            phase_status="failed",
            error_summary=long_error,
        )
        assert "..." in result
        # The error field should not exceed MAX_ERROR_CHARS + "..."
        error_line = [l for l in result.split("\n") if "**Error:**" in l][0]
        error_content = error_line.split("**Error:** ")[1]
        assert len(error_content) <= 154  # 150 + "..."

    def test_token_budget_enforcement(self):
        """AC-02: Block stays within 500 token budget."""
        # Create a phase with many files to test truncation
        many_files = [f"file_{i}.py" for i in range(50)]
        result = generate_phase_delta(
            phase_number=1,
            phase_name="Feature",
            phase_status="complete",
            files_created=many_files,
            files_modified=many_files,
            decisions=[f"Decision {i}" for i in range(20)],
        )
        word_count = len(result.split())
        assert word_count <= 550  # Some tolerance for the truncation message

    def test_empty_files(self):
        """No files created or modified → 'ninguno'."""
        result = generate_phase_delta(
            phase_number=1,
            phase_name="Config",
            phase_status="complete",
        )
        assert "**Archivos creados:** ninguno" in result
        assert "**Archivos modificados:** ninguno" in result

    def test_file_list_truncation(self):
        """More than 10 files per category → truncated."""
        many_files = [f"file_{i}.py" for i in range(15)]
        result = generate_phase_delta(
            phase_number=1,
            phase_name="Feature",
            phase_status="complete",
            files_created=many_files,
        )
        assert "y 5 más" in result


class TestCompileUcStatus:
    """Test UC status compilation."""

    def test_basic_compilation(self):
        delta1 = generate_phase_delta(1, "DB", "complete", ["a.py"])
        delta2 = generate_phase_delta(2, "Feature", "complete", ["b.py"])
        result = compile_uc_status(
            "UC-001",
            "feature/sync",
            [delta1, delta2],
            timestamp="2026-03-15T14:32:00Z",
        )
        assert "### Implementation Status — UC-001" in result
        assert "**Timestamp:** 2026-03-15T14:32:00Z" in result
        assert "**Branch:** feature/sync" in result
        assert "Fase 1: DB" in result
        assert "Fase 2: Feature" in result

    def test_auto_timestamp(self):
        """Timestamp is auto-generated if not provided."""
        result = compile_uc_status("UC-002", "feature/x", [])
        assert "**Timestamp:** 20" in result  # Starts with year

    def test_empty_deltas(self):
        result = compile_uc_status("UC-003", "feature/x", [])
        assert "### Implementation Status — UC-003" in result
