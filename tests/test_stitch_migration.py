"""Tests for v6.5.0 Stitch migration tools (F7).

Covers detect_stitch_migration_case classification and the recipe shape
for migrate_project_to_native_v2 plus the telemetry aggregator. The
tools follow the v6.0.1 MCP Path Contract (content-passing), so the
tests are pure functions on string inputs — no filesystem or network.
"""

from __future__ import annotations

import json

import pytest

from server.tools.stitch_migration import (
    DesignMdShape,
    SettingsView,
    _classify_case,
    _classify_design_md,
    _parse_settings,
    _recipe_for_case,
    _recommendation_for,
    aggregate_migration_log,
)


# ── DESIGN.md shape classifier ────────────────────────────────────────


class TestClassifyDesignMd:
    def test_none_returns_no_frontmatter(self):
        shape = _classify_design_md(None)
        assert shape == DesignMdShape(False, False, False, False)

    def test_empty_returns_no_frontmatter(self):
        assert _classify_design_md("") == DesignMdShape(False, False, False, False)

    def test_no_yaml_delimiters(self):
        shape = _classify_design_md("# Just markdown\nno frontmatter at all")
        assert not shape.has_frontmatter

    def test_material3_frontmatter_detected(self):
        md = """---
name: Test
theme:
  colorMode: LIGHT
  colorVariant: FIDELITY
  roundness: ROUND_EIGHT
  headlineFont: INTER
  customColor: '#0EA5E9'
---
# Body
"""
        shape = _classify_design_md(md)
        assert shape.has_frontmatter
        assert shape.is_material3
        assert not shape.is_legacy_specbox
        assert not shape.is_custom

    def test_legacy_specbox_frontmatter_detected(self):
        md = """---
name: Test
colors:
  primary: '#0EA5E9'
  primary_hover: '#0284C7'
  text_primary: '#0F172A'
typography:
  fontFamily:
    heading: Inter
    body: Inter
  fontSize:
    h1: 32px
    body: 16px
---
# Body
"""
        shape = _classify_design_md(md)
        assert shape.has_frontmatter
        assert shape.is_legacy_specbox
        assert not shape.is_material3
        assert not shape.is_custom

    def test_custom_frontmatter_detected(self):
        md = """---
custom_field_one: hello
random_yaml_key: 42
---
# Body
"""
        shape = _classify_design_md(md)
        assert shape.has_frontmatter
        assert shape.is_custom
        assert not shape.is_material3
        assert not shape.is_legacy_specbox


# ── Settings parser ───────────────────────────────────────────────────


class TestParseSettings:
    def test_none_returns_empty_view(self):
        assert _parse_settings(None) == SettingsView(None, None, None)

    def test_invalid_json_returns_empty_view(self):
        assert _parse_settings("not-json") == SettingsView(None, None, None)

    def test_extracts_stitch_contract_and_project_id(self):
        s = json.dumps(
            {"stitch": {"contract": "native_v2", "projectId": "abc"}}
        )
        view = _parse_settings(s)
        assert view.contract == "native_v2"
        assert view.stitch_project_id == "abc"

    def test_extracts_multirepo_role(self):
        s = json.dumps({"multirepo": {"role": "orchestrator"}})
        view = _parse_settings(s)
        assert view.multirepo_role == "orchestrator"


# ── Case classifier — covers all 6 paths ──────────────────────────────


def _md_legacy() -> str:
    return """---
name: T
colors:
  primary: '#0EA5E9'
  text_primary: '#0F172A'
typography:
  fontFamily:
    heading: Inter
    body: Inter
  fontSize:
    h1: 32px
    body: 16px
---
"""


def _md_custom() -> str:
    return """---
some_user_field: bar
---
"""


class TestClassifyCase:
    def test_case_a_already_native_v2(self):
        s = _parse_settings(json.dumps({"stitch": {"contract": "native_v2"}}))
        case, _ = _classify_case(s, _classify_design_md(None), generated_screens_count=0)
        assert case == "A"

    def test_case_b_stitch_unused(self):
        s = _parse_settings(json.dumps({"stitch": {"projectId": "p1"}}))
        case, _ = _classify_case(s, _classify_design_md(None), generated_screens_count=0)
        assert case == "B"

    def test_case_c_design_md_without_stitch_project(self):
        s = _parse_settings(json.dumps({"stitch": {}}))
        case, _ = _classify_case(s, _classify_design_md(_md_legacy()), generated_screens_count=0)
        assert case == "C"

    def test_case_d_stitch_with_screens(self):
        s = _parse_settings(json.dumps({"stitch": {"projectId": "p123"}}))
        case, _ = _classify_case(s, _classify_design_md(_md_legacy()), generated_screens_count=5)
        assert case == "D"

    def test_case_e_custom_design_md(self):
        s = _parse_settings(json.dumps({"stitch": {}}))
        case, _ = _classify_case(s, _classify_design_md(_md_custom()), generated_screens_count=0)
        assert case == "E"

    def test_case_f_multirepo_orchestrator(self):
        s = _parse_settings(json.dumps({"multirepo": {"role": "orchestrator"}, "stitch": {}}))
        case, _ = _classify_case(s, _classify_design_md(None), generated_screens_count=0)
        assert case == "F"

    def test_case_f_multirepo_satellite(self):
        s = _parse_settings(json.dumps({"multirepo": {"role": "satellite"}, "stitch": {}}))
        case, _ = _classify_case(s, _classify_design_md(None), generated_screens_count=0)
        assert case == "F"

    def test_multirepo_wins_over_native_v2(self):
        # Even if contract is already native_v2, multirepo classification
        # takes precedence so the caller is reminded to coordinate.
        s = _parse_settings(json.dumps({
            "multirepo": {"role": "orchestrator"},
            "stitch": {"contract": "native_v2"},
        }))
        case, _ = _classify_case(s, _classify_design_md(None), generated_screens_count=0)
        assert case == "F"


