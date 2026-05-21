"""Developer identity for the SpecBox NativeBackend — Frontier 1 (H2).

This module is the single chokepoint for *who* is calling the native backend
and *whether* they may touch a given project. It lives outside the SpecBackend
ABC (see :mod:`server.coordination`) so the storage abstraction stays clean.

Two frontiers, kept distinct
============================
- **Frontier 1 (here):** a developer presents a *token* on every native call.
  The token resolves to a ``developer_id``; that developer must be a member of
  the target project. Failures map to two stable codes:

    * :class:`UnauthenticatedError` → ``UNAUTHENTICATED`` (no/invalid token)
    * :class:`ForbiddenError`       → ``FORBIDDEN`` (valid token, wrong project)

- **Frontier 2 (server.db.pool):** the Postgres service credential. It lives
  ONLY in ``SPECBOX_NATIVE_DSN`` and is never seen here. This module receives a
  ready connection/pool; it never reads a DSN.

Token handling [AC-10, AC-11]
=============================
- Tokens are NEVER stored in clear. :func:`hash_token` computes the SHA-256 hex
  digest and that is what lands in ``developers.token_hash``.
- This module never logs the clear token. Callers (set_auth_token, tools) must
  likewise keep the token out of logs — only ``developer_id`` is safe to log.
- ``resolve_developer`` compares hashes, so a leaked log line can never be
  replayed as a credential.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


# ── Errors (stable codes for the MCP boundary) ───────────────────────


class UnauthenticatedError(Exception):
    """No token, or a token that resolves to no developer.

    Maps to ``UNAUTHENTICATED`` at the tool boundary. The message deliberately
    does NOT reveal whether a developer exists — it only says the token is not
    valid, so an attacker cannot enumerate developers [AC-15].
    """

    code = "UNAUTHENTICATED"

    def __init__(self, message: str = "No valid developer token presented.") -> None:
        super().__init__(message)


class ForbiddenError(Exception):
    """A valid token, but the developer is not a member of the target project.

    Maps to ``FORBIDDEN`` at the tool boundary [AC-13].
    """

    code = "FORBIDDEN"

    def __init__(self, developer_id: str, project_id: str) -> None:
        self.developer_id = developer_id
        self.project_id = project_id
        super().__init__(
            f"Developer {developer_id!r} is not a member of project {project_id!r}."
        )


# ── Developer record ─────────────────────────────────────────────────


@dataclass(frozen=True)
class Developer:
    """A resolved developer identity. NEVER carries the clear token."""

    developer_id: str
    display_name: str

    def to_public(self) -> dict[str, str]:
        """Serialize for a tool response (whoami)."""
        return {"developer_id": self.developer_id, "display_name": self.display_name}


# ── Token hashing [AC-10] ────────────────────────────────────────────


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a token.

    The clear token is never stored or returned — only this digest is. Empty or
    whitespace-only tokens are rejected up front so we never persist a hash that
    would match a "no token" call.
    """
    if not token or not token.strip():
        raise UnauthenticatedError("Empty token cannot be hashed.")
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


# ── Registration ─────────────────────────────────────────────────────


async def register_developer(
    conn: asyncpg.Connection | asyncpg.Pool,
    *,
    developer_id: str,
    display_name: str,
    token: str,
    meta: dict[str, Any] | None = None,
) -> Developer:
    """Create or update a developer. Stores ONLY the token hash [AC-10].

    Idempotent on ``developer_id``: re-registering updates display_name and
    rotates the token hash. The clear token is hashed here and discarded.
    """
    token_hash = hash_token(token)
    import json

    meta_json = json.dumps(meta or {}, ensure_ascii=False)

    async def _run(c: asyncpg.Connection) -> None:
        await c.execute(
            """
            INSERT INTO developers (developer_id, display_name, token_hash, meta)
            VALUES ($1, $2, $3, $4::jsonb)
            ON CONFLICT (developer_id) DO UPDATE
                SET display_name = EXCLUDED.display_name,
                    token_hash   = EXCLUDED.token_hash,
                    meta         = EXCLUDED.meta,
                    updated_at   = now()
            """,
            developer_id,
            display_name,
            token_hash,
            meta_json,
        )

    if isinstance(conn, asyncpg.Pool):
        async with conn.acquire() as c:
            await _run(c)
    else:
        await _run(conn)

    # Log the id only — never the token [AC-11].
    logger.info("developer_registered", developer_id=developer_id)
    return Developer(developer_id=developer_id, display_name=display_name)


async def add_project_member(
    conn: asyncpg.Connection | asyncpg.Pool,
    *,
    project_id: str,
    developer_id: str,
    role: str = "member",
) -> None:
    """Associate a developer with a project (authorization edge) [AC-13].

    Idempotent on ``(project_id, developer_id)``.
    """

    async def _run(c: asyncpg.Connection) -> None:
        await c.execute(
            """
            INSERT INTO project_members (project_id, developer_id, role)
            VALUES ($1, $2, $3)
            ON CONFLICT (project_id, developer_id) DO UPDATE
                SET role = EXCLUDED.role
            """,
            project_id,
            developer_id,
            role,
        )

    if isinstance(conn, asyncpg.Pool):
        async with conn.acquire() as c:
            await _run(c)
    else:
        await _run(conn)


# ── Authentication & authorization (Frontier 1) ──────────────────────


async def resolve_developer(
    conn: asyncpg.Connection | asyncpg.Pool,
    token: str | None,
) -> Developer:
    """Resolve a token to a :class:`Developer`, or raise UNAUTHENTICATED.

    Compares the token's SHA-256 hash against ``developers.token_hash``. A
    missing/empty token or one that matches no row raises
    :class:`UnauthenticatedError` — the error never discloses whether a
    developer exists [AC-12, AC-15].
    """
    if not token or not token.strip():
        raise UnauthenticatedError()
    token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()

    async def _run(c: asyncpg.Connection) -> asyncpg.Record | None:
        return await c.fetchrow(
            "SELECT developer_id, display_name FROM developers WHERE token_hash = $1",
            token_hash,
        )

    if isinstance(conn, asyncpg.Pool):
        async with conn.acquire() as c:
            row = await _run(c)
    else:
        row = await _run(conn)

    if row is None:
        # Do not log the token; do not reveal existence.
        raise UnauthenticatedError()
    return Developer(developer_id=row["developer_id"], display_name=row["display_name"])


async def authorize(
    conn: asyncpg.Connection | asyncpg.Pool,
    *,
    developer_id: str,
    project_id: str,
) -> None:
    """Raise FORBIDDEN unless the developer is a member of the project [AC-13]."""

    async def _run(c: asyncpg.Connection) -> Any:
        return await c.fetchval(
            "SELECT 1 FROM project_members WHERE project_id = $1 AND developer_id = $2",
            project_id,
            developer_id,
        )

    if isinstance(conn, asyncpg.Pool):
        async with conn.acquire() as c:
            ok = await _run(c)
    else:
        ok = await _run(conn)

    if not ok:
        raise ForbiddenError(developer_id, project_id)


async def authenticate_and_authorize(
    conn: asyncpg.Connection | asyncpg.Pool,
    *,
    token: str | None,
    project_id: str,
) -> Developer:
    """The full Frontier-1 gate: resolve the token, then check membership.

    Returns the resolved :class:`Developer` on success. Raises
    :class:`UnauthenticatedError` (no Postgres write happens beyond the lookup)
    or :class:`ForbiddenError`.
    """
    dev = await resolve_developer(conn, token)
    await authorize(conn, developer_id=dev.developer_id, project_id=project_id)
    return dev
