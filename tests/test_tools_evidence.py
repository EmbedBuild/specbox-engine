"""Tests for tools/evidence.py — attach_evidence, get_evidence."""

import pytest
from unittest.mock import AsyncMock, patch

from src.tools.evidence import attach_evidence, get_evidence


def _patch_client(mock_trello_client):
    async def _get(ctx):
        return mock_trello_client
    return patch("src.tools.evidence.get_session_client", side_effect=_get)


class TestAttachEvidence:
    async def test_attach_prd(self, mock_trello_client, mock_ctx):
        md = "# PRD\n\nProject requirements..."
        with _patch_client(mock_trello_client):
            result = await attach_evidence("board123", "UC-001", "uc", "prd", md, mock_ctx)
        assert result["target_id"] == "UC-001"
        assert result["evidence_type"] == "prd"
        assert result["comment_added"] is True
        mock_trello_client.add_attachment.assert_called_once()

    async def test_attach_with_summary(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await attach_evidence("board123", "US-01", "us", "delivery", "# Report", mock_ctx, summary="Sprint 1 done")
        assert result["comment_added"] is True
        calls = mock_trello_client.add_comment.call_args_list
        assert "Sprint 1 done" in str(calls[0])

    async def test_invalid_target_type(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await attach_evidence("board123", "X", "invalid", "prd", "md", mock_ctx)
        assert result["code"] == "INVALID_TARGET_TYPE"

    async def test_invalid_evidence_type(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await attach_evidence("board123", "UC-001", "uc", "invalid", "md", mock_ctx)
        assert result["code"] == "INVALID_EVIDENCE_TYPE"

    async def test_target_not_found(self, mock_trello_client, mock_ctx):
        mock_trello_client.get_board_cards.return_value = []
        with _patch_client(mock_trello_client):
            result = await attach_evidence("board123", "UC-999", "uc", "prd", "md", mock_ctx)
        assert result["code"] == "TARGET_NOT_FOUND"

    async def test_all_evidence_types(self, mock_trello_client, mock_ctx):
        for etype in ["prd", "plan", "ag09", "delivery", "feedback"]:
            with _patch_client(mock_trello_client):
                result = await attach_evidence("board123", "UC-001", "uc", etype, "# Content", mock_ctx)
            assert result["evidence_type"] == etype


class TestGetEvidence:
    async def test_returns_attachments(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_evidence("board123", "UC-001", "uc", mock_ctx)
        assert result["target_id"] == "UC-001"
        assert len(result["attachments"]) == 1
        assert len(result["activity"]) == 1

    async def test_filter_by_type(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_evidence("board123", "UC-001", "uc", mock_ctx, evidence_type="prd")
        assert len(result["attachments"]) == 1

    async def test_filter_no_match(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_evidence("board123", "UC-001", "uc", mock_ctx, evidence_type="nonexistent")
        assert len(result["attachments"]) == 0

    async def test_invalid_target_type(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_evidence("board123", "X", "invalid", mock_ctx)
        assert result["code"] == "INVALID_TARGET_TYPE"

    async def test_not_found(self, mock_trello_client, mock_ctx):
        mock_trello_client.get_board_cards.return_value = []
        with _patch_client(mock_trello_client):
            result = await get_evidence("board123", "UC-999", "uc", mock_ctx)
        assert result["code"] == "TARGET_NOT_FOUND"
