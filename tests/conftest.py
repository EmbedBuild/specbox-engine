"""Pytest fixtures with httpx mocks for Trello API.

Also, for every test (UC-5901): the native pool hygiene and the ``native_db``
marker, see below.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import socket
from unittest.mock import AsyncMock

import pytest

import server.db.pool as native_pool
import tests._native_db as native_db
from server.trello_client import TrelloClient

# ── native_db marker (UC-5901) ────────────────────────────────────────
#
# Every test module that talks to the native Postgres goes through the shared
# helper ``tests/_native_db.py`` (DSN, reachability probe, fixtures). Its tests
# get the ``native_db`` marker, so ``pytest -m native_db`` runs exactly the
# Postgres-backed suite — the one ``.github/workflows/native-tests.yml`` runs
# on every PR — and a new module joins it just by using the helper.

_NATIVE_DB_EXPORTS = (
    native_db,
    native_db.DSN,
    native_db.probe,
    native_db.reachable,
    native_db.seed_organization,
)


def _uses_native_db(module) -> bool:
    return any(value is export for value in vars(module).values() for export in _NATIVE_DB_EXPORTS)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "native_db: uses the native Postgres through tests/_native_db.py (run with -m native_db)",
    )


def pytest_collection_modifyitems(config, items):
    seen: dict[str, bool] = {}
    for item in items:
        module = getattr(item, "module", None)
        if module is None:
            continue
        if module.__name__ not in seen:
            seen[module.__name__] = _uses_native_db(module)
        if seen[module.__name__]:
            item.add_marker(pytest.mark.native_db)


# ── Native pool hygiene (UC-5901) ─────────────────────────────────────
#
# ``server.db.pool`` keeps ONE asyncpg pool per process, and pytest-asyncio
# gives every test its own event loop. A test that created the pool and did not
# close it (a fixture that failed half-way, or code that reached ``get_pool()``
# lazily because SPECBOX_NATIVE_DSN was exported) left behind a pool tied to a
# closed loop. Two things followed:
#
# * every later ``init_pool()`` got that dead pool back ("attached to a
#   different loop", "Event loop is closed"), so whole modules failed by order;
# * modules that worked around it with ``_pool = None`` dropped the pool
#   without closing it. Its connections stayed open on the server, some of them
#   inside a transaction or half-way through a statement, still holding locks —
#   and the next ``apply_migrations`` waited for those locks forever. That was
#   the hang of the full suite against Postgres.
#
# The pool now never outlives the test that opened it: async tests close it in
# their own loop, before pytest-asyncio closes that loop.

#: Seconds a graceful close may take before its connections are terminated (a
#: graceful close waits for every connection the test still holds).
_POOL_CLOSE_TIMEOUT_S = 5.0


def _cut_pool_connections(pool) -> None:
    """Close a pool's sockets without its event loop (which may be closed).

    The server ends those sessions and releases their locks. Only for a pool
    that can no longer be closed gracefully.
    """
    for holder in getattr(pool, "_holders", ()):
        transport = getattr(getattr(holder, "_con", None), "_transport", None)
        sock = transport.get_extra_info("socket") if transport is not None else None
        if sock is not None:
            with contextlib.suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)


async def _close_native_pool() -> None:
    pool = native_pool._pool
    if pool is None:
        return
    try:
        if getattr(pool, "_loop", None) is asyncio.get_running_loop():
            try:
                await asyncio.wait_for(pool.close(), timeout=_POOL_CLOSE_TIMEOUT_S)
            except Exception:  # noqa: BLE001 — a connection still in use, or broken
                try:
                    pool.terminate()
                except Exception:  # noqa: BLE001
                    _cut_pool_connections(pool)
        else:
            _cut_pool_connections(pool)
    finally:
        native_pool._pool = None


@pytest.fixture
async def _native_pool_closer():
    yield
    await _close_native_pool()


@pytest.fixture(autouse=True)
def _native_pool_guard(request):
    """Close the shared native pool when the test that opened it ends."""
    if inspect.iscoroutinefunction(getattr(request.node, "obj", None)):
        # Async fixture → its teardown runs in the test's loop, before it closes.
        request.getfixturevalue("_native_pool_closer")
    yield
    pool = native_pool._pool
    loop = getattr(pool, "_loop", None)
    if pool is not None and (loop is None or loop.is_closed()):
        # A sync test that ran async code in a throwaway loop.
        _cut_pool_connections(pool)
        native_pool._pool = None


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
