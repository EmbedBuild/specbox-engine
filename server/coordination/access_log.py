"""Tool access log — every tool call leaves a trail (UC-3803, US-38).

Origin: when the external tester reported the cross-tenant leaks (2026-09-24)
the hosted MCP could not say who had called which tool, when, or with what
outcome. ``audit_log`` (0006) records native mutations; nothing recorded the
calls themselves. This module closes that gap with a FastMCP middleware that
appends one :class:`AccessRecord` per tool call, on every transport.

What a record holds (AC-01) — and what it never holds (AC-03)
=============================================================
* when (``occurred_at``), which tool, who (``developer_id`` or the reason
  there is none: ``anonymous`` / ``invalid_token`` / ``unresolved``), the
  outcome (``ok`` / ``error`` / ``exception``) with a short ``error_code``,
  the duration, the transport, the MCP client name, the remote address and
  the MCP session id, plus the argument NAMES (``arg_keys``).
* never a token, never an argument value, never a returned payload, never an
  error message (messages can quote data). The token is only ever hashed in
  memory to cache its resolution for a few seconds, and that hash is not
  stored either.

Where it goes
=============
:class:`PostgresStore` appends to ``tool_access_log`` (migration 0022: an
append-only table guarded by a trigger that refuses UPDATE / DELETE /
TRUNCATE). When the insert fails (database unreachable) the record is spooled
to a local JSONL file and replayed on the next successful write, so a
database blip never silences the trail — and never breaks the tool call.
Without ``SPECBOX_NATIVE_DSN`` the :class:`JsonlStore` keeps a local
append-only file instead (dev / stdio servers).

Who may read it (AC-02)
=======================
The query tool (``server/tools/access_log.py``) is reserved to the ecosystem
operator: the SuperAdmin of the cloud panel (``panel.profiles.role =
'superadmin'`` for the caller's ``developer_id``) or, as an explicit
bootstrap/dev override, an id listed in ``SPECBOX_OPERATOR_DEVELOPER_IDS``.
Everyone else gets an authorization error and no entries.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import structlog
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext

from .identity import UnauthenticatedError, resolve_developer

logger = structlog.get_logger(__name__)

#: How an unidentified caller is named in reports (AC-01 wording).
ANONYMOUS_LABEL = "anónimo"

KIND_DEVELOPER = "developer"
KIND_ANONYMOUS = "anonymous"
KIND_INVALID_TOKEN = "invalid_token"
KIND_UNRESOLVED = "unresolved"

OUTCOME_OK = "ok"
OUTCOME_ERROR = "error"
OUTCOME_EXCEPTION = "exception"

#: Comma-separated developer ids that count as ecosystem operators without a
#: panel profile (bootstrap / dev). Production relies on the panel role.
OPERATOR_IDS_ENV = "SPECBOX_OPERATOR_DEVELOPER_IDS"

MAX_CODE_LEN = 64
MAX_ARG_KEYS = 32
MAX_QUERY_LIMIT = 1000
_IDENTITY_TTL_SECONDS = 30.0
_ERROR_STATUSES = frozenset({"unauthenticated", "forbidden", "error"})


@dataclass(frozen=True)
class AccessRecord:
    """One tool call. Built entirely before anything async happens with it."""

    occurred_at: str
    tool: str
    identity_kind: str
    developer_id: str | None
    outcome: str
    error_code: str | None = None
    duration_ms: int | None = None
    project_id: str | None = None
    transport: str = "stdio"
    client: str | None = None
    remote_addr: str | None = None
    session_id: str | None = None
    arg_keys: tuple[str, ...] = ()

    @property
    def identity_label(self) -> str:
        return self.developer_id or ANONYMOUS_LABEL

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["arg_keys"] = list(self.arg_keys)
        data["identity"] = self.identity_label
        return data


# ── Identity of the caller, for the log only ────────────────────────

_IDENTITY_CACHE: dict[str, tuple[str | None, str, float]] = {}


def _clear_identity_cache() -> None:
    """Test-only."""
    _IDENTITY_CACHE.clear()


async def identity_for_log(ctx: Any) -> tuple[str | None, str, str | None]:
    """Resolve ``(developer_id, identity_kind, project_id)`` for a call.

    Never raises and never logs the token. The token's SHA-256 is used only as
    an in-memory cache key for :data:`_IDENTITY_TTL_SECONDS`, so a burst of
    calls from one session costs one database lookup.
    """
    if ctx is None:
        return None, KIND_ANONYMOUS, None
    try:
        from ..auth_gateway import BACKEND_STATE_KEY

        config = await ctx.get_state(BACKEND_STATE_KEY)
    except Exception:  # noqa: BLE001 — a broken context is an anonymous call
        return None, KIND_ANONYMOUS, None
    if not isinstance(config, Mapping) or config.get("backend_type") != "native":
        return None, KIND_ANONYMOUS, None
    project_id = config.get("project_id") or None
    token = str(config.get("dev_token") or "").strip()
    if not token:
        return None, KIND_ANONYMOUS, project_id

    key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = time.monotonic()
    cached = _IDENTITY_CACHE.get(key)
    if cached and cached[2] > now:
        return cached[0], cached[1], project_id

    try:
        from ..db.pool import get_pool

        pool = await get_pool()
        developer = await resolve_developer(pool, token)
        entry: tuple[str | None, str, float] = (developer.developer_id, KIND_DEVELOPER, now + _IDENTITY_TTL_SECONDS)
    except UnauthenticatedError:
        entry = (None, KIND_INVALID_TOKEN, now + _IDENTITY_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001 — identity DB unavailable: say so, don't fail the call
        logger.warning("access_log_identity_unresolved", reason=type(exc).__name__)
        return None, KIND_UNRESOLVED, project_id
    _IDENTITY_CACHE[key] = entry
    return entry[0], entry[1], project_id


# ── Operator role (AC-02) ───────────────────────────────────────────


def operator_ids_from_env() -> frozenset[str]:
    raw = os.getenv(OPERATOR_IDS_ENV, "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


async def is_operator(developer_id: str | None, *, pool: Any | None = None) -> bool:
    """True when ``developer_id`` is an ecosystem operator.

    The panel's SuperAdmin role is the source of truth
    (``panel.profiles.developer_id`` links a panel account to a native
    developer). :data:`OPERATOR_IDS_ENV` is an explicit override for servers
    without the panel schema. Any failure to check means "not an operator".
    """
    if not developer_id:
        return False
    if developer_id in operator_ids_from_env():
        return True
    try:
        if pool is None:
            from ..db.pool import get_pool

            pool = await get_pool()
        found = await pool.fetchval(
            "SELECT EXISTS (SELECT 1 FROM panel.profiles WHERE developer_id = $1 AND role::text = 'superadmin')",
            developer_id,
        )
        return bool(found)
    except Exception as exc:  # noqa: BLE001 — no panel schema / no DB → nobody is operator
        logger.warning("operator_check_unavailable", reason=type(exc).__name__)
        return False


# ── Stores ──────────────────────────────────────────────────────────


class AccessLogStore(Protocol):
    async def write(self, record: AccessRecord) -> None: ...

    async def query(
        self,
        *,
        developer_id: str | None = None,
        identity_kind: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        tool: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]: ...


def _matches(
    row: Mapping[str, Any],
    *,
    developer_id: str | None,
    identity_kind: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    tool: str | None,
) -> bool:
    if developer_id is not None and row.get("developer_id") != developer_id:
        return False
    if identity_kind is not None and row.get("identity_kind") != identity_kind:
        return False
    if tool is not None and row.get("tool") != tool:
        return False
    if date_from is not None or date_to is not None:
        try:
            when = datetime.fromisoformat(str(row.get("occurred_at")))
        except ValueError:
            return False
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if date_from is not None and when < date_from:
            return False
        if date_to is not None and when > date_to:
            return False
    return True


class MemoryStore:
    """In-memory store (tests, and the last-resort fallback)."""

    def __init__(self) -> None:
        self.records: list[AccessRecord] = []

    async def write(self, record: AccessRecord) -> None:
        self.records.append(record)

    async def query(self, *, developer_id=None, identity_kind=None, date_from=None, date_to=None, tool=None, limit=200):
        rows = [r.to_dict() for r in self.records]
        rows = [r for r in rows if _matches(r, developer_id=developer_id, identity_kind=identity_kind, date_from=date_from, date_to=date_to, tool=tool)]
        rows.sort(key=lambda r: r["occurred_at"], reverse=True)
        return rows[: max(1, min(limit, MAX_QUERY_LIMIT))]


class JsonlStore:
    """Append-only JSONL file (servers without an identity database)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    async def write(self, record: AccessRecord) -> None:
        line = json.dumps(record.to_dict(), ensure_ascii=False)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            logger.warning("access_log_file_write_failed", path=str(self.path), reason=type(exc).__name__)

    def _rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    async def query(self, *, developer_id=None, identity_kind=None, date_from=None, date_to=None, tool=None, limit=200):
        rows = [r for r in self._rows() if _matches(r, developer_id=developer_id, identity_kind=identity_kind, date_from=date_from, date_to=date_to, tool=tool)]
        rows.sort(key=lambda r: str(r.get("occurred_at", "")), reverse=True)
        return rows[: max(1, min(limit, MAX_QUERY_LIMIT))]


