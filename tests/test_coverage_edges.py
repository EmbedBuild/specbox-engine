"""Tests for remaining edge cases to reach 100% coverage."""

import pytest
import httpx
import respx
from unittest.mock import AsyncMock, patch, MagicMock

from src.board_helpers import (
    build_us_description,
    extract_custom_field_value,
    get_card_custom_value,
    build_custom_field_map,
)
from src.trello_client import TrelloClient


# --- board_helpers edge cases ---

class TestBoardHelpersEdges:
    def test_extract_number_invalid(self):
        """Number field with invalid value."""
        card = {"customFieldItems": [{"idCustomField": "cf1", "value": {"number": "invalid"}}]}
        result = extract_custom_field_value(card, "cf1", "number")
        assert result == 0.0

    def test_extract_list_no_custom_fields(self):
        """List field without custom_fields for lookup."""
        card = {"customFieldItems": [{"idCustomField": "cf1", "idValue": "opt1"}]}
        result = extract_custom_field_value(card, "cf1", "list", None)
        assert result == "opt1"

    def test_get_card_custom_value_missing_field(self):
        """Field not in cf_map."""
        card = {"customFieldItems": []}
        cf_map = {}
        result = get_card_custom_value(card, "nonexistent", cf_map, [])
        assert result is None

    def test_build_us_description_no_desc(self):
        """US description without extra description text."""
        desc = build_us_description("US-01", "Auth", 11, "1A")
        assert "## US-01: Auth" in desc
        assert "Descripcion" not in desc


# --- trello_client edge: timeout retry ---

class TestTrelloClientTimeout:
    @respx.mock
    async def test_timeout_retry(self):
        client = TrelloClient(api_key="k", token="t")
        route = respx.get("https://api.trello.com/1/boards/b1")
        route.side_effect = [
            httpx.TimeoutException("timeout"),
            httpx.Response(200, json={"id": "b1"}),
        ]
        result = await client.get_board("b1")
        assert result["id"] == "b1"
        await client.close()

    @respx.mock
    async def test_timeout_exhaust_retries(self):
        client = TrelloClient(api_key="k", token="t")
        respx.get("https://api.trello.com/1/boards/b1").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        with pytest.raises(httpx.TimeoutException):
            await client.get_board("b1")
        await client.close()


# --- board.py helper edges ---

class TestBoardHelperEdges:
    async def test_set_card_type_no_tipo_field(self):
        """_set_card_type when tipo not in cf_map."""
        from src.tools.board import _set_card_type
        client = AsyncMock()
        await _set_card_type(client, "card1", "US", {}, [])
        client.set_custom_field_value.assert_not_called()

    async def test_set_card_type_no_option(self):
        """_set_card_type when option not found."""
        from src.tools.board import _set_card_type
        client = AsyncMock()
        cf_map = {"tipo": {"id": "cf1", "type": "list"}}
        await _set_card_type(client, "card1", "UNKNOWN", cf_map, [])
        client.set_custom_field_value.assert_not_called()

    async def test_set_text_field_empty_value(self):
        """_set_text_field with empty value."""
        from src.tools.board import _set_text_field
        client = AsyncMock()
        cf_map = {"us_id": {"id": "cf1"}}
        await _set_text_field(client, "card1", "us_id", "", cf_map)
        client.set_custom_field_value.assert_not_called()

    async def test_set_text_field_no_field(self):
        """_set_text_field when field not in cf_map."""
        from src.tools.board import _set_text_field
        client = AsyncMock()
        await _set_text_field(client, "card1", "nonexistent", "val", {})
        client.set_custom_field_value.assert_not_called()

    async def test_set_number_field_no_field(self):
        """_set_number_field when field not in cf_map."""
        from src.tools.board import _set_number_field
        client = AsyncMock()
        await _set_number_field(client, "card1", "nonexistent", 5.0, {})
        client.set_custom_field_value.assert_not_called()

    async def test_set_actor_field_no_field(self):
        """_set_actor_field when actor not in cf_map."""
        from src.tools.board import _set_actor_field
        client = AsyncMock()
        await _set_actor_field(client, "card1", "Todos", {}, [])
        client.set_custom_field_value.assert_not_called()

    async def test_set_actor_field_no_option(self):
        """_set_actor_field when option not found."""
        from src.tools.board import _set_actor_field
        client = AsyncMock()
        cf_map = {"actor": {"id": "cf1", "type": "list"}}
        await _set_actor_field(client, "card1", "UNKNOWN", cf_map, [])
        client.set_custom_field_value.assert_not_called()


# --- use_case._update_us_checklist_for_uc edge: US not found ---

class TestUpdateUsChecklistEdge:
    async def test_us_not_found(self):
        from src.tools.use_case import _update_us_checklist_for_uc
        client = AsyncMock()
        # Empty cards — no US found
        result = await _update_us_checklist_for_uc(client, [], {}, [], [], "US-99", "UC-001")
        assert result == (False, False)


# --- dashboard blocked US card detection ---

class TestSprintBlockedUs:
    async def test_blocked_us_card(self, mock_ctx):
        """Blocked US card detected in sprint status."""
        from src.tools.dashboard import get_sprint_status

        mock_client = AsyncMock()
        us_card = {
            "id": "card_us",
            "name": "US-01: Auth",
            "idList": "list_backlog",
            "labels": [
                {"id": "label_us", "name": "US", "color": "blue"},
                {"id": "label_blocked", "name": "Bloqueado", "color": "red"},
            ],
            "customFieldItems": [
                {"idCustomField": "cf_tipo", "idValue": "opt_us"},
                {"idCustomField": "cf_us_id", "value": {"text": "US-01"}},
            ],
        }
        mock_client.get_board.return_value = {"name": "TEST"}
        mock_client.get_board_lists.return_value = [
            {"id": "list_backlog", "name": "User Stories"},
            {"id": "list_done", "name": "Done"},
        ]
        mock_client.get_board_cards.return_value = [us_card]
        mock_client.get_board_custom_fields.return_value = [
            {"id": "cf_tipo", "name": "tipo", "type": "list", "options": [
                {"id": "opt_us", "value": {"text": "US"}},
                {"id": "opt_uc", "value": {"text": "UC"}},
            ]},
            {"id": "cf_us_id", "name": "us_id", "type": "text", "options": []},
        ]
        mock_client.get_board_labels.return_value = [
            {"id": "label_blocked", "name": "Bloqueado", "color": "red"},
        ]
        mock_client.get_card_checklists.return_value = []
        mock_client.close = AsyncMock()

        async def _get(ctx):
            return mock_client
        with patch("src.tools.dashboard.get_session_client", side_effect=_get):
            result = await get_sprint_status("board123", mock_ctx)

        assert len(result["blocked"]) == 1
        assert result["blocked"][0]["id"] == "US-01"
