"""SpecBox NativeBackend database layer (UC-102).

This package owns the native Postgres infrastructure:

- ``pool``   — asyncpg connection pool (lazy init, env-only DSN).
- ``migrate`` — programmatic, idempotent migration runner.
- ``migrations/`` — ordered ``*.sql`` files (schema source of truth).

Scope note (UC-102): this layer provides schema + pool + migration runner
ONLY. The SpecBackend ABC implementation and dispatch wiring belong to
UC-101 / UC-103.
"""

from __future__ import annotations

from .migrate import apply_migrations
from .pool import MIGRATIONS_DIR, close_pool, get_pool, init_pool

__all__ = [
    "MIGRATIONS_DIR",
    "apply_migrations",
    "close_pool",
    "get_pool",
    "init_pool",
]
