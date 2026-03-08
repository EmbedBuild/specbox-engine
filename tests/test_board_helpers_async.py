"""Tests for async functions in board_helpers.py."""

import pytest
from unittest.mock import AsyncMock

from src.board_helpers import (
    find_card_by_custom_field,
    get_list_id_by_name,
    get_list_id_for_state,
    get_list_map,
    get_us_children,
)


@pytest.fixture
def mock_client(sample_lists, sample_custom_fields, sample_us_card, sample_uc_card):
    client = AsyncMock()
    client.get_board_lists.return_value = sample_lists
    client.get_board_cards.return_value = [sample_us_card, sample_uc_card]
    client.get_board_custom_fields.return_value = sample_custom_fields
    return client


class TestGetListIdByName:
    async def test_finds_list(self, mock_client):
        result = await get_list_id_by_name(mock_client, "board123", "Backlog")
        assert result == "list_backlog"

    async def test_case_insensitive(self, mock_client):
        result = await get_list_id_by_name(mock_client, "board123", "backlog")
        assert result == "list_backlog"

    async def test_not_found(self, mock_client):
        result = await get_list_id_by_name(mock_client, "board123", "Nonexistent")
        assert result is None


class TestGetListMap:
    async def test_returns_map(self, mock_client):
        result = await get_list_map(mock_client, "board123")
        assert "backlog" in result
        assert "done" in result
        assert result["backlog"] == "list_backlog"


class TestGetListIdForState:
    async def test_finds_state(self, mock_client):
        result = await get_list_id_for_state(mock_client, "board123", "backlog")
        assert result == "list_backlog"

    async def test_raises_on_not_found(self, mock_client):
        mock_client.get_board_lists.return_value = []
        with pytest.raises(ValueError, match="not found"):
            await get_list_id_for_state(mock_client, "board123", "backlog")


class TestFindCardByCustomField:
    async def test_finds_us(self, mock_client):
        result = await find_card_by_custom_field(mock_client, "board123", "us_id", "US-01")
        assert result is not None
        assert result["id"] == "card_us01"

    async def test_finds_uc(self, mock_client):
        result = await find_card_by_custom_field(mock_client, "board123", "uc_id", "UC-001")
        assert result is not None
        assert result["id"] == "card_uc001"

    async def test_not_found(self, mock_client):
        result = await find_card_by_custom_field(mock_client, "board123", "us_id", "US-99")
        assert result is None


class TestGetUsChildren:
    async def test_finds_children(self, mock_client):
        result = await get_us_children(mock_client, "board123", "US-01")
        assert len(result) == 1
        assert result[0]["id"] == "card_uc001"

    async def test_no_children(self, mock_client):
        result = await get_us_children(mock_client, "board123", "US-99")
        assert result == []
