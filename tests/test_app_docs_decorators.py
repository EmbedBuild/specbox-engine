"""Tests for the @requires_app_docs_sync decorator (v5.29.0 PR-12)."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from server.app_docs.decorators import (
    extract_canonical_event_payload,
    extract_set_auth_token_payload,
    extract_uc_event_payload,
    requires_app_docs_sync,
    skip_when_tool_errored,
)


def _seed_app_spec(path: Path) -> None:
    path.write_text(
        "<!-- @specbox:zone start kind=\"auto\" id=\"stack\" -->\n## 1. Stack\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"auto\" id=\"tracking_backend\" -->\n## 2. Tracking backend\n- Tipo: trello\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"brand_visual\" -->\nb\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"conventions\" -->\nc\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"auto\" id=\"autopilot\" -->\n## 5. Autopilot\n- Level: low\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"hybrid\" id=\"canonical_decisions\" -->\nd\n<!-- @specbox:zone end -->\n",
        encoding="utf-8",
    )


def _seed_app_prd(path: Path) -> None:
    path.write_text(
        "<!-- @specbox:zone start kind=\"manual\" id=\"vision\" -->\nv\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"audience\" -->\na\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"scope\" -->\ns\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"hybrid\" id=\"success_metrics\" -->\nm\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"auto\" id=\"roadmap\" -->\n## 5. Roadmap\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"stakeholders\" -->\np\n<!-- @specbox:zone end -->\n",
        encoding="utf-8",
    )


# ── Sync tool decoration ─────────────────────────────────────────────


class TestSyncToolDecorator:
    def test_successful_sync_annotates_dict_result(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_spec(app / "app_spec.md")

        @requires_app_docs_sync(
            "set_auth_token",
            payload_extractor=extract_set_auth_token_payload,
        )
        def fake_set_auth_token(*, backend_type: str, project_path: str = "."):
            return {"success": True, "message": f"FreeForm backend initialized at {project_path}/doc/tracking/"}

        result = fake_set_auth_token(backend_type="freeform", project_path=str(tmp_path))
        assert "app_docs_sync" in result
        assert result["app_docs_sync"]["ok"] is True
        new_spec = (app / "app_spec.md").read_text()
        assert "freeform" in new_spec.lower()

    def test_failed_payload_extractor_annotates_failure(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_spec(app / "app_spec.md")

        @requires_app_docs_sync(
            "set_auth_token",
            payload_extractor=lambda *a, **kw: 1 / 0,  # raises
        )
        def fake_tool(**kwargs):
            return {"success": True}

        result = fake_tool(project_path=str(tmp_path))
        assert result["app_docs_sync"]["ok"] is False
        assert result["app_docs_sync"]["error"] == "payload_extractor_failed"

    def test_skip_when_tool_errored(self, tmp_path):
        @requires_app_docs_sync(
            "set_auth_token",
            payload_extractor=extract_set_auth_token_payload,
            skip_when=skip_when_tool_errored,
        )
        def fake_failing_tool(**kwargs):
            return {"error": "something_went_wrong"}

        result = fake_failing_tool(project_path=str(tmp_path), backend_type="freeform")
        assert "app_docs_sync" not in result, "skip_when must short-circuit"

    def test_strict_mode_promotes_failure_to_top_level(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SPECBOX_APP_DOCS_STRICT_SYNC", "true")

        @requires_app_docs_sync(
            "set_auth_token",
            payload_extractor=lambda *a, **kw: 1 / 0,
        )
        def fake_tool(**kwargs):
            return {"success": True}

        result = fake_tool(project_path=str(tmp_path))
        assert result.get("ok") is False
        assert result.get("error") == "payload_extractor_failed"

    def test_non_dict_result_not_mutated_on_success(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_spec(app / "app_spec.md")

        @requires_app_docs_sync(
            "set_auth_token",
            payload_extractor=lambda *a, **kw: {"backend_type": "freeform"},
        )
        def fake_tool(**kwargs) -> str:
            return "plain string return"

        result = fake_tool(project_path=str(tmp_path))
        assert result == "plain string return"


# ── Async tool decoration ────────────────────────────────────────────


class TestAsyncToolDecorator:
    @pytest.mark.asyncio
    async def test_async_decorator_runs_sync_after_tool(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_prd(app / "app_prd.md")

        rows = [{"us_id": "US-01", "title": "x", "state": "done", "uc_count": 1, "updated_at": "2026-05-02"}]

        @requires_app_docs_sync(
            "complete_uc",
            payload_extractor=lambda result, *a, **kw: {"rows": rows},
        )
        async def fake_complete_uc(uc_id: str, project_path: str = "."):
            await asyncio.sleep(0)
            return {"ok": True, "uc_id": uc_id}

        result = await fake_complete_uc("UC-007", project_path=str(tmp_path))
        assert "app_docs_sync" in result
        assert result["app_docs_sync"]["ok"] is True


# ── Payload extractors ───────────────────────────────────────────────


class TestExtractors:
    def test_set_auth_token_extractor_freeform(self):
        result = {"message": "FreeForm backend initialized at /Users/x/proj/doc/tracking/"}
        payload = extract_set_auth_token_payload(result, backend_type="freeform")
        assert payload["backend_type"] == "freeform"
        assert payload["freeform_root_absolute"] == "/Users/x/proj/doc/tracking"
        assert payload["external_reporting"] == "no"

    def test_set_auth_token_extractor_trello(self):
        result = {"success": True}
        payload = extract_set_auth_token_payload(result, backend_type="trello", board_id="abc")
        assert payload["backend_type"] == "trello"
        assert payload["trello_board_id"] == "abc"
        assert payload["external_reporting"] == "yes"

    def test_uc_event_extractor_passes_roadmap_rows(self):
        rows = [{"us_id": "US-99", "title": "x", "state": "done", "uc_count": 2, "updated_at": "2026-05-02"}]
        payload = extract_uc_event_payload({}, roadmap_rows=rows)
        assert payload["rows"] == rows

    def test_canonical_event_extractor_active_only(self):
        result = {"canonical": {"decision_key": "veg_mode_selection", "value": "per_icp", "promoted_at": "2026", "confirmations": 3}}
        payload = extract_canonical_event_payload(result)
        assert len(payload["entries"]) == 1
        assert payload["entries"][0]["decision_key"] == "veg_mode_selection"

    def test_canonical_event_extractor_no_canonical(self):
        result = {"canonical": None}
        payload = extract_canonical_event_payload(result)
        assert payload["entries"] == []
