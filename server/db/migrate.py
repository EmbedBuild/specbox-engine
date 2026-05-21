"""Idempotent migration runner for the SpecBox NativeBackend (UC-102).

DEPRECATED FOR PRODUCTION (UC-402) [AC-31]
==========================================
Production runs on a managed Supabase Postgres, and the **source of truth for
the schema is the Supabase migration ledger** (``supabase/migrations/*.sql``,
applied via ``supabase db push`` / the ``apply_migration`` MCP tool and tracked
in ``supabase_migrations.schema_migrations``). Do NOT run this runner against
the production Supabase database — that would create a second, divergent source
of truth.

This runner is retained ONLY for **local dev and tests**: it lets the
conformance suite spin a throwaway Postgres (docker-compose.dev.yml) or a
Supabase branch DB up to the same schema without invoking the Supabase CLI. The
``server/db/migrations/*.sql`` files it reads are kept byte-for-byte in sync
with ``supabase/migrations/*.sql``.

Applies every ``*.sql`` file under a migrations directory in lexical order.
The migrations themselves are written to be re-appliable (CREATE TABLE/INDEX
IF NOT EXISTS), so :func:`apply_migrations` is safe to call repeatedly —
idempotency is a property of the SQL [AC-04, AC-29].

Accepts either an asyncpg ``Pool`` or a single ``Connection`` so callers and
tests can run migrations against whatever handle they hold.
"""

from __future__ import annotations

from pathlib import Path

import asyncpg

from .pool import MIGRATIONS_DIR


def _read_migrations(migrations_dir: Path) -> list[tuple[str, str]]:
    """Return ``(filename, sql)`` for every ``*.sql`` file, sorted by name."""
    if not migrations_dir.is_dir():
        raise FileNotFoundError(f"Migrations directory not found: {migrations_dir}")
    files = sorted(migrations_dir.glob("*.sql"), key=lambda p: p.name)
    return [(p.name, p.read_text(encoding="utf-8")) for p in files]


async def apply_migrations(
    pool_or_conn: asyncpg.Pool | asyncpg.Connection,
    migrations_dir: Path | str | None = None,
) -> list[str]:
    """Apply every ``*.sql`` migration in order. Safe to call twice [AC-04].

    Args:
        pool_or_conn: An asyncpg ``Pool`` or ``Connection``.
        migrations_dir: Directory of ``*.sql`` files. Defaults to the package
            ``migrations/`` directory.

    Returns:
        The list of migration filenames applied, in order.
    """
    directory = Path(migrations_dir) if migrations_dir is not None else MIGRATIONS_DIR
    migrations = _read_migrations(directory)

    async def _run(conn: asyncpg.Connection) -> None:
        for _name, sql in migrations:
            # Each file is wrapped in a transaction; idempotent DDL means a
            # re-run is a no-op rather than an error.
            async with conn.transaction():
                await conn.execute(sql)

    if isinstance(pool_or_conn, asyncpg.Connection):
        await _run(pool_or_conn)
    else:
        async with pool_or_conn.acquire() as conn:
            await _run(conn)

    return [name for name, _ in migrations]
