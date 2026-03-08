"""Tests for TrelloClient using respx mocks."""

import pytest
import httpx
import respx

from src.trello_client import TrelloClient


@pytest.fixture
def trello_client():
    return TrelloClient(api_key="test_key", token="test_token")


class TestTrelloClientRequests:
    @respx.mock
    async def test_get_board(self, trello_client):
        respx.get("https://api.trello.com/1/boards/board123").mock(
            return_value=httpx.Response(200, json={"id": "board123", "name": "Test"})
        )
        result = await trello_client.get_board("board123")
        assert result["id"] == "board123"
        await trello_client.close()

    @respx.mock
    async def test_create_board(self, trello_client):
        respx.post("https://api.trello.com/1/boards").mock(
            return_value=httpx.Response(200, json={"id": "new_board", "name": "New", "url": "https://trello.com/b/new"})
        )
        result = await trello_client.create_board("New")
        assert result["id"] == "new_board"
        await trello_client.close()

    @respx.mock
    async def test_get_board_cards(self, trello_client):
        respx.get("https://api.trello.com/1/boards/board123/cards").mock(
            return_value=httpx.Response(200, json=[{"id": "c1"}, {"id": "c2"}])
        )
        result = await trello_client.get_board_cards("board123")
        assert len(result) == 2
        await trello_client.close()

    @respx.mock
    async def test_create_card(self, trello_client):
        respx.post("https://api.trello.com/1/cards").mock(
            return_value=httpx.Response(200, json={"id": "new_card", "name": "Test Card"})
        )
        result = await trello_client.create_card("list123", "Test Card")
        assert result["id"] == "new_card"
        await trello_client.close()

    @respx.mock
    async def test_move_card(self, trello_client):
        respx.put("https://api.trello.com/1/cards/card123").mock(
            return_value=httpx.Response(200, json={"id": "card123", "idList": "list456"})
        )
        result = await trello_client.move_card("card123", "list456")
        assert result["idList"] == "list456"
        await trello_client.close()

    @respx.mock
    async def test_create_checklist(self, trello_client):
        respx.post("https://api.trello.com/1/checklists").mock(
            return_value=httpx.Response(200, json={"id": "cl123", "name": "ACs"})
        )
        result = await trello_client.create_checklist("card123", "ACs")
        assert result["id"] == "cl123"
        await trello_client.close()

    @respx.mock
    async def test_add_comment(self, trello_client):
        respx.post("https://api.trello.com/1/cards/card123/actions/comments").mock(
            return_value=httpx.Response(200, json={"id": "action123"})
        )
        result = await trello_client.add_comment("card123", "Test comment")
        assert result["id"] == "action123"
        await trello_client.close()

    @respx.mock
    async def test_retry_on_429(self, trello_client):
        route = respx.get("https://api.trello.com/1/boards/board123")
        route.side_effect = [
            httpx.Response(429),
            httpx.Response(200, json={"id": "board123"}),
        ]
        result = await trello_client.get_board("board123")
        assert result["id"] == "board123"
        await trello_client.close()

    @respx.mock
    async def test_error_on_404(self, trello_client):
        respx.get("https://api.trello.com/1/boards/invalid").mock(
            return_value=httpx.Response(404, text="not found")
        )
        with pytest.raises(httpx.HTTPStatusError):
            await trello_client.get_board("invalid")
        await trello_client.close()


class TestCustomFields:
    @respx.mock
    async def test_create_custom_field(self, trello_client):
        respx.post("https://api.trello.com/1/customFields").mock(
            return_value=httpx.Response(200, json={"id": "cf123", "name": "tipo"})
        )
        result = await trello_client.create_custom_field("board123", "tipo", "list", ["US", "UC"])
        assert result["id"] == "cf123"
        await trello_client.close()

    @respx.mock
    async def test_set_custom_field_value(self, trello_client):
        respx.put("https://api.trello.com/1/cards/card123/customField/cf123/item").mock(
            return_value=httpx.Response(200, json={})
        )
        result = await trello_client.set_custom_field_value("card123", "cf123", {"value": {"text": "US-01"}})
        assert result == {}
        await trello_client.close()


