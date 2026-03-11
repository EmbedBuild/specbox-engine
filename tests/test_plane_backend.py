"""Unit tests for PlaneBackend with a fully mocked PlaneClient."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, PropertyMock

from src.spec_backend import (
    BackendUser,
    BoardConfig,
    ChecklistItemDTO,
    CommentDTO,
    ItemDTO,
)
from src.backends.plane_backend import (
    PlaneBackend,
    _extract_meta_from_html,
    _build_description_html,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_plane_client():
    """Fully mocked PlaneClient with AsyncMock methods."""
    client = AsyncMock()
    client.base_url = "https://plane.example.com"
    client.workspace_slug = "my-ws"
    # Auth
    client.get_me.return_value = {
        "id": "user-uuid-1",
        "username": "jps",
        "email": "jps@example.com",
        "display_name": "Jesus PS",
        "first_name": "Jesus",
    }
    # Projects
    client.create_project.return_value = {
        "id": "proj-uuid-1",
        "name": "Test Project",
        "identifier": "TESTP",
    }
    client.get_project.return_value = {
        "id": "proj-uuid-1",
        "name": "Test Project",
    }
    # States
    client.list_states.return_value = [
        {"id": "st-us", "name": "User Stories", "group": "backlog"},
        {"id": "st-bl", "name": "Backlog", "group": "backlog"},
        {"id": "st-ip", "name": "In Progress", "group": "started"},
        {"id": "st-rv", "name": "Review", "group": "started"},
        {"id": "st-dn", "name": "Done", "group": "completed"},
    ]
    client.create_state.return_value = {
        "id": "st-new",
        "name": "New State",
        "group": "backlog",
    }
    # Labels
    client.list_labels.return_value = [
        {"id": "lbl-us", "name": "US", "color": "#3B82F6"},
        {"id": "lbl-uc", "name": "UC", "color": "#22C55E"},
        {"id": "lbl-ac", "name": "AC", "color": "#A855F7"},
        {"id": "lbl-infra", "name": "Infra", "color": "#EAB308"},
        {"id": "lbl-blocked", "name": "Bloqueado", "color": "#EF4444"},
    ]
    client.create_label.return_value = {
        "id": "lbl-new",
        "name": "NewLabel",
        "color": "#000",
    }
    # Work items
    client.list_work_items.return_value = []
    client.get_work_item.return_value = {}
    client.create_work_item.return_value = {"id": "item-new-uuid"}
    client.update_work_item.return_value = {}
    # Comments
    client.list_comments.return_value = []
    client.create_comment.return_value = {
        "id": "comment-uuid-1",
        "comment_html": "<p>Test comment</p>",
        "created_at": "2026-03-10T10:00:00Z",
        "actor_detail": {"display_name": "Jesus PS"},
    }
    # Links
    client.list_links.return_value = []
    # Modules
    client.create_module.return_value = {
        "id": "mod-uuid-1",
        "name": "Sprint 1",
        "status": "planned",
    }
    client.add_items_to_module.return_value = None
    # Cleanup
    client.close = AsyncMock()

    return client


@pytest.fixture
def backend(mock_plane_client):
    """PlaneBackend with mocked client injected."""
    be = PlaneBackend(
        base_url="https://plane.example.com",
        api_key="test-api-key",
        workspace_slug="my-ws",
    )
    # Replace real client with mock
    be.client = mock_plane_client
    return be


BOARD_ID = "proj-uuid-1"


# ── Sample raw items ─────────────────────────────────────────────────


def _make_raw_item(
    item_id: str,
    name: str,
    labels: list[str] | None = None,
    state: str = "st-bl",
    parent: str | None = None,
    description_html: str = "",
    priority: str = "none",
) -> dict:
    """Build a raw Plane API work item response."""
    return {
        "id": item_id,
        "name": name,
        "labels": labels or [],
        "state": state,
        "parent": parent,
        "description_html": description_html,
        "priority": priority,
        "project": BOARD_ID,
    }


# ── Tests ────────────────────────────────────────────────────────────


class TestValidateAuth:
    async def test_validate_auth(self, backend, mock_plane_client):
        user = await backend.validate_auth()
        mock_plane_client.get_me.assert_awaited_once()
        assert isinstance(user, BackendUser)
        assert user.id == "user-uuid-1"
        assert user.username == "jps"
        assert user.display_name == "Jesus PS"


class TestSetupBoard:
    async def test_setup_board(self, backend, mock_plane_client):
        # list_states returns existing defaults (no "User Stories" among them)
        mock_plane_client.list_states.return_value = [
            {"id": "st-todo", "name": "Todo", "group": "backlog"},
            {"id": "st-ip", "name": "In Progress", "group": "started"},
            {"id": "st-dn", "name": "Done", "group": "completed"},
        ]
        # No existing labels
        mock_plane_client.list_labels.return_value = []

        result = await backend.setup_board("My Board")

        assert isinstance(result, BoardConfig)
        assert result.board_id == "proj-uuid-1"
        assert "proj-uuid-1" in result.board_url
        assert result.custom_fields == {}

        # Should have created project
        mock_plane_client.create_project.assert_awaited_once()

        # Should have created labels for US, UC, AC, Infra, Bloqueado
        assert mock_plane_client.create_label.await_count == 5


class TestListItems:
    async def test_list_items(self, backend, mock_plane_client):
        mock_plane_client.list_work_items.return_value = [
            _make_raw_item("i1", "[US-01] Auth", labels=["lbl-us"], state="st-bl"),
            _make_raw_item(
                "i2",
                "[UC-001] Login",
                labels=["lbl-uc"],
                state="st-ip",
                parent="i1",
            ),
        ]
        items = await backend.list_items(BOARD_ID)

        assert len(items) == 2
        assert all(isinstance(i, ItemDTO) for i in items)

        us = items[0]
        assert us.id == "i1"
        assert us.name == "[US-01] Auth"
        assert us.state == "backlog"  # st-bl maps to backlog
        assert us.state_id == "st-bl"

        uc = items[1]
        assert uc.id == "i2"
        assert uc.parent_id == "i1"
        assert uc.state == "in_progress"  # st-ip maps to in_progress


class TestGetItem:
    async def test_get_item(self, backend, mock_plane_client):
        mock_plane_client.get_work_item.return_value = {
            "id": "i1",
            "name": "[US-01] Auth System",
            "labels": [
                {"id": "lbl-us", "name": "US"},
            ],
            "state": {"id": "st-bl", "name": "Backlog"},
            "parent": None,
            "description_html": "<p>Auth system description</p>",
            "priority": "high",
            "project": BOARD_ID,
        }

        item = await backend.get_item(BOARD_ID, "i1")

        assert isinstance(item, ItemDTO)
        assert item.id == "i1"
        assert item.name == "[US-01] Auth System"
        assert "US" in item.labels
        assert item.state == "backlog"
        assert item.priority == "high"
        mock_plane_client.get_work_item.assert_awaited_with(
            BOARD_ID, "i1", expand="labels,state"
        )


class TestCreateItem:
    async def test_create_item_us(self, backend, mock_plane_client):
        # After create, get_item is called for re-fetch
        mock_plane_client.get_work_item.return_value = {
            "id": "item-new-uuid",
            "name": "[US-01] Auth",
            "labels": [{"id": "lbl-us", "name": "US"}],
            "state": {"id": "st-bl", "name": "Backlog"},
            "parent": None,
            "description_html": "<p><strong>Horas</strong>: 8</p>",
            "priority": "none",
            "project": BOARD_ID,
        }

        result = await backend.create_item(
            BOARD_ID,
            name="[US-01] Auth",
            description="Auth description",
            state="backlog",
            labels=["US"],
            meta={"horas": 8},
        )

        assert isinstance(result, ItemDTO)
        assert result.id == "item-new-uuid"

        # Verify create_work_item was called
        mock_plane_client.create_work_item.assert_awaited_once()
        call_kwargs = mock_plane_client.create_work_item.call_args
        # "US" label should be included
        assert "labels" in call_kwargs.kwargs or len(call_kwargs.args) > 1
        # description_html should contain metadata
        data = call_kwargs.kwargs
        assert "Horas" in data.get("description_html", "")

    async def test_create_item_uc_with_parent(self, backend, mock_plane_client):
        mock_plane_client.get_work_item.return_value = {
            "id": "item-new-uuid",
            "name": "[UC-001] Login",
            "labels": [{"id": "lbl-uc", "name": "UC"}],
            "state": {"id": "st-bl", "name": "Backlog"},
            "parent": "parent-us-id",
            "description_html": "",
            "priority": "none",
            "project": BOARD_ID,
        }

        result = await backend.create_item(
            BOARD_ID,
            name="[UC-001] Login",
            state="backlog",
            labels=["UC"],
            parent_id="parent-us-id",
        )

        assert result.parent_id == "parent-us-id"
        # Verify parent was passed to create_work_item
        call_kwargs = mock_plane_client.create_work_item.call_args.kwargs
        assert call_kwargs.get("parent") == "parent-us-id"


class TestFindItemByField:
    async def test_find_item_by_field_us_id(self, backend, mock_plane_client):
        mock_plane_client.list_work_items.return_value = [
            _make_raw_item("i1", "[US-01] Auth", labels=["lbl-us"]),
            _make_raw_item("i2", "[US-02] Dashboard", labels=["lbl-us"]),
        ]

        result = await backend.find_item_by_field(BOARD_ID, "us_id", "US-02")

        assert result is not None
        assert result.id == "i2"
        assert result.name == "[US-02] Dashboard"

    async def test_find_item_by_field_not_found(self, backend, mock_plane_client):
        mock_plane_client.list_work_items.return_value = [
            _make_raw_item("i1", "[US-01] Auth", labels=["lbl-us"]),
        ]

        result = await backend.find_item_by_field(BOARD_ID, "us_id", "US-99")
        assert result is None


class TestGetItemChildren:
    async def test_get_item_children(self, backend, mock_plane_client):
        mock_plane_client.list_work_items.return_value = [
            _make_raw_item("us1", "[US-01] Auth", labels=["lbl-us"]),
            _make_raw_item(
                "uc1", "[UC-001] Login", labels=["lbl-uc"], parent="us1"
            ),
            _make_raw_item(
                "uc2", "[UC-002] Register", labels=["lbl-uc"], parent="us1"
            ),
            _make_raw_item(
                "uc3", "[UC-003] Stats", labels=["lbl-uc"], parent="us2"
            ),
        ]

        children = await backend.get_item_children(BOARD_ID, "us1")
        assert len(children) == 2
        assert {c.id for c in children} == {"uc1", "uc2"}


class TestAcceptanceCriteria:
    async def test_get_acceptance_criteria(self, backend, mock_plane_client):
        mock_plane_client.list_work_items.return_value = [
            _make_raw_item("uc1", "[UC-001] Login", labels=["lbl-uc"]),
            _make_raw_item(
                "ac1",
                "[AC-01] Validates email",
                labels=["lbl-ac"],
                parent="uc1",
                state="st-bl",
            ),
            _make_raw_item(
                "ac2",
                "[AC-02] Shows error",
                labels=["lbl-ac"],
                parent="uc1",
                state="st-dn",
            ),
            # AC belonging to different UC — should not appear
            _make_raw_item(
                "ac3",
                "[AC-01] Other",
                labels=["lbl-ac"],
                parent="uc2",
            ),
        ]

        criteria = await backend.get_acceptance_criteria(BOARD_ID, "uc1")

        assert len(criteria) == 2
        assert all(isinstance(c, ChecklistItemDTO) for c in criteria)

        ac1 = next(c for c in criteria if c.id == "AC-01")
        assert ac1.text == "Validates email"
        assert ac1.done is False  # backlog state

        ac2 = next(c for c in criteria if c.id == "AC-02")
        assert ac2.text == "Shows error"
        assert ac2.done is True  # done (completed group)

    async def test_mark_acceptance_criterion(self, backend, mock_plane_client):
        mock_plane_client.list_work_items.return_value = [
            _make_raw_item("uc1", "[UC-001] Login", labels=["lbl-uc"]),
            _make_raw_item(
                "ac1",
                "[AC-01] Validates email",
                labels=["lbl-ac"],
                parent="uc1",
                state="st-bl",
            ),
        ]

        result = await backend.mark_acceptance_criterion(
            BOARD_ID, "uc1", "AC-01", passed=True
        )

        assert isinstance(result, ChecklistItemDTO)
        assert result.id == "AC-01"
        assert result.done is True
        assert result.backend_id == "ac1"

        # Should have called update_work_item to move AC to Done
        mock_plane_client.update_work_item.assert_awaited_once_with(
            BOARD_ID, "ac1", state="st-dn"
        )

    async def test_mark_acceptance_criterion_not_found(self, backend, mock_plane_client):
        mock_plane_client.list_work_items.return_value = [
            _make_raw_item("uc1", "[UC-001] Login", labels=["lbl-uc"]),
        ]

        with pytest.raises(ValueError, match="AC-99.*not found"):
            await backend.mark_acceptance_criterion(
                BOARD_ID, "uc1", "AC-99", passed=True
            )

    async def test_create_acceptance_criteria(self, backend, mock_plane_client):
        mock_plane_client.create_work_item.return_value = {"id": "new-ac-uuid"}

        criteria = [
            ("AC-01", "Validates email"),
            ("AC-02", "Shows error"),
        ]
        result = await backend.create_acceptance_criteria(
            BOARD_ID, "uc-parent-id", criteria
        )

        assert len(result) == 2
        assert result[0].id == "AC-01"
        assert result[0].text == "Validates email"
        assert result[0].done is False
        assert result[0].backend_id == "new-ac-uuid"

        assert result[1].id == "AC-02"
        assert result[1].text == "Shows error"

        # Should have called create_work_item twice
        assert mock_plane_client.create_work_item.await_count == 2

        # Verify parent and label were passed
        for call in mock_plane_client.create_work_item.call_args_list:
            kwargs = call.kwargs
            assert kwargs.get("parent") == "uc-parent-id"
            assert "labels" in kwargs


class TestComments:
    async def test_add_comment(self, backend, mock_plane_client):
        result = await backend.add_comment(BOARD_ID, "item1", "Test comment text")

        assert isinstance(result, CommentDTO)
        assert result.id == "comment-uuid-1"
        assert result.author == "Jesus PS"

        # Verify HTML wrapping
        call_args = mock_plane_client.create_comment.call_args
        comment_html = call_args.args[2] if len(call_args.args) > 2 else call_args.kwargs.get("comment_html", "")
        # Plain text should be wrapped in <p> tags
        assert "<p>" in comment_html

    async def test_add_comment_already_html(self, backend, mock_plane_client):
        """If text is already HTML, don't double-wrap."""
        await backend.add_comment(BOARD_ID, "item1", "<p>Already HTML</p>")

        call_args = mock_plane_client.create_comment.call_args
        comment_html = call_args.args[2] if len(call_args.args) > 2 else ""
        assert comment_html == "<p>Already HTML</p>"

    async def test_get_comments(self, backend, mock_plane_client):
        mock_plane_client.list_comments.return_value = [
            {
                "id": "c1",
                "comment_html": "<p>First comment</p>",
                "created_at": "2026-03-10T10:00:00Z",
                "actor_detail": {"display_name": "Dev1"},
            },
            {
                "id": "c2",
                "comment_html": "<p>Second comment</p>",
                "created_at": "2026-03-10T11:00:00Z",
                "actor_detail": {"display_name": "Dev2"},
            },
        ]

        comments = await backend.get_comments(BOARD_ID, "item1")

        assert len(comments) == 2
        assert all(isinstance(c, CommentDTO) for c in comments)
        assert comments[0].id == "c1"
        assert comments[0].text == "First comment"  # HTML stripped
        assert comments[0].author == "Dev1"
        assert comments[1].text == "Second comment"


