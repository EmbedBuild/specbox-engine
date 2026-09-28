"""UC-3901 — el servidor remoto exige un token válido en cada conexión.

Tres capas:
  * la política y el parseo (sin red ni base);
  * el middleware ASGI contra una app de juguete (todos los caminos de rechazo);
  * un servidor FastMCP real por HTTP: la inicialización se rechaza antes de
    llegar al MCP, un token válido identifica al usuario durante la sesión (el
    registro de accesos se lo atribuye sin volver a pasar el token), /health es
    público y, en periodo de gracia, cada respuesta lleva el aviso.

La identidad se resuelve con un resolver falso: no hace falta Postgres.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import httpx
import pytest
from fastmcp import Context, FastMCP
from starlette.middleware import Middleware

from server.coordination import access_log as al
from server.coordination import transport_auth as ta

DEADLINE = dt.date(2026, 10, 29)
BEFORE = dt.date(2026, 10, 1)
TOKENS = {"tok-alice": "alice"}


@pytest.fixture(autouse=True)
def _fresh_caches():
    ta._clear_cache()
    al._clear_identity_cache()
    yield
    ta._clear_cache()
    al._clear_identity_cache()


async def fake_resolver(token: str) -> str | None:
    return TOKENS.get(token)


# ── Política y parseo ─────────────────────────────────────────────────


def test_policy_defaults_to_off_so_deploying_changes_nothing():
    assert ta.TransportPolicy.from_env({}) == ta.TransportPolicy(mode="off")
    assert ta.TransportPolicy(mode="off").tokenless_verdict(BEFORE) == ta.VERDICT_ALLOW


def test_policy_grace_until_the_deadline_then_the_same_as_enforce():
    grace = ta.TransportPolicy.from_env({ta.MODE_ENV: "grace", ta.GRACE_UNTIL_ENV: "2026-10-29"})
    assert grace == ta.TransportPolicy(mode="grace", grace_until=DEADLINE)
    assert grace.tokenless_verdict(BEFORE) == ta.VERDICT_WARN
    assert grace.tokenless_verdict(DEADLINE) == ta.VERDICT_REJECT
    assert grace.tokenless_verdict(DEADLINE + dt.timedelta(days=1)) == ta.VERDICT_REJECT
    assert ta.TransportPolicy(mode="enforce").tokenless_verdict(BEFORE) == ta.VERDICT_REJECT


@pytest.mark.parametrize(
    "env",
    [
        {ta.MODE_ENV: "grace"},  # sin fecha
        {ta.MODE_ENV: "grace", ta.GRACE_UNTIL_ENV: "29/10/2026"},  # fecha ilegible
        {ta.MODE_ENV: "loquesea"},  # modo desconocido
    ],
)
def test_a_misconfigured_policy_fails_closed(env):
    assert ta.TransportPolicy.from_env(env).tokenless_verdict(BEFORE) == ta.VERDICT_REJECT


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ([], (False, "")),
        ([(b"authorization", b"Bearer tok-alice")], (True, "tok-alice")),
        ([(b"Authorization", b"bearer   tok-alice ")], (True, "tok-alice")),
        ([(b"authorization", b"Basic YWxpY2U6eA==")], (True, "")),
        ([(b"authorization", b"Bearer ")], (True, "")),
        ({"Authorization": "Bearer tok-alice"}, (True, "tok-alice")),
    ],
)
def test_bearer_token_parsing(headers, expected):
    assert ta.bearer_token(headers) == expected


def test_ac05_notice_carries_the_deadline_and_both_ways_and_is_the_same_before_and_after():
    policy = ta.TransportPolicy(mode="grace", grace_until=DEADLINE)
    for locale, first_way in (("es", "extensión de VSCode"), ("en", "VSCode extension")):
        text = ta.token_required_message(policy, locale)
        assert "2026-10-29" in text and first_way in text and "`specbox login`" in text
    # El mismo texto sirve de aviso antes de la fecha y de rechazo después (AC-05).
    assert ta.token_required_message(policy, "es") == ta.token_required_message(policy, "es")


# ── Middleware ASGI contra una app de juguete ──────────────────────────


class Recorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, scope, receive, send):
        self.calls.append(dict(scope.get("state") or {}))
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})


def _client(policy: ta.TransportPolicy, resolver=fake_resolver, today=BEFORE) -> tuple[httpx.AsyncClient, Recorder]:
    app = Recorder()
    mw = ta.TransportAuthMiddleware(app, policy=policy, resolver=resolver, today=lambda: today)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=mw), base_url="http://mcp.test"), app


ENFORCE = ta.TransportPolicy(mode="enforce")
GRACE = ta.TransportPolicy(mode="grace", grace_until=DEADLINE)
OFF = ta.TransportPolicy(mode="off")


async def test_ac02_health_is_public_even_when_enforcing():
    client, app = _client(ENFORCE)
    async with client:
        resp = await client.get("/health")
    assert resp.status_code == 200 and len(app.calls) == 1


async def test_cors_preflights_pass_even_when_enforcing():
    """Un preflight nunca lleva credenciales: rechazarlo rompería a los clientes de navegador."""
    client, app = _client(ENFORCE)
    async with client:
        resp = await client.options(
            "/mcp", headers={"origin": "https://claude.ai", "access-control-request-method": "POST"}
        )
    assert resp.status_code == 200 and len(app.calls) == 1


async def test_ac01_no_token_is_rejected_when_enforcing_before_the_app_runs():
    client, app = _client(ENFORCE)
    async with client:
        resp = await client.post("/mcp", json={}, headers={"accept-language": "es-ES"})
    assert resp.status_code == 401 and app.calls == []
    assert resp.headers["www-authenticate"].startswith('Bearer realm="specbox"')
    body = resp.json()
    assert body["error"] == "token_required" and "`specbox login`" in body["message"]
    assert "extensión de VSCode" in body["message"]


@pytest.mark.parametrize("policy", [OFF, GRACE, ENFORCE], ids=["off", "grace", "enforce"])
@pytest.mark.parametrize("header", ["Bearer tok-desconocido", "Basic YWxpY2U6eA==", "Bearer "])
async def test_ac01_an_invalid_token_is_rejected_in_every_mode(policy, header):
    client, app = _client(policy)
    async with client:
        resp = await client.post("/mcp", json={}, headers={"authorization": header})
    assert resp.status_code == 401 and app.calls == []
    assert resp.json()["error"] == "invalid_token"
    assert 'error="invalid_token"' in resp.headers["www-authenticate"]


async def test_ac01_a_revoked_token_stops_authenticating():
    revoked: set[str] = set()

    async def resolver(token: str) -> str | None:
        return None if token in revoked else TOKENS.get(token)

    client, app = _client(ENFORCE, resolver=resolver)
    async with client:
        ok = await client.post("/mcp", json={}, headers={"authorization": "Bearer tok-alice"})
        revoked.add("tok-alice")
        ta._clear_cache()  # pasados los 30 s de caché
        denied = await client.post("/mcp", json={}, headers={"authorization": "Bearer tok-alice"})
    assert ok.status_code == 200 and denied.status_code == 401 and len(app.calls) == 1


async def test_ac02_a_valid_token_becomes_the_identity_of_the_request():
    client, app = _client(ENFORCE)
    async with client:
        resp = await client.post("/mcp", json={}, headers={"authorization": "Bearer tok-alice"})
    assert resp.status_code == 200
    identity = app.calls[0][ta.STATE_KEY]
    assert identity == ta.TransportIdentity(developer_id="alice", kind="developer")


async def test_the_identity_lookup_is_cached_and_never_needs_the_token_twice():
    seen: list[str] = []

    async def resolver(token: str) -> str | None:
        seen.append(token)
        return TOKENS.get(token)

    client, _ = _client(ENFORCE, resolver=resolver)
    async with client:
        for _ in range(3):
            await client.post("/mcp", json={}, headers={"authorization": "Bearer tok-alice"})
    assert seen == ["tok-alice"]


async def test_an_identity_outage_is_503_not_401():
    async def broken(token: str) -> str | None:
        raise ConnectionError("db down")

    client, app = _client(ENFORCE, resolver=broken)
    async with client:
        resp = await client.post("/mcp", json={}, headers={"authorization": "Bearer tok-alice"})
    assert resp.status_code == 503 and resp.json()["error"] == "auth_unavailable" and app.calls == []


async def test_ac05_grace_lets_tokenless_through_with_the_notice_and_rejects_after_the_deadline():
    client, app = _client(GRACE, today=BEFORE)
    async with client:
        resp = await client.post("/mcp", json={})
    assert resp.status_code == 200
    identity = app.calls[0][ta.STATE_KEY]
    assert identity.kind == "anonymous" and "2026-10-29" in identity.grace_notice

    late, late_app = _client(GRACE, today=DEADLINE)
    async with late:
        rejected = await late.post("/mcp", json={})
    assert rejected.status_code == 401 and late_app.calls == []
    assert rejected.json()["message"] == identity.grace_notice  # el mismo mensaje


async def test_off_mode_lets_tokenless_through_without_notice():
    client, app = _client(OFF)
    async with client:
        resp = await client.post("/mcp", json={})
    assert resp.status_code == 200 and app.calls[0][ta.STATE_KEY].grace_notice is None


# ── Servidor FastMCP real por HTTP ────────────────────────────────────

MCP_HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
    "mcp-protocol-version": "2025-06-18",
}


def _server(policy: ta.TransportPolicy, store: al.MemoryStore):
    mcp = FastMCP("probe", version="0.0.1")

    @mcp.tool
    async def quien_soy(ctx: Context) -> dict[str, Any]:
        identity = ta.transport_identity(ctx)
        return {
            "developer_id": identity.developer_id if identity else None,
            "token_de_la_conexion": bool(ta.transport_token(ctx)),
        }

    mcp.add_middleware(al.ToolAccessLogMiddleware(store, transport="http", blocking=True))
    mcp.add_middleware(ta.TransportNoticeMiddleware())

    @mcp.custom_route("/health", methods=["GET"])
    async def _health(_request):
        from starlette.responses import JSONResponse

        return JSONResponse({"status": "ok"})

    app = mcp.http_app(
        middleware=[
            Middleware(ta.TransportAuthMiddleware, policy=policy, resolver=fake_resolver, today=lambda: BEFORE)
        ],
        json_response=True,
    )
    return app


async def _open_session(client: httpx.AsyncClient, headers: dict[str, str]) -> httpx.Response:
    return await client.post(
        "/mcp",
        headers={**MCP_HEADERS, **headers},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "prueba", "version": "1.0"},
            },
        },
    )


async def _call_tool(client: httpx.AsyncClient, session: str, headers: dict[str, str]) -> dict[str, Any]:
    base = {**MCP_HEADERS, **headers, "mcp-session-id": session}
    await client.post("/mcp", headers=base, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    resp = await client.post(
        "/mcp",
        headers=base,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "quien_soy", "arguments": {}}},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["result"]


async def _with_server(policy: ta.TransportPolicy, store: al.MemoryStore):
    app = _server(policy, store)
    return app, httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://mcp.test")


async def test_http_ac01_initialize_without_or_with_a_bad_token_never_reaches_the_mcp():
    store = al.MemoryStore()
    app, client = await _with_server(ENFORCE, store)
    async with app.router.lifespan_context(app), client:
        sin_token = await _open_session(client, {})
        falso = await _open_session(client, {"authorization": "Bearer tok-desconocido"})
    assert sin_token.status_code == 401 and sin_token.json()["error"] == "token_required"
    assert falso.status_code == 401 and falso.json()["error"] == "invalid_token"
    assert "mcp-session-id" not in sin_token.headers and "mcp-session-id" not in falso.headers
    assert store.records == []


async def test_http_ac02_a_valid_token_identifies_the_user_for_the_whole_session():
    store = al.MemoryStore()
    app, client = await _with_server(ENFORCE, store)
    auth = {"authorization": "Bearer tok-alice"}
    async with app.router.lifespan_context(app), client:
        init = await _open_session(client, auth)
        assert init.status_code == 200, init.text
        result = await _call_tool(client, init.headers["mcp-session-id"], auth)
        health = await client.get("/health")
    payload = result["structuredContent"]
    assert payload == {"developer_id": "alice", "token_de_la_conexion": True}
    # El registro de accesos atribuye la llamada a alice sin ningún set_auth_token.
    assert [(r.tool, r.developer_id, r.identity_kind) for r in store.records] == [("quien_soy", "alice", "developer")]
    assert health.status_code == 200 and health.json() == {"status": "ok"}


async def test_http_ac05_in_grace_every_tool_response_carries_the_notice():
    store = al.MemoryStore()
    app, client = await _with_server(GRACE, store)
    async with app.router.lifespan_context(app), client:
        init = await _open_session(client, {"accept-language": "es"})
        assert init.status_code == 200, init.text
        result = await _call_tool(client, init.headers["mcp-session-id"], {"accept-language": "es"})
    texts = [c["text"] for c in result["content"] if c.get("type") == "text"]
    notice = texts[-1]
    assert notice.startswith("⚠️") and "2026-10-29" in notice and "`specbox login`" in notice
    assert result["structuredContent"] == {"developer_id": None, "token_de_la_conexion": False}
    assert store.records[0].identity_kind == "anonymous"


def test_set_auth_token_uses_the_connection_token_when_none_is_passed(monkeypatch):
    """AC-02 en set_auth_token (native): token="" toma el de la conexión."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from server.tools import spec_driven as sd

    backend = MagicMock()
    backend.validate_auth = AsyncMock(return_value=MagicMock(id="alice", username="alice", display_name="Alice"))
    backend.setup_board = AsyncMock(return_value=MagicMock(board_id="acme/api", board_url=""))
    backend.close = AsyncMock()
    stored: dict[str, Any] = {}

    async def fake_store(ctx, project_id, dev_token):
        stored.update(project_id=project_id, dev_token=dev_token)

    with (
        patch("server.coordination.transport_auth.transport_token", return_value="tok-alice"),
        patch("server.backends.native_backend.NativeBackend", return_value=backend) as ctor,
        patch.object(sd, "store_native_credentials", new=fake_store),
    ):
        out = asyncio.run(
            sd.set_auth_token(api_key="", token="", ctx=MagicMock(), backend_type="native", project_id="acme/api")
        )
    assert out.get("success") is True, out
    assert ctor.call_args.kwargs["dev_token"] == "tok-alice" and stored["dev_token"] == "tok-alice"


def test_json_bodies_never_contain_the_token():
    body = json.dumps({"error": "invalid_token", "message": ta.message("invalid_token", "es")})
    assert "tok-alice" not in body