_INSERT_SQL = """
INSERT INTO tool_access_log
    (occurred_at, tool, identity_kind, developer_id, project_id, outcome, error_code,
     duration_ms, transport, client, remote_addr, session_id, arg_keys)
VALUES ($1::timestamptz, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::text[])
"""

_QUERY_SQL = """
SELECT id, occurred_at, tool, identity_kind, developer_id, project_id, outcome, error_code,
       duration_ms, transport, client, remote_addr, session_id, arg_keys
  FROM tool_access_log
 WHERE ($1::text IS NULL OR developer_id = $1)
   AND ($2::text IS NULL OR identity_kind = $2)
   AND ($3::timestamptz IS NULL OR occurred_at >= $3)
   AND ($4::timestamptz IS NULL OR occurred_at <= $4)
   AND ($5::text IS NULL OR tool = $5)
 ORDER BY occurred_at DESC, id DESC
 LIMIT $6
"""


class PostgresStore:
    """``tool_access_log`` in the native database, with a local spool as safety net."""

    def __init__(self, spool_path: Path | None = None, *, pool_getter: Any | None = None) -> None:
        self.spool_path = Path(spool_path) if spool_path else None
        self._pool_getter = pool_getter
        self._lock = asyncio.Lock()

    async def _pool(self) -> Any:
        if self._pool_getter is not None:
            return await self._pool_getter()
        from ..db.pool import get_pool

        return await get_pool()

    @staticmethod
    def _params(record: AccessRecord) -> tuple[Any, ...]:
        return (
            datetime.fromisoformat(record.occurred_at),
            record.tool,
            record.identity_kind,
            record.developer_id,
            record.project_id,
            record.outcome,
            record.error_code,
            record.duration_ms,
            record.transport,
            record.client,
            record.remote_addr,
            record.session_id,
            list(record.arg_keys),
        )

    async def _replay_spool(self, pool: Any) -> int:
        if self.spool_path is None or not self.spool_path.exists():
            return 0
        replayed = 0
        lines = self.spool_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            data.pop("identity", None)
            data["arg_keys"] = tuple(data.get("arg_keys") or ())
            await pool.execute(_INSERT_SQL, *self._params(AccessRecord(**data)))
            replayed += 1
        self.spool_path.unlink()
        if replayed:
            logger.info("access_log_spool_replayed", entries=replayed)
        return replayed

    def _spool(self, record: AccessRecord) -> None:
        if self.spool_path is None:
            return
        try:
            self.spool_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.spool_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("access_log_spool_failed", reason=type(exc).__name__)

    async def write(self, record: AccessRecord) -> None:
        async with self._lock:
            try:
                pool = await self._pool()
                await self._replay_spool(pool)
                await pool.execute(_INSERT_SQL, *self._params(record))
            except Exception as exc:  # noqa: BLE001 — never break a tool call over its own log
                logger.warning("access_log_db_write_failed", reason=type(exc).__name__, spooled=self.spool_path is not None)
                self._spool(record)

    async def query(self, *, developer_id=None, identity_kind=None, date_from=None, date_to=None, tool=None, limit=200):
        pool = await self._pool()
        rows = await pool.fetch(
            _QUERY_SQL, developer_id, identity_kind, date_from, date_to, tool, max(1, min(limit, MAX_QUERY_LIMIT))
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            when = item.get("occurred_at")
            if isinstance(when, datetime):
                item["occurred_at"] = when.astimezone(timezone.utc).isoformat()
            item["arg_keys"] = list(item.get("arg_keys") or [])
            item["identity"] = item.get("developer_id") or ANONYMOUS_LABEL
            out.append(item)
        return out


_STORE: AccessLogStore | None = None


def configure_store(store: AccessLogStore | None) -> None:
    global _STORE
    _STORE = store


def get_store() -> AccessLogStore:
    global _STORE
    if _STORE is None:
        _STORE = MemoryStore()
    return _STORE


def build_default_store(state_path: Path) -> AccessLogStore:
    """Postgres when the identity database is configured, a local JSONL file otherwise."""
    from ..db.pool import DSN_ENV_VAR

    if os.getenv(DSN_ENV_VAR):
        return PostgresStore(spool_path=state_path / "tool_access_log.spool.jsonl")
    return JsonlStore(state_path / "tool_access_log.jsonl")


# ── Middleware ──────────────────────────────────────────────────────


def classify_result(result: Any) -> tuple[str, str | None]:
    """``(outcome, error_code)`` from a tool result; never reads message text."""
    if getattr(result, "is_error", False):
        return OUTCOME_ERROR, "TOOL_ERROR"
    payload = getattr(result, "structured_content", None)
    if isinstance(payload, Mapping) and set(payload.keys()) == {"result"}:
        payload = payload["result"]
    if isinstance(payload, Mapping):
        status = payload.get("status")
        if payload.get("error") or (isinstance(status, str) and status.lower() in _ERROR_STATUSES):
            code = payload.get("code") or payload.get("status") or "ERROR"
            return OUTCOME_ERROR, str(code)[:MAX_CODE_LEN]
    return OUTCOME_OK, None


def _request_facts(ctx: Any) -> tuple[str | None, str | None, str | None]:
    """``(client, remote_addr, session_id)`` — every part best-effort, never raises."""
    client: str | None = None
    remote: str | None = None
    session_id: str | None = None
    try:
        params = getattr(getattr(ctx, "session", None), "client_params", None)
        info = getattr(params, "clientInfo", None)
        if info is not None:
            client = f"{getattr(info, 'name', '')} {getattr(info, 'version', '')}".strip() or None
    except Exception:  # noqa: BLE001
        client = None
    try:
        from fastmcp.server.dependencies import get_http_request

        request = get_http_request()
        forwarded = request.headers.get("x-forwarded-for") if request is not None else None
        if forwarded:
            remote = forwarded.split(",")[0].strip()
        elif request is not None and request.client is not None:
            remote = request.client.host
    except Exception:  # noqa: BLE001 — stdio has no HTTP request
        remote = None
    try:
        session_id = ctx.session_id if ctx is not None else None
    except Exception:  # noqa: BLE001
        session_id = None
    return client, remote, (str(session_id) if session_id else None)


class ToolAccessLogMiddleware(Middleware):
    """Appends one :class:`AccessRecord` per ``tools/call`` — success, error or crash."""

    def __init__(self, store: AccessLogStore | None = None, *, transport: str | None = None, blocking: bool = False) -> None:
        self._store = store
        self._transport = transport
        self._blocking = blocking
        self._pending: set[asyncio.Task[None]] = set()

    @property
    def store(self) -> AccessLogStore:
        return self._store or get_store()

    def _transport_name(self) -> str:
        if self._transport:
            return self._transport
        from ..transport import transport_name

        return transport_name()

    async def _safe_write(self, record: AccessRecord) -> None:
        try:
            await self.store.write(record)
        except Exception as exc:  # noqa: BLE001 — the log must never take a tool down
            logger.warning("access_log_write_failed", tool=record.tool, reason=type(exc).__name__)

    async def _emit(self, record: AccessRecord) -> None:
        if self._blocking:
            await self._safe_write(record)
            return
        task = asyncio.create_task(self._safe_write(record))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def drain(self) -> None:
        """Wait for in-flight writes (tests, graceful shutdown)."""
        if self._pending:
            await asyncio.gather(*list(self._pending), return_exceptions=True)

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        started = time.monotonic()
        occurred_at = datetime.now(timezone.utc).isoformat()
        message = context.message
        tool = str(getattr(message, "name", "") or "?")
        arguments = getattr(message, "arguments", None) or {}
        arg_keys = tuple(sorted(str(k) for k in arguments)[:MAX_ARG_KEYS]) if isinstance(arguments, Mapping) else ()
        ctx = context.fastmcp_context
        developer_id, kind, project_id = await identity_for_log(ctx)
        client, remote, session_id = _request_facts(ctx)

        def _record(outcome: str, code: str | None) -> AccessRecord:
            return AccessRecord(
                occurred_at=occurred_at,
                tool=tool,
                identity_kind=kind,
                developer_id=developer_id,
                outcome=outcome,
                error_code=code,
                duration_ms=int((time.monotonic() - started) * 1000),
                project_id=project_id,
                transport=self._transport_name(),
                client=client,
                remote_addr=remote,
                session_id=session_id,
                arg_keys=arg_keys,
            )

        try:
            result = await call_next(context)
        except Exception as exc:
            await self._emit(_record(OUTCOME_EXCEPTION, type(exc).__name__[:MAX_CODE_LEN]))
            raise
        outcome, code = classify_result(result)
        await self._emit(_record(outcome, code))
        return result