class TestGetBoardName:
    async def test_get_board_name(self, backend, mock_plane_client):
        name = await backend.get_board_name(BOARD_ID)
        assert name == "Test Project"
        mock_plane_client.get_project.assert_awaited_once_with(BOARD_ID)


class TestStateCaching:
    async def test_state_caching(self, backend, mock_plane_client):
        """States should be fetched once and cached for subsequent calls."""
        # First call populates cache
        states1 = await backend.get_states(BOARD_ID)
        # Second call should use cache
        states2 = await backend.get_states(BOARD_ID)

        assert states1 == states2
        # list_states should only be called once
        mock_plane_client.list_states.assert_awaited_once()

    async def test_cache_invalidation(self, backend, mock_plane_client):
        """After invalidation, states should be re-fetched."""
        await backend.get_states(BOARD_ID)
        assert mock_plane_client.list_states.await_count == 1

        backend._invalidate_caches(BOARD_ID)
        await backend.get_states(BOARD_ID)
        assert mock_plane_client.list_states.await_count == 2


# ── Helper function tests ────────────────────────────────────────────


class TestExtractMetaFromHtml:
    def test_extract_single_field(self):
        html_str = "<p><strong>Horas</strong>: 8</p>"
        meta = _extract_meta_from_html(html_str)
        assert meta == {"horas": "8"}

    def test_extract_multiple_fields(self):
        html_str = (
            "<p><strong>Horas</strong>: 8</p>\n"
            "<p><strong>Pantallas</strong>: 1A, 1B</p>\n"
            "<p><strong>Actor</strong>: Profesional</p>"
        )
        meta = _extract_meta_from_html(html_str)
        assert meta["horas"] == "8"
        assert meta["pantallas"] == "1A, 1B"
        assert meta["actor"] == "Profesional"

    def test_extract_empty_string(self):
        meta = _extract_meta_from_html("")
        assert meta == {}

    def test_extract_none(self):
        meta = _extract_meta_from_html(None)  # type: ignore[arg-type]
        assert meta == {}

    def test_extract_no_meta_fields(self):
        html_str = "<p>Just some regular text</p>"
        meta = _extract_meta_from_html(html_str)
        assert meta == {}

    def test_extract_strips_inner_html_tags(self):
        html_str = "<p><strong>Horas</strong>: <em>8</em></p>"
        meta = _extract_meta_from_html(html_str)
        assert meta["horas"] == "8"

    def test_keys_are_lowercase(self):
        html_str = "<p><strong>HORAS</strong>: 10</p>"
        meta = _extract_meta_from_html(html_str)
        assert "horas" in meta
        assert meta["horas"] == "10"


