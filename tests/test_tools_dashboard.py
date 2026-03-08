"""Tests for tools/dashboard.py — get_sprint_status, get_delivery_report, find_next_uc."""

import pytest
from unittest.mock import AsyncMock, patch

from src.tools.dashboard import get_sprint_status, get_delivery_report, find_next_uc


from contextlib import contextmanager

@contextmanager
def _patch_client(mock_trello_client):
    """Patch get_session_client in both dashboard and use_case (find_next_uc calls get_uc)."""
    async def _get(ctx):
        return mock_trello_client
    with patch("src.tools.dashboard.get_session_client", side_effect=_get), \
         patch("src.tools.use_case.get_session_client", side_effect=_get):
        yield


class TestGetSprintStatus:
    async def test_returns_dashboard(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_sprint_status("board123", mock_ctx)
        assert result["board_name"] == "TALENT-ON"
        assert result["total_us"] == 1
        assert result["total_uc"] == 1
        assert "by_status" in result
        assert "hours" in result
        assert "acs" in result

    async def test_by_status_structure(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_sprint_status("board123", mock_ctx)
        assert "backlog" in result["by_status"]
        assert result["by_status"]["backlog"]["us"] == 1
        assert result["by_status"]["backlog"]["uc"] == 1

    async def test_hours_calculation(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_sprint_status("board123", mock_ctx)
        assert result["hours"]["total"] == 3.0
        assert result["hours"]["done"] == 0
        assert result["hours"]["pct"] == 0

    async def test_with_done_cards(self, mock_trello_client, mock_ctx, sample_us_card, sample_uc_card):
        uc_done = dict(sample_uc_card)
        uc_done["id"] = "card_uc_done"
        uc_done["idList"] = "list_done"
        mock_trello_client.get_board_cards.return_value = [sample_us_card, sample_uc_card, uc_done]
        with _patch_client(mock_trello_client):
            result = await get_sprint_status("board123", mock_ctx)
        assert result["hours"]["done"] == 3.0
        assert result["total_uc"] == 2

    async def test_blocked_detection(self, mock_trello_client, mock_ctx, sample_us_card, sample_uc_card):
        blocked_uc = dict(sample_uc_card)
        blocked_uc["id"] = "card_blocked"
        blocked_uc["labels"] = [
            {"id": "label_uc", "name": "UC", "color": "green"},
            {"id": "label_blocked", "name": "Bloqueado", "color": "red"},
        ]
        mock_trello_client.get_board_cards.return_value = [sample_us_card, blocked_uc]
        with _patch_client(mock_trello_client):
            result = await get_sprint_status("board123", mock_ctx)
        assert len(result["blocked"]) == 1

    async def test_empty_board(self, mock_trello_client, mock_ctx):
        mock_trello_client.get_board_cards.return_value = []
        with _patch_client(mock_trello_client):
            result = await get_sprint_status("board123", mock_ctx)
        assert result["total_us"] == 0
        assert result["total_uc"] == 0

    async def test_acs_count(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_sprint_status("board123", mock_ctx)
        assert result["acs"]["total"] == 3
        assert result["acs"]["passed"] == 1


class TestGetDeliveryReport:
    async def test_returns_report(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_delivery_report("board123", mock_ctx)
        assert result["project"] == "TALENT-ON"
        assert "generated_at" in result
        assert result["summary"]["total_us"] == 1
        assert len(result["user_stories"]) == 1

    async def test_us_detail(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_delivery_report("board123", mock_ctx)
        us = result["user_stories"][0]
        assert us["us_id"] == "US-01"
        assert us["ucs_completed"] == "0/1"

    async def test_completed_percentage(self, mock_trello_client, mock_ctx, sample_us_card):
        us_done = dict(sample_us_card)
        us_done["idList"] = "list_done"
        mock_trello_client.get_board_cards.return_value = [us_done]
        with _patch_client(mock_trello_client):
            result = await get_delivery_report("board123", mock_ctx)
        assert result["summary"]["completed_us"] == 1
        assert result["summary"]["pct"] == 100.0

    async def test_empty_board(self, mock_trello_client, mock_ctx):
        mock_trello_client.get_board_cards.return_value = []
        with _patch_client(mock_trello_client):
            result = await get_delivery_report("board123", mock_ctx)
        assert result["summary"]["total_us"] == 0
        assert result["summary"]["pct"] == 0


class TestFindNextUc:
    async def test_no_ready_ucs(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await find_next_uc("board123", mock_ctx)
        assert result is None

    async def test_finds_ready_uc(self, mock_trello_client, mock_ctx, sample_us_card, sample_uc_card):
        uc_ready = dict(sample_uc_card)
        uc_ready["idList"] = "list_ready"
        mock_trello_client.get_board_cards.return_value = [sample_us_card, uc_ready]
        with _patch_client(mock_trello_client):
            result = await find_next_uc("board123", mock_ctx)
        assert result is not None
        assert result["uc_id"] == "UC-001"

    async def test_priority_focus_on_active_us(self, mock_trello_client, mock_ctx, sample_us_card, sample_uc_card, sample_custom_fields):
        uc_ip = dict(sample_uc_card)
        uc_ip["id"] = "card_uc_ip"
        uc_ip["idList"] = "list_ip"
        uc_ip["customFieldItems"] = [
            {"idCustomField": "cf_tipo", "idValue": "opt_uc"},
            {"idCustomField": "cf_uc_id", "value": {"text": "UC-002"}},
            {"idCustomField": "cf_us_id", "value": {"text": "US-01"}},
            {"idCustomField": "cf_horas", "value": {"number": "2"}},
            {"idCustomField": "cf_pantallas", "value": {"text": "1B"}},
        ]

        uc_ready = dict(sample_uc_card)
        uc_ready["id"] = "card_uc_ready"
        uc_ready["idList"] = "list_ready"
        uc_ready["customFieldItems"] = [
            {"idCustomField": "cf_tipo", "idValue": "opt_uc"},
            {"idCustomField": "cf_uc_id", "value": {"text": "UC-003"}},
            {"idCustomField": "cf_us_id", "value": {"text": "US-01"}},
            {"idCustomField": "cf_horas", "value": {"number": "2"}},
            {"idCustomField": "cf_pantallas", "value": {"text": "1C"}},
        ]

        mock_trello_client.get_board_cards.return_value = [sample_us_card, uc_ip, uc_ready]

        with _patch_client(mock_trello_client):
            result = await find_next_uc("board123", mock_ctx)
        assert result is not None
        assert result["uc_id"] == "UC-003"

    async def test_empty_board(self, mock_trello_client, mock_ctx):
        mock_trello_client.get_board_cards.return_value = []
        with _patch_client(mock_trello_client):
            result = await find_next_uc("board123", mock_ctx)
        assert result is None
