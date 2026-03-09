"""Tests for tools/board.py — setup_board, get_board_status, import_spec."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.tools.board import setup_board, get_board_status, import_spec


def _patch_client(mock_trello_client):
    """Patch get_session_client in board module."""
    async def _get(ctx):
        return mock_trello_client
    return patch("src.tools.board.get_session_client", side_effect=_get)


class TestSetupBoard:
    async def test_creates_board_with_structure(self, mock_trello_client, mock_ctx):
        mock_trello_client.create_board.return_value = {
            "id": "board_new", "url": "https://trello.com/b/board_new",
        }

        with _patch_client(mock_trello_client):
            result = await setup_board("TEST-PROJECT", mock_ctx)

        assert result["board_id"] == "board_new"
        assert result["board_url"] == "https://trello.com/b/board_new"
        assert "lists" in result
        assert "custom_fields" in result
        assert "labels" in result

        # 5 lists created
        assert mock_trello_client.create_list.call_count == 5
        # 6 custom fields
        assert mock_trello_client.create_custom_field.call_count == 6
        # 4 labels (US, UC, Infra, Bloqueado)
        assert mock_trello_client.create_label.call_count == 4


class TestGetBoardStatus:
    async def test_returns_status(self, mock_trello_client, mock_ctx, sample_us_card, sample_uc_card):
        with _patch_client(mock_trello_client):
            result = await get_board_status("board123", mock_ctx)

        assert "lists" in result
        assert "progress" in result
        assert "us_summary" in result
        assert len(result["lists"]) == 5

    async def test_counts_cards(self, mock_trello_client, mock_ctx, sample_us_card, sample_uc_card):
        with _patch_client(mock_trello_client):
            result = await get_board_status("board123", mock_ctx)

        # User Stories list should have 1 US and 1 UC
        backlog = next(l for l in result["lists"] if l["name"] == "User Stories")
        assert backlog["us_count"] == 1
        assert backlog["uc_count"] == 1

    async def test_progress_calculation(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await get_board_status("board123", mock_ctx)

        # Nothing in done, so 0%
        assert result["progress"]["horas_done"] == 0
        assert result["progress"]["pct"] == 0

    async def test_progress_with_done_cards(self, mock_trello_client, mock_ctx, sample_us_card, sample_uc_card):
        done_uc = dict(sample_uc_card)
        done_uc["id"] = "card_uc_done"
        done_uc["idList"] = "list_done"
        mock_trello_client.get_board_cards.return_value = [sample_us_card, sample_uc_card, done_uc]

        with _patch_client(mock_trello_client):
            result = await get_board_status("board123", mock_ctx)

        assert result["progress"]["horas_done"] == 3.0
        assert result["progress"]["horas_total"] == 6.0
        assert result["progress"]["pct"] == 50.0


class TestImportSpec:
    async def test_import_minimal(self, mock_trello_client, mock_ctx):
        spec = {
            "user_stories": [
                {
                    "us_id": "US-01",
                    "name": "Auth",
                    "hours": 11,
                    "screens": "1A, 1B",
                    "description": "Auth system",
                    "use_cases": [
                        {
                            "uc_id": "UC-001",
                            "name": "Login",
                            "actor": "Todos",
                            "hours": 3,
                            "screens": "1A",
                            "acceptance_criteria": ["Validates email", "Shows error"],
                            "context": "Supabase Auth",
                        },
                    ],
                },
            ],
        }
        with _patch_client(mock_trello_client):
            result = await import_spec("board123", spec, mock_ctx)

        assert result["created"]["us"] == 1
        assert result["created"]["uc"] == 1
        assert result["created"]["ac"] == 2
        assert result["errors"] == []

    async def test_import_no_backlog_list(self, mock_trello_client, mock_ctx):
        mock_trello_client.get_board_lists.return_value = [{"id": "x", "name": "Other"}]
        with _patch_client(mock_trello_client):
            result = await import_spec("board123", {"user_stories": [{"us_id": "US-01", "name": "T", "use_cases": []}]}, mock_ctx)
        assert result["code"] == "LIST_NOT_FOUND"

    async def test_import_multiple_us_uc(self, mock_trello_client, mock_ctx):
        spec = {
            "user_stories": [
                {
                    "us_id": "US-01", "name": "Auth", "hours": 5, "screens": "", "description": "",
                    "use_cases": [
                        {"uc_id": "UC-001", "name": "Login", "hours": 2, "acceptance_criteria": ["AC1"]},
                        {"uc_id": "UC-002", "name": "Register", "hours": 3, "acceptance_criteria": ["AC1", "AC2"]},
                    ],
                },
                {
                    "us_id": "US-02", "name": "Profile", "hours": 4, "screens": "", "description": "",
                    "use_cases": [
                        {"uc_id": "UC-003", "name": "View Profile", "hours": 4, "acceptance_criteria": ["AC1"]},
                    ],
                },
            ],
        }
        with _patch_client(mock_trello_client):
            result = await import_spec("board123", spec, mock_ctx)

        assert result["created"]["us"] == 2
        assert result["created"]["uc"] == 3
        assert result["created"]["ac"] == 4

    async def test_import_handles_uc_error(self, mock_trello_client, mock_ctx):
        # Make create_card fail on second call (UC card)
        call_count = 0
        original = mock_trello_client.create_card

        async def failing_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second create_card is first UC
                raise Exception("API error")
            return await original(*args, **kwargs)

        mock_trello_client.create_card = failing_create

        spec = {
            "user_stories": [{
                "us_id": "US-01", "name": "Auth", "use_cases": [
                    {"uc_id": "UC-001", "name": "Login", "acceptance_criteria": []},
                ],
            }],
        }
        with _patch_client(mock_trello_client):
            result = await import_spec("board123", spec, mock_ctx)

        assert len(result["errors"]) == 1
        assert "UC-001" in result["errors"][0]

    async def test_import_empty_spec(self, mock_trello_client, mock_ctx):
        with _patch_client(mock_trello_client):
            result = await import_spec("board123", {"user_stories": []}, mock_ctx)
        assert result["created"]["us"] == 0
        assert result["created"]["uc"] == 0
