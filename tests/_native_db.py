"""Shared native-DB test helpers (UC-405).

Centralises the DSN resolution + reachability probe used by the native test
modules (``test_native_schema``, ``test_native_backend_conformance``,
``test_native_dispatch``). Having one place means the Supabase TLS handling is
applied consistently: a probe that did a plain ``asyncpg.connect(dsn)`` would
fail the Supabase handshake (TLS required) and make the suite *skip* as if no
DB existed, even when Supabase is reachable — defeating AC-38.

The probe reuses the project's own SSL resolution (:func:`server.db.pool._resolve_ssl`)
so it matches exactly how ``init_pool`` will connect:

- Supabase DSN (``*.supabase.co`` / ``*.supabase.com``) → ``ssl="require"``.
- Local throwaway Postgres → plaintext.
- ``SPECBOX_NATIVE_SSL`` override honoured either way.

It runs in a dedicated, fully torn-down event loop so it never leaves a closed
loop as the asyncio default (which would poison the pool created later under
pytest-asyncio's own loop on Python 3.14).
"""

from __future__ import annotations

import asyncio
import os

import asyncpg

from server.db.pool import _resolve_ssl

#: Frontier 2: DSN is normally env-only. Tests honour an explicit override and
#: fall back to the documented dev DSN (docker-compose.dev.yml). To run against
#: Supabase, export SPECBOX_NATIVE_DSN with the Pooler transaction-mode URI.
_DEV_DSN = "postgresql://specbox:specbox_dev_only@localhost:55432/specbox_native"
DSN = os.environ.get("SPECBOX_NATIVE_DSN", _DEV_DSN)


def probe(dsn: str = DSN) -> None:
    """Confirm Postgres is reachable, TLS-aware, in a throwaway event loop.

    Raises whatever ``asyncpg`` raises when the DB is not reachable; callers
    turn that into a clean module-level skip.
    """
    ssl = _resolve_ssl(dsn)

    async def _connect() -> None:
        conn = await asyncio.wait_for(asyncpg.connect(dsn, ssl=ssl), timeout=5.0)
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_connect())
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def reachable() -> tuple[bool, str]:
    """Return ``(ok, skip_reason)`` for module-level skip guards."""
    try:
        probe(DSN)
        return True, ""
    except Exception as exc:  # noqa: BLE001 — any failure means "no DB", just skip
        target = "Supabase" if "supabase.co" in DSN or "supabase.com" in DSN else "dev Postgres"
        return False, (
            f"{target} not reachable ({exc!r}); export SPECBOX_NATIVE_DSN "
            "(Supabase Pooler transaction-mode URI) or run "
            "docker compose -f docker-compose.dev.yml up -d"
        )
