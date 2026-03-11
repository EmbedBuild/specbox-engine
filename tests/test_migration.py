"""Tests for migration tools — bidirectional Trello ↔ Plane migration."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import field

from src.tools.migration import (
    _classify_items,
    _build_external_id,
    _read_source,
    migrate_preview,
    switch_backend,
)
from src.spec_backend import ItemDTO, ChecklistItemDTO, CommentDTO


# ── _classify_items ──────────────────────────────────────────────────


class TestClassifyItems:
    def test_classify_items(self):
        """Mixed items are sorted into US, UC, AC, other buckets."""
        items = [
            ItemDTO(id="1", name="US-01: Login", labels=["US"]),
            ItemDTO(id="2", name="UC-001: Submit form", labels=["UC"]),
            ItemDTO(id="3", name="AC-01: Field validation", labels=["AC"]),
            ItemDTO(id="4", name="UC-002: Logout", labels=["uc"]),  # lowercase
            ItemDTO(id="5", name="Some task", labels=["bug"]),
            ItemDTO(id="6", name="US-02: Dashboard", labels=["Us"]),  # mixed case
        ]

        result = _classify_items(items)

        assert len(result["us"]) == 2
        assert len(result["uc"]) == 2
        assert len(result["ac"]) == 1
        assert len(result["other"]) == 1

        assert result["us"][0].id == "1"
        assert result["us"][1].id == "6"
        assert result["uc"][0].id == "2"
        assert result["uc"][1].id == "4"
        assert result["ac"][0].id == "3"
        assert result["other"][0].id == "5"

    def test_classify_items_empty(self):
        """Empty list returns empty buckets."""
        result = _classify_items([])
        assert result == {"us": [], "uc": [], "ac": [], "other": []}


# ── _build_external_id ───────────────────────────────────────────────


class TestBuildExternalId:
    def test_build_external_id(self):
        """External ID is 'source_type:item_id'."""
        assert _build_external_id("trello", "abc123") == "trello:abc123"
        assert _build_external_id("plane", "xyz") == "plane:xyz"


# ── _read_source ─────────────────────────────────────────────────────


class TestReadSource:
    async def test_read_source(self):
        """Reads items, ACs, comments, labels, states from a backend."""
        us_item = ItemDTO(id="us1", name="US-01: Feature", labels=["US"])
        uc_item = ItemDTO(id="uc1", name="UC-001: Step", labels=["UC"], parent_id="us1")
        other_item = ItemDTO(id="o1", name="Bug fix", labels=["bug"])

        ac1 = ChecklistItemDTO(id="ac1", text="AC-01: Field required", done=False, backend_id="b1")
        ac2 = ChecklistItemDTO(id="ac2", text="AC-02: Valid email", done=True, backend_id="b2")

        comment = CommentDTO(id="c1", text="Progress update", created_at="2025-01-01", author="dev")

        backend = AsyncMock()
        backend.list_items = AsyncMock(return_value=[us_item, uc_item, other_item])
        backend.get_acceptance_criteria = AsyncMock(return_value=[ac1, ac2])
        backend.get_comments = AsyncMock(side_effect=lambda board, item_id: [comment] if item_id == "us1" else [])
        backend.get_labels = AsyncMock(return_value=[{"name": "US"}, {"name": "UC"}])
        backend.get_states = AsyncMock(return_value={"backlog": "Backlog", "done": "Done"})
        backend.get_board_name = AsyncMock(return_value="Test Board")

        result = await _read_source(backend, "board123")

        # Verify structure
        assert result["board_name"] == "Test Board"
        assert len(result["items"]) == 3
        assert len(result["classified"]["us"]) == 1
        assert len(result["classified"]["uc"]) == 1
        assert len(result["classified"]["other"]) == 1

        # AC data for the UC
        assert "uc1" in result["ac_data"]
        assert len(result["ac_data"]["uc1"]) == 2
        assert result["ac_data"]["uc1"][0]["text"] == "AC-01: Field required"
        assert result["ac_data"]["uc1"][1]["done"] is True

        # Comments for US
        assert "us1" in result["comments_data"]
        assert len(result["comments_data"]["us1"]) == 1
        assert result["comments_data"]["us1"][0]["text"] == "Progress update"

        # Labels and states
        assert result["labels"] == [{"name": "US"}, {"name": "UC"}]
        assert result["states"] == {"backlog": "Backlog", "done": "Done"}


# ── migrate_preview ──────────────────────────────────────────────────


class TestMigratePreview:
    async def test_migrate_preview(self):
        """Dry-run preview returns counts and hierarchy."""
        us_item = ItemDTO(id="us1", name="US-01: Login", labels=["US"], state="backlog")
        uc_item = ItemDTO(
            id="uc1", name="UC-001: Submit", labels=["UC"],
            parent_id="us1", state="in_progress", meta={"us_id": "US-01"},
        )

        ac1 = ChecklistItemDTO(id="ac1", text="AC-01: Required", done=False, backend_id="b1")

        mock_backend = AsyncMock()
        mock_backend.list_items = AsyncMock(return_value=[us_item, uc_item])
        mock_backend.get_acceptance_criteria = AsyncMock(return_value=[ac1])
        mock_backend.get_comments = AsyncMock(return_value=[])
        mock_backend.get_labels = AsyncMock(return_value=[{"name": "US"}, {"name": "UC"}])
        mock_backend.get_states = AsyncMock(return_value={"backlog": "Backlog", "in_progress": "In Progress"})
        mock_backend.get_board_name = AsyncMock(return_value="My Project")
        mock_backend.close = AsyncMock()

        ctx = AsyncMock()

        with patch("src.tools.migration.get_session_backend", return_value=mock_backend):
            result = await migrate_preview(
                source_type="trello",
                source_id="board1",
                target_type="plane",
                ctx=ctx,
            )

        assert result["dry_run"] is True
        assert result["source"]["type"] == "trello"
        assert result["source"]["name"] == "My Project"
        assert result["target"]["type"] == "plane"
        assert result["counts"]["user_stories"] == 1
        assert result["counts"]["use_cases"] == 1
        assert result["counts"]["acceptance_criteria"] == 1

        # Hierarchy
        assert len(result["hierarchy"]) == 1
        us = result["hierarchy"][0]
        assert us["us_id"] == "US-01"
        assert us["uc_count"] == 1

        mock_backend.close.assert_awaited_once()

    async def test_migrate_preview_same_type_error(self):
        """source_type == target_type returns error."""
        ctx = AsyncMock()
        result = await migrate_preview(
            source_type="trello",
            source_id="board1",
            target_type="trello",
            ctx=ctx,
        )
        assert "error" in result


# ── switch_backend ───────────────────────────────────────────────────


class TestSwitchBackendValidation:
    async def test_switch_backend_validation(self):
        """Invalid backend_type returns error dict."""
        ctx = AsyncMock()
        result = await switch_backend(
            project_slug="my-proj",
            backend_type="jira",
            board_id="b1",
            ctx=ctx,
        )
        assert "error" in result
        assert "Invalid backend_type" in result["error"]
        assert "jira" in result["error"]

    async def test_switch_backend_valid_types_accepted(self):
        """Trello and plane are valid types (may fail on missing registry, but not on validation)."""
        ctx = AsyncMock()

        # Both valid types should NOT return the "Invalid backend_type" error
        for valid_type in ("trello", "plane"):
            result = await switch_backend(
                project_slug="test",
                backend_type=valid_type,
                board_id="b1",
                ctx=ctx,
            )
            # May fail for other reasons (missing registry), but NOT for invalid type
            if "error" in result:
                assert "Invalid backend_type" not in result["error"]
