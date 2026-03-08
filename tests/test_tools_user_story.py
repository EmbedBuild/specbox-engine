"""Tests for tools/user_story.py — list_us, get_us, move_us, get_us_progress."""

import pytest
from unittest.mock import AsyncMock, patch

from src.tools.user_story import list_us, get_us, move_us, get_us_progress


def _patch_client(mock_trello_client):
    async def _get(ctx):
        return mock_trello_client
    return patch("src.tools.user_story.get_session_client", side_effect=_get)


class TestListUs:
    async def test_lists_all(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await list_us("board123", mock_ctx)
        assert len(result) == 1
        assert result[0]["us_id"] == "US-01"
        assert result[0]["status"] == "backlog"

    async def test_filter_by_status(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await list_us("board123", mock_ctx, status="done")
        assert len(result) == 0

    async def test_filter_matching(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await list_us("board123", mock_ctx, status="backlog")
        assert len(result) == 1

    async def test_includes_uc_counts(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await list_us("board123", mock_ctx)
        assert result[0]["uc_total"] == 1
        assert result[0]["ac_total"] == 3  # 3 ACs in sample checklist

    async def test_empty_board(self, mock_trello_client, mock_ctx):
        mock_trello_client.get_board_cards.return_value = []
        with _patch_client(mock_trello_client):
            result = await list_us("board123", mock_ctx)
        assert result == []


class TestGetUs:
    async def test_returns_detail(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_us("board123", "US-01", mock_ctx)
        assert result["us_id"] == "US-01"
        assert len(result["use_cases"]) == 1
        assert result["use_cases"][0]["uc_id"] == "UC-001"

    async def test_not_found(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_us("board123", "US-99", mock_ctx)
        assert result["code"] == "US_NOT_FOUND"

    async def test_includes_attachments(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_us("board123", "US-01", mock_ctx)
        assert len(result["attachments"]) == 1


class TestMoveUs:
    async def test_move_to_backlog(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await move_us("board123", "US-01", "backlog", mock_ctx)
        assert result["us_id"] == "US-01"
        assert result["new_status"] == "backlog"
        assert result["ucs_moved"] == 1

    async def test_move_to_ready(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await move_us("board123", "US-01", "ready", mock_ctx)
        assert result["new_status"] == "ready"
        assert result["ucs_moved"] == 1

    async def test_move_to_in_progress(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await move_us("board123", "US-01", "in_progress", mock_ctx)
        assert result["new_status"] == "in_progress"
        assert result["ucs_moved"] == 1

    async def test_move_to_review_blocked(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await move_us("board123", "US-01", "review", mock_ctx)
        assert result["code"] == "UC_NOT_READY_FOR_REVIEW"

    async def test_move_to_review_allowed(self, mock_trello_client, mock_ctx, sample_us_card, sample_uc_card):
        uc_in_review = dict(sample_uc_card)
        uc_in_review["idList"] = "list_review"
        mock_trello_client.get_board_cards.return_value = [sample_us_card, uc_in_review]
        with _patch_client(mock_trello_client):
            result = await move_us("board123", "US-01", "review", mock_ctx)
        assert result["new_status"] == "review"

    async def test_move_to_done_blocked(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await move_us("board123", "US-01", "done", mock_ctx)
        assert result["code"] == "UC_NOT_DONE"

    async def test_move_to_done_allowed(self, mock_trello_client, mock_ctx, sample_us_card, sample_uc_card):
        uc_done = dict(sample_uc_card)
        uc_done["idList"] = "list_done"
        mock_trello_client.get_board_cards.return_value = [sample_us_card, uc_done]
        with _patch_client(mock_trello_client):
            result = await move_us("board123", "US-01", "done", mock_ctx)
        assert result["new_status"] == "done"

    async def test_invalid_target(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await move_us("board123", "US-01", "invalid", mock_ctx)
        assert result["code"] == "INVALID_TARGET"

    async def test_us_not_found(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await move_us("board123", "US-99", "backlog", mock_ctx)
        assert result["code"] == "US_NOT_FOUND"


class TestGetUsProgress:
    async def test_returns_progress(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_us_progress("board123", "US-01", mock_ctx)
        assert result["us_id"] == "US-01"
        assert result["total_ucs"] == 1
        assert result["total_acs"] == 3
        assert result["passed_acs"] == 1  # 1 AC is complete in sample

    async def test_not_found(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_us_progress("board123", "US-99", mock_ctx)
        assert result["code"] == "US_NOT_FOUND"

    async def test_done_hours(self, mock_trello_client, mock_ctx, sample_us_card, sample_uc_card):
        uc_done = dict(sample_uc_card)
        uc_done["idList"] = "list_done"
        mock_trello_client.get_board_cards.return_value = [sample_us_card, uc_done]
        with _patch_client(mock_trello_client):
            result = await get_us_progress("board123", "US-01", mock_ctx)
        assert result["hours_done"] == 3.0
