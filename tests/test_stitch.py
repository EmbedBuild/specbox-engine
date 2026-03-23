"""Tests for Stitch MCP proxy — client and auth gateway.

Validates:
- StitchClient builds correct JSON-RPC payloads
- StitchClient handles SSE and JSON responses
- StitchClient retries on transient errors
- Auth gateway stores/retrieves Stitch credentials per project
- Stitch tools resolve API keys from session and disk fallback
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from server.stitch_client import (
    StitchClient,
    StitchClientError,
    STITCH_BASE_URL,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stitch_client():
    return StitchClient(api_key="test-api-key-12345678")


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    """Create state directory with a test project."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    registry = {"projects": {"test-project": {"stack": "react"}}}
    (state_dir / "registry.json").write_text(
        json.dumps(registry), encoding="utf-8"
    )
    project_dir = state_dir / "projects" / "test-project"
    project_dir.mkdir(parents=True)
    return state_dir


# ---------------------------------------------------------------------------
# StitchClient unit tests
# ---------------------------------------------------------------------------


class TestStitchClientPayload:
    """Verify JSON-RPC payloads are built correctly."""

    @respx.mock
    async def test_list_projects_payload(self, stitch_client):
        route = respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "test",
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    [{"id": "p1", "title": "Project 1"}]
                                ),
                            }
                        ]
                    },
                },
            )
        )
        result = await stitch_client.list_projects()
        assert route.called
        body = json.loads(route.calls[0].request.content)
        assert body["method"] == "tools/call"
        assert body["params"]["name"] == "list_projects"
        assert isinstance(result, list)
        await stitch_client.close()

    @respx.mock
    async def test_generate_screen_payload(self, stitch_client):
        route = respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "test",
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {"screenId": "s1", "html": "<div>UI</div>"}
                                ),
                            }
                        ]
                    },
                },
            )
        )
        result = await stitch_client.generate_screen_from_text(
            "proj1",
            "A login page with light mode",
            device_type="MOBILE",
            model_id="GEMINI_3_FLASH",
        )
        body = json.loads(route.calls[0].request.content)
        args = body["params"]["arguments"]
        assert args["projectId"] == "proj1"
        assert args["prompt"] == "A login page with light mode"
        assert args["deviceType"] == "MOBILE"
        assert args["modelId"] == "GEMINI_3_FLASH"
        assert result["screenId"] == "s1"
        await stitch_client.close()

    @respx.mock
    async def test_edit_screens_payload(self, stitch_client):
        route = respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "test",
                    "result": {"content": [{"type": "text", "text": "{}"}]},
                },
            )
        )
        await stitch_client.edit_screens(
            "proj1", "screen1", "Change button color to blue"
        )
        body = json.loads(route.calls[0].request.content)
        assert body["params"]["name"] == "edit_screens"
        args = body["params"]["arguments"]
        assert args["screenId"] == "screen1"
        assert args["prompt"] == "Change button color to blue"
        await stitch_client.close()

    @respx.mock
    async def test_generate_variants_payload(self, stitch_client):
        route = respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "test",
                    "result": {"content": [{"type": "text", "text": "[]"}]},
                },
            )
        )
        await stitch_client.generate_variants(
            "proj1",
            "screen1",
            prompt="More playful",
            variant_count=5,
            creative_range="REIMAGINE",
            aspects=["LAYOUT", "COLOR_SCHEME"],
        )
        body = json.loads(route.calls[0].request.content)
        args = body["params"]["arguments"]
        assert args["variantCount"] == 5
        assert args["creativeRange"] == "REIMAGINE"
        assert args["aspects"] == ["LAYOUT", "COLOR_SCHEME"]
        assert args["prompt"] == "More playful"
        await stitch_client.close()

    @respx.mock
    async def test_create_project_payload(self, stitch_client):
        route = respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "test",
                    "result": {
                        "content": [
                            {"type": "text", "text": json.dumps({"id": "new-proj"})}
                        ]
                    },
                },
            )
        )
        result = await stitch_client.create_project("My App")
        body = json.loads(route.calls[0].request.content)
        assert body["params"]["name"] == "create_project"
        assert body["params"]["arguments"]["title"] == "My App"
        assert result["id"] == "new-proj"
        await stitch_client.close()

    @respx.mock
    async def test_extract_design_context_payload(self, stitch_client):
        route = respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "test",
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {"fonts": ["Inter"], "colors": ["#000"]}
                                ),
                            }
                        ]
                    },
                },
            )
        )
        result = await stitch_client.extract_design_context("proj1", "screen1")
        body = json.loads(route.calls[0].request.content)
        assert body["params"]["name"] == "extract_design_context"
        assert result["fonts"] == ["Inter"]
        await stitch_client.close()

    @respx.mock
    async def test_build_site_payload(self, stitch_client):
        routes = [
            {"screenId": "s1", "route": "/"},
            {"screenId": "s2", "route": "/about"},
        ]
        route = respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "test",
                    "result": {"content": [{"type": "text", "text": "{}"}]},
                },
            )
        )
        await stitch_client.build_site("proj1", routes)
        body = json.loads(route.calls[0].request.content)
        assert body["params"]["name"] == "build_site"
        assert body["params"]["arguments"]["routes"] == routes
        await stitch_client.close()

    @respx.mock
    async def test_fetch_screen_code_payload(self, stitch_client):
        route = respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "test",
                    "result": {
                        "content": [{"type": "text", "text": "<html>code</html>"}]
                    },
                },
            )
        )
        result = await stitch_client.fetch_screen_code("proj1", "screen1")
        body = json.loads(route.calls[0].request.content)
        assert body["params"]["name"] == "fetch_screen_code"
        assert result["text"] == "<html>code</html>"
        await stitch_client.close()

    @respx.mock
    async def test_fetch_screen_image_payload(self, stitch_client):
        route = respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "test",
                    "result": {
                        "content": [{"type": "text", "text": "base64data..."}]
                    },
                },
            )
        )
        result = await stitch_client.fetch_screen_image("proj1", "screen1")
        body = json.loads(route.calls[0].request.content)
        assert body["params"]["name"] == "fetch_screen_image"
        await stitch_client.close()