class TestRemainingMethods:
    """Cover all remaining TrelloClient methods."""

    @respx.mock
    async def test_get_board_lists(self, trello_client):
        respx.get("https://api.trello.com/1/boards/b1/lists").mock(
            return_value=httpx.Response(200, json=[{"id": "l1", "name": "Backlog"}])
        )
        result = await trello_client.get_board_lists("b1")
        assert len(result) == 1
        await trello_client.close()

    @respx.mock
    async def test_get_board_labels(self, trello_client):
        respx.get("https://api.trello.com/1/boards/b1/labels").mock(
            return_value=httpx.Response(200, json=[{"id": "lb1", "name": "US"}])
        )
        result = await trello_client.get_board_labels("b1")
        assert len(result) == 1
        await trello_client.close()

    @respx.mock
    async def test_get_board_custom_fields(self, trello_client):
        respx.get("https://api.trello.com/1/boards/b1/customFields").mock(
            return_value=httpx.Response(200, json=[{"id": "cf1"}])
        )
        result = await trello_client.get_board_custom_fields("b1")
        assert len(result) == 1
        await trello_client.close()

    @respx.mock
    async def test_create_list(self, trello_client):
        respx.post("https://api.trello.com/1/lists").mock(
            return_value=httpx.Response(200, json={"id": "l1"})
        )
        result = await trello_client.create_list("b1", "Backlog")
        assert result["id"] == "l1"
        await trello_client.close()

    @respx.mock
    async def test_get_card(self, trello_client):
        respx.get("https://api.trello.com/1/cards/c1").mock(
            return_value=httpx.Response(200, json={"id": "c1", "name": "Card"})
        )
        result = await trello_client.get_card("c1")
        assert result["id"] == "c1"
        await trello_client.close()

    @respx.mock
    async def test_update_card(self, trello_client):
        respx.put("https://api.trello.com/1/cards/c1").mock(
            return_value=httpx.Response(200, json={"id": "c1"})
        )
        result = await trello_client.update_card("c1", name="Updated")
        assert result["id"] == "c1"
        await trello_client.close()

    @respx.mock
    async def test_get_card_attachments(self, trello_client):
        respx.get("https://api.trello.com/1/cards/c1/attachments").mock(
            return_value=httpx.Response(200, json=[{"id": "a1"}])
        )
        result = await trello_client.get_card_attachments("c1")
        assert len(result) == 1
        await trello_client.close()

    @respx.mock
    async def test_add_attachment(self, trello_client):
        respx.post("https://api.trello.com/1/cards/c1/attachments").mock(
            return_value=httpx.Response(200, json={"id": "a1", "url": "http://x"})
        )
        result = await trello_client.add_attachment("c1", b"pdf_bytes", "test.pdf")
        assert result["id"] == "a1"
        await trello_client.close()

    @respx.mock
    async def test_get_card_actions(self, trello_client):
        respx.get("https://api.trello.com/1/cards/c1/actions").mock(
            return_value=httpx.Response(200, json=[{"id": "act1"}])
        )
        result = await trello_client.get_card_actions("c1")
        assert len(result) == 1
        await trello_client.close()

    @respx.mock
    async def test_get_card_custom_field_items(self, trello_client):
        respx.get("https://api.trello.com/1/cards/c1/customFieldItems").mock(
            return_value=httpx.Response(200, json=[{"id": "cfi1"}])
        )
        result = await trello_client.get_card_custom_field_items("c1")
        assert len(result) == 1
        await trello_client.close()

    @respx.mock
    async def test_add_checklist_item(self, trello_client):
        respx.post("https://api.trello.com/1/checklists/cl1/checkItems").mock(
            return_value=httpx.Response(200, json={"id": "ci1"})
        )
        result = await trello_client.add_checklist_item("cl1", "Item 1")
        assert result["id"] == "ci1"
        await trello_client.close()

    @respx.mock
    async def test_update_checklist_item(self, trello_client):
        respx.put("https://api.trello.com/1/cards/c1/checkItem/ci1").mock(
            return_value=httpx.Response(200, json={})
        )
        result = await trello_client.update_checklist_item("c1", "ci1", "complete")
        assert result == {}
        await trello_client.close()

    @respx.mock
    async def test_get_card_checklists(self, trello_client):
        respx.get("https://api.trello.com/1/cards/c1/checklists").mock(
            return_value=httpx.Response(200, json=[{"id": "cl1"}])
        )
        result = await trello_client.get_card_checklists("c1")
        assert len(result) == 1
        await trello_client.close()

    @respx.mock
    async def test_create_label(self, trello_client):
        respx.post("https://api.trello.com/1/labels").mock(
            return_value=httpx.Response(200, json={"id": "lb1"})
        )
        result = await trello_client.create_label("b1", "US", "blue")
        assert result["id"] == "lb1"
        await trello_client.close()

    @respx.mock
    async def test_add_label_to_card(self, trello_client):
        respx.post("https://api.trello.com/1/cards/c1/idLabels").mock(
            return_value=httpx.Response(200, json={})
        )
        result = await trello_client.add_label_to_card("c1", "lb1")
        assert result == {}
        await trello_client.close()

    @respx.mock
    async def test_get_me(self, trello_client):
        respx.get("https://api.trello.com/1/members/me").mock(
            return_value=httpx.Response(200, json={"id": "u1", "username": "dev"})
        )
        result = await trello_client.get_me()
        assert result["username"] == "dev"
        await trello_client.close()

    @respx.mock
    async def test_create_card_with_labels(self, trello_client):
        respx.post("https://api.trello.com/1/cards").mock(
            return_value=httpx.Response(200, json={"id": "c1"})
        )
        result = await trello_client.create_card("l1", "Card", label_ids=["lb1", "lb2"])
        assert result["id"] == "c1"
        await trello_client.close()

    @respx.mock
    async def test_create_custom_field_text(self, trello_client):
        respx.post("https://api.trello.com/1/customFields").mock(
            return_value=httpx.Response(200, json={"id": "cf1"})
        )
        result = await trello_client.create_custom_field("b1", "us_id", "text")
        assert result["id"] == "cf1"
        await trello_client.close()

    @respx.mock
    async def test_204_response(self, trello_client):
        respx.delete("https://api.trello.com/1/cards/c1").mock(
            return_value=httpx.Response(204)
        )
        result = await trello_client._request("DELETE", "/cards/c1")
        assert result == {}
        await trello_client.close()

    async def test_close_idempotent(self, trello_client):
        await trello_client.close()
        await trello_client.close()  # Should not raise

    @respx.mock
    async def test_connection_error_retry(self, trello_client):
        route = respx.get("https://api.trello.com/1/boards/b1")
        route.side_effect = [
            httpx.ConnectError("connection refused"),
            httpx.Response(200, json={"id": "b1"}),
        ]
        result = await trello_client.get_board("b1")
        assert result["id"] == "b1"
        await trello_client.close()
