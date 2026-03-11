"""Async HTTP client for Plane REST API v1.

Encapsulates ALL HTTP calls to Plane. Mirrors the pattern of trello_client.py
with retry logic, exponential backoff, and async httpx.
"""

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


class PlaneClient:
    """Async client for Plane REST API v1 (self-hosted or cloud)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        workspace_slug: str,
    ) -> None:
        # Normalize base_url: strip trailing slash
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.workspace_slug = workspace_slug
        self._client: httpx.AsyncClient | None = None

    # ── Internal HTTP ────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[dict[str, Any]] | None = None,
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
                )
                resp.raise_for_status()
                if resp.status_code == 204 or not resp.content:
                    return {}
                return resp.json()

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in RETRYABLE_STATUS_CODES:
                    logger.error(
                        "plane_http_error",
                        status=exc.response.status_code,
                        path=path,
                        body=exc.response.text[:500],
                    )
                    raise
                delay = min(RETRY_BASE_DELAY * (2**attempt), RETRY_MAX_DELAY)
                jitter = random.uniform(0, delay * 0.1)
                logger.warning(
                    "plane_retry",
                    status=exc.response.status_code,
                    attempt=attempt + 1,
                    delay=delay + jitter,
                )
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(delay + jitter)

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                delay = min(RETRY_BASE_DELAY * (2**attempt), RETRY_MAX_DELAY)
                logger.warning(
                    "plane_connection_retry",
                    error=str(exc),
                    attempt=attempt + 1,
                    delay=delay,
                )
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(delay)

        if last_exc:
            raise last_exc
        raise RuntimeError("No retry attempts executed")

    def _ws_path(self, suffix: str) -> str:
        """Build workspace-scoped API v1 path."""
        return f"/api/v1/workspaces/{self.workspace_slug}/{suffix}"

    def _proj_path(self, project_id: str, suffix: str) -> str:
        """Build project-scoped API v1 path."""
        return self._ws_path(f"projects/{project_id}/{suffix}")

    # ── Auth ─────────────────────────────────────────────────────

    async def get_me(self) -> dict:
        """Get the authenticated user."""
        return await self._request("GET", "/api/v1/users/me/")

    # ── Projects ─────────────────────────────────────────────────

    async def list_projects(self) -> list[dict]:
        return await self._request("GET", self._ws_path("projects/"))

    async def create_project(
        self, name: str, identifier: str, **kwargs: Any
    ) -> dict:
        body: dict[str, Any] = {"name": name, "identifier": identifier, **kwargs}
        return await self._request("POST", self._ws_path("projects/"), json=body)

    async def get_project(self, project_id: str) -> dict:
        return await self._request("GET", self._ws_path(f"projects/{project_id}/"))

    # ── States ───────────────────────────────────────────────────

    async def list_states(self, project_id: str) -> list[dict]:
        return await self._request("GET", self._proj_path(project_id, "states/"))

    async def create_state(
        self,
        project_id: str,
        name: str,
        color: str,
        group: str,
        **kwargs: Any,
    ) -> dict:
        body: dict[str, Any] = {
            "name": name,
            "color": color,
            "group": group,
            **kwargs,
        }
        return await self._request(
            "POST", self._proj_path(project_id, "states/"), json=body
        )

    # ── Labels ───────────────────────────────────────────────────

    async def list_labels(self, project_id: str) -> list[dict]:
        return await self._request("GET", self._proj_path(project_id, "labels/"))

    async def create_label(
        self, project_id: str, name: str, color: str, **kwargs: Any
    ) -> dict:
        body: dict[str, Any] = {"name": name, "color": color, **kwargs}
        return await self._request(
            "POST", self._proj_path(project_id, "labels/"), json=body
        )

    # ── Work Items (Issues) ──────────────────────────────────────

    async def list_work_items(
        self, project_id: str, **params: Any
    ) -> list[dict]:
        """List all work items with automatic pagination support."""
        all_items: list[dict] = []
        query_params = dict(params)
        page = 1

        while True:
            query_params["page"] = page
            response = await self._request(
                "GET",
                self._proj_path(project_id, "issues/"),
                params=query_params,
            )

            # Handle paginated response
            if isinstance(response, dict) and "results" in response:
                all_items.extend(response["results"])
                if not response.get("next_page_results", False):
                    break
                page += 1
            # Handle plain list response
            elif isinstance(response, list):
                all_items.extend(response)
                break
            else:
                # Unexpected format — return as-is in a list
                logger.warning(
                    "plane_unexpected_response_format",
                    project_id=project_id,
                    response_type=type(response).__name__,
                )
                break

        return all_items

    async def get_work_item(
        self,
        project_id: str,
        item_id: str,
        expand: str = "labels,state",
    ) -> dict:
        params: dict[str, Any] = {}
        if expand:
            params["expand"] = expand
        return await self._request(
            "GET",
            self._proj_path(project_id, f"issues/{item_id}/"),
            params=params,
        )

    async def create_work_item(
        self, project_id: str, **data: Any
    ) -> dict:
        return await self._request(
            "POST",
            self._proj_path(project_id, "issues/"),
            json=data,
        )

    async def update_work_item(
        self, project_id: str, item_id: str, **data: Any
    ) -> dict:
        return await self._request(
            "PATCH",
            self._proj_path(project_id, f"issues/{item_id}/"),
            json=data,
        )

    # ── Comments ─────────────────────────────────────────────────

    async def list_comments(
        self, project_id: str, item_id: str
    ) -> list[dict]:
        return await self._request(
            "GET",
            self._proj_path(project_id, f"issues/{item_id}/comments/"),
        )

    async def create_comment(
        self, project_id: str, item_id: str, comment_html: str
    ) -> dict:
        return await self._request(
            "POST",
            self._proj_path(project_id, f"issues/{item_id}/comments/"),
            json={"comment_html": comment_html},
        )

    # ── Links ────────────────────────────────────────────────────

    async def list_links(
        self, project_id: str, item_id: str
    ) -> list[dict]:
        return await self._request(
            "GET",
            self._proj_path(project_id, f"issues/{item_id}/links/"),
        )

    async def create_link(
        self, project_id: str, item_id: str, url: str, title: str = ""
    ) -> dict:
        body: dict[str, Any] = {"url": url}
        if title:
            body["title"] = title
        return await self._request(
            "POST",
            self._proj_path(project_id, f"issues/{item_id}/links/"),
            json=body,
        )

    # ── Modules ──────────────────────────────────────────────────

    async def list_modules(self, project_id: str) -> list[dict]:
        return await self._request(
            "GET", self._proj_path(project_id, "modules/")
        )

    async def create_module(
        self, project_id: str, name: str, **kwargs: Any
    ) -> dict:
        body: dict[str, Any] = {"name": name, **kwargs}
        return await self._request(
            "POST", self._proj_path(project_id, "modules/"), json=body
        )

    async def add_items_to_module(
        self,
        project_id: str,
        module_id: str,
        item_ids: list[str],
    ) -> None:
        """Add work items to a module."""
        body = [{"issue": iid} for iid in item_ids]
        await self._request(
            "POST",
            self._proj_path(project_id, f"modules/{module_id}/issues/"),
            json=body,
        )

    async def list_module_items(
        self, project_id: str, module_id: str
    ) -> list[dict]:
        return await self._request(
            "GET",
            self._proj_path(project_id, f"modules/{module_id}/issues/"),
        )

    # ── Activities ───────────────────────────────────────────────

    async def list_activities(
        self, project_id: str, item_id: str
    ) -> list[dict]:
        return await self._request(
            "GET",
            self._proj_path(project_id, f"issues/{item_id}/activities/"),
        )

    # ── Cleanup ──────────────────────────────────────────────────

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
