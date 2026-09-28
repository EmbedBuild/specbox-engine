"""UC-3903 AC-02 — límites de tamaño y de tasa por identidad.

Una petición de más de 2 MB, o más de 60 llamadas por minuto desde una misma
identidad, se rechaza con un error explícito; las demás identidades siguen
trabajando. Sin red: middleware ASGI contra una app de juguete.
"""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from server.coordination import abuse_guard as ag
from server.coordination import transport_auth as ta

TWO_MB = 2 * 1024 * 1024


def _tool_call(i: int = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": "whoami", "arguments": {}}}


class Recorder:
    def __init__(self) -> None:
        self.bodies: list[bytes] = []

    async def __call__(self, scope, receive, send):
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        self.bodies.append(body)
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})


class WithIdentity:
    """Stands in for TransportAuthMiddleware: puts a developer in the request state."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        developer = dict(scope.get("headers") or ()).get(b"x-test-developer")
        if developer:
            scope.setdefault("state", {})[ta.STATE_KEY] = ta.TransportIdentity(
                developer_id=developer.decode(), kind="developer"
            )
        await self.app(scope, receive, send)


def _client(limit: int = ag.DEFAULT_RATE_PER_MINUTE) -> tuple[httpx.AsyncClient, Recorder]:
    app = Recorder()
    guard = ag.AbuseGuardMiddleware(app, max_body_bytes=TWO_MB, limiter=ag.RateLimiter(limit))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=WithIdentity(guard)), base_url="http://mcp.test"), app


# ── Piezas ────────────────────────────────────────────────────────────


def test_defaults_are_2mb_and_60_calls_per_minute():
    with patch.dict(os.environ, {}, clear=True):
        guard = ag.AbuseGuardMiddleware(Recorder())
    assert guard.max_body_bytes == TWO_MB and guard.limiter.limit == 60


def test_rate_limiter_slides_a_one_minute_window():
    now = [0.0]
    limiter = ag.RateLimiter(60, clock=lambda: now[0])
    assert all(limiter.acquire("developer:alice") is None for _ in range(60))
    wait = limiter.acquire("developer:alice")
    assert wait is not None and 0 < wait <= 60
    assert limiter.acquire("developer:bob") is None  # otra identidad, otra cuota
    now[0] = 60.01
    assert limiter.acquire("developer:alice") is None


def test_identity_key_prefers_the_developer_then_the_ip_added_by_the_proxy():
    dev = {"state": {ta.STATE_KEY: ta.TransportIdentity(developer_id="alice", kind="developer")}}
    assert ag.identity_key(dev) == "developer:alice"
    spoofed = {"headers": [(b"x-forwarded-for", b"6.6.6.6, 81.40.143.217")], "client": ("10.0.0.5", 1)}
    assert ag.identity_key(spoofed) == "ip:81.40.143.217"  # la de la izquierda la puede escribir el cliente
    assert ag.identity_key({"client": ("10.0.0.5", 1)}) == "ip:10.0.0.5"


def test_only_tool_calls_count():
    assert ag.count_tool_calls(json.dumps(_tool_call()).encode()) == 1
    assert ag.count_tool_calls(json.dumps([_tool_call(1), _tool_call(2), {"method": "ping"}]).encode()) == 2
    assert ag.count_tool_calls(json.dumps({"method": "initialize"}).encode()) == 0
    assert ag.count_tool_calls(b"no-json") == 0


# ── Tamaño ────────────────────────────────────────────────────────────


async def test_a_body_over_2mb_is_rejected_by_its_declared_length():
    client, app = _client()
    async with client:
        resp = await client.post("/mcp", content=b"x" * (TWO_MB + 1), headers={"accept-language": "es"})
    assert resp.status_code == 413 and app.bodies == []
    assert resp.json() == {
        "error": "request_too_large",
        "message": "La petición supera el máximo de 2 MB y no se ha procesado.",
    }


async def test_a_chunked_body_over_2mb_is_rejected_while_it_is_read():
    async def chunks():
        for _ in range(3):
            yield b"x" * (TWO_MB // 2 + 1)

    client, app = _client()
    async with client:
        resp = await client.post("/mcp", content=chunks())
    assert resp.status_code == 413 and app.bodies == []


async def test_a_body_under_the_limit_reaches_the_app_intact():
    body = json.dumps(_tool_call()).encode() + b" " * 1000
    client, app = _client()
    async with client:
        resp = await client.post("/mcp", content=body)
    assert resp.status_code == 200 and app.bodies == [body]


# ── Tasa por identidad ────────────────────────────────────────────────


async def test_the_61st_call_in_a_minute_is_rejected_and_other_identities_keep_working():
    client, app = _client()
    alice = {"x-test-developer": "alice", "accept-language": "es"}
    async with client:
        statuses = [(await client.post("/mcp", json=_tool_call(i), headers=alice)).status_code for i in range(60)]
        limited = await client.post("/mcp", json=_tool_call(61), headers=alice)
        bob = await client.post("/mcp", json=_tool_call(1), headers={"x-test-developer": "bob"})
    assert statuses == [200] * 60
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) >= 1
    body = limited.json()
    assert body["error"] == "rate_limited" and "60 por minuto" in body["message"]
    assert bob.status_code == 200


async def test_anonymous_callers_have_one_budget_per_client_ip():
    client, _ = _client(limit=2)
    first = {"x-forwarded-for": "81.40.143.217"}
    async with client:
        a = [(await client.post("/mcp", json=_tool_call(i), headers=first)).status_code for i in range(3)]
        other = await client.post("/mcp", json=_tool_call(1), headers={"x-forwarded-for": "79.116.239.68"})
        spoof = await client.post("/mcp", json=_tool_call(1), headers={"x-forwarded-for": "1.2.3.4, 81.40.143.217"})
    assert a == [200, 200, 429] and other.status_code == 200
    assert spoof.status_code == 429  # falsificar la IP de la izquierda no da cuota nueva


async def test_protocol_messages_do_not_spend_the_budget():
    client, _ = _client(limit=1)
    alice = {"x-test-developer": "alice"}
    async with client:
        for i in range(5):
            assert (
                await client.post("/mcp", json={"jsonrpc": "2.0", "id": i, "method": "tools/list"}, headers=alice)
            ).status_code == 200
        assert (await client.post("/mcp", json=_tool_call(), headers=alice)).status_code == 200


async def test_health_get_and_preflight_are_never_limited():
    client, _ = _client(limit=1)
    async with client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/mcp")).status_code == 200
        assert (await client.options("/mcp")).status_code == 200


def test_main_puts_the_guard_right_after_the_authentication():
    from server.server import main

    with patch.dict(os.environ, {"MCP_TRANSPORT": "streamable-http"}, clear=False), patch("server.server.mcp") as fake:
        main()
    classes = [m.cls for m in fake.run.call_args.kwargs["middleware"]]
    assert classes == [ta.TransportAuthMiddleware, ag.AbuseGuardMiddleware]


@pytest.mark.parametrize("raw", ["", "abc", "-5", "0"])
def test_a_bad_setting_falls_back_to_the_default(raw):
    with patch.dict(os.environ, {ag.RATE_ENV: raw}, clear=False):
        assert ag.AbuseGuardMiddleware(Recorder()).limiter.limit == 60
