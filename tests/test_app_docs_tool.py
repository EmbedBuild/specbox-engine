"""Tests for the read_app_docs / get_inheritable_values MCP tools (v5.29.0 PR-4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from server.tools.app_docs import (
    PRD_REQUIRED_ZONES,
    SPEC_REQUIRED_ZONES,
    get_inheritable_values,
    read_app_docs,
)


# ── read_app_docs ────────────────────────────────────────────────────


class TestReadAppDocs:
    def test_returns_false_flags_when_no_doc_app(self, tmp_path):
        result = read_app_docs(tmp_path)
        assert result["has_app_prd"] is False
        assert result["has_app_spec"] is False
        assert result["prd"] is None
        assert result["spec"] is None
        assert "app-init" in result["summary"]

    def test_reads_app_prd_when_present(self, tmp_path):
        doc_app = tmp_path / "doc" / "app"
        doc_app.mkdir(parents=True)
        (doc_app / "app_prd.md").write_text(
            "<!-- @specbox:zone start kind=\"manual\" id=\"vision\" -->\n"
            "Vision text.\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"audience\" -->\n"
            "Devs.\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"scope\" -->\n"
            "v1: feature X.\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"hybrid\" id=\"success_metrics\" -->\n"
            "M1\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"auto\" id=\"roadmap\" -->\n"
            "(empty)\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"stakeholders\" -->\n"
            "PO: Jesus\n"
            "<!-- @specbox:zone end -->\n",
            encoding="utf-8",
        )

        result = read_app_docs(tmp_path)
        assert result["has_app_prd"] is True
        assert result["has_app_spec"] is False
        prd = result["prd"]
        assert prd["well_formed"] is True
        assert "vision" in prd["zones"]
        assert prd["zones"]["vision"]["body"].strip() == "Vision text."

    def test_reports_partial_when_only_one_doc_exists(self, tmp_path):
        doc_app = tmp_path / "doc" / "app"
        doc_app.mkdir(parents=True)
        # Solo PRD existe.
        (doc_app / "app_prd.md").write_text(
            "<!-- @specbox:zone start kind=\"manual\" id=\"vision\" -->\nX\n<!-- @specbox:zone end -->\n",
            encoding="utf-8",
        )
        result = read_app_docs(tmp_path)
        assert result["has_app_prd"] is True
        assert result["has_app_spec"] is False
        assert "Solo uno" in result["summary"]

    def test_reports_format_errors_in_prd(self, tmp_path):
        doc_app = tmp_path / "doc" / "app"
        doc_app.mkdir(parents=True)
        (doc_app / "app_prd.md").write_text(
            "<!-- @specbox:zone start kind=\"manual\" id=\"vision\" -->\n"
            "No closing marker — should report error.\n",
            encoding="utf-8",
        )
        (doc_app / "app_spec.md").write_text("", encoding="utf-8")
        result = read_app_docs(tmp_path)
        assert result["prd"]["well_formed"] is False
        assert any(e["severity"] == "error" for e in result["prd"]["errors"])

    def test_required_zones_constants_match_templates(self):
        # Sanity: the constants embedded in app_docs.py must match what
        # the shipped templates declare. Drift here would break /app-init refresh.
        repo_root = Path(__file__).resolve().parent.parent
        prd_template = (repo_root / "templates" / "app_prd.md.template").read_text(encoding="utf-8")
        spec_template = (repo_root / "templates" / "app_spec.md.template").read_text(encoding="utf-8")
        for zid in PRD_REQUIRED_ZONES:
            assert f'id="{zid}"' in prd_template, f"PRD template missing zone {zid!r}"
        for zid in SPEC_REQUIRED_ZONES:
            assert f'id="{zid}"' in spec_template, f"Spec template missing zone {zid!r}"


# ── get_inheritable_values ───────────────────────────────────────────


class TestGetInheritableValues:
    def test_all_false_when_no_docs(self, tmp_path):
        out = get_inheritable_values(tmp_path)
        assert out["audience_defined"] is False
        assert out["scope_defined"] is False
        assert out["veg_mode_known"] is False
        assert out["stack_known"] is False
        assert out["backend_type"] is None
        assert out["autopilot_level"] is None

    def test_audience_defined_when_real_content(self, tmp_path):
        doc_app = tmp_path / "doc" / "app"
        doc_app.mkdir(parents=True)
        (doc_app / "app_prd.md").write_text(
            "<!-- @specbox:zone start kind=\"manual\" id=\"vision\" -->\nv\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"audience\" -->\n"
            "PMs senior, devs frontend.\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"scope\" -->\nv1: foo\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"hybrid\" id=\"success_metrics\" -->\nM\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"auto\" id=\"roadmap\" -->\n-\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"stakeholders\" -->\nPO\n<!-- @specbox:zone end -->\n",
            encoding="utf-8",
        )
        out = get_inheritable_values(tmp_path)
        assert out["audience_defined"] is True
        assert "PMs senior" in out["audience_text"]

    def test_audience_undefined_when_template_placeholder_remains(self, tmp_path):
        doc_app = tmp_path / "doc" / "app"
        doc_app.mkdir(parents=True)
        (doc_app / "app_prd.md").write_text(
            "<!-- @specbox:zone start kind=\"manual\" id=\"vision\" -->\nv\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"audience\" -->\n"
            "**Targets:** {target_name}\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"scope\" -->\nv\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"hybrid\" id=\"success_metrics\" -->\nM\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"auto\" id=\"roadmap\" -->\n-\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"stakeholders\" -->\nPO\n<!-- @specbox:zone end -->\n",
            encoding="utf-8",
        )
        out = get_inheritable_values(tmp_path)
        assert out["audience_defined"] is False, "template placeholder must not count as defined"

    def test_extracts_backend_type_and_autopilot(self, tmp_path):
        doc_app = tmp_path / "doc" / "app"
        doc_app.mkdir(parents=True)
        (doc_app / "app_spec.md").write_text(
            "<!-- @specbox:zone start kind=\"auto\" id=\"stack\" -->\n"
            "Frontend: React 19\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"auto\" id=\"tracking_backend\" -->\n"
            "- Tipo: freeform\n"
            "- Path absoluto: /Users/x/proj/doc/tracking\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"brand_visual\" -->\n"
            "VEG arquetipo: Startup\n"
            "Modo VEG: per_icp\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"conventions\" -->\n-\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"auto\" id=\"autopilot\" -->\n"
            "- Level: equilibrado\n"
            "- Image budget €/feature: 5\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"hybrid\" id=\"canonical_decisions\" -->\n-\n<!-- @specbox:zone end -->\n",
            encoding="utf-8",
        )
        out = get_inheritable_values(tmp_path)
        assert out["backend_type"] == "freeform"
        assert out["freeform_root_absolute"] == "/Users/x/proj/doc/tracking"
        assert out["autopilot_level"] == "equilibrado"
        assert out["image_budget_eur_per_feature"] == 5.0
        assert out["veg_archetype"] == "Startup"
        assert out["veg_mode_known"] is True
        assert out["stack_known"] is True

    def test_invalid_autopilot_value_ignored(self, tmp_path):
        doc_app = tmp_path / "doc" / "app"
        doc_app.mkdir(parents=True)
        (doc_app / "app_spec.md").write_text(
            "<!-- @specbox:zone start kind=\"auto\" id=\"stack\" -->\n-\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"auto\" id=\"tracking_backend\" -->\n-\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"brand_visual\" -->\n-\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"conventions\" -->\n-\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"auto\" id=\"autopilot\" -->\n"
            "- Level: chaotic\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"hybrid\" id=\"canonical_decisions\" -->\n-\n<!-- @specbox:zone end -->\n",
            encoding="utf-8",
        )
        out = get_inheritable_values(tmp_path)
        assert out["autopilot_level"] is None  # "chaotic" must be rejected
