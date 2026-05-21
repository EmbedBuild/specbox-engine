"""asyncpg connection pool for the SpecBox NativeBackend (UC-102) [AC-02].

FRONTIER 2 RULE — database credential security
==============================================
The Postgres DSN (the "crown jewel" service credential) is read **ONLY** from
the environment variable ``SPECBOX_NATIVE_DSN``. It is NEVER read from the
per-session MCP config, never accepted as a tool argument, and never logged.
This module is the single chokepoint for opening the native DB connection, so
the env-only invariant is enforced here. Callers in UC-101/UC-103 obtain a
ready pool via :func:`get_pool` — they never see the DSN.

Lifecycle
=========
- :func:`init_pool` — explicit, idempotent. Creates the pool from the env DSN
  (or an override passed in by tests). Safe to call once at MCP startup.
- :func:`get_pool` — lazy: initialises on first access if not already done.
- :func:`close_pool` — graceful shutdown; safe to call when no pool exists.

Wiring into server.py / auth_gateway.py is intentionally out of scope for
UC-102.
"""

from __future__ import annotations

import os
from pathlib import Path

import asyncpg

#: Environment variable that holds the native Postgres DSN. Frontier 2: this is
#: the ONLY accepted source for the credential.
DSN_ENV_VAR = "SPECBOX_NATIVE_DSN"

#: Directory holding the ordered ``*.sql`` migrations.
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

#: Sane pool bounds for a single MCP process serving concurrent tool calls.
_MIN_POOL_SIZE = 2
_MAX_POOL_SIZE = 10

# Module-level singleton. asyncpg pools are safe to share across coroutines.
_pool: asyncpg.Pool | None = None


def _resolve_dsn(dsn: str | None) -> str:
    """Resolve the DSN, enforcing the env-only Frontier 2 rule.

    An explicit ``dsn`` is honoured only to let tests target a throwaway DB;
    production callers pass nothing and the value comes from the environment.
    """
    if dsn:
        return dsn
    env_dsn = os.environ.get(DSN_ENV_VAR)
    if not env_dsn:
        raise RuntimeError(
            f"Native DB DSN not configured. Set the {DSN_ENV_VAR} environment "
            "variable. The credential is never read from session config."
        )
    return env_dsn


async def init_pool(dsn: str | None = None) -> asyncpg.Pool:
    """Create (or return the existing) shared asyncpg pool. Idempotent.

    Args:
        dsn: Optional explicit DSN (tests only). When ``None``, the DSN is
            read from the ``SPECBOX_NATIVE_DSN`` environment variable.

    Returns:
        The shared :class:`asyncpg.Pool`.
    """
    global _pool
    if _pool is not None:
        return _pool
    _pool = await asyncpg.create_pool(
        _resolve_dsn(dsn),
        min_size=_MIN_POOL_SIZE,
        max_size=_MAX_POOL_SIZE,
    )
    return _pool


async def get_pool() -> asyncpg.Pool:
    """Return the shared pool, initialising it lazily on first access."""
    if _pool is None:
        return await init_pool()
    return _pool


async def close_pool() -> None:
    """Close the shared pool and reset the singleton. Safe if none exists."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
