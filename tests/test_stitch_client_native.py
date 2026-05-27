"""Tests for the v6.4.0 native chain methods on StitchClient.

Validates JSON-RPC payload shapes against the schema captured in smoke
test v2. Uses respx to mock the MCP endpoint without hitting the network.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from server.stitch_client import (
    STITCH_MCP_URL,
    StitchClient,
    StitchClientError,
)


@pytest.fixture
async def stitch_client():
    client = StitchClient(api_key="test-key")
    yield client
    await client.close()


def _ok_response(payload: dict | str) -> httpx.Response:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": "test",
            "result": {"content": [{"type": "text", "text": text}]},
        },
    )


class TestNativeDesignSystemPayloads:
    """The 6 new design-system wrappers build the right JSON-RPC envelope."""

    @respx.mock
    async def test_upload_design_md_base64_encodes_input(self, stitch_client):
        route = respx.post(STITCH_MCP_URL).mock(
            return_value=_ok_response({"id": "s1", "sourceScreen": "projects/p1/screens/s1"})
        )
        await stitch_client.upload_design_md("p1", "# Tiny DESIGN.md\n")
        body = json.loads(route.calls[0].request.content)
        args = body["params"]["arguments"]
        assert body["params"]["name"] == "upload_design_md"
        assert args["projectId"] == "p1"
        # Server expects base64, not raw markdown.
        import base64
        assert base64.b64decode(args["designMdBase64"]).startswith(b"# Tiny")

    @respx.mock
    async def test_create_design_system_minimal(self, stitch_client):
        route = respx.post(STITCH_MCP_URL).mock(
            return_value=_ok_response({"name": "assets/abc"})
        )
        await stitch_client.create_design_system("p1")
        body = json.loads(route.calls[0].request.content)
        assert body["params"]["name"] == "create_design_system"
        assert body["params"]["arguments"] == {"projectId": "p1"}

    @respx.mock
    async def test_create_design_system_with_display_name(self, stitch_client):
        route = respx.post(STITCH_MCP_URL).mock(
            return_value=_ok_response({"name": "assets/abc"})
        )
        await stitch_client.create_design_system("p1", display_name="Brand DS")
        body = json.loads(route.calls[0].request.content)
        assert body["params"]["arguments"]["displayName"] == "Brand DS"

    @respx.mock
    async def test_create_design_system_from_design_md(self, stitch_client):
        route = respx.post(STITCH_MCP_URL).mock(
            return_value=_ok_response({"assetId": "abc"})
        )
        await stitch_client.create_design_system_from_design_md(
            "p1",
            selected_screen_instance={
                "id": "s1",
                "sourceScreen": "projects/p1/screens/s1",
            },
            device_type="MOBILE",
        )
        body = json.loads(route.calls[0].request.content)
        args = body["params"]["arguments"]
        assert body["params"]["name"] == "create_design_system_from_design_md"
        assert args["projectId"] == "p1"
        assert args["selectedScreenInstance"]["id"] == "s1"
        assert args["deviceType"] == "MOBILE"

    @respx.mock
    async def test_update_design_system_strips_legacy_font(self, stitch_client):
        # The MCP server rejects the legacy "font" key — we don't filter
        # it on the client (the MCP tool wrapper does), but the wrapper
        # itself must send what the caller gave. The strip happens at
        # the MCP tool layer, see test_stitch_update_design_system.
        route = respx.post(STITCH_MCP_URL).mock(
            return_value=_ok_response({"name": "assets/abc", "designSystem": {}})
        )
        await stitch_client.update_design_system(
            "assets/abc",
            "p1",
            theme={
                "colorMode": "LIGHT",
                "headlineFont": "INTER",
                "roundness": "ROUND_EIGHT",
            },
        )
        body = json.loads(route.calls[0].request.content)
        args = body["params"]["arguments"]
        assert body["params"]["name"] == "update_design_system"
        assert args["name"] == "assets/abc"
        assert args["projectId"] == "p1"
        assert args["designSystem"]["theme"]["colorMode"] == "LIGHT"

    @respx.mock
    async def test_list_design_systems(self, stitch_client):
        route = respx.post(STITCH_MCP_URL).mock(
            return_value=_ok_response({"designSystems": []})
        )
        await stitch_client.list_design_systems("p1")
        body = json.loads(route.calls[0].request.content)
        assert body["params"]["name"] == "list_design_systems"
        assert body["params"]["arguments"] == {"projectId": "p1"}

    @respx.mock
    async def test_apply_design_system_validates_screen_instances(self, stitch_client):
        # Position/dimension fields are forbidden — client must reject
        # them pre-flight rather than letting the server return
        # invalid argument.
        with pytest.raises(StitchClientError, match="must contain only id"):
            await stitch_client.apply_design_system(
                "p1",
                "abc",
                [{"id": "s1", "sourceScreen": "projects/p1/screens/s1", "x": 0, "y": 0}],
            )

    @respx.mock
    async def test_apply_design_system_happy_path(self, stitch_client):
        route = respx.post(STITCH_MCP_URL).mock(
            return_value=_ok_response({"projectId": "p1", "sessionId": "sess1"})
        )
        await stitch_client.apply_design_system(
            "p1",
            "abc",
            [{"id": "s1", "sourceScreen": "projects/p1/screens/s1"}],
        )
        body = json.loads(route.calls[0].request.content)
        args = body["params"]["arguments"]
        assert body["params"]["name"] == "apply_design_system"
        assert args["projectId"] == "p1"
        assert args["assetId"] == "abc"
        assert args["selectedScreenInstances"][0]["id"] == "s1"


class TestGhostToolsRemoved:
    """The 2 ghost tools must not be accessible — they break in prod."""

    async def test_extract_design_context_attribute_gone(self, stitch_client):
        assert not hasattr(stitch_client, "extract_design_context")

    async def test_build_site_attribute_gone(self, stitch_client):
        assert not hasattr(stitch_client, "build_site")


class TestRestBatchCreate:
    """REST helper for large uploads (DESIGN.md > ~5KB, HTML, images)."""

    @respx.mock
    async def test_rest_upload_design_md_uses_batch_create_endpoint(self, stitch_client):
        route = respx.post(
            "https://stitch.googleapis.com/v1/projects/p1/screens:batchCreate"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "screen": {
                                "id": "s1",
                                "screenType": "DOCUMENT",
                            }
                        }
                    ],
                    "screenInstances": [
                        {"id": "s1", "sourceScreen": "projects/p1/screens/s1"}
                    ],
                },
            )
        )
        result = await stitch_client.upload_via_rest_batch_create(
            "p1",
            content_bytes=b"# Big DESIGN.md\n" + b"X" * 6000,
            mime_type="text/markdown",
            title="DESIGN.md",
        )
        assert route.called
        body = json.loads(route.calls[0].request.content)
        assert body["parent"] == "projects/p1"
        screen = body["requests"][0]["screen"]
        assert screen["screenType"] == "DOCUMENT"
        assert screen["htmlCode"]["mimeType"] == "text/markdown"
        assert "fileContentBase64" in screen["htmlCode"]
        assert body["createScreenInstances"] is True
        # Response shape preserved.
        assert result["screenInstances"][0]["id"] == "s1"

    @respx.mock
    async def test_rest_upload_image_uses_screenshot_field(self, stitch_client):
        route = respx.post(
            "https://stitch.googleapis.com/v1/projects/p1/screens:batchCreate"
        ).mock(return_value=httpx.Response(200, json={"results": []}))
        await stitch_client.upload_via_rest_batch_create(
            "p1",
            content_bytes=b"\x89PNG fake",
            mime_type="image/png",
        )
        body = json.loads(route.calls[0].request.content)
        screen = body["requests"][0]["screen"]
        assert screen["screenType"] == "IMAGE"
        assert screen["screenshot"]["mimeType"] == "image/png"
        assert "htmlCode" not in screen

    @respx.mock
    async def test_rest_upload_rejects_unsupported_mime(self, stitch_client):
        with pytest.raises(StitchClientError, match="Unsupported MIME"):
            await stitch_client.upload_via_rest_batch_create(
                "p1",
                content_bytes=b"...",
                mime_type="application/pdf",
            )

    @respx.mock
    async def test_rest_upload_propagates_non_2xx(self, stitch_client):
        respx.post(
            "https://stitch.googleapis.com/v1/projects/p1/screens:batchCreate"
        ).mock(return_value=httpx.Response(403, text="forbidden"))
        with pytest.raises(StitchClientError, match="403"):
            await stitch_client.upload_via_rest_batch_create(
                "p1",
                content_bytes=b"# md",
                mime_type="text/markdown",
            )
