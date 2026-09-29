"""UC-3901 — the remote server asks for a valid token on every connection.

Until now the streamable-HTTP transport accepted any request, session
initialisation included; identity was only checked tool by tool. This module
moves the check to the transport:

* :class:`TransportAuthMiddleware` (pure ASGI, so streamed responses pass
  through untouched) reads ``Authorization: Bearer <token>`` on every HTTP
  request except the public ``/health`` probe:

  - a token that is present but invalid, expired or revoked is rejected with
    ``401 invalid_token`` before any MCP handler runs — in every mode;
  - a valid token becomes the identity of the request (``scope["state"]``);
  - a request without a token follows :class:`TransportPolicy`:
    ``off`` lets it through (the default, so deploying this changes nothing
    until the operator decides), ``grace`` lets it through until the deadline
    with a notice appended to every tool response, and afterwards — or in
    ``enforce`` — rejects it with ``401 token_required`` and the same message.

* :class:`TransportNoticeMiddleware` (FastMCP) appends that notice to tool
  results during the grace period.

* :func:`transport_token` lets tools use the connection's token as the
  caller's identity, so nobody has to pass it again (``set_auth_token``,
  :func:`~server.coordination.scope.resolve_caller_scope`, the access log).

The MCP authorization spec requires the token on every HTTP request of a
session; clients such as Claude Code (``headers`` / ``headersHelper``) and
``mcp-remote --header`` send it automatically. Tokens are never logged: only
their SHA-256 is kept, in memory, as a cache key.

Configuration (environment of the server):

* ``SPECBOX_TRANSPORT_AUTH`` — ``off`` (default) | ``grace`` | ``enforce``.
* ``SPECBOX_TRANSPORT_AUTH_GRACE_UNTIL`` — ``YYYY-MM-DD`` (UTC): first day on
  which a connection without token is rejected. Required for ``grace``; a
  ``grace`` without a valid date fails closed (behaves as ``enforce``).

Runbook: ``doc/runbooks/transport-auth.md``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import structlog

from .i18n_messages import DEFAULT_LOCALE, SupportedLocale, normalize_locale

logger = structlog.get_logger(__name__)

MODE_ENV = "SPECBOX_TRANSPORT_AUTH"
GRACE_UNTIL_ENV = "SPECBOX_TRANSPORT_AUTH_GRACE_UNTIL"

MODE_OFF = "off"
MODE_GRACE = "grace"
MODE_ENFORCE = "enforce"
MODES = frozenset({MODE_OFF, MODE_GRACE, MODE_ENFORCE})

#: Paths served without a token (liveness probe, uptime monitors).
PUBLIC_PATHS = frozenset({"/health"})

#: Key of the request identity inside the ASGI ``scope["state"]``.
STATE_KEY = "specbox_transport"

#: How long a token → developer answer is reused (same window as the rest of
#: the identity caches): a revocation is visible to the transport in ≤ 30 s.
IDENTITY_TTL_SECONDS = 30.0

VERDICT_ALLOW = "allow"
VERDICT_WARN = "warn"
VERDICT_REJECT = "reject"

KIND_DEVELOPER = "developer"
KIND_ANONYMOUS = "anonymous"

#: UC-3904 AC-06 — "Cómo se conecta SpecBox", pública en el panel (ES y EN).
#: Todos los rechazos de conexión la enlazan en ``docs_url``.
HOW_TO_CONNECT_URLS: dict[str, str] = {
    "es": "https://cloud.specbox.build/como-se-conecta",
    "en": "https://cloud.specbox.build/how-to-connect",
}
HOW_TO_CONNECT_URL = HOW_TO_CONNECT_URLS["es"]


def how_to_connect_url(locale: str) -> str:
    return HOW_TO_CONNECT_URLS.get(locale, HOW_TO_CONNECT_URLS["en"])


# ── Policy ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TransportPolicy:
    """What happens to a request that arrives without a token."""

    mode: str = MODE_OFF
    grace_until: dt.date | None = None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> TransportPolicy:
        env = os.environ if environ is None else environ
        raw_mode = (env.get(MODE_ENV) or MODE_OFF).strip().lower()
        if raw_mode not in MODES:
            logger.error("transport_auth_bad_mode", mode=raw_mode)
            raw_mode = MODE_ENFORCE  # an unknown value never opens the door
        grace_until: dt.date | None = None
        raw_date = (env.get(GRACE_UNTIL_ENV) or "").strip()
        if raw_date:
            try:
                grace_until = dt.date.fromisoformat(raw_date)
            except ValueError:
                logger.error("transport_auth_bad_grace_date", value=raw_date)
        if raw_mode == MODE_GRACE and grace_until is None:
            logger.error("transport_auth_grace_without_date")
            raw_mode = MODE_ENFORCE
        return cls(mode=raw_mode, grace_until=grace_until)

    def tokenless_verdict(self, today: dt.date) -> str:
        """Verdict for a request without a token on ``today`` (UTC)."""
        if self.mode == MODE_OFF:
            return VERDICT_ALLOW
        if self.mode == MODE_GRACE and self.grace_until is not None and today < self.grace_until:
            return VERDICT_WARN
        return VERDICT_REJECT


def utc_today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


# ── Messages (AC-05: the same text before and after the deadline) ───

_MESSAGES: dict[str, dict[str, str]] = {
    "token_required_dated": {
        "es": (
            "A partir del {deadline}, el servidor remoto de SpecBox solo acepta conexiones con cuenta. "
            "Conéctate de una de estas dos formas: inicia sesión desde la extensión de VSCode "
            "(«SpecBox: Iniciar sesión con GitHub») o ejecuta `specbox login` en la terminal."
        ),
        "en": (
            "From {deadline}, the SpecBox remote server only accepts connections with an account. "
            "Connect in one of two ways: sign in from the VSCode extension "
            '("SpecBox: Sign in with GitHub") or run `specbox login` in a terminal.'
        ),
    },
    "token_required": {
        "es": (
            "El servidor remoto de SpecBox solo acepta conexiones con cuenta. "
            "Conéctate de una de estas dos formas: inicia sesión desde la extensión de VSCode "
            "(«SpecBox: Iniciar sesión con GitHub») o ejecuta `specbox login` en la terminal."
        ),
        "en": (
            "The SpecBox remote server only accepts connections with an account. "
            "Connect in one of two ways: sign in from the VSCode extension "
            '("SpecBox: Sign in with GitHub") or run `specbox login` in a terminal.'
        ),
    },
    "invalid_token": {
        "es": (
            "La conexión desde este dispositivo ha terminado: su token no es válido, ha caducado o fue revocado. "
            "Vuelve a conectarte iniciando sesión desde la extensión de VSCode "
            "(«SpecBox: Iniciar sesión con GitHub») o ejecutando `specbox login` en la terminal."
        ),
        "en": (
            "The connection from this device has ended: its token is invalid, expired or revoked. "
            'Reconnect by signing in from the VSCode extension ("SpecBox: Sign in with GitHub") '
            "or running `specbox login` in a terminal."
        ),
    },
    "auth_unavailable": {
        "es": "No se pudo comprobar la identidad de esta conexión ahora mismo. Inténtalo de nuevo en unos segundos.",
        "en": "The identity of this connection could not be checked right now. Try again in a few seconds.",
    },
}


def message(key: str, locale: SupportedLocale = DEFAULT_LOCALE, **fmt: str) -> str:
    entries = _MESSAGES[key]
    return (entries.get(locale) or entries[DEFAULT_LOCALE]).format(**fmt)


def token_required_message(policy: TransportPolicy, locale: SupportedLocale = DEFAULT_LOCALE) -> str:
    """The notice for connections without a token — identical before and after the deadline."""
    if policy.grace_until is not None:
        return message("token_required_dated", locale, deadline=policy.grace_until.isoformat())
    return message("token_required", locale)


# ── Parsing ─────────────────────────────────────────────────────────


def bearer_token(headers: Any) -> tuple[bool, str]:
    """``(present, token)`` from ASGI headers or any mapping of headers.

    ``present`` is True as soon as an ``Authorization`` header exists; a header
    that is not a non-empty ``Bearer`` credential comes back as ``(True, "")``
    and is treated as an invalid token, never as "no token".
    """
    raw: str | None = None
    if isinstance(headers, Mapping):
        for key, value in headers.items():
            if str(key).lower() == "authorization":
                raw = str(value)
                break
    else:
        for key, value in headers or ():
            name = key.decode("latin-1") if isinstance(key, bytes) else str(key)
            if name.lower() == "authorization":
                raw = value.decode("latin-1") if isinstance(value, bytes) else str(value)
                break
    if raw is None:
        return False, ""
    scheme, _, credential = raw.strip().partition(" ")
    if scheme.lower() != "bearer":
        return True, ""
    return True, credential.strip()


def _header(scope: Mapping[str, Any], name: str) -> str | None:
    wanted = name.lower().encode("latin-1")
    for key, value in scope.get("headers") or ():
        if key.lower() == wanted:
            return value.decode("latin-1")
    return None


# ── Identity resolution (cached, never logs the token) ──────────────

Resolver = Callable[[str], Awaitable["str | None"]]

_CACHE: dict[str, tuple[str | None, float]] = {}


def _clear_cache() -> None:
    """Test-only."""
    _CACHE.clear()


async def resolve_token(token: str) -> str | None:
    """Developer id behind ``token`` or ``None`` when it is invalid or revoked.

    Raises when the identity database cannot be reached (the caller answers
    503, never 401: an outage is not the user's fault).
    """
    from ..db.pool import get_pool
    from .identity import UnauthenticatedError, resolve_developer

    pool = await get_pool()
    try:
        developer = await resolve_developer(pool, token)
    except UnauthenticatedError:
        return None
    return developer.developer_id


async def _resolve_cached(token: str, resolver: Resolver) -> str | None:
    key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = time.monotonic()
    hit = _CACHE.get(key)
    if hit and hit[1] > now:
        return hit[0]
    developer_id = await resolver(token)
    _CACHE[key] = (developer_id, now + IDENTITY_TTL_SECONDS)
    return developer_id


@dataclass(frozen=True)
class TransportIdentity:
    """Who is behind an HTTP request, as established by the transport."""

    developer_id: str | None
    kind: str
    grace_notice: str | None = None


# ── ASGI middleware (AC-01, AC-05) ──────────────────────────────────


class TransportAuthMiddleware:
    """Authenticate every HTTP request before the MCP app sees it."""

    def __init__(
        self,
        app: Any,
        policy: TransportPolicy | None = None,
        resolver: Resolver | None = None,
        today: Callable[[], dt.date] | None = None,
    ) -> None:
        self.app = app
        self.policy = policy or TransportPolicy.from_env()
        self.resolver = resolver or resolve_token
        self.today = today or utc_today
        logger.info(
            "transport_auth_configured",
            mode=self.policy.mode,
            grace_until=self.policy.grace_until.isoformat() if self.policy.grace_until else None,
        )

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        # CORS preflights never carry credentials: rejecting them would break
        # browser clients even when they hold a valid token. They run no tool.
        if scope.get("type") != "http" or scope.get("path") in PUBLIC_PATHS or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        locale = normalize_locale(_header(scope, "accept-language"))
        present, token = bearer_token(scope.get("headers") or ())

        if present:
            if not token:
                await _reject(send, 401, "invalid_token", message("invalid_token", locale), locale)
                return
            try:
                developer_id = await _resolve_cached(token, self.resolver)
            except Exception as exc:  # noqa: BLE001 — identity DB unreachable
                logger.warning("transport_auth_unavailable", reason=type(exc).__name__)
                await _reject(send, 503, "auth_unavailable", message("auth_unavailable", locale), locale)
                return
            if developer_id is None:
                await _reject(send, 401, "invalid_token", message("invalid_token", locale), locale)
                return
            identity = TransportIdentity(developer_id=developer_id, kind=KIND_DEVELOPER)
        else:
            verdict = self.policy.tokenless_verdict(self.today())
            if verdict == VERDICT_REJECT:
                await _reject(send, 401, "token_required", token_required_message(self.policy, locale), locale)
                return
            notice = token_required_message(self.policy, locale) if verdict == VERDICT_WARN else None
            identity = TransportIdentity(developer_id=None, kind=KIND_ANONYMOUS, grace_notice=notice)

        scope.setdefault("state", {})[STATE_KEY] = identity
        await self.app(scope, receive, send)


async def _reject(send: Any, status: int, code: str, text: str, locale: str = DEFAULT_LOCALE) -> None:
    body = json.dumps(
        {"error": code, "message": text, "docs_url": how_to_connect_url(locale)}, ensure_ascii=False
    ).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode("latin-1")),
    ]
    if status == 401:
        challenge = 'Bearer realm="specbox"'
        if code == "invalid_token":
            challenge += ', error="invalid_token"'
        headers.append((b"www-authenticate", challenge.encode("latin-1")))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


# ── Reading the transport identity from a tool (AC-02) ──────────────


def _current_request(ctx: Any | None) -> Any | None:
    if ctx is not None:
        try:
            request = ctx.request_context.request
            if request is not None:
                return request
        except (AttributeError, LookupError, RuntimeError, ValueError):
            pass
    try:
        from fastmcp.server.dependencies import get_http_request

        return get_http_request()
    except (LookupError, RuntimeError, ImportError):
        return None


def transport_identity(ctx: Any | None = None) -> TransportIdentity | None:
    """The identity :class:`TransportAuthMiddleware` attached to this request, if any."""
    request = _current_request(ctx)
    if request is None:
        return None
    state = getattr(request, "scope", {}).get("state")
    identity = state.get(STATE_KEY) if isinstance(state, Mapping) else None
    return identity if isinstance(identity, TransportIdentity) else None


def transport_token(ctx: Any | None = None) -> str:
    """The token this connection presented — only once the transport validated it.

    Lets a tool treat the connection's identity as the caller's without asking
    for the token again. Empty when the request carried no token, when the
    middleware is not installed (stdio, tests) or when the token was rejected.
    """
    identity = transport_identity(ctx)
    if identity is None or identity.kind != KIND_DEVELOPER:
        return ""
    request = _current_request(ctx)
    present, token = bearer_token(getattr(request, "headers", {}) or {})
    return token if present else ""


# ── Grace notice on tool results (AC-05) ────────────────────────────

try:  # FastMCP is always present on the server; keep the module importable without it.
    from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
except ImportError:  # pragma: no cover
    Middleware = object  # type: ignore[assignment,misc]
    CallNext = Any  # type: ignore[assignment,misc]
    MiddlewareContext = Any  # type: ignore[assignment,misc]


def append_notice(result: Any, notice: str) -> Any:
    """``result`` with ``notice`` as an extra text block (structured content untouched)."""
    from fastmcp.tools.tool import ToolResult
    from mcp.types import TextContent

    if not isinstance(result, ToolResult):
        return result
    content = list(result.content or [])
    content.append(TextContent(type="text", text=f"⚠️ {notice}"))
    return ToolResult(
        content=content,
        structured_content=result.structured_content,
        meta=result.meta,
        is_error=bool(getattr(result, "is_error", False)),
    )


class TransportNoticeMiddleware(Middleware):  # type: ignore[misc,valid-type]
    """During the grace period every tool response carries the notice."""

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext) -> Any:  # type: ignore[valid-type]
        result = await call_next(context)
        identity = transport_identity(getattr(context, "fastmcp_context", None))
        if identity is None or not identity.grace_notice:
            return result
        return append_notice(result, identity.grace_notice)
