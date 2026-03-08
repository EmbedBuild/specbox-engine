"""Tests for tools/acceptance.py — mark_ac, mark_ac_batch, get_ac_status."""

import pytest
from unittest.mock import AsyncMock, patch

from src.tools.acceptance import mark_ac, mark_ac_batch, get_ac_status


def _patch_client(mock_trello_client):
    async def _get(ctx):
        return mock_trello_client
    return patch("src.tools.acceptance.get_session_client", side_effect=_get)


class TestMarkAc:
    async def test_mark_passed(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await mark_ac("board123", "UC-001", "AC-01", True, mock_ctx)
        assert result["ac_id"] == "AC-01"
        assert result["passed"] is True
        assert result["ac_total"] == 3
        mock_trello_client.update_checklist_item.assert_called_once()

    async def test_mark_failed(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await mark_ac("board123", "UC-001", "AC-02", False, mock_ctx)
        assert result["passed"] is False

    async def test_with_evidence(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await mark_ac("board123", "UC-001", "AC-01", True, mock_ctx, evidence="Screenshot attached")
        calls = mock_trello_client.add_comment.call_args_list
        comment_text = str(calls[0])
        assert "Screenshot attached" in comment_text

    async def test_uc_not_found(self, mock_trello_client, mock_ctx):
        mock_trello_client.get_board_cards.return_value = []
        with _patch_client(mock_trello_client):
            result = await mark_ac("board123", "UC-999", "AC-01", True, mock_ctx)
        assert result["code"] == "UC_NOT_FOUND"

    async def test_ac_not_found(self, mock_trello_client, mock_ctx):
        mock_trello_client.get_card_checklists.return_value = [
            {"name": "Criterios de Aceptacion", "checkItems": []}
        ]
        with _patch_client(mock_trello_client):
            result = await mark_ac("board123", "UC-001", "AC-99", True, mock_ctx)
        assert result["code"] == "AC_NOT_FOUND"


class TestMarkAcBatch:
    async def test_batch_all_pass(self, mock_trello_client, mock_ctx):
        results = [
            {"ac_id": "AC-01", "passed": True},
            {"ac_id": "AC-02", "passed": True},
            {"ac_id": "AC-03", "passed": True},
        ]
        with _patch_client(mock_trello_client):
            result = await mark_ac_batch("board123", "UC-001", results, mock_ctx)
        assert result["total"] == 3
        assert result["passed"] == 3
        assert result["failed"] == 0
        assert mock_trello_client.add_comment.call_count == 2

    async def test_batch_mixed(self, mock_trello_client, mock_ctx):
        results = [
            {"ac_id": "AC-01", "passed": True},
            {"ac_id": "AC-02", "passed": False},
        ]
        with _patch_client(mock_trello_client):
            result = await mark_ac_batch("board123", "UC-001", results, mock_ctx)
        assert result["passed"] == 1
        assert result["failed"] == 1
        assert mock_trello_client.add_comment.call_count == 1

    async def test_batch_uc_not_found(self, mock_trello_client, mock_ctx):
        mock_trello_client.get_board_cards.return_value = []
        with _patch_client(mock_trello_client):
            result = await mark_ac_batch("board123", "UC-999", [], mock_ctx)
        assert result["code"] == "UC_NOT_FOUND"

    async def test_batch_empty_results(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await mark_ac_batch("board123", "UC-001", [], mock_ctx)
        assert result["total"] == 0
        assert result["passed"] == 0


class TestGetAcStatus:
    async def test_returns_status(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_ac_status("board123", "UC-001", mock_ctx)
        assert result["uc_id"] == "UC-001"
        assert result["total"] == 3
        assert result["done"] == 1
        assert result["pending"] == 2
        assert len(result["criteria"]) == 3

    async def test_uc_not_found(self, mock_trello_client, mock_ctx):
        mock_trello_client.get_board_cards.return_value = []
        with _patch_client(mock_trello_client):
            result = await get_ac_status("board123", "UC-999", mock_ctx)
        assert result["code"] == "UC_NOT_FOUND"
