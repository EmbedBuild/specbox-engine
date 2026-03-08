"""Tests for tools/use_case.py — list_uc, get_uc, move_uc, start_uc, complete_uc."""

import pytest
from unittest.mock import AsyncMock, patch

from src.tools.use_case import list_uc, get_uc, move_uc, start_uc, complete_uc


def _patch_client(mock_trello_client):
    async def _get(ctx):
        return mock_trello_client
    return patch("src.tools.use_case.get_session_client", side_effect=_get)


class TestListUc:
    async def test_lists_all(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await list_uc("board123", mock_ctx)
        assert len(result) == 1
        assert result[0]["uc_id"] == "UC-001"

    async def test_filter_by_us_id(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await list_uc("board123", mock_ctx, us_id="US-01")
        assert len(result) == 1

    async def test_filter_by_wrong_us_id(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await list_uc("board123", mock_ctx, us_id="US-99")
        assert len(result) == 0

    async def test_filter_by_status(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await list_uc("board123", mock_ctx, status="backlog")
        assert len(result) == 1

    async def test_filter_by_wrong_status(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await list_uc("board123", mock_ctx, status="done")
        assert len(result) == 0

    async def test_combined_filter(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await list_uc("board123", mock_ctx, us_id="US-01", status="backlog")
        assert len(result) == 1

    async def test_empty_board(self, mock_trello_client, mock_ctx):
        mock_trello_client.get_board_cards.return_value = []
        with _patch_client(mock_trello_client):
            result = await list_uc("board123", mock_ctx)
        assert result == []


class TestGetUc:
    async def test_returns_detail(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_uc("board123", "UC-001", mock_ctx)
        assert result["uc_id"] == "UC-001"
        assert result["us_id"] == "US-01"
        assert result["status"] == "backlog"
        assert len(result["acceptance_criteria"]) == 3
        assert "trello_card_id" in result
        assert "trello_card_url" in result

    async def test_includes_context(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_uc("board123", "UC-001", mock_ctx)
        assert "Supabase" in result["context"]

    async def test_not_found(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_uc("board123", "UC-999", mock_ctx)
        assert result["code"] == "UC_NOT_FOUND"

    async def test_includes_attachments(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_uc("board123", "UC-001", mock_ctx)
        assert len(result["attachments"]) == 1

    async def test_includes_us_name(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_uc("board123", "UC-001", mock_ctx)
        assert result["us_name"] != ""


class TestMoveUc:
    async def test_move_to_ready(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await move_uc("board123", "UC-001", "ready", mock_ctx)
        assert result["uc_id"] == "UC-001"
        assert result["new_status"] == "ready"

    async def test_move_to_done_updates_checklist(self, mock_trello_client, mock_ctx, sample_us_checklist):
        mock_trello_client.get_card_checklists.return_value = sample_us_checklist
        with _patch_client(mock_trello_client):
            result = await move_uc("board123", "UC-001", "done", mock_ctx)
        assert result["new_status"] == "done"
        assert result["us_checklist_updated"] is True

    async def test_not_found(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await move_uc("board123", "UC-999", "ready", mock_ctx)
        assert result["code"] == "UC_NOT_FOUND"

    async def test_invalid_target(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await move_uc("board123", "UC-001", "invalid", mock_ctx)
        assert result["code"] == "INVALID_TARGET"


class TestStartUc:
    async def test_starts_uc(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await start_uc("board123", "UC-001", mock_ctx)
        assert result["uc_id"] == "UC-001"
        mock_trello_client.move_card.assert_called()
        mock_trello_client.add_comment.assert_called()

    async def test_not_found(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await start_uc("board123", "UC-999", mock_ctx)
        assert result["code"] == "UC_NOT_FOUND"


class TestCompleteUc:
    async def test_completes_uc(self, mock_trello_client, mock_ctx, sample_us_checklist):
        mock_trello_client.get_card_checklists.return_value = sample_us_checklist
        with _patch_client(mock_trello_client):
            result = await complete_uc("board123", "UC-001", mock_ctx)
        assert result["uc_id"] == "UC-001"
        assert "completed_at" in result
        assert result["us_id"] == "US-01"

    async def test_with_evidence(self, mock_trello_client, mock_ctx, sample_us_checklist):
        mock_trello_client.get_card_checklists.return_value = sample_us_checklist
        with _patch_client(mock_trello_client):
            result = await complete_uc("board123", "UC-001", mock_ctx, evidence="All tests passing")
        assert result["uc_id"] == "UC-001"
        calls = mock_trello_client.add_comment.call_args_list
        evidence_call = [c for c in calls if "All tests passing" in str(c)]
        assert len(evidence_call) > 0

    async def test_not_found(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await complete_uc("board123", "UC-999", mock_ctx)
        assert result["code"] == "UC_NOT_FOUND"

    async def test_all_done_triggers_comment(self, mock_trello_client, mock_ctx, sample_us_card, sample_uc_card, sample_us_checklist):
        uc_done = dict(sample_uc_card)
        uc_done["idList"] = "list_done"
        mock_trello_client.get_board_cards.return_value = [sample_us_card, uc_done]
        mock_trello_client.get_card_checklists.return_value = sample_us_checklist
        with _patch_client(mock_trello_client):
            result = await complete_uc("board123", "UC-001", mock_ctx)
        assert result["us_all_done"] is True
