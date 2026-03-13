"""Tests for server/prd_parser.py — UC-003 Spec-Code Sync."""

import pytest

from src.prd_parser import parse_implementation_status, UCImplementationStatus


SAMPLE_PRD = """# PRD: Test Feature

## 2. User Stories

### US-01: Something

Content here.

---

## Implementation Status

### Implementation Status — UC-001
**Timestamp:** 2026-03-15T14:32:00Z
**Branch:** feature/spec-code-sync

#### Fase 1: DB Schema
- **Estado:** complete
- **Archivos creados:** `server/delta_generator.py`
- **Archivos modificados:** ninguno
- **Deltas vs plan:** Sin deltas — implementación conforme al plan
- **Decisiones:** ninguna

#### Fase 2: Feature Logic
- **Estado:** complete
- **Archivos creados:** `server/prd_writer.py`
- **Archivos modificados:** `server/server.py`, `server/tools/spec_driven.py`
- **Deltas vs plan:** Archivos adicionales: `server/prd_writer.py`
- **Decisiones:** Módulo prd_writer separado para SRP

### Implementation Status — UC-002
**Timestamp:** 2026-03-16T10:15:00Z
**Branch:** feature/spec-code-sync

#### Fase 1: Feature Logic
- **Estado:** complete
- **Archivos creados:** `server/prd_parser.py`
- **Archivos modificados:** ninguno
- **Deltas vs plan:** Sin deltas — implementación conforme al plan
- **Decisiones:** ninguna
"""


SAMPLE_PRD_NO_STATUS = """# PRD: Test Feature

## 2. User Stories

### US-01: Something

Content here.
"""


class TestParseUCStatus:
    """Test UC-level parsing."""

    def test_parse_existing_uc(self):
        """AC-11: Parse UC with known status."""
        results = parse_implementation_status(SAMPLE_PRD, "UC-001")
        assert len(results) == 1
        uc = results[0]
        assert uc.uc_id == "UC-001"
        assert uc.timestamp == "2026-03-15T14:32:00Z"
        assert uc.branch == "feature/spec-code-sync"
        assert len(uc.phases) == 2
        assert uc.phases[0].phase_name == "DB Schema"
        assert uc.phases[0].status == "complete"
        assert "server/delta_generator.py" in uc.phases[0].files_created

    def test_parse_uc_not_implemented(self):
        """AC-12: UC without status → not_implemented."""
        results = parse_implementation_status(SAMPLE_PRD, "UC-099")
        assert len(results) == 1
        assert results[0].uc_id == "UC-099"
        assert results[0].overall_status == "not_implemented"
        assert results[0].phases == []

    def test_parse_uc_no_impl_section(self):
        """AC-12: PRD without Implementation Status → not_implemented."""
        results = parse_implementation_status(SAMPLE_PRD_NO_STATUS, "UC-001")
        assert len(results) == 1
        assert results[0].overall_status == "not_implemented"

    def test_delta_count(self):
        """AC-14: delta_count counts phases with actual deltas."""
        results = parse_implementation_status(SAMPLE_PRD, "UC-001")
        uc = results[0]
        # Phase 1 has "Sin deltas" → not counted
        # Phase 2 has "Archivos adicionales" → counted
        assert uc.delta_count == 1

    def test_overall_status_conforme(self):
        """Overall status is 'conforme' when no deltas."""
        results = parse_implementation_status(SAMPLE_PRD, "UC-002")
        assert results[0].overall_status == "conforme"

    def test_overall_status_con_deltas(self):
        """Overall status is 'con_deltas' when deltas exist."""
        results = parse_implementation_status(SAMPLE_PRD, "UC-001")
        assert results[0].overall_status == "con_deltas"


class TestParseUSStatus:
    """Test US-level parsing."""

    def test_parse_us_returns_all_ucs(self):
        """AC-13: US-id returns array with all its UC statuses."""
        results = parse_implementation_status(SAMPLE_PRD, "US-01")
        assert len(results) == 2
        uc_ids = {r.uc_id for r in results}
        assert uc_ids == {"UC-001", "UC-002"}

    def test_parse_us_no_matching_ucs(self):
        """US with no implemented UCs → empty list."""
        results = parse_implementation_status(SAMPLE_PRD, "US-99")
        assert len(results) == 0


class TestPhaseFieldParsing:
    """Test detailed field extraction from phase blocks."""

    def test_files_created_parsed(self):
        results = parse_implementation_status(SAMPLE_PRD, "UC-001")
        phase1 = results[0].phases[0]
        assert phase1.files_created == ["server/delta_generator.py"]

    def test_files_modified_parsed(self):
        results = parse_implementation_status(SAMPLE_PRD, "UC-001")
        phase2 = results[0].phases[1]
        assert "server/server.py" in phase2.files_modified
        assert "server/tools/spec_driven.py" in phase2.files_modified

    def test_decisions_parsed(self):
        results = parse_implementation_status(SAMPLE_PRD, "UC-001")
        phase2 = results[0].phases[1]
        assert len(phase2.decisions) == 1
        assert "SRP" in phase2.decisions[0]

    def test_ninguno_files(self):
        results = parse_implementation_status(SAMPLE_PRD, "UC-001")
        phase1 = results[0].phases[0]
        assert phase1.files_modified == []

    def test_ninguna_decisions(self):
        results = parse_implementation_status(SAMPLE_PRD, "UC-001")
        phase1 = results[0].phases[0]
        assert phase1.decisions == []


class TestFailedAndHealingPhases:
    """Test parsing of failed/healing phases."""

    FAILED_PRD = """# PRD

---

## Implementation Status

### Implementation Status — UC-010
**Timestamp:** 2026-03-20T08:00:00Z
**Branch:** feature/bdd-export

#### Fase 1: Setup
- **Estado:** complete
- **Archivos creados:** `setup.py`
- **Archivos modificados:** ninguno
- **Deltas vs plan:** Sin deltas — implementación conforme al plan
- **Decisiones:** ninguna

#### Fase 2: Feature
- **Estado:** failed
- **Archivos creados:** ninguno
- **Archivos modificados:** ninguno
- **Deltas vs plan:** Sin deltas — implementación conforme al plan
- **Decisiones:** ninguna
- **Error:** Test suite failed: 3 tests broken in auth module

#### Fase 3: Recovery
- **Estado:** needs_healing
- **Archivos creados:** `fix.py`
- **Archivos modificados:** ninguno
- **Deltas vs plan:** Sin deltas — implementación conforme al plan
- **Decisiones:** ninguna
- **Self-healing:** auto-fix — resuelto
"""

    def test_overall_status_parcial(self):
        results = parse_implementation_status(self.FAILED_PRD, "UC-010")
        assert results[0].overall_status == "parcial"

    def test_error_parsed(self):
        results = parse_implementation_status(self.FAILED_PRD, "UC-010")
        phase2 = results[0].phases[1]
        assert phase2.error is not None
        assert "auth module" in phase2.error

    def test_healing_parsed(self):
        results = parse_implementation_status(self.FAILED_PRD, "UC-010")
        phase3 = results[0].phases[2]
        assert phase3.healing is not None
        assert "auto-fix" in phase3.healing