# ── Recipe shape ──────────────────────────────────────────────────────


class TestRecipeForCase:
    def test_recipe_a_is_noop(self):
        r = _recipe_for_case(
            "A",
            project_name="t",
            has_design_md=False,
            settings_view=_parse_settings("{}"),
        )
        assert r["actions"] == ["noop"]
        assert r["confirmation_required"] is None

    def test_recipe_b_only_flips_settings(self):
        r = _recipe_for_case(
            "B",
            project_name="t",
            has_design_md=False,
            settings_view=_parse_settings("{}"),
        )
        assert r["actions"] == ["set_contract_native_v2"]
        assert r["settings_patch"]["stitch"]["contract"] == "native_v2"
        assert r["confirmation_required"] is None

    def test_recipe_c_bootstraps_ds_chain(self):
        r = _recipe_for_case(
            "C",
            project_name="t",
            has_design_md=True,
            settings_view=_parse_settings("{}"),
        )
        assert "backup_design_md_if_present" in r["actions"]
        assert "regenerate_design_md_as_native_v2" in r["actions"]
        assert "create_design_system_from_design_md" in r["actions"]
        assert "set_contract_native_v2" in r["actions"]
        assert r["confirmation_required"] is None

    def test_recipe_d_requires_retroactive_literal(self):
        r = _recipe_for_case(
            "D",
            project_name="t",
            has_design_md=True,
            settings_view=_parse_settings(json.dumps({"stitch": {"projectId": "abc"}})),
        )
        assert r["confirmation_required"]["literal"] == "MIGRATE-RETROACTIVE"
        assert "preview_apply_design_system" in r["actions"]
        # Confirmation must gate before the destructive step.
        prev_idx = r["actions"].index("preview_apply_design_system")
        wait_idx = r["actions"].index("WAIT_FOR_LITERAL_CONFIRMATION")
        apply_idx = r["actions"].index("apply_design_system_to_all_screens")
        assert prev_idx < wait_idx < apply_idx

    def test_recipe_e_requires_apply_proposal_literal(self):
        r = _recipe_for_case(
            "E",
            project_name="t",
            has_design_md=True,
            settings_view=_parse_settings("{}"),
        )
        assert r["confirmation_required"]["literal"] == "APPLY-PROPOSAL"
        # Writes a proposal file but no actual mutation until confirmed.
        assert any(
            f["path"].endswith("migration_proposal_material3.md")
            for f in r["files_to_write"]
        )

    def test_recipe_f_delegates_to_orchestrator(self):
        r = _recipe_for_case(
            "F",
            project_name="t",
            has_design_md=False,
            settings_view=_parse_settings("{}"),
        )
        assert r["actions"] == ["delegate_to_orchestrator"]


# ── Recommendations ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "case,expected",
    [
        ("A", "no_op"),
        ("B", "mark_native_v2_no_data_migration"),
        ("C", "migrate_design_md_then_bootstrap_ds"),
        ("D", "d2_retroactive_assisted"),
        ("E", "generate_mapping_proposal_for_review"),
        ("F", "migrate_orchestrator_only"),
    ],
)
def test_recommendation_for(case, expected):
    assert _recommendation_for(case) == expected


# ── Telemetry aggregator ──────────────────────────────────────────────


class TestAggregateMigrationLog:
    def test_empty_input(self):
        agg = aggregate_migration_log([])
        assert agg["total_events"] == 0
        assert agg["by_case"] == {}

    def test_skips_malformed_rows(self):
        rows = [
            "",
            "not-json",
            json.dumps({"case": "A", "action": "noop", "outcome": "ok"}),
        ]
        agg = aggregate_migration_log(rows)
        assert agg["total_events"] == 1
        assert agg["by_case"] == {"A": 1}

    def test_counts_per_dimension(self):
        rows = [
            json.dumps({"case": "C", "action": "backup_design_md", "outcome": "ok"}),
            json.dumps({"case": "C", "action": "regenerate_design_md_as_native_v2", "outcome": "ok"}),
            json.dumps({"case": "D", "action": "apply_design_system_to_all_screens", "outcome": "fail"}),
        ]
        agg = aggregate_migration_log(rows)
        assert agg["total_events"] == 3
        assert agg["by_case"] == {"C": 2, "D": 1}
        assert agg["by_outcome"] == {"ok": 2, "fail": 1}
        assert agg["by_action"]["apply_design_system_to_all_screens"] == 1
