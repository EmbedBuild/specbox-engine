"""Server transport detection (UC-3801).

Single source of truth for "is this MCP server running remotely?". The answer
is derived from how the *server process* was started (``MCP_TRANSPORT``, the
same variable ``server.server.main`` reads to pick the transport), never from a
client-side hint such as ``SPECBOX_ENGINE_MCP_URL``.

Why this matters: the FreeForm backend must never read or write the server's
filesystem when the server is remote — the "doc/tracking" a remote client
names lives on the client's machine, not on the VPS. Before UC-3801 the guard
keyed off ``SPECBOX_ENGINE_MCP_URL`` being present in the *server* environment,
which is a client setting nobody sets on the server, so the guard never fired
where it mattered (tester report, 2026-09-24).
"""

from __future__ import annotations

import os

#: Transports served over the network. ``stdio`` (the default) is local.
REMOTE_TRANSPORTS: frozenset[str] = frozenset({"http", "streamable-http", "sse"})

#: Environment variable that selects the transport at server start-up.
TRANSPORT_ENV = "MCP_TRANSPORT"


def transport_name() -> str:
    """Return the configured transport name, normalised (default ``stdio``)."""
    return (os.getenv(TRANSPORT_ENV) or "stdio").strip().lower() or "stdio"


def is_remote_transport() -> bool:
    """True when the server is reachable over the network (http/sse).

    A remote server has no access to the client's filesystem, so every
    filesystem-backed backend must operate in content-passing mode.
    """
    return transport_name() in REMOTE_TRANSPORTS
