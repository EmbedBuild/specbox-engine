"""Tests for the app_docs.zones parser (v5.29.0 PR-3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from server.app_docs.zones import (
    ParsedDoc,
    Zone,
    ZoneKind,
    compute_signature,
    parse_document,
    replace_zone_body,
    validate_document,
)


# ── Parsing ──────────────────────────────────────────────────────────


class TestParseDocument:
    def test_parses_single_manual_zone(self):
        content = (
            "# Title\n\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"vision\" -->\n"
            "## 1. Vision\n"
            "Hello world.\n"
            "<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("app_prd.md"), content=content)
        assert doc.is_well_formed
        assert len(doc.zones) == 1
        z = doc.zones[0]
        assert z.kind == ZoneKind.MANUAL
        assert z.id == "vision"
        assert "## 1. Vision" in z.body
        assert "Hello world." in z.body

    def test_parses_auto_zone_with_auto_sync_on(self):
        content = (
            "<!-- @specbox:zone start kind=\"auto\" id=\"roadmap\" "
            "auto_sync_on=\"complete_uc, move_uc\" -->\n"
            "## Roadmap\n"
            "<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("app_prd.md"), content=content)
        assert doc.is_well_formed
        assert doc.zones[0].auto_sync_on == ("complete_uc", "move_uc")

    def test_parses_hybrid_zone_with_merge_attr(self):
        content = (
            "<!-- @specbox:zone start kind=\"hybrid\" id=\"decisions\" "
            "merge=\"append_only\" -->\n"
            "## Decisions\n"
            "<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("app_spec.md"), content=content)
        assert doc.is_well_formed
        assert doc.zones[0].merge == "append_only"

    def test_multiple_zones_separated_by_preamble(self):
        content = (
            "# Header\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\n"
            "Content A\n"
            "<!-- @specbox:zone end -->\n"
            "Some intro between zones.\n"
            "<!-- @specbox:zone start kind=\"auto\" id=\"b\" -->\n"
            "Content B\n"
            "<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("doc.md"), content=content)
        assert doc.is_well_formed
        assert len(doc.zones) == 2
        assert [z.id for z in doc.zones] == ["a", "b"]
        # Preamble chunks captured
        assert len(doc.preamble_chunks) >= 1
        joined_preamble = "\n".join(p[2] for p in doc.preamble_chunks)
        assert "Some intro" in joined_preamble

    def test_zone_by_id(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"vision\" -->\n"
            "X\n"
            "<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("d.md"), content=content)
        assert doc.zone_by_id("vision") is not None
        assert doc.zone_by_id("ghost") is None

    def test_zones_of_kind(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nA\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"auto\" id=\"b\" -->\nB\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"c\" -->\nC\n<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("d.md"), content=content)
        manuals = doc.zones_of_kind(ZoneKind.MANUAL)
        assert {z.id for z in manuals} == {"a", "c"}


class TestParseErrors:
    def test_unclosed_zone_reports_error(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"open\" -->\n"
            "Body without closing marker\n"
        )
        doc = parse_document(Path("d.md"), content=content)
        assert not doc.is_well_formed
        assert any("unclosed" in e for e in doc.errors)

    def test_end_without_start_reports_error(self):
        content = "<!-- @specbox:zone end -->\n"
        doc = parse_document(Path("d.md"), content=content)
        assert not doc.is_well_formed
        assert any("end without matching start" in e for e in doc.errors)

    def test_invalid_kind_reports_error(self):
        content = (
            "<!-- @specbox:zone start kind=\"chaotic\" id=\"x\" -->\n"
            "<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("d.md"), content=content)
        assert not doc.is_well_formed
        assert any("invalid kind" in e for e in doc.errors)

    def test_missing_id_reports_error(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" -->\n"
            "<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("d.md"), content=content)
        assert any("missing id" in e for e in doc.errors)

    def test_nested_zones_report_error(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"outer\" -->\n"
            "<!-- @specbox:zone start kind=\"auto\" id=\"inner\" -->\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("d.md"), content=content)
        assert any("nested zone start" in e for e in doc.errors)


# ── Validation ───────────────────────────────────────────────────────


class TestValidateDocument:
    def test_well_formed_doc_no_errors(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nA\n<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("d.md"), content=content)
        issues = validate_document(doc)
        assert all(i.severity != "error" for i in issues)

    def test_duplicate_id_reported_as_error(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"dup\" -->\nA\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"auto\" id=\"dup\" -->\nB\n<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("d.md"), content=content)
        issues = validate_document(doc)
        errors = [i for i in issues if i.severity == "error"]
        assert any("duplicate zone id" in e.message for e in errors)

    def test_manual_zone_with_auto_sync_on_warns(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"x\" auto_sync_on=\"complete_uc\" -->\n"
            "<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("d.md"), content=content)
        issues = validate_document(doc)
        assert any(i.severity == "warning" for i in issues)

    def test_required_zones_missing_reported(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"vision\" -->\n"
            "<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("d.md"), content=content)
        issues = validate_document(
            doc,
            required_zones={
                "vision": ZoneKind.MANUAL,
                "roadmap": ZoneKind.AUTO,  # missing → error
            },
        )
        errors = [i for i in issues if i.severity == "error"]
        assert any("required zone 'roadmap' missing" in e.message for e in errors)

    def test_required_zone_kind_mismatch_reported(self):
        content = (
            "<!-- @specbox:zone start kind=\"auto\" id=\"vision\" -->\n"
            "<!-- @specbox:zone end -->\n"
        )
        doc = parse_document(Path("d.md"), content=content)
        issues = validate_document(doc, required_zones={"vision": ZoneKind.MANUAL})
        errors = [i for i in issues if i.severity == "error"]
        assert any("kind=auto, expected manual" in e.message for e in errors)


# ── Signature ────────────────────────────────────────────────────────


class TestComputeSignature:
    def test_same_content_same_signature(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nHello\n<!-- @specbox:zone end -->\n"
        )
        s1 = compute_signature(parse_document(Path("d.md"), content=content))
        s2 = compute_signature(parse_document(Path("d.md"), content=content))
        assert s1 == s2

    def test_body_change_changes_signature(self):
        content_a = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nHello\n<!-- @specbox:zone end -->\n"
        )
        content_b = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nHi\n<!-- @specbox:zone end -->\n"
        )
        s1 = compute_signature(parse_document(Path("d.md"), content=content_a))
        s2 = compute_signature(parse_document(Path("d.md"), content=content_b))
        assert s1 != s2

    def test_preamble_change_does_not_affect_signature(self):
        content_a = (
            "# Title A\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nBody\n<!-- @specbox:zone end -->\n"
        )
        content_b = (
            "# Title B\n\n"  # different preamble + extra blank line
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nBody\n<!-- @specbox:zone end -->\n"
        )
        s1 = compute_signature(parse_document(Path("d.md"), content=content_a))
        s2 = compute_signature(parse_document(Path("d.md"), content=content_b))
        assert s1 == s2

    def test_zone_order_does_not_affect_signature(self):
        content_a = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nA\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"b\" -->\nB\n<!-- @specbox:zone end -->\n"
        )
        content_b = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"b\" -->\nB\n<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nA\n<!-- @specbox:zone end -->\n"
        )
        s1 = compute_signature(parse_document(Path("d.md"), content=content_a))
        s2 = compute_signature(parse_document(Path("d.md"), content=content_b))
        assert s1 == s2

    def test_kind_change_changes_signature(self):
        content_a = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nX\n<!-- @specbox:zone end -->\n"
        )
        content_b = (
            "<!-- @specbox:zone start kind=\"auto\" id=\"a\" -->\nX\n<!-- @specbox:zone end -->\n"
        )
        s1 = compute_signature(parse_document(Path("d.md"), content=content_a))
        s2 = compute_signature(parse_document(Path("d.md"), content=content_b))
        assert s1 != s2


# ── Replace zone body ────────────────────────────────────────────────


class TestReplaceZoneBody:
    def test_replaces_only_target_zone(self):
        content = (
            "# Header\n"
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\n"
            "Old A\n"
            "<!-- @specbox:zone end -->\n"
            "<!-- @specbox:zone start kind=\"auto\" id=\"b\" -->\n"
            "Old B\n"
            "<!-- @specbox:zone end -->\n"
        )
        new = replace_zone_body(content, "b", "Brand new B body")
        assert "Old A" in new
        assert "Old B" not in new
        assert "Brand new B body" in new
        # Markers preserved
        assert "<!-- @specbox:zone start kind=\"auto\" id=\"b\" -->" in new
        assert new.count("<!-- @specbox:zone end -->") == 2

    def test_preserves_trailing_newline(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nX\n<!-- @specbox:zone end -->\n"
        )
        new = replace_zone_body(content, "a", "Y")
        assert new.endswith("\n")

    def test_unknown_zone_raises_keyerror(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nX\n<!-- @specbox:zone end -->\n"
        )
        with pytest.raises(KeyError):
            replace_zone_body(content, "ghost", "Y")

    def test_empty_new_body_collapses_zone(self):
        content = (
            "<!-- @specbox:zone start kind=\"manual\" id=\"a\" -->\nOld\n<!-- @specbox:zone end -->\n"
        )
        new = replace_zone_body(content, "a", "")
        assert "Old" not in new
        assert "<!-- @specbox:zone start" in new
        assert "<!-- @specbox:zone end -->" in new


# ── Round-trip with shipped templates ────────────────────────────────


class TestTemplates:
    """Sanity check: shipped templates must parse and validate."""

    def _read(self, name: str) -> str:
        repo_root = Path(__file__).resolve().parent.parent
        return (repo_root / "templates" / name).read_text(encoding="utf-8")

    def test_app_prd_template_parses(self):
        doc = parse_document(Path("templates/app_prd.md.template"), content=self._read("app_prd.md.template"))
        assert doc.is_well_formed, doc.errors
        # Required zones for PRD per the v5.29 plan
        ids = {z.id for z in doc.zones}
        assert {"vision", "audience", "scope", "success_metrics", "roadmap", "stakeholders"} <= ids

    def test_app_spec_template_parses(self):
        doc = parse_document(Path("templates/app_spec.md.template"), content=self._read("app_spec.md.template"))
        assert doc.is_well_formed, doc.errors
        ids = {z.id for z in doc.zones}
        assert {"stack", "tracking_backend", "brand_visual", "conventions", "autopilot", "canonical_decisions"} <= ids

    def test_app_prd_required_kinds(self):
        doc = parse_document(Path("templates/app_prd.md.template"), content=self._read("app_prd.md.template"))
        issues = validate_document(
            doc,
            required_zones={
                "vision": ZoneKind.MANUAL,
                "audience": ZoneKind.MANUAL,
                "scope": ZoneKind.MANUAL,
                "success_metrics": ZoneKind.HYBRID,
                "roadmap": ZoneKind.AUTO,
                "stakeholders": ZoneKind.MANUAL,
            },
        )
        errors = [i for i in issues if i.severity == "error"]
        assert errors == [], errors

    def test_app_spec_required_kinds(self):
        doc = parse_document(Path("templates/app_spec.md.template"), content=self._read("app_spec.md.template"))
        issues = validate_document(
            doc,
            required_zones={
                "stack": ZoneKind.AUTO,
                "tracking_backend": ZoneKind.AUTO,
                "brand_visual": ZoneKind.MANUAL,
                "conventions": ZoneKind.MANUAL,
                "autopilot": ZoneKind.AUTO,
                "canonical_decisions": ZoneKind.HYBRID,
            },
        )
        errors = [i for i in issues if i.severity == "error"]
        assert errors == [], errors
