"""asyncpg connection pool for the SpecBox NativeBackend (UC-102, UC-401) [AC-02].

FRONTIER 2 RULE — database credential security
==============================================
The Postgres DSN (the "crown jewel" service credential) is read **ONLY** from
the environment variable ``SPECBOX_NATIVE_DSN``. It is NEVER read from the
per-session MCP config, never accepted as a tool argument, and never logged.
This module is the single chokepoint for opening the native DB connection, so
the env-only invariant is enforced here. Callers in UC-101/UC-103 obtain a
ready pool via :func:`get_pool` — they never see the DSN. [AC-26]

Supabase Pooler (UC-401)
========================
The native store is a managed Supabase Postgres reached through the Supabase
**Pooler in transaction mode** (host ``...pooler.supabase.com``, port 6543).
That pooler is PgBouncer in transaction pooling mode, which does **not** keep
server-side state between statements. asyncpg, by default, uses server-side
prepared statements, so a second call reusing a cached statement name explodes
with ``DuplicatePreparedStatementError`` ("prepared statement ... already
exists"). We disable the statement cache (``statement_cache_size=0``) so every
statement is sent unprepared — the documented asyncpg + PgBouncer
transaction-mode combination. [AC-24]

TLS is required by Supabase: connections that do not negotiate SSL are
refused. We pass ``ssl="require"`` whenever the DSN targets Supabase (or when
``SPECBOX_NATIVE_SSL`` is set), so the env-only DSN does not need to carry an
``sslmode`` query param to be safe. A throwaway local Postgres (tests / dev
docker) keeps plaintext. [AC-25]

Lifecycle
=========
- :func:`init_pool` — explicit, idempotent. Creates the pool from the env DSN
  (or an override passed in by tests). Safe to call once at MCP startup.
- :func:`get_pool` — lazy: initialises on first access if not already done.
- :func:`close_pool` — graceful shutdown; safe to call when no pool exists.
"""

from __future__ import annotations

import os
from pathlib import Path

import asyncpg

#: Environment variable that holds the native Postgres DSN. Frontier 2: this is
#: the ONLY accepted source for the credential.
DSN_ENV_VAR = "SPECBOX_NATIVE_DSN"

#: Optional override to force SSL on/off regardless of the DSN host. Accepts
#: ``require``/``1``/``true`` (force on) or ``disable``/``0``/``false`` (off).
#: When unset, SSL is auto-detected from the DSN host (Supabase → on).
SSL_ENV_VAR = "SPECBOX_NATIVE_SSL"

#: Directory holding the ordered ``*.sql`` migrations. UC-402 makes the Supabase
#: migration ledger the production source of truth; this runner stays for local
#: dev / tests only (see server/db/migrate.py).
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

#: Sane pool bounds for a single MCP process serving concurrent tool calls.
#: The Supabase Pooler caps concurrent client connections per project; keeping
#: max_size modest leaves headroom for other clients sharing the pooler. [AC-27]
_MIN_POOL_SIZE = 2
_MAX_POOL_SIZE = 10

#: Hard ceiling for ``max_size``. The Supabase free/small-plan pooler allows a
#: limited number of client connections; opening a pool larger than the pooler
#: will accept fails opaquely at acquire time. We surface a clear error instead
#: when a caller asks for an obviously-too-large pool. [AC-27]
_MAX_POOL_SIZE_CEILING = int(os.environ.get("SPECBOX_NATIVE_POOL_CEILING", "15"))

#: Host substrings that mark a Supabase-managed Postgres (Pooler or direct).
_SUPABASE_HOST_MARKERS = (".supabase.co", ".supabase.com")

# Module-level singleton. asyncpg pools are safe to share across coroutines.
_pool: asyncpg.Pool | None = None


def _resolve_dsn(dsn: str | None) -> str:
    """Resolve the DSN, enforcing the env-only Frontier 2 rule. [AC-26]

    An explicit ``dsn`` is honoured only to let tests target a throwaway DB;
    production callers pass nothing and the value comes from the environment.
    The resolved DSN is never logged.
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


def _is_supabase_dsn(dsn: str) -> bool:
    """True when the DSN host looks like a Supabase-managed Postgres."""
    # Cheap, allocation-free host sniff — avoids parsing (and logging) the DSN.
    return any(marker in dsn for marker in _SUPABASE_HOST_MARKERS)


def _resolve_ssl(dsn: str) -> str | bool:
    """Decide the ``ssl`` kwarg for ``create_pool``. [AC-25]

    - ``SPECBOX_NATIVE_SSL`` explicit override wins.
    - Otherwise Supabase hosts get ``"require"`` (TLS mandatory); a local /
      throwaway Postgres stays plaintext (``False``) so dev & tests work.

    Returns ``"require"`` or ``False`` — never ``True`` (which would also
    verify the cert; ``"require"`` matches libpq ``sslmode=require`` semantics).
    """
    override = os.environ.get(SSL_ENV_VAR, "").strip().lower()
    if override in ("require", "1", "true", "yes", "on"):
        return "require"
    if override in ("disable", "0", "false", "no", "off"):
        return False
    return "require" if _is_supabase_dsn(dsn) else False


def _validate_max_size(max_size: int) -> None:
    """Reject an obviously-oversized pool with a clear, actionable error. [AC-27]

    A pool larger than the Supabase Pooler accepts otherwise fails at first
    acquire with an opaque timeout. Failing fast at init names the ceiling.
    """
    if max_size > _MAX_POOL_SIZE_CEILING:
        raise RuntimeError(
            f"Native pool max_size={max_size} exceeds the configured ceiling "
            f"{_MAX_POOL_SIZE_CEILING}. The Supabase Pooler caps concurrent "
            "client connections per project; lower max_size or raise "
            "SPECBOX_NATIVE_POOL_CEILING to match your plan's pooler limit."
        )


async def init_pool(
    dsn: str | None = None,
    *,
    min_size: int = _MIN_POOL_SIZE,
    max_size: int = _MAX_POOL_SIZE,
) -> asyncpg.Pool:
    """Create (or return the existing) shared asyncpg pool. Idempotent.

    Args:
        dsn: Optional explicit DSN (tests only). When ``None``, the DSN is
            read from the ``SPECBOX_NATIVE_DSN`` environment variable. [AC-26]
        min_size / max_size: Pool bounds. ``max_size`` is validated against the
            pooler ceiling. [AC-27]

    Returns:
        The shared :class:`asyncpg.Pool`.
    """
    global _pool
    if _pool is not None:
        return _pool
    _validate_max_size(max_size)
    resolved = _resolve_dsn(dsn)
    _pool = await asyncpg.create_pool(
        resolved,
        min_size=min_size,
        max_size=max_size,
        # PgBouncer transaction mode is incompatible with server-side prepared
        # statements — disable the cache so asyncpg sends every query
        # unprepared. [AC-24]
        statement_cache_size=0,
        # TLS required by Supabase; plaintext for a local throwaway DB. [AC-25]
        ssl=_resolve_ssl(resolved),
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
