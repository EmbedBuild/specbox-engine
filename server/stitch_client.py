"""Async MCP client for Google Stitch (Streamable HTTP transport).

Communicates with https://stitch.googleapis.com/mcp using the MCP
JSON-RPC protocol over HTTP. Handles long timeouts for screen generation
(up to 5 minutes) and API key authentication.

Exposes 14 native MCP tools (verified against the live server via
tools/list on 2026-05-26). The 6 design-system tools were added in v6.4.0
after the post-Google-I/O audit:
  - upload_design_md
  - create_design_system
  - create_design_system_from_design_md
  - update_design_system
  - list_design_systems
  - apply_design_system

Also exposes a REST batchCreate helper for DESIGN.md / HTML / image
uploads that exceed ~5KB (the practical limit for the upload_design_md
MCP tool, which is bounded by the calling LLM's output token budget,
not by the server).
"""

from __future__ import annotations

import asyncio
import base64
import random
import uuid
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

STITCH_MCP_URL = "https://stitch.googleapis.com/mcp"
STITCH_REST_BASE = "https://stitch.googleapis.com"
# Backwards-compat alias — used by older callers.
STITCH_BASE_URL = STITCH_MCP_URL
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 30.0

# Screen generation can take several minutes
DEFAULT_TIMEOUT = 30.0
GENERATE_TIMEOUT = 360.0  # 6 minutes for generate operations
# create_design_system_from_design_md observed at 43s in smoke v2;
# apply_design_system at 19s. Use a margin.
DESIGN_SYSTEM_TIMEOUT = 180.0  # 3 minutes


