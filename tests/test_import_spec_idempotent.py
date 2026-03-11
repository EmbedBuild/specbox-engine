"""Tests for import_spec idempotency (find-or-create pattern)."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub missing dependencies before importing spec_driven (not in test env)
for _mod_name in ("fastmcp", "fpdf", "httpx"):
    if _mod_name not in sys.modules:
        _stub = ModuleType(_mod_name)
        _stub.Context = MagicMock  # type: ignore[attr-defined]
        _stub.FPDF = MagicMock  # type: ignore[attr-defined]
        sys.modules[_mod_name] = _stub

from src.spec_backend import (
    ChecklistItemDTO,
    ItemDTO,
    ModuleDTO,
)
from src.tools.spec_driven import import_spec


# ── Fixtures ────────────────────────────────────────────────────────


def _make_spec(
    *,
    us_id: str = "US-01",
    us_name: str = "Auth",
    uc_id: str = "UC-001",
    uc_name: str = "Login",
    acceptance_criteria: list[str] | None = None,
) -> dict:
    """Build a minimal valid spec dict."""
    return {
        "user_stories": [
            {
                "us_id": us_id,
                "name": us_name,
                "hours": 8,
                "screens": "1A, 1B",
                "description": "Auth feature",
                "use_cases": [
                    {
                        "uc_id": uc_id,
                        "name": uc_name,
                        "actor": "User",
                        "hours": 4,
                        "screens": "1A",
                        "acceptance_criteria": acceptance_criteria or [
                            "User can login",
                            "Error on bad password",
                        ],
                        "context": "Standard login flow",
                    }
                ],
            }
        ]
    }


def _make_backend() -> AsyncMock:
    """Create a mock backend with sensible defaults."""
    backend = AsyncMock()
    backend.find_item_by_field = AsyncMock(return_value=None)
    backend.create_item = AsyncMock(
        side_effect=lambda board_id, **kw: ItemDTO(
            id=f"new-{kw.get('meta', {}).get('us_id') or kw.get('meta', {}).get('uc_id', 'x')}",
            name=kw.get("name", ""),
        )
    )
    backend.update_item = AsyncMock(
        side_effect=lambda board_id, item_id, **kw: ItemDTO(
            id=item_id,
            name=kw.get("name", ""),
        )
    )
    backend.create_module = AsyncMock(
        return_value=ModuleDTO(id="mod-1", name="US-01")
    )
    backend.add_items_to_module = AsyncMock()
    backend.create_acceptance_criteria = AsyncMock(return_value=[])
    backend.get_acceptance_criteria = AsyncMock(return_value=[])
    backend.close = AsyncMock()
    return backend


@pytest.fixture
def mock_ctx():
    return MagicMock()


# ── AC-01: Fresh board creates everything correctly ─────────────────


class TestImportSpecFreshBoard:
    """AC-01: import_spec on empty board creates all US, UC, and AC."""

    async def test_creates_us_uc_ac(self, mock_ctx):
        backend = _make_backend()

        with patch("src.tools.spec_driven.get_session_backend", return_value=backend):
            result = await import_spec("board1", _make_spec(), mock_ctx)

        assert result["created"]["us"] == 1
        assert result["created"]["uc"] == 1
        assert result["created"]["ac"] == 2
        assert result["updated"]["us"] == 0
        assert result["updated"]["uc"] == 0
        assert result["errors"] == []

    async def test_creates_module_with_us_id_only(self, mock_ctx):
        """create_module receives only the us_id, not the full name."""
        backend = _make_backend()

        with patch("src.tools.spec_driven.get_session_backend", return_value=backend):
            await import_spec("board1", _make_spec(), mock_ctx)

        backend.create_module.assert_called_once_with("board1", "US-01")

    async def test_links_uc_to_module(self, mock_ctx):
        backend = _make_backend()

        with patch("src.tools.spec_driven.get_session_backend", return_value=backend):
            await import_spec("board1", _make_spec(), mock_ctx)

        backend.add_items_to_module.assert_called_once()
        call_args = backend.add_items_to_module.call_args
        assert call_args[0][0] == "board1"
        assert call_args[0][1] == "mod-1"
        assert len(call_args[0][2]) == 1  # 1 UC


# ── AC-02: No duplicates on re-import ──────────────────────────────


class TestImportSpecIdempotent:
    """AC-02: import_spec on populated board does NOT create duplicates."""

    async def test_no_duplicates_when_all_exist(self, mock_ctx):
        backend = _make_backend()

        existing_us = ItemDTO(id="existing-us-1", name="US-01: Auth", labels=["US"])
        existing_uc = ItemDTO(
            id="existing-uc-1", name="UC-001: Login", labels=["UC"], parent_id="existing-us-1"
        )

        async def find_mock(board_id, field_name, value):
            if field_name == "us_id" and value == "US-01":
                return existing_us
            if field_name == "uc_id" and value == "UC-001":
                return existing_uc
            return None

        backend.find_item_by_field = AsyncMock(side_effect=find_mock)
        backend.get_acceptance_criteria = AsyncMock(
            return_value=[
                ChecklistItemDTO(id="AC-01", text="User can login"),
                ChecklistItemDTO(id="AC-02", text="Error on bad password"),
            ]
        )

        with patch("src.tools.spec_driven.get_session_backend", return_value=backend):
            result = await import_spec("board1", _make_spec(), mock_ctx)

        # Nothing created, everything updated
        assert result["created"]["us"] == 0
        assert result["created"]["uc"] == 0
        assert result["created"]["ac"] == 0
        assert result["updated"]["us"] == 1
        assert result["updated"]["uc"] == 1

        # create_item never called (no new items)
        backend.create_item.assert_not_called()
        # create_acceptance_criteria never called (all ACs exist)
        backend.create_acceptance_criteria.assert_not_called()


# ── AC-03: Partial import creates only missing items ───────────────


class TestImportSpecPartial:
    """AC-03: Partially existing board — creates only what's missing."""

    async def test_existing_us_new_uc(self, mock_ctx):
        """US exists but UC is new — should create UC, not US."""
        backend = _make_backend()
        existing_us = ItemDTO(id="existing-us-1", name="US-01: Auth", labels=["US"])

        async def find_mock(board_id, field_name, value):
            if field_name == "us_id" and value == "US-01":
                return existing_us
            return None

        backend.find_item_by_field = AsyncMock(side_effect=find_mock)
        # create_module for existing US with new UCs
        backend.create_module = AsyncMock(
            return_value=ModuleDTO(id="mod-existing", name="US-01")
        )

        with patch("src.tools.spec_driven.get_session_backend", return_value=backend):
            result = await import_spec("board1", _make_spec(), mock_ctx)

        assert result["created"]["us"] == 0
        assert result["updated"]["us"] == 1
        assert result["created"]["uc"] == 1
        assert result["created"]["ac"] == 2

    async def test_existing_uc_new_ac(self, mock_ctx):
        """UC exists with 1 AC, spec has 2 — should create only the missing AC."""
        backend = _make_backend()
        existing_us = ItemDTO(id="us-1", name="US-01: Auth", labels=["US"])
        existing_uc = ItemDTO(id="uc-1", name="UC-001: Login", labels=["UC"], parent_id="us-1")

        async def find_mock(board_id, field_name, value):
            if field_name == "us_id" and value == "US-01":
                return existing_us
            if field_name == "uc_id" and value == "UC-001":
                return existing_uc
            return None

        backend.find_item_by_field = AsyncMock(side_effect=find_mock)
        backend.get_acceptance_criteria = AsyncMock(
            return_value=[
                ChecklistItemDTO(id="AC-01", text="User can login"),
            ]
        )

        with patch("src.tools.spec_driven.get_session_backend", return_value=backend):
            result = await import_spec("board1", _make_spec(), mock_ctx)

        assert result["created"]["ac"] == 1  # Only AC-02 created
        # create_acceptance_criteria called with only the missing AC
        backend.create_acceptance_criteria.assert_called_once()
        criteria_arg = backend.create_acceptance_criteria.call_args[0][2]
        assert len(criteria_arg) == 1
        assert criteria_arg[0][0] == "AC-02"


