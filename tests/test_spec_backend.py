"""Unit tests for the abstract SpecBackend and shared DTOs/helpers."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from src.spec_backend import (
    AttachmentDTO,
    BackendUser,
    BoardConfig,
    ChecklistItemDTO,
    CommentDTO,
    ItemDTO,
    ModuleDTO,
    SpecBackend,
    parse_item_id,
)


# ── parse_item_id tests ──────────────────────────────────────────────


class TestParseItemId:
    """Test the parse_item_id helper for Trello and Plane name formats."""

    def test_us_colon_format(self):
        item_id, name = parse_item_id("US-01: Registro", "US")
        assert item_id == "US-01"
        assert name == "Registro"

    def test_us_bracket_format(self):
        item_id, name = parse_item_id("[US-01] Registro", "US")
        assert item_id == "US-01"
        assert name == "Registro"

    def test_uc_bracket_format(self):
        item_id, name = parse_item_id("[UC-001] Login", "UC")
        assert item_id == "UC-001"
        assert name == "Login"

    def test_ac_colon_format(self):
        item_id, name = parse_item_id("AC-01: Validates email", "AC")
        assert item_id == "AC-01"
        assert name == "Validates email"

    def test_no_match_returns_empty_id(self):
        item_id, name = parse_item_id("Random name", "US")
        assert item_id == ""
        assert name == "Random name"

    def test_uc_colon_format(self):
        item_id, name = parse_item_id("UC-042: Gestionar perfil", "UC")
        assert item_id == "UC-042"
        assert name == "Gestionar perfil"

    def test_us_without_bracket_or_colon(self):
        """US-XX followed by space and name (no colon, no bracket)."""
        item_id, name = parse_item_id("US-05 My feature", "US")
        assert item_id == "US-05"
        assert name == "My feature"

    def test_ac_bracket_format(self):
        item_id, name = parse_item_id("[AC-03] Redirige segun rol", "AC")
        assert item_id == "AC-03"
        assert name == "Redirige segun rol"

    def test_unknown_prefix_returns_empty(self):
        """Unknown prefix returns empty id and original name."""
        item_id, name = parse_item_id("US-10: Something", "UNKNOWN")
        assert item_id == ""
        assert name == "US-10: Something"

    def test_empty_string(self):
        item_id, name = parse_item_id("", "US")
        assert item_id == ""
        assert name == ""

    def test_whitespace_in_name_is_stripped(self):
        item_id, name = parse_item_id("US-01:   Registro con espacios  ", "US")
        assert item_id == "US-01"
        assert name == "Registro con espacios"


# ── DTO dataclass creation tests ─────────────────────────────────────


class TestDTOs:
    """Test that all DTOs can be instantiated with expected defaults."""

    def test_item_dto_defaults(self):
        dto = ItemDTO(id="i1", name="Test item")
        assert dto.id == "i1"
        assert dto.name == "Test item"
        assert dto.description == ""
        assert dto.state == ""
        assert dto.state_id == ""
        assert dto.parent_id is None
        assert dto.labels == []
        assert dto.label_ids == []
        assert dto.priority == "none"
        assert dto.url == ""
        assert dto.external_source == ""
        assert dto.external_id == ""
        assert dto.meta == {}
        assert dto.raw == {}

    def test_item_dto_full(self):
        dto = ItemDTO(
            id="i1",
            name="[US-01] Registro",
            description="Some desc",
            state="backlog",
            state_id="s1",
            parent_id="p1",
            labels=["US"],
            label_ids=["l1"],
            priority="high",
            url="https://example.com",
            external_source="trello",
            external_id="ext1",
            meta={"tipo": "US", "us_id": "US-01"},
            raw={"id": "i1"},
        )
        assert dto.parent_id == "p1"
        assert dto.labels == ["US"]
        assert dto.meta["tipo"] == "US"

    def test_checklist_item_dto_defaults(self):
        dto = ChecklistItemDTO(id="ac1", text="Validates email")
        assert dto.id == "ac1"
        assert dto.text == "Validates email"
        assert dto.done is False
        assert dto.backend_id == ""

    def test_checklist_item_dto_done(self):
        dto = ChecklistItemDTO(id="ac1", text="Validates", done=True, backend_id="b1")
        assert dto.done is True
        assert dto.backend_id == "b1"

    def test_comment_dto_defaults(self):
        dto = CommentDTO(id="c1", text="Hello")
        assert dto.id == "c1"
        assert dto.text == "Hello"
        assert dto.created_at == ""
        assert dto.author == ""

    def test_comment_dto_full(self):
        dto = CommentDTO(id="c1", text="Hello", created_at="2026-03-01", author="dev")
        assert dto.created_at == "2026-03-01"
        assert dto.author == "dev"

    def test_attachment_dto_defaults(self):
        dto = AttachmentDTO(id="a1", name="file.pdf", url="https://example.com/file.pdf")
        assert dto.id == "a1"
        assert dto.name == "file.pdf"
        assert dto.url == "https://example.com/file.pdf"
        assert dto.size == 0
        assert dto.created_at == ""
        assert dto.mime_type == ""

    def test_attachment_dto_full(self):
        dto = AttachmentDTO(
            id="a1",
            name="evidence.pdf",
            url="https://cdn/evidence.pdf",
            size=2048,
            created_at="2026-03-10",
            mime_type="application/pdf",
        )
        assert dto.size == 2048
        assert dto.mime_type == "application/pdf"

    def test_module_dto_defaults(self):
        dto = ModuleDTO(id="m1", name="Sprint 1")
        assert dto.id == "m1"
        assert dto.name == "Sprint 1"
        assert dto.status == ""
        assert dto.item_ids == []

    def test_module_dto_full(self):
        dto = ModuleDTO(id="m1", name="Sprint 1", status="planned", item_ids=["i1", "i2"])
        assert dto.status == "planned"
        assert len(dto.item_ids) == 2

    def test_backend_user(self):
        user = BackendUser(id="u1", username="dev", display_name="Developer")
        assert user.id == "u1"
        assert user.username == "dev"
        assert user.display_name == "Developer"

    def test_board_config(self):
        cfg = BoardConfig(
            board_id="b1",
            board_url="https://example.com/board",
            states={"backlog": "s1", "done": "s2"},
            labels={"US": "l1", "UC": "l2"},
            custom_fields={"tipo": "cf1"},
        )
        assert cfg.board_id == "b1"
        assert cfg.states["backlog"] == "s1"
        assert cfg.labels["US"] == "l1"
        assert cfg.custom_fields["tipo"] == "cf1"

    def test_item_dto_labels_not_shared_between_instances(self):
        """Ensure mutable default fields are independent per instance."""
        dto1 = ItemDTO(id="i1", name="A")
        dto2 = ItemDTO(id="i2", name="B")
        dto1.labels.append("US")
        assert dto2.labels == []

    def test_module_dto_item_ids_not_shared(self):
        m1 = ModuleDTO(id="m1", name="A")
        m2 = ModuleDTO(id="m2", name="B")
        m1.item_ids.append("x")
        assert m2.item_ids == []


# ── SpecBackend abstract class tests ─────────────────────────────────


class TestSpecBackendAbstract:
    """Test that SpecBackend cannot be instantiated directly."""

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError, match="abstract"):
            SpecBackend()  # type: ignore[abstract]


# ── Concrete mock subclass for convenience methods ───────────────────


class _MockBackend(SpecBackend):
    """Minimal concrete subclass for testing non-abstract convenience methods."""

    def __init__(self, items: list[ItemDTO] | None = None):
        self._items = items or []

    async def validate_auth(self) -> BackendUser:
        return BackendUser(id="u1", username="mock", display_name="Mock")

    async def setup_board(self, name: str) -> BoardConfig:
        return BoardConfig(
            board_id="b1",
            board_url="",
            states={},
            labels={},
            custom_fields={},
        )

    async def get_board_name(self, board_id: str) -> str:
        return "Mock Board"

    async def list_items(self, board_id: str) -> list[ItemDTO]:
        return self._items

    async def get_item(self, board_id: str, item_id: str) -> ItemDTO:
        for i in self._items:
            if i.id == item_id:
                return i
        raise ValueError(f"Item {item_id} not found")

    async def create_item(self, board_id, name="", description="", state="backlog",
                          labels=None, parent_id=None, priority="none",
                          external_source="", external_id="", meta=None) -> ItemDTO:
        return ItemDTO(id="new", name=name)

    async def update_item(self, board_id, item_id, *, name=None, description=None,
                          state=None, labels=None, parent_id=None, priority=None,
                          external_source=None, external_id=None, meta=None) -> ItemDTO:
        return ItemDTO(id=item_id, name=name or "")

    async def find_item_by_field(self, board_id, field_name, value) -> ItemDTO | None:
        return None

    async def get_item_children(self, board_id, parent_id) -> list[ItemDTO]:
        return [i for i in self._items if i.parent_id == parent_id]

    async def get_acceptance_criteria(self, board_id, uc_item_id) -> list:
        return []

    async def mark_acceptance_criterion(self, board_id, uc_item_id, ac_id, passed):
        return ChecklistItemDTO(id=ac_id, text="", done=passed)

    async def create_acceptance_criteria(self, board_id, uc_item_id, criteria) -> list:
        return []

    async def update_acceptance_criterion(
        self, board_id, uc_item_id, ac_id, *, text=None, done=None
    ):
        from server.spec_backend import ChecklistItemDTO as _CL
        return _CL(id=ac_id, text=text or "", done=bool(done))

    async def delete_acceptance_criterion(self, board_id, uc_item_id, ac_id) -> None:
        return None

    async def archive_item(self, board_id, item_id, *, reason=""):
        return {"archive_location": "test", "archived_at": "2026-01-01T00:00:00+00:00"}

    async def add_comment(self, board_id, item_id, text) -> CommentDTO:
        return CommentDTO(id="c1", text=text)

    async def get_comments(self, board_id, item_id) -> list:
        return []

    async def add_attachment(self, board_id, item_id, filename, content, mime_type="application/pdf"):
        return AttachmentDTO(id="a1", name=filename, url="")

    async def get_attachments(self, board_id, item_id) -> list:
        return []

    async def create_module(self, board_id, name, description="") -> ModuleDTO:
        return ModuleDTO(id="m1", name=name)

    async def add_items_to_module(self, board_id, module_id, item_ids) -> None:
        pass

    async def create_label(self, board_id, name, color) -> dict[str, str]:
        return {"name": name, "id": "l_new", "color": color}

    async def get_labels(self, board_id) -> list[dict[str, str]]:
        return []

    async def get_state_id(self, board_id, state) -> str:
        return "state_id"

    async def get_states(self, board_id) -> dict[str, str]:
        return {}

    async def close(self) -> None:
        pass


class TestFindUsItems:
    """Test the convenience find_us_items method."""

    @pytest.fixture
    def backend_with_items(self):
        items = [
            ItemDTO(id="i1", name="[US-01] Auth", labels=["US"]),
            ItemDTO(id="i2", name="[UC-001] Login", labels=["UC"], parent_id="i1"),
            ItemDTO(id="i3", name="[US-02] Dashboard", labels=["US"]),
            ItemDTO(id="i4", name="Infra task", labels=["Infra"]),
        ]
        return _MockBackend(items)

    async def test_find_us_items_returns_only_us(self, backend_with_items):
        result = await backend_with_items.find_us_items("board1")
        assert len(result) == 2
        assert all("US" in i.labels for i in result)

    async def test_find_us_items_empty_board(self):
        backend = _MockBackend([])
        result = await backend.find_us_items("board1")
        assert result == []


class TestFindUcItems:
    """Test the convenience find_uc_items method."""

    @pytest.fixture
    def backend_with_hierarchy(self):
        items = [
            ItemDTO(
                id="us1",
                name="[US-01] Auth",
                labels=["US"],
                meta={"us_id": "US-01", "tipo": "US"},
            ),
            ItemDTO(
                id="uc1",
                name="[UC-001] Login",
                labels=["UC"],
                parent_id="us1",
                meta={"uc_id": "UC-001", "us_id": "US-01", "tipo": "UC"},
            ),
            ItemDTO(
                id="uc2",
                name="[UC-002] Register",
                labels=["UC"],
                parent_id="us1",
                meta={"uc_id": "UC-002", "us_id": "US-01", "tipo": "UC"},
            ),
            ItemDTO(
                id="us2",
                name="[US-02] Dashboard",
                labels=["US"],
                meta={"us_id": "US-02", "tipo": "US"},
            ),
            ItemDTO(
                id="uc3",
                name="[UC-003] View stats",
                labels=["UC"],
                parent_id="us2",
                meta={"uc_id": "UC-003", "us_id": "US-02", "tipo": "UC"},
            ),
        ]
        return _MockBackend(items)

    async def test_find_all_uc_items(self, backend_with_hierarchy):
        result = await backend_with_hierarchy.find_uc_items("board1")
        assert len(result) == 3
        assert all("UC" in i.labels for i in result)

    async def test_find_uc_items_filtered_by_us_id(self, backend_with_hierarchy):
        result = await backend_with_hierarchy.find_uc_items("board1", us_id="US-01")
        assert len(result) == 2
        ids = {i.id for i in result}
        assert ids == {"uc1", "uc2"}

    async def test_find_uc_items_no_match(self, backend_with_hierarchy):
        result = await backend_with_hierarchy.find_uc_items("board1", us_id="US-99")
        assert result == []

    async def test_find_uc_items_parent_matches_via_name(self):
        """UCs that don't have us_id in meta but whose parent name matches."""
        items = [
            ItemDTO(
                id="us1",
                name="[US-01] Auth",
                labels=["US"],
                meta={"us_id": "US-01"},
            ),
            ItemDTO(
                id="uc1",
                name="[UC-001] Login",
                labels=["UC"],
                parent_id="us1",
                # No us_id in meta — must match via parent name
                meta={"uc_id": "UC-001"},
            ),
        ]
        backend = _MockBackend(items)
        result = await backend.find_uc_items("board1", us_id="US-01")
        assert len(result) == 1
        assert result[0].id == "uc1"
