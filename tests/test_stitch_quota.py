"""Tests for stitch_quota module + MCP tool (v5.31.0 Phase 5)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP

from server.stitch_quota.computation import (
    DEFAULT_LIMIT_EXPERIMENTAL,
    DEFAULT_LIMIT_STANDARD,
    classify_model,
    compute_quota,
    compute_quota_payload,
    load_entries,
)
from server.tools.stitch_v2 import register_stitch_v2_tools


# ── classify_model ─────────────────────────────────────────────────────


class TestClassifyModel:
    @pytest.mark.parametrize(
        "model_id, expected",
        [
            ("GEMINI_3_PRO", "experimental"),
            ("GEMINI_3_FLASH", "standard"),
            ("gemini_3_flash", "standard"),
            ("Gemini-3-Pro", "experimental"),
            ("", "experimental"),  # default to PRO since it's our default
            (None, "experimental"),
            ("GEMINI_2", "unknown"),
        ],
    )
    def test_classifies_correctly(self, model_id, expected):
        assert classify_model(model_id) == expected


# ── compute_quota ──────────────────────────────────────────────────────


def _entry(tool, model_id="GEMINI_3_PRO", status="ok", ts="2026-05-15T10:00:00Z"):
    return {"tool": tool, "model_id": model_id, "status": status, "ts": ts}


class TestComputeQuota:
    def test_empty_returns_zero(self):
        snap = compute_quota([], month="2026-05")
        assert snap.standard_used == 0
        assert snap.experimental_used == 0

    def test_counts_pro_generations(self):
        entries = [
            _entry("stitch_generate_screen", "GEMINI_3_PRO"),
            _entry("stitch_generate_screen", "GEMINI_3_PRO"),
            _entry("stitch_edit_screens", "GEMINI_3_PRO"),
        ]
        snap = compute_quota(entries, month="2026-05")
        assert snap.experimental_used == 3
        assert snap.standard_used == 0

    def test_counts_flash_generations(self):
        entries = [
            _entry("stitch_generate_screen", "GEMINI_3_FLASH"),
            _entry("stitch_generate_variants", "GEMINI_3_FLASH"),
        ]
        snap = compute_quota(entries, month="2026-05")
        assert snap.standard_used == 2
        assert snap.experimental_used == 0

    def test_skips_metadata_tools(self):
        entries = [
            _entry("validate_stitch_prompt"),
            _entry("generate_design_md"),
            _entry("upload_design_md"),
            _entry("stitch_set_api_key"),
            _entry("stitch_get_screen"),
        ]
        snap = compute_quota(entries, month="2026-05")
        assert snap.standard_used == 0
        assert snap.experimental_used == 0

    def test_skips_failed_calls(self):
        entries = [
            _entry("stitch_generate_screen", "GEMINI_3_PRO", status="error"),
            _entry("stitch_generate_screen", "GEMINI_3_PRO", status="ok"),
        ]
        snap = compute_quota(entries, month="2026-05")
        assert snap.experimental_used == 1

    def test_skips_other_months(self):
        entries = [
            _entry("stitch_generate_screen", ts="2026-04-15T10:00:00Z"),
            _entry("stitch_generate_screen", ts="2026-05-15T10:00:00Z"),
            _entry("stitch_generate_screen", ts="2026-06-01T10:00:00Z"),
        ]
        snap = compute_quota(entries, month="2026-05")
        assert snap.experimental_used == 1

    def test_handles_missing_model_id_as_pro(self):
        entries = [{"tool": "stitch_generate_screen", "status": "ok", "ts": "2026-05-01T00:00:00Z"}]
        snap = compute_quota(entries, month="2026-05")
        assert snap.experimental_used == 1
        assert snap.standard_used == 0


class TestComputeQuotaPayload:
    def test_no_warning_when_low(self):
        entries = [_entry("stitch_generate_screen") for _ in range(10)]
        p = compute_quota_payload(entries, month="2026-05")
        assert p.warning is None

    def test_warning_when_pro_above_80_pct(self):
        # PRO limit defaults to 200 → 161 = 80.5%
        entries = [_entry("stitch_generate_screen") for _ in range(161)]
        p = compute_quota_payload(entries, month="2026-05")
        assert p.warning is not None
        assert "PRO" in p.warning

    def test_exhausted_message_at_100(self):
        entries = [
            _entry("stitch_generate_screen") for _ in range(DEFAULT_LIMIT_EXPERIMENTAL)
        ]
        p = compute_quota_payload(entries, month="2026-05")
        assert "exhausted" in (p.warning or "").lower()

    def test_summary_format(self):
        entries = [
            _entry("stitch_generate_screen", "GEMINI_3_PRO") for _ in range(50)
        ]
        entries += [
            _entry("stitch_generate_screen", "GEMINI_3_FLASH") for _ in range(100)
        ]
        p = compute_quota_payload(entries, month="2026-05")
        assert "PRO 50/200" in p.summary
        assert "Flash 100/350" in p.summary

    def test_reset_at_next_month_first_day(self):
        p = compute_quota_payload([], month="2026-05")
        assert p.reset_at == "2026-06-01T00:00:00Z"

    def test_reset_at_year_rollover(self):
        p = compute_quota_payload([], month="2026-12")
        assert p.reset_at == "2027-01-01T00:00:00Z"


# ── load_entries ───────────────────────────────────────────────────────


class TestLoadEntries:
    def test_returns_empty_for_missing_file(self, tmp_path: Path):
        assert load_entries(tmp_path / "nope.jsonl") == []

    def test_parses_one_entry_per_line(self, tmp_path: Path):
        f = tmp_path / "u.jsonl"
        f.write_text(
            json.dumps({"tool": "x"}) + "\n"
            + json.dumps({"tool": "y"}) + "\n",
            encoding="utf-8",
        )
        out = load_entries(f)
        assert len(out) == 2
        assert out[0]["tool"] == "x"

    def test_skips_invalid_json_lines(self, tmp_path: Path):
        f = tmp_path / "u.jsonl"
        f.write_text(
            json.dumps({"tool": "x"}) + "\n"
            + "{ not json\n"
            + json.dumps({"tool": "y"}) + "\n",
            encoding="utf-8",
        )
        out = load_entries(f)
        assert len(out) == 2


# ── MCP tool ────────────────────────────────────────────────────────────


@pytest.fixture
def mcp_with_v2(tmp_path: Path):
    mcp = FastMCP("test-quota")
    state = tmp_path / "state"
    state.mkdir()
    register_stitch_v2_tools(mcp, state)
    return mcp, state


async def _call(mcp, name, **kwargs):
    tool = await mcp._get_tool(name)
    ctx = AsyncMock()
    return await tool.fn(ctx, **kwargs)


def _seed_usage(state_path: Path, project: str, entries: list[dict]) -> None:
    project_dir = state_path / "projects" / project
    project_dir.mkdir(parents=True, exist_ok=True)
    log = project_dir / "stitch_usage.jsonl"
    log.write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )


class TestQuotaTool:
    @pytest.mark.asyncio
    async def test_zero_when_no_telemetry(self, mcp_with_v2):
        mcp, _state = mcp_with_v2
        r = await _call(
            mcp,
            "get_stitch_quota_status",
            project="demo",
            month="2026-05",
            write_cache=False,
        )
        assert r["status"] == "ok"
        assert r["experimental"]["used"] == 0
        assert r["standard"]["used"] == 0

    @pytest.mark.asyncio
    async def test_aggregates_per_month(self, mcp_with_v2):
        mcp, state = mcp_with_v2
        _seed_usage(
            state,
            "demo",
            [
                _entry("stitch_generate_screen", ts="2026-05-01T00:00:00Z"),
                _entry("stitch_generate_screen", ts="2026-05-15T00:00:00Z"),
                _entry("stitch_generate_screen", ts="2026-04-15T00:00:00Z"),
            ],
        )
        r = await _call(
            mcp,
            "get_stitch_quota_status",
            project="demo",
            month="2026-05",
            write_cache=False,
        )
        assert r["experimental"]["used"] == 2

    @pytest.mark.asyncio
    async def test_writes_cache_file(self, mcp_with_v2, tmp_path: Path):
        mcp, state = mcp_with_v2
        _seed_usage(
            state,
            "demo",
            [_entry("stitch_generate_screen") for _ in range(5)],
        )
        proj_root = tmp_path / "proj-root"
        proj_root.mkdir()
        r = await _call(
            mcp,
            "get_stitch_quota_status",
            project="demo",
            project_root=str(proj_root),
            write_cache=True,
        )
        cache_file = proj_root / ".quality" / "stitch_quota.json"
        assert cache_file.exists()
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert data["experimental"]["used"] == r["experimental"]["used"]
        assert "warning" in data
