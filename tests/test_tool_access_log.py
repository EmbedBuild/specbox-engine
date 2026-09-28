"""UC-3803 — Cada llamada a una tool queda registrada con quién, qué y cuándo.

Origen: la auditoría retroactiva que pidió el tester (2026-09-24) fue parcial
porque el MCP remoto no dejaba rastro por llamada; ``audit_log`` solo cubre
mutaciones native.

AC-01: toda llamada deja fecha/hora, tool, identidad (o "anónimo") y resultado
       (éxito/error) en un registro que no admite modificaciones ni borrados.
AC-02: el operador (SuperAdmin) consulta por identidad y rango de fechas y
       recibe exactamente esas entradas; cualquier otro rol recibe un error de
       autorización y ninguna entrada; sin identidad, UNAUTHENTICATED.
AC-03: el registro nunca contiene credenciales ni el contenido devuelto.

Sin Postgres: middleware + MemoryStore + JsonlStore + tool de consulta.
Con Postgres (gated como el resto de la suite native): trigger append-only,
PostgresStore (escritura, consulta, spool y replay) y el rol de operador
contra una tabla ``panel.profiles`` mínima.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import mcp.types as mt
import pytest
from fastmcp import FastMCP
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.tools.tool import ToolResult

from server.coordination import access_log as al
from server.coordination.identity import UnauthenticatedError
from server.coordination.scope import CallerScope
from server.tools.access_log import parse_bound, register_access_log_tools

NATIVE = {"backend_type": "native", "project_id": "acme/api", "dev_token": "spbx_SECRET_TOKEN_VALUE"}
ALICE = MagicMock(developer_id="alice", display_name="Alice")


@pytest.fixture(autouse=True)
def _fresh_identity_cache():
    al._clear_identity_cache()
    yield
    al._clear_identity_cache()


def _ctx(config: dict[str, Any] | None = NATIVE) -> MagicMock:
    ctx = MagicMock()
    ctx.get_state = AsyncMock(return_value=config)
    ctx.session.client_params.clientInfo = SimpleNamespace(name="claude-code", version="2.0")
    ctx.session_id = "sess-1"
    return ctx


def _call(name: str, arguments: dict[str, Any] | None = None, ctx: Any = None) -> MiddlewareContext:
    return MiddlewareContext(
        message=mt.CallToolRequestParams(name=name, arguments=arguments or {}),
        fastmcp_context=ctx,
        method="tools/call",
    )


def _identified(dev=ALICE):
    return (
        patch("server.coordination.access_log.resolve_developer", new=AsyncMock(return_value=dev)),
        patch("server.db.pool.get_pool", new=AsyncMock(return_value=object())),
    )


async def _run(mw: al.ToolAccessLogMiddleware, name: str, arguments=None, ctx=None, *, result=None, raises=None):
    async def call_next(_context):
        if raises is not None:
            raise raises
        return result if result is not None else ToolResult(structured_content={"success": True})

    return await mw.on_call_tool(_call(name, arguments, ctx), call_next)


# ── AC-01: quién, qué, cuándo, resultado ──────────────────────────────


async def test_ac01_identified_call_is_recorded_with_who_what_when_outcome():
    store = al.MemoryStore()
    mw = al.ToolAccessLogMiddleware(store, transport="http", blocking=True)
    p1, p2 = _identified()
    with p1, p2:
        await _run(mw, "list_us", {"board_id": "acme/api", "items_content": "[]"}, _ctx())
    rec = store.records[0]
    assert rec.tool == "list_us" and rec.outcome == "ok" and rec.error_code is None
    assert rec.developer_id == "alice" and rec.identity_kind == "developer" and rec.identity_label == "alice"
    assert rec.project_id == "acme/api" and rec.transport == "http"
    assert rec.client == "claude-code 2.0" and rec.session_id == "sess-1"
    assert rec.arg_keys == ("board_id", "items_content")
    assert rec.duration_ms is not None and rec.duration_ms >= 0
    when = datetime.fromisoformat(rec.occurred_at)
    assert when.tzinfo is not None and abs((datetime.now(timezone.utc) - when).total_seconds()) < 60


async def test_ac01_unidentified_callers_are_recorded_as_anonymous_with_the_reason():
    store = al.MemoryStore()
    mw = al.ToolAccessLogMiddleware(store, transport="http", blocking=True)
    # No session at all / freeform session → anonymous.
    await _run(mw, "get_engine_version", {}, None)
    await _run(mw, "list_us", {}, _ctx({"backend_type": "freeform", "root_path": None}))
    # A token nobody recognises → invalid_token, identity still "anónimo".
    with patch("server.coordination.access_log.resolve_developer", new=AsyncMock(side_effect=UnauthenticatedError())), patch(
        "server.db.pool.get_pool", new=AsyncMock(return_value=object())
    ):
        await _run(mw, "whoami", {}, _ctx())
    # Identity database down → unresolved, the call still goes through.
    al._clear_identity_cache()
    with patch("server.db.pool.get_pool", new=AsyncMock(side_effect=RuntimeError("no DSN"))):
        await _run(mw, "whoami", {}, _ctx())
    kinds = [(r.identity_kind, r.identity_label, r.developer_id) for r in store.records]
    assert kinds == [
        ("anonymous", "anónimo", None),
        ("anonymous", "anónimo", None),
        ("invalid_token", "anónimo", None),
        ("unresolved", "anónimo", None),
    ]


async def test_ac01_error_envelopes_tool_errors_and_exceptions_are_distinguished():
    store = al.MemoryStore()
    mw = al.ToolAccessLogMiddleware(store, transport="http", blocking=True)
    await _run(mw, "list_onboarded_projects", {}, None, result=ToolResult(structured_content={"status": "unauthenticated", "code": "UNAUTHENTICATED", "message": "Sign in"}))
    await _run(mw, "upgrade_project", {}, None, result=ToolResult(structured_content={"error": "Project 'x' is not registered", "code": "PROJECT_NOT_VISIBLE"}))
    await _run(mw, "get_uc", {}, None, result=ToolResult(content=[mt.TextContent(type="text", text="boom")], is_error=True))
    await _run(mw, "list_us", {}, None, result=ToolResult(structured_content={"result": [{"us_id": "US-01"}]}))
    with pytest.raises(ValueError):
        await _run(mw, "move_uc", {}, None, raises=ValueError("Backend credentials not configured"))
    got = [(r.tool, r.outcome, r.error_code) for r in store.records]
    assert got == [
        ("list_onboarded_projects", "error", "UNAUTHENTICATED"),
        ("upgrade_project", "error", "PROJECT_NOT_VISIBLE"),
        ("get_uc", "error", "TOOL_ERROR"),
        ("list_us", "ok", None),
        ("move_uc", "exception", "ValueError"),
    ]


async def test_ac01_identity_lookup_is_cached_per_token():
    store = al.MemoryStore()
    mw = al.ToolAccessLogMiddleware(store, transport="http", blocking=True)
    resolver = AsyncMock(return_value=ALICE)
    with patch("server.coordination.access_log.resolve_developer", new=resolver), patch(
        "server.db.pool.get_pool", new=AsyncMock(return_value=object())
    ):
        for _ in range(5):
            await _run(mw, "list_us", {}, _ctx())
    assert resolver.await_count == 1
    assert all(r.developer_id == "alice" for r in store.records)


async def test_ac01_a_failing_store_never_breaks_the_tool_call():
    class Exploding:
        async def write(self, record):
            raise OSError("disk full")

        async def query(self, **_):
            return []

    mw = al.ToolAccessLogMiddleware(Exploding(), transport="http", blocking=True)
    result = await _run(mw, "list_us", {}, None)
    assert result.structured_content == {"success": True}


async def test_ac01_non_blocking_writes_are_drained():
    store = al.MemoryStore()
    mw = al.ToolAccessLogMiddleware(store, transport="stdio")
    await _run(mw, "get_engine_version", {}, None)
    await mw.drain()
    assert [r.tool for r in store.records] == ["get_engine_version"]


# ── AC-03: nunca credenciales ni contenido ────────────────────────────


async def test_ac03_records_hold_no_token_no_argument_values_no_payload_no_message():
    store = al.MemoryStore()
    mw = al.ToolAccessLogMiddleware(store, transport="http", blocking=True)
    p1, p2 = _identified()
    with p1, p2:
        await _run(
            mw,
            "set_auth_token",
            {"token": "spbx_ARGUMENT_SECRET", "items_content": "PAYLOAD-CONTENT", "api_key": ""},
            _ctx(),
            result=ToolResult(structured_content={"success": True, "board_url": "RESULT-CONTENT-URL", "summary": "RESULT-SUMMARY"}),
        )
        await _run(
            mw,
            "list_us",
            {"board_id": "b"},
            _ctx(),
            result=ToolResult(structured_content={"error": "Developer 'alice' cannot see MESSAGE-WITH-DATA", "code": "FORBIDDEN"}),
        )
    blob = json.dumps([r.to_dict() for r in store.records], ensure_ascii=False)
    for secret in ("spbx_", "SECRET", "PAYLOAD-CONTENT", "RESULT-CONTENT-URL", "RESULT-SUMMARY", "MESSAGE-WITH-DATA"):
        assert secret not in blob, secret
    assert store.records[0].arg_keys == ("api_key", "items_content", "token")
    assert store.records[1].error_code == "FORBIDDEN"


# ── Stores (file) ─────────────────────────────────────────────────────


def _rec(tool="list_us", dev="alice", kind="developer", days_ago=0, outcome="ok") -> al.AccessRecord:
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return al.AccessRecord(occurred_at=when.isoformat(), tool=tool, identity_kind=kind, developer_id=dev, outcome=outcome)


async def test_jsonl_store_appends_and_filters(tmp_path):
    store = al.JsonlStore(tmp_path / "log" / "tool_access_log.jsonl")
    for r in (_rec(days_ago=0), _rec(days_ago=3), _rec(dev=None, kind="anonymous", days_ago=0), _rec(dev="bob", tool="whoami")):
        await store.write(r)
    assert len((tmp_path / "log" / "tool_access_log.jsonl").read_text().splitlines()) == 4
    since = datetime.now(timezone.utc) - timedelta(days=1)
    alice_recent = await store.query(developer_id="alice", date_from=since)
    assert [r["identity"] for r in alice_recent] == ["alice"]
    anon = await store.query(identity_kind="anonymous")
    assert len(anon) == 1 and anon[0]["identity"] == "anónimo"
    assert [r["tool"] for r in await store.query(tool="whoami")] == ["whoami"]
    assert len(await store.query(limit=2)) == 2


def test_parse_bound_day_and_datetime():
    assert parse_bound("2026-09-24", end=False) == datetime(2026, 9, 24, tzinfo=timezone.utc)
    assert parse_bound("2026-09-24", end=True).hour == 23
    assert parse_bound("2026-09-24T18:11:30Z", end=False) == datetime(2026, 9, 24, 18, 11, 30, tzinfo=timezone.utc)
    assert parse_bound("", end=False) is None
    with pytest.raises(ValueError):
        parse_bound("24/09/2026", end=False)


# ── AC-02: tool de consulta reservada al operador ─────────────────────


async def _query_tool():
    mcp = FastMCP(name="t-access-log")
    register_access_log_tools(mcp)
    return (await mcp.get_tool("get_tool_access_log")).fn


def _seed_store() -> al.MemoryStore:
    store = al.MemoryStore()
    store.records = [
        _rec(days_ago=0),                                     # alice today
        _rec(days_ago=5),                                     # alice 5 days ago
        _rec(dev="bob", days_ago=0),                          # bob today
        _rec(dev=None, kind="anonymous", days_ago=0),         # anonymous today
        _rec(dev=None, kind="invalid_token", days_ago=0),     # bad token today
    ]
    return store


async def test_ac02_without_identity_unauthenticated_and_no_entries(monkeypatch):
    al.configure_store(_seed_store())
    fn = await _query_tool()
    with patch("server.tools.access_log.resolve_caller_scope", new=AsyncMock(side_effect=UnauthenticatedError())):
        result = await fn(ctx=None)
    assert result["code"] == "UNAUTHENTICATED" and "entries" not in result


async def test_ac02_non_operator_gets_authorization_error_and_no_entries(monkeypatch):
    monkeypatch.delenv(al.OPERATOR_IDS_ENV, raising=False)
    al.configure_store(_seed_store())
    fn = await _query_tool()
    scope = CallerScope("alice", "Alice", frozenset({"acme/api"}))
    with patch("server.tools.access_log.resolve_caller_scope", new=AsyncMock(return_value=scope)), patch(
        "server.db.pool.get_pool", new=AsyncMock(side_effect=RuntimeError("no panel db"))
    ):
        result = await fn(developer_id="alice", date_from="2026-01-01", date_to="2030-01-01", ctx=None)
    assert result["code"] == "FORBIDDEN" and result["status"] == "forbidden"
    assert result["entries"] == []


async def test_ac02_operator_gets_exactly_the_identity_in_the_range(monkeypatch):
    monkeypatch.setenv(al.OPERATOR_IDS_ENV, "ops, other")
    al.configure_store(_seed_store())
    fn = await _query_tool()
    scope = CallerScope("ops", "Ops", frozenset())
    today = datetime.now(timezone.utc).date().isoformat()
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
    with patch("server.tools.access_log.resolve_caller_scope", new=AsyncMock(return_value=scope)):
        alice_week = await fn(developer_id="alice", date_from=week_ago, date_to=today, ctx=None)
        alice_recent = await fn(developer_id="alice", date_from=two_days_ago, date_to=today, ctx=None)
        anon = await fn(developer_id="anónimo", date_from=week_ago, date_to=today, ctx=None)
        everyone = await fn(date_from=week_ago, date_to=today, ctx=None)
        bad = await fn(date_from=today, date_to=week_ago, ctx=None)
        malformed = await fn(date_from="ayer", ctx=None)
    assert alice_week["operator"] == "ops" and alice_week["total"] == 2
    assert {e["identity"] for e in alice_week["entries"]} == {"alice"}
    assert alice_recent["total"] == 1
    assert anon["total"] == 1 and anon["entries"][0]["identity_kind"] == "anonymous"
    assert everyone["total"] == 5 and everyone["truncated"] is False
    assert bad["code"] == "INVALID_DATE" and malformed["code"] == "INVALID_DATE"
    # AC-03 holds on the way out too: no argument values, no payloads.
    blob = json.dumps(everyone, ensure_ascii=False)
    assert "arg_keys" in blob and "arguments" not in blob and "dev_token" not in blob


def test_operator_env_override_parsing(monkeypatch):
    monkeypatch.setenv(al.OPERATOR_IDS_ENV, " ops ,, other ")
    assert al.operator_ids_from_env() == frozenset({"ops", "other"})
    monkeypatch.delenv(al.OPERATOR_IDS_ENV)
    assert al.operator_ids_from_env() == frozenset()


async def test_is_operator_without_panel_schema_is_false(monkeypatch):
    monkeypatch.delenv(al.OPERATOR_IDS_ENV, raising=False)
    pool = MagicMock()
    pool.fetchval = AsyncMock(side_effect=Exception('relation "panel.profiles" does not exist'))
    assert await al.is_operator("alice", pool=pool) is False
    assert await al.is_operator("", pool=pool) is False


async def test_default_store_choice(tmp_path, monkeypatch):
    monkeypatch.delenv("SPECBOX_NATIVE_DSN", raising=False)
    assert isinstance(al.build_default_store(tmp_path), al.JsonlStore)
    monkeypatch.setenv("SPECBOX_NATIVE_DSN", "postgresql://x:y@localhost:5/z")
    store = al.build_default_store(tmp_path)
    assert isinstance(store, al.PostgresStore) and store.spool_path == tmp_path / "tool_access_log.spool.jsonl"


# ── Postgres-gated: append-only + PostgresStore + operator role ───────

from tests._native_db import DSN, reachable  # noqa: E402

_PG_OK, _PG_SKIP_REASON = reachable()
pg = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)


@pytest.fixture
async def pg_pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import close_pool, get_pool, init_pool

    await init_pool(dsn=DSN)
    pool = await get_pool()
    await apply_migrations(pool)
    try:
        yield pool
    finally:
        await close_pool()


@pg
async def test_pg_ac01_table_is_append_only(pg_pool):
    import asyncpg

    tag = f"t-{uuid.uuid4().hex[:8]}"
    await pg_pool.execute("INSERT INTO tool_access_log (tool, identity_kind, outcome) VALUES ($1, 'anonymous', 'ok')", tag)
    for stmt in (
        "UPDATE tool_access_log SET tool = 'x' WHERE tool = $1",
        "DELETE FROM tool_access_log WHERE tool = $1",
    ):
        with pytest.raises(asyncpg.PostgresError) as exc:
            await pg_pool.execute(stmt, tag)
        assert exc.value.sqlstate == "42501"
    with pytest.raises(asyncpg.PostgresError):
        await pg_pool.execute("TRUNCATE tool_access_log")
    assert await pg_pool.fetchval("SELECT count(*) FROM tool_access_log WHERE tool = $1", tag) == 1


@pg
async def test_pg_store_writes_queries_and_filters(pg_pool):
    tag = f"list_us-{uuid.uuid4().hex[:8]}"

    async def getter():
        return pg_pool

    store = al.PostgresStore(pool_getter=getter)
    await store.write(al.AccessRecord(datetime.now(timezone.utc).isoformat(), tag, "developer", "alice", "ok", arg_keys=("board_id",), project_id="acme/api", transport="http", client="claude-code 2.0", session_id="s1"))
    await store.write(al.AccessRecord((datetime.now(timezone.utc) - timedelta(days=3)).isoformat(), tag, "developer", "alice", "error", error_code="FORBIDDEN"))
    await store.write(al.AccessRecord(datetime.now(timezone.utc).isoformat(), tag, "anonymous", None, "error", error_code="UNAUTHENTICATED"))
    since = datetime.now(timezone.utc) - timedelta(days=1)
    recent_alice = await store.query(developer_id="alice", date_from=since, tool=tag)
    assert len(recent_alice) == 1 and recent_alice[0]["arg_keys"] == ["board_id"] and recent_alice[0]["identity"] == "alice"
    assert len(await store.query(developer_id="alice", tool=tag)) == 2
    anon = await store.query(identity_kind="anonymous", tool=tag)
    assert len(anon) == 1 and anon[0]["identity"] == "anónimo" and anon[0]["error_code"] == "UNAUTHENTICATED"
    assert recent_alice[0]["occurred_at"].endswith("+00:00")


@pg
async def test_pg_store_spools_when_db_fails_and_replays_later(pg_pool, tmp_path):
    tag = f"spool-{uuid.uuid4().hex[:8]}"
    calls = {"fail": True}

    async def getter():
        if calls["fail"]:
            raise RuntimeError("db down")
        return pg_pool

    spool = tmp_path / "spool.jsonl"
    store = al.PostgresStore(spool_path=spool, pool_getter=getter)
    await store.write(al.AccessRecord(datetime.now(timezone.utc).isoformat(), tag, "developer", "alice", "ok"))
    await store.write(al.AccessRecord(datetime.now(timezone.utc).isoformat(), tag, "anonymous", None, "ok"))
    assert len(spool.read_text().splitlines()) == 2
    assert await pg_pool.fetchval("SELECT count(*) FROM tool_access_log WHERE tool = $1", tag) == 0
    calls["fail"] = False
    await store.write(al.AccessRecord(datetime.now(timezone.utc).isoformat(), tag, "developer", "bob", "ok"))
    assert not spool.exists()
    assert await pg_pool.fetchval("SELECT count(*) FROM tool_access_log WHERE tool = $1", tag) == 3


@pg
async def test_pg_operator_role_comes_from_the_panel_superadmin(pg_pool, monkeypatch):
    monkeypatch.delenv(al.OPERATOR_IDS_ENV, raising=False)
    await pg_pool.execute("CREATE SCHEMA IF NOT EXISTS panel")
    await pg_pool.execute("CREATE TABLE IF NOT EXISTS panel.profiles (id uuid PRIMARY KEY, developer_id text, role text NOT NULL)")
    boss, dev = f"boss-{uuid.uuid4().hex[:6]}", f"dev-{uuid.uuid4().hex[:6]}"
    await pg_pool.execute("INSERT INTO panel.profiles (id, developer_id, role) VALUES ($1, $2, 'superadmin'), ($3, $4, 'developer')", uuid.uuid4(), boss, uuid.uuid4(), dev)
    assert await al.is_operator(boss, pool=pg_pool) is True
    assert await al.is_operator(dev, pool=pg_pool) is False
    assert await al.is_operator("nobody", pool=pg_pool) is False