class StitchClientError(Exception):
    """Error from the Stitch MCP endpoint."""

    def __init__(self, message: str, code: int | None = None, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


class StitchClient:
    """Async MCP client for Google Stitch design service."""

    def __init__(
        self,
        api_key: str,
        base_url: str = STITCH_MCP_URL,
        rest_base: str = STITCH_REST_BASE,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.rest_base = rest_base.rstrip("/")
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

    # -- Design system (v6.4.0 — native Material 3 chain) --

    async def upload_design_md(
        self,
        project_id: str,
        design_md_content: str,
    ) -> Any:
        """Upload a DESIGN.md file (Material 3 YAML frontmatter) to a project.

        Use this when DESIGN.md is < ~5KB. For larger files, use
        :meth:`upload_via_rest_batch_create`, which bypasses the LLM
        output-token limit on the base64 payload.

        Returns a dict with at minimum ``{"id", "sourceScreen"}`` —
        the new screen instance that can anchor
        :meth:`create_design_system_from_design_md`.
        """
        b64 = base64.b64encode(design_md_content.encode("utf-8")).decode("ascii")
        return await self._call_tool(
            "upload_design_md",
            {
                "projectId": project_id,
                "designMdBase64": b64,
            },
            timeout=DESIGN_SYSTEM_TIMEOUT,
        )

    async def create_design_system(
        self,
        project_id: str,
        *,
        display_name: str | None = None,
    ) -> Any:
        """Create an empty design system on a project.

        Use this when you want full manual control over theme tokens via
        :meth:`update_design_system`. For DESIGN.md-driven creation,
        prefer :meth:`create_design_system_from_design_md` which
        auto-populates theme tokens from the YAML frontmatter and
        avoids a second round trip.
        """
        args: dict[str, Any] = {"projectId": project_id}
        if display_name:
            args["displayName"] = display_name
        return await self._call_tool(
            "create_design_system",
            args,
            timeout=DESIGN_SYSTEM_TIMEOUT,
        )

    async def create_design_system_from_design_md(
        self,
        project_id: str,
        selected_screen_instance: dict[str, str],
        *,
        device_type: str = "DESKTOP",
    ) -> Any:
        """Parse a previously-uploaded DESIGN.md and materialise a DS server-side.

        Args:
            project_id: Stitch project ID (the ID part, NOT the full
                "projects/{id}" path).
            selected_screen_instance: ``{"id": "...", "sourceScreen": "..."}``
                of the DOCUMENT screen returned by :meth:`upload_design_md`.
                MUST NOT include position/dimension fields.
            device_type: Target device — DESKTOP, MOBILE, or TABLET.

        Smoke-verified latency: ~43s.
        """
        return await self._call_tool(
            "create_design_system_from_design_md",
            {
                "projectId": project_id,
                "selectedScreenInstance": selected_screen_instance,
                "deviceType": device_type,
            },
            timeout=DESIGN_SYSTEM_TIMEOUT,
        )

    async def update_design_system(
        self,
        asset_name: str,
        project_id: str,
        theme: dict[str, Any],
        *,
        display_name: str | None = None,
    ) -> Any:
        """Mutate the theme tokens of an existing design system in place.

        Args:
            asset_name: Full asset name like ``"assets/{assetId}"``.
            project_id: Stitch project ID.
            theme: DesignTheme dict. Server-validated against
                :class:`server.stitch_enums.ColorMode`, ``ColorVariant``,
                ``Roundness``, and ``StitchFont``. Use
                ``headlineFont``/``bodyFont``/``labelFont`` — the
                legacy ``font`` field WILL be rejected with
                ``invalid argument``.
            display_name: Optional rename of the DS.

        Operation is destructive on the theme (no versioning).
        """
        design_system: dict[str, Any] = {"theme": theme}
        if display_name:
            design_system["displayName"] = display_name
        return await self._call_tool(
            "update_design_system",
            {
                "name": asset_name,
                "projectId": project_id,
                "designSystem": design_system,
            },
            timeout=DESIGN_SYSTEM_TIMEOUT,
        )

    async def list_design_systems(self, project_id: str) -> Any:
        """List all design systems registered on a project.

        Returns either ``{"designSystems": [...]}`` or an empty dict
        when the project has none.
        """
        return await self._call_tool(
            "list_design_systems",
            {"projectId": project_id},
        )

    async def apply_design_system(
        self,
        project_id: str,
        asset_id: str,
        selected_screen_instances: list[dict[str, str]],
    ) -> Any:
        """Apply a design system to one or more screen instances.

        Args:
            project_id: Stitch project ID.
            asset_id: The bare assetId (NOT the full ``assets/{id}`` name).
            selected_screen_instances: List of ``{"id", "sourceScreen"}``
                dicts. Position/dimension fields ARE NOT allowed by the
                server and WILL produce ``invalid argument``. Filter out
                instances of type ``DESIGN_SYSTEM_INSTANCE`` (the DS's
                own instance) before calling.

        Smoke-verified latency: ~19s for a single screen.
        """
        # Server-side validation guard — fail fast on the client to give
        # better error context than "invalid argument".
        forbidden = {"x", "y", "width", "height"}
        for inst in selected_screen_instances:
            extras = forbidden & set(inst.keys())
            if extras:
                raise StitchClientError(
                    "apply_design_system: selectedScreenInstances must "
                    f"contain only id and sourceScreen, found {sorted(extras)}"
                )
        return await self._call_tool(
            "apply_design_system",
            {
                "projectId": project_id,
                "assetId": asset_id,
                "selectedScreenInstances": selected_screen_instances,
            },
            timeout=DESIGN_SYSTEM_TIMEOUT,
        )

    # -- REST helper for large uploads (bypasses MCP output-token limit) --

    async def upload_via_rest_batch_create(
        self,
        project_id: str,
        *,
        content_bytes: bytes,
        mime_type: str,
        title: str | None = None,
    ) -> Any:
        """Upload content via REST batchCreate endpoint.

        Use this when:
          - DESIGN.md is larger than ~5KB (the upload_design_md MCP tool
            is bounded by the LLM's output-token budget, not by the server).
          - Uploading raw HTML or image assets (PNG / JPEG / WebP) that
            cannot be sent through the MCP at all.

        MIME mapping:
          - ``text/markdown``, ``text/html`` → screen.htmlCode with
            ``screenType: DOCUMENT``.
          - ``image/png``, ``image/jpeg``, ``image/webp`` → screen.screenshot
            with ``screenType: IMAGE``.

        Returns the JSON body of the batchCreate response. ``screenInstances``
        contains the ``{id, sourceScreen}`` records that anchor downstream
        :meth:`create_design_system_from_design_md` calls.
        """
        b64 = base64.b64encode(content_bytes).decode("ascii")
        is_doc = mime_type in {"text/markdown", "text/html"}
        is_image = mime_type in {"image/png", "image/jpeg", "image/webp"}
        if not is_doc and not is_image:
            raise StitchClientError(
                f"Unsupported MIME type for batchCreate: {mime_type}"
            )
        screen: dict[str, Any] = {
            "screenType": "DOCUMENT" if is_doc else "IMAGE",
            "isCreatedByClient": True,
        }
        if is_doc:
            screen["htmlCode"] = {
                "fileContentBase64": b64,
                "mimeType": mime_type,
            }
        else:
            screen["screenshot"] = {
                "fileContentBase64": b64,
                "mimeType": mime_type,
            }
        if title:
            screen["title"] = title

        url = f"{self.rest_base}/v1/projects/{project_id}/screens:batchCreate"
        payload = {
            "parent": f"projects/{project_id}",
            "requests": [{"screen": screen}],
            "createScreenInstances": True,
        }
        client = await self._get_client(timeout=DESIGN_SYSTEM_TIMEOUT)
        resp = await client.post(url, json=payload)
        if resp.status_code not in (200, 201):
            raise StitchClientError(
                f"REST batchCreate failed {resp.status_code}: "
                f"{resp.text[:500]}",
                code=resp.status_code,
            )
        return resp.json()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
