"""Content-passing result plumbing for FreeForm tools (UC-3801, builds on UC-660).

A remote MCP server cannot reach the client's ``doc/tracking/items.json``. The
content-passing contract is: the client sends the board as ``items_content``,
the server operates on an in-memory :class:`FreeformBackend`, and the tool
returns the mutated board under ``items_content`` so the client writes it back.

The seven original mutation tools (UC-660) wire that return by hand. This
module generalises the *return* half for every other tool so that each of them
only needs two mechanical changes — accept ``items_content`` and forward it to
``get_session_backend`` — and gets the "return the updated board" behaviour for
free:

* :func:`server.auth_gateway.get_session_backend` records the memory-mode
  backend it builds in a :class:`contextvars.ContextVar` scoped to the running
  task.
* :func:`returns_items_content` wraps the tool, resets that slot before the
  call and, if the caller passed ``items_content`` and the result is a dict
  without an ``items_content`` key, adds the backend's current board to it.

Read-only tools may also carry the decorator harmlessly: the board they return
is the one they were given.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from ..auth_gateway import consume_memory_backend, reset_memory_backend

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])

RESULT_KEY = "items_content"


def returns_items_content(fn: F) -> F:
    """Add the mutated ``items_content`` to a tool's dict result in memory mode.

    Transparent when the caller did not pass ``items_content`` (disk mode,
    Trello, Plane, Native) and when the tool already set the key itself.
    ``functools.wraps`` keeps the original signature visible to FastMCP, so
    the ``items_content`` parameter the tool declares is what the schema shows.
    """
    signature = inspect.signature(fn)

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            bound = signature.bind_partial(*args, **kwargs)
            items_content = bound.arguments.get(RESULT_KEY)
        except TypeError:
            items_content = kwargs.get(RESULT_KEY)

        reset_memory_backend()
        result = await fn(*args, **kwargs)
        if items_content is None:
            return result

        backend = consume_memory_backend()
        if backend is not None and isinstance(result, dict) and RESULT_KEY not in result:
            result[RESULT_KEY] = backend.get_items_content()
        return result

    return wrapper  # type: ignore[return-value]
