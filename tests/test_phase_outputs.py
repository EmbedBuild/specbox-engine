"""Tests for phase_outputs (v5.32.0 Phase 4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from server.implement_context import (
    PhaseOutput,
    aggregate_for_spec_sync,
    append_phase_output,
    phase_outputs_path,
    read_phase_outputs,
)


def _entry(**overrides):
    base = dict(
        schema_version=1,
        phase="feature",
        phase_index=4,
        agent="AG-01",
        status="ok",
    )
    base.update(overrides)
    return base


# ── Schema ─────────────────────────────────────────────────────────────


class TestPhaseOutputSchema:
    def test_minimal_validates(self):
        po = PhaseOutput(**_entry())
        assert po.phase == "feature"
        assert po.healing_attempts == 0
        assert po.files_created == []

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            PhaseOutput(**_entry(unexpected="boom"))

    def test_optional_fields_accepted(self):
        po = PhaseOutput(
            **_entry(
                duration_s=42.5,
                summary="did stuff",
                files_created=["lib/x.dart"],
                files_modified=["lib/main.dart"],
                tokens_used_prompt=14000,
                tokens_used_response=2000,
                healing_attempts=2,
                task_id="abc123",
            )
        )
        assert po.duration_s == 42.5
        assert po.healing_attempts == 2
        assert po.files_created == ["lib/x.dart"]


# ── Path resolution ────────────────────────────────────────────────────


class TestPhaseOutputsPath:
    def test_resolves_under_evidence_dir(self, tmp_path: Path):
        p = phase_outputs_path("uc-x", project_root=tmp_path)
        assert p == tmp_path / ".quality/evidence/uc-x/phase_outputs.jsonl"


# ── Append + read ──────────────────────────────────────────────────────


class TestAppendRead:
    def test_creates_file_and_appends_line(self, tmp_path: Path):
        path = append_phase_output("uc-x", _entry(), project_root=tmp_path)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert content.endswith("\n")
        line = json.loads(content.strip())
        assert line["phase"] == "feature"

    def test_two_appends_yield_two_lines(self, tmp_path: Path):
        append_phase_output("uc-x", _entry(phase="db", phase_index=1, agent="AG-03"), project_root=tmp_path)
        append_phase_output("uc-x", _entry(phase="feature", phase_index=4, agent="AG-01"), project_root=tmp_path)
        entries = read_phase_outputs("uc-x", project_root=tmp_path)
        assert len(entries) == 2
        assert entries[0].phase == "db"
        assert entries[1].phase == "feature"

    def test_invalid_payload_raises(self, tmp_path: Path):
        with pytest.raises(ValidationError):
            append_phase_output("uc-x", {"phase": "x"}, project_root=tmp_path)

    def test_accepts_phase_output_instance(self, tmp_path: Path):
        entry = PhaseOutput(**_entry())
        append_phase_output("uc-x", entry, project_root=tmp_path)
        out = read_phase_outputs("uc-x", project_root=tmp_path)
        assert out[0].phase == "feature"

    def test_read_returns_empty_for_missing_file(self, tmp_path: Path):
        assert read_phase_outputs("missing", project_root=tmp_path) == []

    def test_read_skips_corrupt_lines(self, tmp_path: Path):
        path = phase_outputs_path("uc-x", project_root=tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(_entry()) + "\n"
            + "{ not valid json\n"
            + json.dumps(_entry(phase="qa", phase_index=8, agent="AG-04")) + "\n",
            encoding="utf-8",
        )
        out = read_phase_outputs("uc-x", project_root=tmp_path)
        assert len(out) == 2
        assert [e.phase for e in out] == ["feature", "qa"]


# ── Aggregation ────────────────────────────────────────────────────────


class TestAggregateForSpecSync:
    def test_empty_returns_empty_status(self, tmp_path: Path):
        agg = aggregate_for_spec_sync("uc-x", project_root=tmp_path)
        assert agg.overall_status == "empty"
        assert agg.delta_count == 0
        assert agg.phases == []

    def test_aggregates_files_across_phases(self, tmp_path: Path):
        append_phase_output(
            "uc-x",
            _entry(
                phase="db",
                phase_index=1,
                agent="AG-03",
                files_created=["supabase/migrations/01.sql"],
                duration_s=10.0,
            ),
            project_root=tmp_path,
        )
        append_phase_output(
            "uc-x",
            _entry(
                phase="feature",
                phase_index=4,
                agent="AG-01",
                files_created=["lib/features/staff/x.dart"],
                files_modified=["lib/main.dart"],
                duration_s=20.0,
            ),
            project_root=tmp_path,
        )
        agg = aggregate_for_spec_sync("uc-x", project_root=tmp_path)
        assert agg.overall_status == "ok"
        assert agg.delta_count == 3
        assert "supabase/migrations/01.sql" in agg.files_created
        assert "lib/features/staff/x.dart" in agg.files_created
        assert "lib/main.dart" in agg.files_modified
        assert agg.total_duration_s == 30.0

    def test_dedupes_files_first_seen_order(self, tmp_path: Path):
        append_phase_output(
            "uc-x",
            _entry(files_modified=["lib/main.dart"]),
            project_root=tmp_path,
        )
        append_phase_output(
            "uc-x",
            _entry(
                phase="qa",
                phase_index=8,
                agent="AG-04",
                files_modified=["lib/main.dart", "lib/extra.dart"],
            ),
            project_root=tmp_path,
        )
        agg = aggregate_for_spec_sync("uc-x", project_root=tmp_path)
        assert agg.files_modified == ["lib/main.dart", "lib/extra.dart"]

    def test_overall_error_when_any_phase_errors(self, tmp_path: Path):
        append_phase_output("uc-x", _entry(status="ok"), project_root=tmp_path)
        append_phase_output(
            "uc-x",
            _entry(phase="qa", phase_index=8, agent="AG-04", status="error", error="tests failed"),
            project_root=tmp_path,
        )
        agg = aggregate_for_spec_sync("uc-x", project_root=tmp_path)
        assert agg.overall_status == "error"

    def test_overall_partial_when_no_errors_but_some_partial(self, tmp_path: Path):
        append_phase_output("uc-x", _entry(status="ok"), project_root=tmp_path)
        append_phase_output(
            "uc-x",
            _entry(phase="qa", phase_index=8, agent="AG-04", status="partial"),
            project_root=tmp_path,
        )
        agg = aggregate_for_spec_sync("uc-x", project_root=tmp_path)
        assert agg.overall_status == "partial"

    def test_phases_in_file_order(self, tmp_path: Path):
        append_phase_output("uc-x", _entry(phase="db", phase_index=1, agent="AG-03"), project_root=tmp_path)
        append_phase_output("uc-x", _entry(phase="qa", phase_index=8, agent="AG-04"), project_root=tmp_path)
        append_phase_output("uc-x", _entry(phase="feature", phase_index=4, agent="AG-01"), project_root=tmp_path)
        agg = aggregate_for_spec_sync("uc-x", project_root=tmp_path)
        # Order is the order of writes, not phase_index.
        assert [p["phase"] for p in agg.phases] == ["db", "qa", "feature"]

    def test_total_healing_attempts_summed(self, tmp_path: Path):
        append_phase_output("uc-x", _entry(healing_attempts=2), project_root=tmp_path)
        append_phase_output(
            "uc-x",
            _entry(phase="qa", phase_index=8, agent="AG-04", healing_attempts=3),
            project_root=tmp_path,
        )
        agg = aggregate_for_spec_sync("uc-x", project_root=tmp_path)
        assert agg.total_healing_attempts == 5
