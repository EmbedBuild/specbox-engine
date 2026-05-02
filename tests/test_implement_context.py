"""Tests for the implement_context module (v5.32.0 Phase 1)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from server.implement_context import (
    SCHEMA_VERSION,
    ExecutionContext,
    compute_plan_hash,
    context_path,
    read_execution_context,
    update_last_updated,
    write_execution_context,
)


def _kwargs(**overrides):
    base = dict(
        feature_slug="uc-021-staff",
        branch="feature/uc-021-staff",
        stack="flutter",
        project_name="talent-on",
        project_root_absolute="/Users/test/talent-on",
        engine_version="5.32.0",
    )
    base.update(overrides)
    return base


# ── Schema ─────────────────────────────────────────────────────────────


class TestExecutionContextSchema:
    def test_minimal_fields_round_trip(self):
        ctx = ExecutionContext(**_kwargs())
        assert ctx.schema_version == SCHEMA_VERSION
        assert ctx.feature_slug == "uc-021-staff"
        # defaults applied
        assert ctx.base_branch == "main"
        assert ctx.backend_type == "freeform"

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            ExecutionContext(**_kwargs(unexpected_field="boom"))

    def test_optional_fields_accepted(self):
        ctx = ExecutionContext(
            **_kwargs(
                uc_id="UC-021",
                us_id="US-04",
                board_id="ff-abc",
                plan_path="doc/plans/uc-021_plan.md",
                plan_hash="deadbeef",
                autopilot_level="equilibrado",
            )
        )
        assert ctx.uc_id == "UC-021"
        assert ctx.autopilot_level == "equilibrado"


# ── Path resolution ────────────────────────────────────────────────────


class TestContextPath:
    def test_uses_cwd_by_default(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        p = context_path("uc-x")
        assert p == tmp_path / ".quality/evidence/uc-x/execution_context.json"

    def test_uses_explicit_root(self, tmp_path: Path):
        p = context_path("uc-x", project_root=tmp_path)
        assert p == tmp_path / ".quality/evidence/uc-x/execution_context.json"


# ── write/read round-trip ──────────────────────────────────────────────


class TestWriteRead:
    def test_writes_and_reads_back(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        write_execution_context(**_kwargs())
        ctx = read_execution_context("uc-021-staff")
        assert ctx is not None
        assert ctx.feature_slug == "uc-021-staff"
        assert ctx.branch == "feature/uc-021-staff"

    def test_returns_none_when_absent(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert read_execution_context("missing") is None

    def test_creates_parent_dirs(self, tmp_path: Path):
        p = write_execution_context(project_root=tmp_path, **_kwargs())
        assert p.exists()
        assert p.parent.exists()

    def test_file_is_valid_json(self, tmp_path: Path):
        p = write_execution_context(project_root=tmp_path, **_kwargs())
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["feature_slug"] == "uc-021-staff"
        assert data["schema_version"] == SCHEMA_VERSION

    def test_corrupt_file_raises_on_read(self, tmp_path: Path):
        target = tmp_path / ".quality/evidence/x/execution_context.json"
        target.parent.mkdir(parents=True)
        target.write_text("{ not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            read_execution_context("x", project_root=tmp_path)


# ── Idempotency ────────────────────────────────────────────────────────


class TestIdempotency:
    def test_second_write_with_same_content_does_not_change_mtime(
        self, tmp_path: Path
    ):
        p1 = write_execution_context(project_root=tmp_path, **_kwargs())
        m1 = p1.stat().st_mtime
        time.sleep(1.1)
        write_execution_context(project_root=tmp_path, **_kwargs())
        m2 = p1.stat().st_mtime
        assert m1 == m2

    def test_changed_field_does_overwrite(self, tmp_path: Path):
        write_execution_context(project_root=tmp_path, **_kwargs())
        write_execution_context(
            project_root=tmp_path, **_kwargs(branch="feature/different")
        )
        ctx = read_execution_context("uc-021-staff", project_root=tmp_path)
        assert ctx.branch == "feature/different"


class TestUpdateLastUpdated:
    def test_no_op_when_file_absent(self, tmp_path: Path):
        result = update_last_updated("missing", project_root=tmp_path)
        assert result is None

    def test_bumps_timestamp(self, tmp_path: Path):
        write_execution_context(project_root=tmp_path, **_kwargs())
        before = read_execution_context("uc-021-staff", project_root=tmp_path)
        time.sleep(1.1)
        update_last_updated("uc-021-staff", project_root=tmp_path)
        after = read_execution_context("uc-021-staff", project_root=tmp_path)
        assert before.last_updated_at != after.last_updated_at


# ── compute_plan_hash ──────────────────────────────────────────────────


class TestComputePlanHash:
    def test_hashes_a_known_string(self, tmp_path: Path):
        plan = tmp_path / "p.md"
        plan.write_text("hello", encoding="utf-8")
        # sha256("hello") = 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
        assert compute_plan_hash(plan).startswith("2cf24dba")

    def test_raises_for_missing(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            compute_plan_hash(tmp_path / "nope.md")

    def test_changes_on_content_change(self, tmp_path: Path):
        plan = tmp_path / "p.md"
        plan.write_text("first", encoding="utf-8")
        h1 = compute_plan_hash(plan)
        plan.write_text("second", encoding="utf-8")
        h2 = compute_plan_hash(plan)
        assert h1 != h2


# ── Atomic writes ──────────────────────────────────────────────────────


class TestAtomicWrites:
    def test_no_partial_files_left_on_disk(self, tmp_path: Path):
        write_execution_context(project_root=tmp_path, **_kwargs())
        evidence_dir = tmp_path / ".quality/evidence/uc-021-staff"
        # Only the canonical filename should exist; no .tmp leftovers.
        names = [p.name for p in evidence_dir.iterdir()]
        assert names == ["execution_context.json"]
