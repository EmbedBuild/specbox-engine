"""A per-identity call limit on the hosted MCP (UC-11401, US-114).

Origin: on 2026-11-07 the Supabase organization was restricted for egress
(13.6 of 5 GB). One MCP client of another tenant had polled the hosted MCP
every ~3 minutes for five days — ~54,500 calls, 36,582 of them ``get_uc`` —
and every read of the board crossed the database pooler. In the 30 days
before, no legitimate identity went past 59 calls a minute, 597 an hour or
2,121 a day.

What it does
============
Each identity gets sliding windows: by default 120 calls per minute, 1,200
per hour and 5,000 per day, two to two and a half times the highest
legitimate use measured. A call over any window gets ``RATE_LIMITED`` with
``retry_after_s`` and the tool does not run; rejected calls do not count, so
waiting is enough to get through again.

The identity is the ``developer_id`` the access log resolves (the session's
token or the transport's); a caller without one is limited by its MCP session
or, without that, its address.

Only on a remote transport: a local stdio server has one person behind it.

Configuration
=============
``SPECBOX_RATE_LIMITS`` replaces the defaults without a release, e.g.
``"60/min,600/h,3000/d"`` (units: ``s``, ``min``, ``h``, ``d``); ``"off"``
turns the limit off. A malformed value keeps the defaults and logs a warning.

Where it sits
=============
Registered right after ``ToolAccessLogMiddleware`` (FastMCP wraps middleware
in registration order), so every rejected call still leaves its line in
``tool_access_log`` with the code ``RATE_LIMITED`` — also for tools whose
result is a list, through :data:`RESULT_CODE_META_KEY`.
"""

from __future__ import annotations

import bisect
import math
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import structlog

from .access_log import RESULT_CODE_META_KEY, _request_facts, identity_for_log
from .tool_envelope import envelope_result

logger = structlog.get_logger(__name__)

RATE_LIMITS_ENV = "SPECBOX_RATE_LIMITS"
DEFAULT_RATE_LIMITS = "120/min,1200/h,5000/d"
CODE_RATE_LIMITED = "RATE_LIMITED"

_UNIT_SECONDS = {"s": 1, "sec": 1, "min": 60, "m": 60, "h": 3600, "hour": 3600, "d": 86400, "day": 86400}
_UNIT_WORDS = {1: "second", 60: "minute", 3600: "hour", 86400: "day"}
_SPEC = re.compile(r"^\s*(\d+)\s*/\s*([a-z]+)\s*$")


@dataclass(frozen=True)
class Window:
    """At most ``limit`` calls in any ``seconds`` span."""

    limit: int
    seconds: int

    @property
    def label(self) -> str:
        unit = {1: "s", 60: "min", 3600: "h", 86400: "d"}.get(self.seconds, f"{self.seconds}s")
        return f"{self.limit}/{unit}"

    @property
    def span(self) -> str:
        word = _UNIT_WORDS.get(self.seconds)
        return f"one {word}" if word else f"{self.seconds} seconds"


def parse_limits(raw: str | None) -> tuple[Window, ...]:
    """``"120/min,1200/h"`` → windows; empty → defaults; ``"off"`` → none.

    Raises ``ValueError`` on anything else, so a typo never silently opens the
    gate: :func:`limits_from_env` falls back to the defaults.
    """
    text = (raw or "").strip().lower()
    if not text:
        text = DEFAULT_RATE_LIMITS
    if text in {"off", "none", "0", "false"}:
        return ()
    windows: dict[int, Window] = {}
    for part in text.split(","):
        match = _SPEC.match(part)
        if not match or match.group(2) not in _UNIT_SECONDS:
            raise ValueError(f"invalid rate limit {part.strip()!r}; expected e.g. 120/min, 1200/h, 5000/d")
        limit, seconds = int(match.group(1)), _UNIT_SECONDS[match.group(2)]
        if limit < 1:
            raise ValueError(f"invalid rate limit {part.strip()!r}; the number must be at least 1")
        windows[seconds] = Window(limit=limit, seconds=seconds)
    return tuple(sorted(windows.values(), key=lambda w: w.seconds))


