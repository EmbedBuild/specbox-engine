"""Async MCP client for Google Stitch (Streamable HTTP transport).

Communicates with https://stitch.googleapis.com/mcp using the MCP
JSON-RPC protocol over HTTP. Handles long timeouts for screen generation
(up to 5 minutes) and API key authentication.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

STITCH_BASE_URL = "https://stitch.googleapis.com/mcp"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 30.0

# Screen generation can take several minutes
DEFAULT_TIMEOUT = 30.0
GENERATE_TIMEOUT = 360.0  # 6 minutes for generate operations


class StitchClientError(Exception):
    """Error from the Stitch MCP endpoint."""

    def __init__(self, message: str, code: int | None = None, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


class StitchClient:
    """Async MCP client for Google Stitch design service."""

    def __init__(self, api_key: str, base_url: str = STITCH_BASE_URL) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._initialized = False

    async def _get_client(self, timeout: float = DEFAULT_TIMEOUT) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-goog-api-key": self.api_key,
                },
                timeout=httpx.Timeout(timeout, connect=10.0),
            )
        return self._client

    async def _call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Any:
        """Call a tool on the Stitch MCP endpoint via JSON-RPC.

        Uses MCP Streamable HTTP transport: POST with JSON-RPC 2.0 body.
        """
        request_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
        }

        last_exc: Exception | None = None

        for attempt in range(RETRY_MAX_ATTEMPTS):
            try:
                client = await self._get_client(timeout=timeout)
                resp = await client.post(self.base_url, json=payload)

                if resp.status_code in RETRYABLE_STATUS_CODES:
                    delay = min(
                        RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1),
                        RETRY_MAX_DELAY,
                    )
                    logger.warning(
                        "stitch_retryable_error",
                        tool=tool_name,
                        status=resp.status_code,
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                resp.raise_for_status()

                # Handle SSE responses (text/event-stream)
                content_type = resp.headers.get("content-type", "")
                if "text/event-stream" in content_type:
                    return self._parse_sse_response(resp.text, request_id)

                # Standard JSON-RPC response
                result = resp.json()
                if "error" in result:
                    err = result["error"]
                    raise StitchClientError(
                        err.get("message", "Unknown Stitch error"),
                        code=err.get("code"),
                        data=err.get("data"),
                    )

                return self._extract_tool_result(result)

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code in RETRYABLE_STATUS_CODES:
                    delay = min(
                        RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1),
                        RETRY_MAX_DELAY,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(
                    "stitch_http_error",
                    tool=tool_name,
                    status=exc.response.status_code,
                    body=exc.response.text[:500],
                )
                raise StitchClientError(
                    f"Stitch API error {exc.response.status_code}: {exc.response.text[:200]}"
                ) from exc

            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    delay = min(
                        RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1),
                        RETRY_MAX_DELAY,
                    )
                    logger.warning(
                        "stitch_timeout",
                        tool=tool_name,
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise StitchClientError(
                    f"Stitch request timed out after {timeout}s for tool {tool_name}"
                ) from exc

            except (httpx.RequestError, OSError) as exc:
                last_exc = exc
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    delay = min(
                        RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1),
                        RETRY_MAX_DELAY,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise StitchClientError(
                    f"Network error calling Stitch: {exc}"
                ) from exc

        raise StitchClientError(
            f"Failed after {RETRY_MAX_ATTEMPTS} attempts for tool {tool_name}"
        ) from last_exc

    def _parse_sse_response(self, body: str, request_id: str) -> Any:
        """Parse a Server-Sent Events response to extract the JSON-RPC result."""
        import json

        for line in body.splitlines():
            if line.startswith("data: "):
                data_str = line[6:].strip()
                if not data_str:
                    continue
                try:
                    data = json.loads(data_str)
                    if isinstance(data, dict) and "result" in data:
                        return self._extract_tool_result(data)
                    if isinstance(data, dict) and "error" in data:
                        err = data["error"]
                        raise StitchClientError(
                            err.get("message", "Unknown Stitch error"),
                            code=err.get("code"),
                            data=err.get("data"),
                        )
                except json.JSONDecodeError:
                    continue
        raise StitchClientError("No valid JSON-RPC result found in SSE response")

    @staticmethod
    def _extract_tool_result(rpc_response: dict) -> Any:
        """Extract the tool result content from a JSON-RPC response."""
        result = rpc_response.get("result", {})
        # MCP tools/call result has a "content" array
        content = result.get("content", [])
        if not content:
            return result

        # If single text content, return the text directly
        if len(content) == 1 and content[0].get("type") == "text":
            text = content[0].get("text", "")
            # Try to parse as JSON
            import json
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return {"text": text}

        # Return all content items
        return {"content": content, "isError": result.get("isError", False)}

    # ── High-level tool wrappers ──────────────────────────────────
    # Covers all 12 native Stitch MCP tools.

    # -- Project management --

    async def create_project(self, title: str) -> Any:
        """Create a new Stitch project/workspace."""
        return await self._call_tool("create_project", {"title": title})

    async def list_projects(self) -> Any:
        """List all Stitch projects for the authenticated user."""
        return await self._call_tool("list_projects")

    async def get_project(self, project_id: str) -> Any:
        """Get details of a specific Stitch project."""
        return await self._call_tool("get_project", {"projectId": project_id})

    # -- Screen queries --

    async def list_screens(self, project_id: str) -> Any:
        """List all screens in a Stitch project."""
        return await self._call_tool("list_screens", {"projectId": project_id})

    async def get_screen(self, project_id: str, screen_id: str) -> Any:
        """Get metadata for a specific screen."""
        return await self._call_tool(
            "get_screen",
            {"projectId": project_id, "screenId": screen_id},
        )

    async def fetch_screen_code(self, project_id: str, screen_id: str) -> Any:
        """Download the raw HTML/frontend code of a screen."""
        return await self._call_tool(
            "fetch_screen_code",
            {"projectId": project_id, "screenId": screen_id},
        )

    async def fetch_screen_image(self, project_id: str, screen_id: str) -> Any:
        """Download the high-res screenshot of a screen (base64)."""
        return await self._call_tool(
            "fetch_screen_image",
            {"projectId": project_id, "screenId": screen_id},
        )

    # -- Generation --

    async def generate_screen_from_text(
        self,
        project_id: str,
        prompt: str,
        *,
        device_type: str = "DESKTOP",
        model_id: str = "GEMINI_3_PRO",
    ) -> Any:
        """Generate a UI screen from a text prompt. Can take several minutes."""
        return await self._call_tool(
            "generate_screen_from_text",
            {
                "projectId": project_id,
                "prompt": prompt,
                "deviceType": device_type,
                "modelId": model_id,
            },
            timeout=GENERATE_TIMEOUT,
        )

    async def edit_screens(
        self,
        project_id: str,
        screen_id: str,
        prompt: str,
        *,
        device_type: str | None = None,
        model_id: str | None = None,
    ) -> Any:
        """Edit an existing screen with a text prompt. Can take several minutes."""
        args: dict[str, Any] = {
            "projectId": project_id,
            "screenId": screen_id,
            "prompt": prompt,
        }
        if device_type:
            args["deviceType"] = device_type
        if model_id:
            args["modelId"] = model_id
        return await self._call_tool("edit_screens", args, timeout=GENERATE_TIMEOUT)

    async def generate_variants(
        self,
        project_id: str,
        screen_id: str,
        *,
        prompt: str | None = None,
        variant_count: int = 3,
        creative_range: str = "EXPLORE",
        aspects: list[str] | None = None,
    ) -> Any:
        """Generate design variants of an existing screen.

        Args:
            creative_range: REFINE | EXPLORE | REIMAGINE
            aspects: subset of LAYOUT, COLOR_SCHEME, IMAGES, TEXT_FONT, TEXT_CONTENT
        """
        args: dict[str, Any] = {
            "projectId": project_id,
            "screenId": screen_id,
            "variantCount": variant_count,
            "creativeRange": creative_range,
        }
        if prompt:
            args["prompt"] = prompt
        if aspects:
            args["aspects"] = aspects
        return await self._call_tool("generate_variants", args, timeout=GENERATE_TIMEOUT)

    # -- Design intelligence --

    async def extract_design_context(self, project_id: str, screen_id: str) -> Any:
        """Extract Design DNA (fonts, colors, layouts) from a screen."""
        return await self._call_tool(
            "extract_design_context",
            {"projectId": project_id, "screenId": screen_id},
        )

    async def build_site(
        self,
        project_id: str,
        routes: list[dict[str, str]],
    ) -> Any:
        """Build a multi-page site by mapping screens to routes.

        Args:
            routes: List of {"screenId": "...", "route": "/"} mappings.
        """
        return await self._call_tool(
            "build_site",
            {"projectId": project_id, "routes": routes},
            timeout=GENERATE_TIMEOUT,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