# ── AC-04: Updates metadata on existing items ──────────────────────


class TestImportSpecUpdates:
    """AC-04: import_spec updates name, description, hours on existing items."""

    async def test_updates_us_metadata(self, mock_ctx):
        backend = _make_backend()
        existing_us = ItemDTO(id="us-1", name="US-01: Old Name", labels=["US"])

        async def find_mock(board_id, field_name, value):
            if field_name == "us_id" and value == "US-01":
                return existing_us
            return None

        backend.find_item_by_field = AsyncMock(side_effect=find_mock)

        with patch("src.tools.spec_driven.get_session_backend", return_value=backend):
            await import_spec("board1", _make_spec(), mock_ctx)

        # update_item called for US with new name
        us_update_call = backend.update_item.call_args_list[0]
        assert us_update_call[0] == ("board1", "us-1")
        assert us_update_call[1]["name"] == "US-01: Auth"
        assert us_update_call[1]["meta"]["horas"] == 8

    async def test_updates_uc_metadata(self, mock_ctx):
        backend = _make_backend()
        existing_us = ItemDTO(id="us-1", name="US-01: Auth", labels=["US"])
        existing_uc = ItemDTO(id="uc-1", name="UC-001: Old", labels=["UC"], parent_id="us-1")

        async def find_mock(board_id, field_name, value):
            if field_name == "us_id" and value == "US-01":
                return existing_us
            if field_name == "uc_id" and value == "UC-001":
                return existing_uc
            return None

        backend.find_item_by_field = AsyncMock(side_effect=find_mock)
        backend.get_acceptance_criteria = AsyncMock(return_value=[])

        with patch("src.tools.spec_driven.get_session_backend", return_value=backend):
            await import_spec("board1", _make_spec(), mock_ctx)

        # update_item called for UC
        uc_update_call = backend.update_item.call_args_list[1]
        assert uc_update_call[0] == ("board1", "uc-1")
        assert uc_update_call[1]["name"] == "UC-001: Login"
        assert uc_update_call[1]["meta"]["horas"] == 4


