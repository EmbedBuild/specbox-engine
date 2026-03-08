"""Async HTTP client for Trello REST API. Encapsulates ALL HTTP calls."""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 30.0


class TrelloClient:
    """Async client for Trello REST API."""

    def __init__(self, api_key: str, token: str, base_url: str = "https://api.trello.com/1"):
        self.api_key = api_key
        self.token = token
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                params={"key": self.api_key, "token": self.token},
                timeout=30.0,
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        """Execute an HTTP request with retry logic."""
        last_exc: Exception | None = None

        for attempt in range(RETRY_MAX_ATTEMPTS):
            try:
                client = await self._get_client()
                resp = await client.request(
                    method.upper(),
                    path,
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                )
                resp.raise_for_status()
                if resp.status_code == 204 or not resp.content:
                    return {}
                return resp.json()

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in RETRYABLE_STATUS_CODES:
                    raise
                delay = min(RETRY_BASE_DELAY * (2**attempt), RETRY_MAX_DELAY)
                jitter = random.uniform(0, delay * 0.1)
                logger.warning(
                    "trello_retry",
                    status=exc.response.status_code,
                    attempt=attempt + 1,
                    delay=delay + jitter,
                )
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(delay + jitter)

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                delay = min(RETRY_BASE_DELAY * (2**attempt), RETRY_MAX_DELAY)
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(delay)

        if last_exc:
            raise last_exc
        raise RuntimeError("No retry attempts executed")

    # --- Board ---

    async def create_board(self, name: str, default_lists: bool = False) -> dict:
        return await self._request("POST", "/boards", params={"name": name, "defaultLists": str(default_lists).lower()})

    async def get_board(self, board_id: str) -> dict:
        return await self._request("GET", f"/boards/{board_id}")

    async def get_board_lists(self, board_id: str, filter: str = "open") -> list[dict]:
        return await self._request("GET", f"/boards/{board_id}/lists", params={"filter": filter})

    async def get_board_cards(self, board_id: str, fields: str = "all") -> list[dict]:
        return await self._request(
            "GET",
            f"/boards/{board_id}/cards",
            params={"fields": fields, "customFieldItems": "true"},
        )

    async def get_board_labels(self, board_id: str) -> list[dict]:
        return await self._request("GET", f"/boards/{board_id}/labels")

    async def get_board_custom_fields(self, board_id: str) -> list[dict]:
        return await self._request("GET", f"/boards/{board_id}/customFields")

    # --- Lists ---

    async def create_list(self, board_id: str, name: str, pos: str = "bottom") -> dict:
        return await self._request("POST", "/lists", params={"name": name, "idBoard": board_id, "pos": pos})

    # --- Cards ---

    async def create_card(
        self,
        list_id: str,
        name: str,
        desc: str = "",
        label_ids: list[str] | None = None,
        pos: str = "bottom",
    ) -> dict:
        params: dict[str, Any] = {"idList": list_id, "name": name, "desc": desc, "pos": pos}
        if label_ids:
            params["idLabels"] = ",".join(label_ids)
        return await self._request("POST", "/cards", params=params)

    async def get_card(self, card_id: str) -> dict:
        return await self._request(
            "GET",
            f"/cards/{card_id}",
            params={"customFieldItems": "true", "fields": "all"},
        )

    async def update_card(self, card_id: str, **fields: Any) -> dict:
        return await self._request("PUT", f"/cards/{card_id}", params=fields)

    async def move_card(self, card_id: str, list_id: str) -> dict:
        return await self._request("PUT", f"/cards/{card_id}", params={"idList": list_id})

    async def add_comment(self, card_id: str, text: str) -> dict:
        return await self._request("POST", f"/cards/{card_id}/actions/comments", params={"text": text})

    async def get_card_attachments(self, card_id: str) -> list[dict]:
        return await self._request("GET", f"/cards/{card_id}/attachments")

    async def add_attachment(self, card_id: str, file_bytes: bytes, name: str, mime_type: str = "application/pdf") -> dict:
        return await self._request(
            "POST",
            f"/cards/{card_id}/attachments",
            files={"file": (name, file_bytes, mime_type)},
        )

    async def get_card_actions(self, card_id: str, filter: str = "commentCard") -> list[dict]:
        return await self._request("GET", f"/cards/{card_id}/actions", params={"filter": filter})

    # --- Custom Fields ---

    async def create_custom_field(
        self,
        board_id: str,
        name: str,
        field_type: str,
        options: list[str] | None = None,
    ) -> dict:
        body: dict[str, Any] = {
            "idModel": board_id,
            "modelType": "board",
            "name": name,
            "type": field_type,
            "pos": "bottom",
        }
        if options and field_type == "list":
            body["options"] = [{"value": {"text": opt}} for opt in options]
        return await self._request("POST", "/customFields", json=body)

    async def set_custom_field_value(self, card_id: str, field_id: str, value: dict[str, Any]) -> dict:
        """Set a custom field value. value format depends on type:
        - text: {"value": {"text": "..."}}
        - number: {"value": {"number": "..."}}
        - list: {"idValue": "option_id"}
        """
        return await self._request("PUT", f"/cards/{card_id}/customField/{field_id}/item", json=value)

    async def get_card_custom_field_items(self, card_id: str) -> list[dict]:
        return await self._request("GET", f"/cards/{card_id}/customFieldItems")

    # --- Checklists ---

    async def create_checklist(self, card_id: str, name: str) -> dict:
        return await self._request("POST", "/checklists", params={"idCard": card_id, "name": name})

    async def add_checklist_item(self, checklist_id: str, name: str, pos: str = "bottom") -> dict:
        return await self._request(
            "POST", f"/checklists/{checklist_id}/checkItems", params={"name": name, "pos": pos}
        )

    async def update_checklist_item(self, card_id: str, checkitem_id: str, state: str = "complete") -> dict:
        return await self._request(
            "PUT",
            f"/cards/{card_id}/checkItem/{checkitem_id}",
            params={"state": state},
        )

    async def get_card_checklists(self, card_id: str) -> list[dict]:
        return await self._request(
            "GET",
            f"/cards/{card_id}/checklists",
            params={"checkItem_fields": "name,state,pos"},
        )

    # --- Labels ---

    async def create_label(self, board_id: str, name: str, color: str) -> dict:
        return await self._request("POST", "/labels", params={"name": name, "color": color, "idBoard": board_id})

    async def add_label_to_card(self, card_id: str, label_id: str) -> dict:
        return await self._request("POST", f"/cards/{card_id}/idLabels", params={"value": label_id})

    # --- Members ---

    async def get_me(self) -> dict:
        return await self._request("GET", "/members/me")

    # --- Cleanup ---

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