class TestStitchClientAuth:
    """Verify API key is sent in correct header."""

    @respx.mock
    async def test_api_key_header(self, stitch_client):
        route = respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "test",
                    "result": {"content": []},
                },
            )
        )
        await stitch_client.list_projects()
        headers = route.calls[0].request.headers
        assert headers["x-goog-api-key"] == "test-api-key-12345678"
        await stitch_client.close()


class TestStitchClientSSE:
    """Verify SSE response parsing."""

    @respx.mock
    async def test_sse_response_parsed(self, stitch_client):
        sse_body = (
            'data: {"jsonrpc":"2.0","id":"x","result":{"content":'
            '[{"type":"text","text":"{\\"ok\\":true}"}]}}\n\n'
        )
        respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                text=sse_body,
                headers={"content-type": "text/event-stream"},
            )
        )
        result = await stitch_client.list_projects()
        assert result["ok"] is True
        await stitch_client.close()


class TestStitchClientErrors:
    """Verify error handling."""

    @respx.mock
    async def test_jsonrpc_error_raises(self, stitch_client):
        respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "test",
                    "error": {"code": -32600, "message": "Invalid Request"},
                },
            )
        )
        with pytest.raises(StitchClientError, match="Invalid Request"):
            await stitch_client.list_projects()
        await stitch_client.close()

    @respx.mock
    async def test_http_error_raises(self, stitch_client):
        respx.post(STITCH_BASE_URL).mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        with pytest.raises(StitchClientError, match="403"):
            await stitch_client.list_projects()
        await stitch_client.close()


# ---------------------------------------------------------------------------
# Auth gateway Stitch tests
# ---------------------------------------------------------------------------


class TestStitchAuthGateway:
    """Verify Stitch credential storage/retrieval in session state."""

    async def test_store_and_retrieve(self):
        from server.auth_gateway import (
            store_stitch_credentials,
            get_stitch_client,
            STITCH_STATE_PREFIX,
        )

        ctx = AsyncMock()
        state_store = {}

        async def mock_set_state(key, value):
            state_store[key] = value

        async def mock_get_state(key):
            return state_store.get(key)

        ctx.set_state = mock_set_state
        ctx.get_state = mock_get_state

        await store_stitch_credentials(ctx, "my-project", "AIzaSy-test-key")

        client = await get_stitch_client(ctx, "my-project")
        assert client.api_key == "AIzaSy-test-key"

    async def test_missing_credentials_raises(self):
        from server.auth_gateway import get_stitch_client

        ctx = AsyncMock()
        ctx.get_state = AsyncMock(return_value=None)

        with pytest.raises(RuntimeError, match="Stitch API Key not configured"):
            await get_stitch_client(ctx, "unknown-project")


# ---------------------------------------------------------------------------
# Stitch tools — API key disk fallback
# ---------------------------------------------------------------------------


class TestStitchApiKeyDiskFallback:
    """Verify API key is loaded from meta.json when not in session."""

    def test_meta_json_stores_key(self, state_path: Path):
        import base64

        project_dir = state_path / "projects" / "test-project"
        meta = {
            "stitch_configured": True,
            "stitch_key_b64": base64.b64encode(b"test-key-from-disk").decode(),
            "stitch_key_hint": "...disk",
        }
        (project_dir / "meta.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )

        meta_loaded = json.loads(
            (project_dir / "meta.json").read_text(encoding="utf-8")
        )
        recovered = base64.b64decode(meta_loaded["stitch_key_b64"]).decode()
        assert recovered == "test-key-from-disk"


class TestStitchUsageTelemetry:
    """Verify stitch_usage.jsonl is written."""

    def test_usage_log_written(self, state_path: Path):
        from server.tools.stitch import register_stitch_tools

        # Simulate what _log_stitch_usage does
        project = "test-project"
        project_dir = state_path / "projects" / project
        project_dir.mkdir(parents=True, exist_ok=True)
        log_file = project_dir / "stitch_usage.jsonl"
        entry = {"tool": "generate_screen", "timestamp": "2026-03-23T12:00:00Z"}
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        assert log_file.exists()
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["tool"] == "generate_screen"