def limits_from_env() -> tuple[Window, ...]:
    raw = os.getenv(RATE_LIMITS_ENV)
    try:
        return parse_limits(raw)
    except ValueError as exc:
        logger.warning("rate_limits_invalid", env=RATE_LIMITS_ENV, reason=str(exc), using=DEFAULT_RATE_LIMITS)
        return parse_limits(None)


class RateLimiter:
    """Sliding windows per key, in memory (one MCP process)."""

    def __init__(self, windows: tuple[Window, ...], *, clock: Callable[[], float] = time.monotonic) -> None:
        self.windows = tuple(sorted(windows, key=lambda w: w.seconds))
        self._clock = clock
        self._calls: dict[str, list[float]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.windows)

    def check(self, key: str) -> tuple[Window, int] | None:
        """Count the call and return ``None``, or return ``(window, retry_after_s)`` without counting it."""
        if not self.windows:
            return None
        now = self._clock()
        calls = self._calls.setdefault(key, [])
        horizon = self.windows[-1].seconds
        del calls[: bisect.bisect_right(calls, now - horizon)]
        for window in self.windows:
            first = bisect.bisect_right(calls, now - window.seconds)
            inside = len(calls) - first
            if inside >= window.limit:
                # Room comes back when enough calls leave the window.
                frees_at = calls[first + inside - window.limit] + window.seconds
                return window, max(1, math.ceil(frees_at - now))
        calls.append(now)
        return None

    def forget_idle(self) -> None:
        """Drop keys with no call inside the longest window (bounded memory)."""
        if not self.windows:
            return
        cutoff = self._clock() - self.windows[-1].seconds
        for key in [k for k, calls in self._calls.items() if not calls or calls[-1] <= cutoff]:
            del self._calls[key]


def rate_limited_payload(window: Window, retry_after_s: int) -> dict[str, Any]:
    return {
        "error": (
            f"{CODE_RATE_LIMITED}: more than {window.limit} calls to the SpecBox MCP in {window.span} "
            f"from this identity. Try again in {retry_after_s} s."
        ),
        "code": CODE_RATE_LIMITED,
        "limit": window.label,
        "retry_after_s": retry_after_s,
        "how_to": (
            "The hosted MCP serves people working on their boards. Poll less often, "
            "or read the whole board once (list_uc / get_board_status) instead of every UC."
        ),
    }


try:  # FastMCP is always present on the server; keep the module importable without it.
    from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
except ImportError:  # pragma: no cover
    Middleware = object  # type: ignore[assignment,misc]
    CallNext = Any  # type: ignore[assignment,misc]
    MiddlewareContext = Any  # type: ignore[assignment,misc]


class RateLimitMiddleware(Middleware):  # type: ignore[misc,valid-type]
    """Answers ``RATE_LIMITED`` instead of running a tool once an identity is over its limit."""

    _FORGET_EVERY = 1000

    def __init__(self, limiter: RateLimiter | None = None, *, remote_only: bool = True) -> None:
        self.limiter = limiter if limiter is not None else RateLimiter(limits_from_env())
        self._remote_only = remote_only
        self._seen = 0

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext) -> Any:  # type: ignore[valid-type]
        if not self.limiter.enabled:
            return await call_next(context)
        if self._remote_only:
            from ..transport import is_remote_transport

            if not is_remote_transport():
                return await call_next(context)

        ctx = context.fastmcp_context
        developer_id, _kind, _project = await identity_for_log(ctx)
        if developer_id:
            key = f"developer:{developer_id}"
        else:
            _client, remote, session_id = _request_facts(ctx)
            key = f"session:{session_id}" if session_id else f"address:{remote or 'unknown'}"

        self._seen += 1
        if self._seen % self._FORGET_EVERY == 0:
            self.limiter.forget_idle()

        verdict = self.limiter.check(key)
        if verdict is None:
            return await call_next(context)

        window, retry_after_s = verdict
        tool = str(getattr(context.message, "name", "") or "")
        logger.warning("rate_limited", key=key, tool=tool, limit=window.label, retry_after_s=retry_after_s)
        result = await envelope_result(context, tool, rate_limited_payload(window, retry_after_s))
        result.meta = {**(result.meta or {}), RESULT_CODE_META_KEY: CODE_RATE_LIMITED}
        return result
