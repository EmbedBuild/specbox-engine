"""US-84 · UC-8503 — generate, edit and variants wait as long as Stitch takes and are not repeated.

The client opened its connection once with the timeout of the first call (30 s
for a read) and kept it: generating was cut at 30 s while the message said
360 s, and then repeated, which Stitch asks not to do («DO NOT RETRY»).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

import server.stitch_client as stitch_client_module
from server.stitch_client import (
    DEFAULT_TIMEOUT,
    GENERATE_TIMEOUT,
    STITCH_MCP_URL,
    StitchClient,
    StitchTimeoutError,
)
from server.stitch_orchestration.fallback import FallbackOutcome, generate_screen_with_fallback


def _ok(payload=None) -> httpx.Response:
    return httpx.Response(
        200, json={"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": json.dumps(payload or {})}]}}
    )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(stitch_client_module.asyncio, "sleep", AsyncMock())
    return StitchClient(api_key="test-api-key-12345678")


GENERATIONS = [
    ("generate_screen_from_text", ("123", "A list"), {}),
    ("edit_screens", ("123", "abc", "Blue"), {}),
    ("generate_variants", ("123", "abc"), {"prompt": "More"}),
]


class TestEachCallHasItsOwnTimeout:
    """AC-01."""

    @respx.mock
    async def test_generation_after_a_read_waits_six_minutes(self, client):
        route = respx.post(STITCH_MCP_URL).mock(side_effect=[_ok({"projects": []}), _ok()])
        await client.list_projects()
        await client.generate_screen_from_text("123", "A list")
        read_timeout = [c.request.extensions["timeout"]["read"] for c in route.calls]
        assert read_timeout == [DEFAULT_TIMEOUT, GENERATE_TIMEOUT]
        await client.close()

    @respx.mock
    async def test_read_after_a_generation_keeps_its_short_timeout(self, client):
        route = respx.post(STITCH_MCP_URL).mock(side_effect=[_ok(), _ok({"projects": []})])
        await client.generate_screen_from_text("123", "A list")
        await client.list_projects()
        assert [c.request.extensions["timeout"]["read"] for c in route.calls] == [GENERATE_TIMEOUT, DEFAULT_TIMEOUT]
        await client.close()

    @respx.mock
    async def test_timeout_message_says_the_real_time(self, client):
        route = respx.post(STITCH_MCP_URL).mock(side_effect=httpx.ReadTimeout("slow"))
        with pytest.raises(StitchTimeoutError, match=f"after {DEFAULT_TIMEOUT:.0f}s") as err:
            await client.list_projects()
        assert route.call_count == 3  # a read can be repeated
        assert err.value.may_still_complete is False
        await client.close()


class TestGenerationsAreNotRepeated:
    """AC-02."""

    @pytest.mark.parametrize(("method", "args", "kwargs"), GENERATIONS)
    @respx.mock
    async def test_timeout_is_not_retried_and_says_how_to_check(self, client, method, args, kwargs):
        route = respx.post(STITCH_MCP_URL).mock(side_effect=httpx.ReadTimeout("slow"))
        with pytest.raises(StitchTimeoutError) as err:
            await getattr(client, method)(*args, **kwargs)
        assert route.call_count == 1
        assert err.value.may_still_complete is True
        message = str(err.value)
        assert f"{GENERATE_TIMEOUT:.0f}s" in message and "list_screens" in message and "twice" in message
        await client.close()

    @pytest.mark.parametrize(("method", "args", "kwargs"), GENERATIONS)
    @respx.mock
    async def test_server_error_is_not_retried(self, client, method, args, kwargs):
        route = respx.post(STITCH_MCP_URL).mock(return_value=httpx.Response(503, text="busy"))
        with pytest.raises(stitch_client_module.StitchClientError, match="503"):
            await getattr(client, method)(*args, **kwargs)
        assert route.call_count == 1
        await client.close()

    @respx.mock
    async def test_reads_still_retry_a_server_error(self, client):
        route = respx.post(STITCH_MCP_URL).mock(side_effect=[httpx.Response(503, text="busy"), _ok({"projects": []})])
        assert await client.list_projects() == {"projects": []}
        assert route.call_count == 2
        await client.close()


class _TimesOut:
    def __init__(self):
        self.calls: list[str] = []

    async def generate_screen(self, project_id, prompt, *, device_type="DESKTOP", model_id=None):
        self.calls.append("generate_screen")
        raise StitchTimeoutError("Stitch did not answer … check list_screens", may_still_complete=True)

    async def edit_screens(self, *a, **k):
        self.calls.append("edit_screens")
        return {"screen": {"id": "e"}}

    async def generate_variants(self, *a, **k):
        self.calls.append("generate_variants")
        return {"screens": [{"id": "v"}]}


class TestFallbackStops:
    async def test_no_other_generation_after_a_timeout(self):
        ops = _TimesOut()
        res = await generate_screen_with_fallback(ops, "123", "A list", baseline_screen_id="base")
        assert ops.calls == ["generate_screen"]
        assert res.outcome == FallbackOutcome.FAILED
        assert "list_screens" in res.error
        assert res.attempts[0]["may_still_complete"] is True
