"""Async MCP client for Google Stitch (Streamable HTTP transport).

Communicates with https://stitch.googleapis.com/mcp using the MCP
JSON-RPC protocol over HTTP. Handles long timeouts for screen generation
(up to 5 minutes) and API key authentication.

The Stitch MCP exposes 15 tools (tools/list on 2026-10-05, saved in
``.quality/evidence/stitch_smoke/mcp_tools_schema.json``; refresh it with
``python -m server.stitch_schema``):
  - projects: create_project, get_project, list_projects, delete_project
  - screens: list_screens, get_screen, generate_screen_from_text,
    edit_screens, generate_variants
  - design systems: upload_design_md, create_design_system,
    create_design_system_from_design_md, update_design_system,
    list_design_systems, apply_design_system

``delete_project`` has no wrapper on purpose: it is irreversible and nothing
in the engine needs it. ``tests/test_stitch_contract.py`` validates every
call below against that schema (UC-8408).

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

from .stitch_enums import DEFAULT_MODEL

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


def project_resource(project_id: str) -> str:
    """``projects/{id}`` for a bare id or one that already has the prefix (UC-8402)."""
    pid = project_id.strip().strip("/")
    return pid if pid.startswith("projects/") else f"projects/{pid}"


def screen_resource(project_id: str, screen_id: str) -> str:
    """``projects/{p}/screens/{s}`` without repeating a prefix the ids already carry."""
    sid = screen_id.strip().strip("/")
    if sid.startswith("projects/"):
        return sid
    if sid.startswith("screens/"):
        sid = sid[len("screens/"):]
    return f"{project_resource(project_id)}/screens/{sid}"


class StitchClientError(Exception):
    """Error from the Stitch MCP endpoint."""

    def __init__(self, message: str, code: int | None = None, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


class StitchTimeoutError(StitchClientError):
    """Stitch did not answer in time.

    For a generation (``may_still_complete``) the work goes on server-side:
    asking again can create the same screen twice (UC-8503).
    """

    may_still_complete = False

    def __init__(self, message: str, *, may_still_complete: bool = False):
        super().__init__(message)
        self.may_still_complete = may_still_complete


def screen_ids_for(screen_ids: str | list[str]) -> list[str]:
    """``selectedScreenIds`` as the API asks for it: bare ids, never empty (UC-8404).

    Accepts one id, a comma-separated string or a list, with or without the
    ``screens/`` or ``projects/{p}/screens/`` prefix.
    """
    items = [screen_ids] if isinstance(screen_ids, str) else list(screen_ids or [])
    ids: list[str] = []
    for item in items:
        for part in str(item).split(","):
            sid = part.strip().strip("/")
            if not sid:
                continue
            sid = sid.rsplit("/screens/", 1)[-1]
            ids.append(sid.removeprefix("screens/"))
    if not ids:
        raise StitchClientError("selectedScreenIds needs at least one screen id")
    return ids


# The theme fields the API marks as required (tools/list, 2026-10-05).
REQUIRED_THEME_FIELDS = ("colorMode", "headlineFont", "bodyFont", "roundness", "customColor")


def design_system_payload(display_name: str | None, theme: dict[str, Any] | None) -> dict[str, Any]:
    """``designSystem`` as ``create_design_system`` and ``update_design_system`` ask for it.

    Checked before any call, so a missing field is named here instead of
    coming back from Stitch as «invalid argument» (UC-8403).
    """
    name = (display_name or "").strip()
    if not name:
        raise StitchClientError("designSystem.displayName is required")
    return {"displayName": name, "theme": check_theme(theme)}


def check_theme(theme: dict[str, Any] | None) -> dict[str, Any]:
    """A copy of ``theme`` with every required field, or the error naming what is missing."""
    theme = dict(theme or {})
    if "font" in theme:
        raise StitchClientError(
            "DesignTheme.font is the deprecated legacy field; use headlineFont / bodyFont / labelFont."
        )
    missing = [field for field in REQUIRED_THEME_FIELDS if not theme.get(field)]
    if missing:
        raise StitchClientError("designSystem.theme is missing required fields: " + ", ".join(missing))
    return theme


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
        generates: bool = False,
    ) -> Any:
        """Call a tool on the Stitch MCP endpoint via JSON-RPC.

        Uses MCP Streamable HTTP transport: POST with JSON-RPC 2.0 body.

        ``timeout`` applies to this request whatever the connection was
        opened with. ``generates`` marks a call that creates screens
        (generate, edit, variants): Stitch asks not to repeat those
        («DO NOT RETRY»), so they get one attempt and a timeout says the
        screen may still appear (UC-8503).
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
        attempts = 1 if generates else RETRY_MAX_ATTEMPTS
        request_timeout = httpx.Timeout(timeout, connect=10.0)

        for attempt in range(attempts):
            try:
                client = await self._get_client(timeout=timeout)
                resp = await client.post(self.base_url, json=payload, timeout=request_timeout)

                if resp.status_code in RETRYABLE_STATUS_CODES and attempt < attempts - 1:
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
                if exc.response.status_code in RETRYABLE_STATUS_CODES and attempt < attempts - 1:
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
                if generates:
                    raise StitchTimeoutError(
                        f"Stitch did not answer within {timeout:.0f}s for {tool_name}. "
                        "The screen may still be generated: check list_screens (or get_screen) "
                        "in a few minutes before asking again — repeating the request can "
                        "create the same screen twice.",
                        may_still_complete=True,
                    ) from exc
                if attempt < attempts - 1:
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
                raise StitchTimeoutError(
                    f"Stitch request timed out after {timeout:.0f}s for tool {tool_name}"
                ) from exc

            except (httpx.RequestError, OSError) as exc:
                last_exc = exc
                if attempt < attempts - 1:
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
            f"Failed after {attempts} attempts for tool {tool_name}"
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
        """Extract the tool result content from a JSON-RPC response.

        Stitch answers a rejected call (validation, unknown resource) with
        HTTP 200, ``isError: true`` and a single text such as «Request
        contains an invalid argument.». That is a failure, not a result:
        raise it so the tools answer with ``error`` instead of ``status: ok``
        (UC-8401).
        """
        result = rpc_response.get("result", {})
        # MCP tools/call result has a "content" array
        content = result.get("content", [])
        if result.get("isError"):
            message = " ".join(
                item.get("text", "") for item in content if item.get("type") == "text"
            ).strip()
            raise StitchClientError(
                message or "Stitch returned an error without a message",
                data=result,
            )
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
    # One per Stitch tool except delete_project (see the module docstring).

    # -- Project management --

    async def create_project(self, title: str) -> Any:
        """Create a new Stitch project/workspace."""
        return await self._call_tool("create_project", {"title": title})

    async def list_projects(self) -> Any:
        """List all Stitch projects for the authenticated user."""
        return await self._call_tool("list_projects")

    async def get_project(self, project_id: str) -> Any:
        """Get details of a Stitch project, by its resource name ``projects/{id}``."""
        return await self._call_tool("get_project", {"name": project_resource(project_id)})

    # -- Screen queries --

    async def list_screens(self, project_id: str) -> Any:
        """List all screens in a Stitch project."""
        return await self._call_tool("list_screens", {"projectId": project_id})

    async def get_screen(self, project_id: str, screen_id: str) -> Any:
        """Get a screen by its resource name ``projects/{p}/screens/{s}``.

        The answer carries ``htmlCode.downloadUrl`` and ``screenshot.downloadUrl``.
        """
        return await self._call_tool(
            "get_screen",
            {"name": screen_resource(project_id, screen_id)},
        )

    async def fetch_screen_code(self, project_id: str, screen_id: str) -> dict[str, Any]:
        """The HTML of a screen, downloaded from ``htmlCode.downloadUrl`` of :meth:`get_screen`.

        Stitch has no ``fetch_screen_code`` tool: the screen resource carries a
        download URL instead (UC-8406).
        """
        screen = await self.get_screen(project_id, screen_id)
        url = ((screen or {}).get("htmlCode") or {}).get("downloadUrl")
        if not url:
            raise StitchClientError(f"{screen_resource(project_id, screen_id)} has no htmlCode.downloadUrl")
        resp = await self._download(url)
        return {
            "screen": screen.get("name"),
            "title": screen.get("title"),
            "html": resp.text,
            "downloadUrl": url,
        }

    async def fetch_screen_image(self, project_id: str, screen_id: str) -> dict[str, Any]:
        """The screenshot of a screen (base64), from ``screenshot.downloadUrl`` of :meth:`get_screen`."""
        screen = await self.get_screen(project_id, screen_id)
        url = ((screen or {}).get("screenshot") or {}).get("downloadUrl")
        if not url:
            raise StitchClientError(f"{screen_resource(project_id, screen_id)} has no screenshot.downloadUrl")
        resp = await self._download(url)
        return {
            "screen": screen.get("name"),
            "title": screen.get("title"),
            "image_base64": base64.b64encode(resp.content).decode("ascii"),
            "mime_type": resp.headers.get("content-type", "").split(";")[0] or None,
            "downloadUrl": url,
        }

    async def _download(self, url: str) -> httpx.Response:
        """GET a Stitch download URL with its own client: the API key never leaves for that host."""
        async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            raise StitchClientError(f"Download failed {resp.status_code} for {url.split('?')[0]}", code=resp.status_code)
        return resp

    # -- Generation --

    async def generate_screen_from_text(
        self,
        project_id: str,
        prompt: str,
        *,
        device_type: str = "DESKTOP",
        model_id: str = DEFAULT_MODEL,
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
            generates=True,
        )

    async def edit_screens(
        self,
        project_id: str,
        screen_ids: str | list[str],
        prompt: str,
        *,
        device_type: str | None = None,
        model_id: str | None = None,
    ) -> Any:
        """Edit one or several screens with a text prompt. Can take several minutes.

        The API asks for ``selectedScreenIds`` (a list of bare ids), not
        ``screenId`` (UC-8404).
        """
        if not (prompt or "").strip():
            raise StitchClientError("edit_screens needs a prompt")
        args: dict[str, Any] = {
            "projectId": project_id,
            "selectedScreenIds": screen_ids_for(screen_ids),
            "prompt": prompt,
        }
        if device_type:
            args["deviceType"] = device_type
        if model_id:
            args["modelId"] = model_id
        return await self._call_tool("edit_screens", args, timeout=GENERATE_TIMEOUT, generates=True)

    async def generate_variants(
        self,
        project_id: str,
        screen_ids: str | list[str],
        *,
        prompt: str = "",
        variant_count: int = 3,
        creative_range: str = "EXPLORE",
        aspects: list[str] | None = None,
        device_type: str | None = None,
        model_id: str | None = None,
    ) -> Any:
        """Generate design variants of one or several screens.

        The API asks for ``selectedScreenIds``, a ``prompt`` (required) and
        ``variantOptions`` with ``variantCount`` (1-5), ``creativeRange``
        and ``aspects`` (UC-8404).

        Args:
            creative_range: REFINE | EXPLORE | REIMAGINE
            aspects: subset of LAYOUT, COLOR_SCHEME, IMAGES, TEXT_FONT, TEXT_CONTENT
        """
        if not (prompt or "").strip():
            raise StitchClientError("generate_variants needs a prompt: say what the variants should explore")
        if not 1 <= int(variant_count) <= 5:
            raise StitchClientError(f"variant_count must be between 1 and 5, got {variant_count}")
        options: dict[str, Any] = {"variantCount": int(variant_count), "creativeRange": creative_range}
        if aspects:
            options["aspects"] = aspects
        args: dict[str, Any] = {
            "projectId": project_id,
            "selectedScreenIds": screen_ids_for(screen_ids),
            "prompt": prompt,
            "variantOptions": options,
        }
        if device_type:
            args["deviceType"] = device_type
        if model_id:
            args["modelId"] = model_id
        return await self._call_tool("generate_variants", args, timeout=GENERATE_TIMEOUT, generates=True)

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
        project_id: str | None,
        display_name: str,
        theme: dict[str, Any],
    ) -> Any:
        """Create a design system with its name and theme (UC-8403).

        The API asks for ``designSystem: {displayName, theme}`` and, in the
        theme, ``colorMode``, ``headlineFont``, ``bodyFont``, ``roundness`` and
        ``customColor``; :func:`design_system_payload` checks them first.
        Without ``project_id`` the design system belongs to the account.
        For DESIGN.md-driven creation prefer
        :meth:`create_design_system_from_design_md`.
        """
        args: dict[str, Any] = {"designSystem": design_system_payload(display_name, theme)}
        if project_id:
            args["projectId"] = project_id
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
            display_name: New name of the DS. The API always asks for it:
                without one, the current name is read with
                :meth:`list_design_systems` and sent again (UC-8403).

        Operation is destructive on the theme (no versioning).
        """
        if not (display_name or "").strip():
            display_name = await self._current_display_name(project_id, asset_name)
        return await self._call_tool(
            "update_design_system",
            {
                "name": asset_name,
                "projectId": project_id,
                "designSystem": design_system_payload(display_name, theme),
            },
            timeout=DESIGN_SYSTEM_TIMEOUT,
        )

    async def _current_display_name(self, project_id: str | None, asset_name: str) -> str:
        """The displayName Stitch has for ``asset_name`` (``assets/{id}`` or the bare id)."""
        wanted = asset_name if asset_name.startswith("assets/") else f"assets/{asset_name}"
        listed = await self.list_design_systems(project_id)
        for item in (listed or {}).get("designSystems", []) if isinstance(listed, dict) else []:
            if item.get("name") == wanted:
                name = (item.get("designSystem") or {}).get("displayName")
                if name:
                    return name
        raise StitchClientError(
            f"{wanted} has no displayName in this project; pass display_name to update it."
        )

    async def list_design_systems(self, project_id: str | None) -> Any:
        """List the design systems of a project, or the account's without one.

        Returns either ``{"designSystems": [...]}`` or an empty dict
        when there are none.
        """
        return await self._call_tool(
            "list_design_systems",
            {"projectId": project_id} if project_id else {},
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