class TestBuildDescriptionHtml:
    def test_plain_text_wrapped_in_paragraphs(self):
        result = _build_description_html("Hello\nWorld")
        assert "<p>Hello</p>" in result
        assert "<p>World</p>" in result

    def test_html_passthrough(self):
        html_input = "<p>Already HTML</p>"
        result = _build_description_html(html_input)
        assert html_input in result

    def test_meta_fields_appended(self):
        result = _build_description_html("Description", {"horas": 8, "pantallas": "1A"})
        assert "<strong>Horas</strong>: 8" in result
        assert "<strong>Pantallas</strong>: 1A" in result

    def test_empty_description_with_meta(self):
        result = _build_description_html("", {"horas": 5})
        assert "<strong>Horas</strong>: 5" in result

    def test_no_description_no_meta(self):
        result = _build_description_html("")
        assert result == ""

    def test_meta_without_relevant_fields(self):
        """Meta with keys not in the recognized list should be ignored."""
        result = _build_description_html("Desc", {"unknown_field": "value"})
        assert "unknown_field" not in result

    def test_meta_html_escaping(self):
        result = _build_description_html("", {"horas": "<script>alert(1)</script>"})
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_empty_lines_become_empty_paragraphs(self):
        result = _build_description_html("Line1\n\nLine3")
        assert "<p></p>" in result

    def test_actor_meta_field(self):
        result = _build_description_html("Desc", {"actor": "Admin"})
        assert "<strong>Actor</strong>: Admin" in result