# ── AC-05: UCs linked to parent US ────────────────────────────────


class TestImportSpecParentLinking:
    """AC-05: UCs are linked to parent US via parent_id."""

    async def test_uc_gets_parent_id(self, mock_ctx):
        backend = _make_backend()

        with patch("src.tools.spec_driven.get_session_backend", return_value=backend):
            await import_spec("board1", _make_spec(), mock_ctx)

        # create_item for UC should have parent_id = US item id
        uc_create_call = backend.create_item.call_args_list[1]
        assert uc_create_call[1]["parent_id"] == "new-US-01"


# ── AC-06: US moved to correct list by status ─────────────────────


class TestImportSpecStateMapping:
    """AC-06: US items placed in user_stories state."""

    async def test_us_created_in_user_stories_state(self, mock_ctx):
        backend = _make_backend()

        with patch("src.tools.spec_driven.get_session_backend", return_value=backend):
            await import_spec("board1", _make_spec(), mock_ctx)

        us_create_call = backend.create_item.call_args_list[0]
        assert us_create_call[1]["state"] == "user_stories"

    async def test_uc_created_in_backlog_state(self, mock_ctx):
        backend = _make_backend()

        with patch("src.tools.spec_driven.get_session_backend", return_value=backend):
            await import_spec("board1", _make_spec(), mock_ctx)

        uc_create_call = backend.create_item.call_args_list[1]
        assert uc_create_call[1]["state"] == "backlog"


# ── Error handling ─────────────────────────────────────────────────


class TestImportSpecErrors:
    """Errors in individual items don't break the whole import."""

    async def test_uc_error_continues_import(self, mock_ctx):
        backend = _make_backend()
        # create_item succeeds for US, fails for UC
        call_count = 0

        async def create_side_effect(board_id, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Plane API error")
            return ItemDTO(id=f"new-{call_count}", name=kw.get("name", ""))

        backend.create_item = AsyncMock(side_effect=create_side_effect)

        with patch("src.tools.spec_driven.get_session_backend", return_value=backend):
            result = await import_spec("board1", _make_spec(), mock_ctx)

        assert result["created"]["us"] == 1
        assert result["created"]["uc"] == 0
        assert len(result["errors"]) == 1
        assert "UC-001" in result["errors"][0]
