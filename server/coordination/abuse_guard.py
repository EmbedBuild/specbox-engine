"""UC-3903 AC-02 — size and rate limits on the remote server.

:class:`AbuseGuardMiddleware` (pure ASGI) sits right after
:class:`~server.coordination.transport_auth.TransportAuthMiddleware`, so it
knows who is calling:

* a request body over ``SPECBOX_MAX_REQUEST_BYTES`` (2 MB by default) is
  rejected with ``413 request_too_large`` before the MCP app parses it — by its
  ``Content-Length`` when declared, by counting the bytes otherwise;
* more than ``SPECBOX_RATE_LIMIT_PER_MINUTE`` tool calls (60 by default) in a
  sliding minute from the same identity are rejected with
  ``429 rate_limited`` and ``Retry-After``. Each identity has its own budget:
  one caller hitting the limit never slows anybody else down.

The identity is the developer the transport authenticated; a connection
without a token is identified by its client IP — the right-most entry of
``X-Forwarded-For``, the one added by the proxy in front of the server, which
a client cannot forge. Only ``tools/call`` messages count: the protocol's own
chatter (initialize, notifications, listings) is not a call.

Budgets live in memory (one server process). ``/health`` and CORS preflights
are never limited.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections import deque
from collections.abc import Callable, Mapping
from typing import Any

import structlog

from .i18n_messages import DEFAULT_LOCALE, SupportedLocale, normalize_locale
from .transport_auth import PUBLIC_PATHS, STATE_KEY

logger = structlog.get_logger(__name__)

MAX_BODY_ENV = "SPECBOX_MAX_REQUEST_BYTES"
RATE_ENV = "SPECBOX_RATE_LIMIT_PER_MINUTE"

DEFAULT_MAX_BODY_BYTES = 2 * 1024 * 1024
DEFAULT_RATE_PER_MINUTE = 60
WINDOW_SECONDS = 60.0

_MESSAGES: dict[str, dict[str, str]] = {
    "request_too_large": {
        "es": "La petición supera el máximo de {limit_mb} MB y no se ha procesado.",
        "en": "The request exceeds the {limit_mb} MB limit and was not processed.",
    },
    "rate_limited": {
        "es": (
            "Demasiadas llamadas: el límite es de {limit} por minuto para cada identidad. "
            "Vuelve a intentarlo en {retry} s."
        ),
        "en": "Too many calls: the limit is {limit} per minute for each identity. Try again in {retry} s.",
    },
}


def _message(key: str, locale: SupportedLocale, **fmt: Any) -> str:
    entries = _MESSAGES[key]
    return (entries.get(locale) or entries[DEFAULT_LOCALE]).format(**fmt)


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.error("abuse_guard_bad_setting", setting=name, value=raw)
        return default
    return value if value > 0 else default


class RateLimiter:
    """Sliding-window counter per key: at most ``limit`` hits in ``window`` seconds."""

    def __init__(self, limit: int, window: float = WINDOW_SECONDS, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def acquire(self, key: str, cost: int = 1) -> float | None:
        """Record ``cost`` hits for ``key``; ``None`` if allowed, else seconds to wait."""
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) + cost > self.limit:
            oldest = hits[0] if hits else now
            return max(0.0, oldest + self.window - now)
        hits.extend([now] * cost)
        if len(self._hits) > 10_000:  # forget idle identities
            for stale in [k for k, q in self._hits.items() if not q or q[-1] <= now - self.window]:
                del self._hits[stale]
        return None


def _header(scope: Mapping[str, Any], name: str) -> str | None:
    wanted = name.lower().encode("latin-1")
    for key, value in scope.get("headers") or ():
        if key.lower() == wanted:
            return value.decode("latin-1")
    return None


def identity_key(scope: Mapping[str, Any]) -> str:
    """Budget key: the authenticated developer, or the client IP seen by the proxy."""
    state = scope.get("state")
    identity = state.get(STATE_KEY) if isinstance(state, Mapping) else None
    developer_id = getattr(identity, "developer_id", None)
    if developer_id:
        return f"developer:{developer_id}"
    forwarded = _header(scope, "x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[-1].strip()}"
    client = scope.get("client")
    return f"ip:{client[0]}" if client else "ip:unknown"


def count_tool_calls(body: bytes) -> int:
    """How many ``tools/call`` messages a JSON-RPC body carries (0 if unparseable)."""
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return 0
    messages = payload if isinstance(payload, list) else [payload]
    return sum(1 for m in messages if isinstance(m, Mapping) and m.get("method") == "tools/call")


class AbuseGuardMiddleware:
    """Reject oversized requests and tool-call floods, per identity."""

    def __init__(
        self,
        app: Any,
        max_body_bytes: int | None = None,
        limiter: RateLimiter | None = None,
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes or _int_env(MAX_BODY_ENV, DEFAULT_MAX_BODY_BYTES)
        self.limiter = limiter or RateLimiter(_int_env(RATE_ENV, DEFAULT_RATE_PER_MINUTE))
        logger.info("abuse_guard_configured", max_body_bytes=self.max_body_bytes, rate_per_minute=self.limiter.limit)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or scope.get("method") != "POST" or scope.get("path") in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        locale = normalize_locale(_header(scope, "accept-language"))
        too_large = _message("request_too_large", locale, limit_mb=f"{self.max_body_bytes / (1024 * 1024):g}")
        declared = _header(scope, "content-length")
        if declared and declared.strip().isdigit() and int(declared) > self.max_body_bytes:
            await _reject(send, 413, "request_too_large", too_large)
            return

        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_body_bytes:
                await _reject(send, 413, "request_too_large", too_large)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)

        calls = count_tool_calls(body)
        if calls:
            key = identity_key(scope)
            retry = self.limiter.acquire(key, calls)
            if retry is not None:
                seconds = max(1, math.ceil(retry))
                logger.warning("rate_limited", identity=key.split(":", 1)[0], retry_after=seconds)
                await _reject(
                    send,
                    429,
                    "rate_limited",
                    _message("rate_limited", locale, limit=self.limiter.limit, retry=seconds),
                    extra_headers=[(b"retry-after", str(seconds).encode("latin-1"))],
                )
                return

        replayed = False

        async def replay() -> dict[str, Any]:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


async def _reject(
    send: Any, status: int, code: str, text: str, extra_headers: list[tuple[bytes, bytes]] | None = None
) -> None:
    body = json.dumps({"error": code, "message": text}, ensure_ascii=False).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode("latin-1")),
        *(extra_headers or []),
    ]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})
