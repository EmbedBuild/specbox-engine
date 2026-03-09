"""Pytest fixtures with httpx mocks for Trello API."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


from src.trello_client import TrelloClient


@pytest.fixture
def mock_ctx():
    """Mock FastMCP Context for per-session auth."""
    ctx = AsyncMock()
    return ctx


@pytest.fixture
def mock_credentials():
    """Provide test credentials as dict (matching new session state format)."""
    return {"api_key": "test_key_123", "token": "test_token_456"}


@pytest.fixture
def client():
    """TrelloClient with test credentials."""
    return TrelloClient(api_key="test_key_123", token="test_token_456")


# --- Sample Trello API responses ---

@pytest.fixture
def sample_board():
    return {
        "id": "board123",
        "name": "TALENT-ON",
        "url": "https://trello.com/b/board123",
    }


@pytest.fixture
def sample_lists():
    return [
        {"id": "list_backlog", "name": "User Stories"},
        {"id": "list_ready", "name": "Backlog"},
        {"id": "list_ip", "name": "In Progress"},
        {"id": "list_review", "name": "Review"},
        {"id": "list_done", "name": "Done"},
    ]


@pytest.fixture
def sample_custom_fields():
    return [
        {
            "id": "cf_tipo", "name": "tipo", "type": "list",
            "options": [
                {"id": "opt_us", "value": {"text": "US"}},
                {"id": "opt_uc", "value": {"text": "UC"}},
            ],
        },
        {"id": "cf_us_id", "name": "us_id", "type": "text", "options": []},
        {"id": "cf_uc_id", "name": "uc_id", "type": "text", "options": []},
        {"id": "cf_horas", "name": "horas", "type": "number", "options": []},
        {"id": "cf_pantallas", "name": "pantallas", "type": "text", "options": []},
        {
            "id": "cf_actor", "name": "actor", "type": "list",
            "options": [
                {"id": "opt_todos", "value": {"text": "Todos"}},
                {"id": "opt_admin", "value": {"text": "Admin"}},
            ],
        },
    ]


@pytest.fixture
def sample_us_card():
    return {
        "id": "card_us01",
        "name": "US-01: Autenticacion y Registro",
        "desc": "## US-01: Autenticacion y Registro\n\n**Horas**: 11\n**Pantallas**: 1A, 1B, 1C",
        "idList": "list_backlog",
        "url": "https://trello.com/c/card_us01",
        "labels": [{"id": "label_us", "name": "US", "color": "blue"}],
        "customFieldItems": [
            {"idCustomField": "cf_tipo", "idValue": "opt_us"},
            {"idCustomField": "cf_us_id", "value": {"text": "US-01"}},
            {"idCustomField": "cf_horas", "value": {"number": "11"}},
            {"idCustomField": "cf_pantallas", "value": {"text": "1A, 1B, 1C"}},
        ],
    }


@pytest.fixture
def sample_uc_card():
    return {
        "id": "card_uc001",
        "name": "UC-001: Iniciar sesion con email y contrasena",
        "desc": (
            "## UC-001: Iniciar sesion con email y contrasena\n\n"
            "**User Story**: US-01 Autenticacion y Registro\n"
            "**Actor**: Todos\n"
            "**Horas**: 3\n"
            "**Pantallas**: 1A, 1B, 1C\n\n"
            "### Criterios de Aceptacion\n"
            "- AC-01: Valida formato email\n"
            "- AC-02: Muestra error si credenciales invalidas\n"
            "- AC-03: Redirige segun rol\n\n"
            "### Contexto\n"
            "Sistema completo de acceso. Supabase Auth email+password.\n\n"
            "### Notas\n"
            "[Notas adicionales]"
        ),
        "idList": "list_backlog",
        "url": "https://trello.com/c/card_uc001",
        "labels": [
            {"id": "label_uc", "name": "UC", "color": "green"},
            {"id": "label_us01", "name": "US-01", "color": "purple"},
        ],
        "customFieldItems": [
            {"idCustomField": "cf_tipo", "idValue": "opt_uc"},
            {"idCustomField": "cf_uc_id", "value": {"text": "UC-001"}},
            {"idCustomField": "cf_us_id", "value": {"text": "US-01"}},
            {"idCustomField": "cf_horas", "value": {"number": "3"}},
            {"idCustomField": "cf_pantallas", "value": {"text": "1A, 1B, 1C"}},
            {"idCustomField": "cf_actor", "idValue": "opt_todos"},
        ],
    }


@pytest.fixture
def sample_checklists():
    return [
        {
            "id": "cl_ac",
            "name": "Criterios de Aceptacion",
            "checkItems": [
                {"id": "ci_01", "name": "AC-01: Valida formato email", "state": "incomplete"},
                {"id": "ci_02", "name": "AC-02: Muestra error si credenciales invalidas", "state": "incomplete"},
                {"id": "ci_03", "name": "AC-03: Redirige segun rol", "state": "complete"},
            ],
        }
    ]


@pytest.fixture
def sample_uc_card_done(sample_uc_card):
    """UC card in Done list."""
    card = dict(sample_uc_card)
    card["idList"] = "list_done"
    return card


@pytest.fixture
def sample_uc_card_ready(sample_uc_card):
    """UC card in Ready list."""
    card = dict(sample_uc_card)
    card["idList"] = "list_ready"
    return card


@pytest.fixture
def sample_us_checklist():
    return [
        {
            "id": "cl_ucs",
            "name": "Casos de Uso",
            "checkItems": [
                {"id": "ci_uc001", "name": "UC-001: Iniciar sesion — https://trello.com/c/card_uc001", "state": "incomplete"},
                {"id": "ci_uc002", "name": "UC-002: Registro — https://trello.com/c/card_uc002", "state": "incomplete"},
            ],
        }
    ]


@pytest.fixture
def mock_trello_client(
    sample_board, sample_lists, sample_custom_fields, sample_us_card,
    sample_uc_card, sample_checklists, sample_us_checklist,
):
    """A fully mocked TrelloClient with realistic responses."""
    tc = AsyncMock()
    tc.get_board.return_value = sample_board
    tc.get_board_lists.return_value = sample_lists
    tc.get_board_cards.return_value = [sample_us_card, sample_uc_card]
    tc.get_board_custom_fields.return_value = sample_custom_fields
    tc.get_board_labels.return_value = [
        {"id": "label_us", "name": "US", "color": "blue"},
        {"id": "label_uc", "name": "UC", "color": "green"},
        {"id": "label_infra", "name": "Infra", "color": "yellow"},
        {"id": "label_blocked", "name": "Bloqueado", "color": "red"},
    ]
    tc.get_card.return_value = sample_uc_card
    tc.get_card_checklists.return_value = sample_checklists
    tc.get_card_attachments.return_value = [
        {"name": "UC-001_prd.pdf", "url": "https://trello.com/attach/1", "date": "2026-03-01", "bytes": 1024},
    ]
    tc.get_card_actions.return_value = [
        {"data": {"text": "AC-01: PASSED"}, "date": "2026-03-01"},
    ]

    # Mutations return reasonable defaults
    tc.create_board.return_value = sample_board
    tc.create_list.return_value = {"id": "new_list_id", "name": "New"}
    tc.create_card.return_value = {"id": "new_card_id", "name": "New Card", "url": "https://trello.com/c/new"}
    tc.create_checklist.return_value = {"id": "new_cl_id", "name": "CL"}
    tc.add_checklist_item.return_value = {"id": "new_ci_id"}
    tc.create_custom_field.return_value = {"id": "new_cf_id", "name": "cf"}
    tc.set_custom_field_value.return_value = {}
    tc.create_label.return_value = {"id": "new_label_id", "name": "Label"}
    tc.add_label_to_card.return_value = {}
    tc.move_card.return_value = {"id": "card_uc001", "idList": "list_done"}
    tc.add_comment.return_value = {"id": "action_id"}
    tc.update_checklist_item.return_value = {}
    tc.add_attachment.return_value = {"id": "att_id", "url": "https://trello.com/attach/new"}
    tc.get_me.return_value = {"id": "user1", "username": "dev", "fullName": "Developer"}
    tc.close = AsyncMock()

    return tc
