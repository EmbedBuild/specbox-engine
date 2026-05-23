"""Developer identity for the SpecBox NativeBackend — Frontier 1 (H2 + UC-504).

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

Token handling [AC-10, AC-11, AC-17, AC-18]
===========================================
- Tokens are NEVER stored in clear. :func:`hash_token` computes the SHA-256 hex
  digest and that is what lands in ``mcp_tokens.token_hash`` (UC-501 moved
  token storage out of ``developers`` — see migration 0005).
- :func:`register_developer` is now identity-only: it inserts/updates the
  ``developers`` row and **does not** take a token (AC-18). Tokens are minted
  separately via :func:`register_mcp_token`, which is an internal helper (not
  exposed as an MCP tool) used by fixtures and the future admin panel.
- :func:`resolve_developer` joins ``mcp_tokens`` against ``developers``
  filtering ``revoked_at IS NULL`` (AC-17): revoked tokens map to UNAUTHENTICATED.
- This module never logs the clear token. Callers (set_auth_token, tools) must
  likewise keep the token out of logs — only ``developer_id`` is safe to log.
"""

from __future__ import annotations

import hashlib
import json
import uuid
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
        super().__init__(f"Developer {developer_id!r} is not a member of project {project_id!r}.")


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
    meta: dict[str, Any] | None = None,
) -> Developer:
    """Create or update a developer row [AC-18].

    Identity-only: this no longer takes a token. Token storage moved to
    ``mcp_tokens`` in UC-501 (migration 0005). Callers that need to mint a
    token must invoke :func:`register_mcp_token` separately.

    Idempotent on ``developer_id``: re-registering updates ``display_name``
    and ``meta`` but leaves any existing ``mcp_tokens`` rows untouched.
    """
    meta_json = json.dumps(meta or {}, ensure_ascii=False)

    async def _run(c: asyncpg.Connection) -> None:
        await c.execute(
            """
            INSERT INTO developers (developer_id, display_name, meta)
            VALUES ($1, $2, $3::jsonb)
            ON CONFLICT (developer_id) DO UPDATE
                SET display_name = EXCLUDED.display_name,
                    meta         = EXCLUDED.meta,
                    updated_at   = now()
            """,
            developer_id,
            display_name,
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


async def register_mcp_token(
    conn: asyncpg.Connection | asyncpg.Pool,
    *,
    developer_id: str,
    token: str,
    token_id: str | None = None,
    github_user_id: int | None = None,
) -> str:
    """Mint an ``mcp_tokens`` row for an existing developer.

    Internal helper (NOT exposed as an MCP tool). Used by:
    - tests / fixtures that need a developer + an active token,
    - :func:`server.migration.native_handling.seed_native_identity`,
    - the future admin panel that will issue tokens for new developers.

    The clear ``token`` is hashed with SHA-256 and discarded immediately. Only
    the hash is persisted (UC-501 design — see :mod:`server.db.migrations`
    ``0005_mcp_tokens.sql``). The returned ``token_id`` is opaque and safe to
    log; the clear token is never logged.

    Args:
        conn: an asyncpg connection or pool.
        developer_id: the owning developer (must already exist in ``developers``).
        token: the clear token. Hashed and discarded.
        token_id: optional caller-supplied id (e.g. for deterministic tests).
            When ``None``, a fresh ``spec_<24hex>`` id is generated.
        github_user_id: optional link to the GitHub identity that minted the
            token (UC-502). NULL when the token comes from another flow.

    Returns:
        The ``token_id`` that was persisted.

    Raises:
        UnauthenticatedError: when ``token`` is empty / whitespace.
    """
    token_hash = hash_token(token)
    tid = token_id or f"spec_{uuid.uuid4().hex[:24]}"

    # Idempotent on token_hash: re-registering the SAME clear token for the
    # same developer is a no-op and returns the existing token_id. This is
    # what callers like ``seed_native_identity`` rely on (the same migration
    # run twice must not raise UNIQUE violations). A different developer
    # presenting the same clear token would also collide here — that is a
    # security property of the SHA-256 mapping, not a bug.
    async def _run(c: asyncpg.Connection) -> str:
        row = await c.fetchrow(
            """
            INSERT INTO mcp_tokens (token_id, developer_id, github_user_id, token_hash)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (token_hash) DO UPDATE
                SET token_hash = EXCLUDED.token_hash
            RETURNING token_id
            """,
            tid,
            developer_id,
            github_user_id,
            token_hash,
        )
        # ON CONFLICT DO UPDATE always returns the row (existing or new) — the
        # no-op SET is the canonical Postgres pattern for "upsert returning id".
        return row["token_id"] if row else tid

    if isinstance(conn, asyncpg.Pool):
        async with conn.acquire() as c:
            tid = await _run(c)
    else:
        tid = await _run(conn)

    # Log the opaque id only — never the clear token [AC-11].
    logger.info(
        "mcp_token_registered",
        token_id=tid,
        developer_id=developer_id,
        github_user_id=github_user_id,
    )
    return tid


async def revoke_mcp_token(
    conn: asyncpg.Connection | asyncpg.Pool,
    *,
    token_id: str,
) -> bool:
    """Mark an ``mcp_tokens`` row as revoked (sets ``revoked_at = now()``).

    Internal helper (NOT exposed as an MCP tool). Used by tests and the future
    admin panel. After revocation, :func:`resolve_developer` no longer matches
    the token — its hash is still in the DB but the ``revoked_at IS NULL``
    filter excludes it [AC-17].

    Returns:
        ``True`` if a row was updated (token existed and was active);
        ``False`` if the token does not exist or was already revoked.
    """

    async def _run(c: asyncpg.Connection) -> Any:
        return await c.fetchval(
            """
            UPDATE mcp_tokens
               SET revoked_at = now()
             WHERE token_id = $1
               AND revoked_at IS NULL
            RETURNING 1
            """,
            token_id,
        )

    if isinstance(conn, asyncpg.Pool):
        async with conn.acquire() as c:
            result = await _run(c)
    else:
        result = await _run(conn)

    revoked = result is not None
    logger.info("mcp_token_revocation", token_id=token_id, revoked=revoked)
    return revoked


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
    """Resolve a token to a :class:`Developer`, or raise UNAUTHENTICATED [AC-17].

    Joins ``mcp_tokens`` against ``developers`` filtering ``revoked_at IS NULL``:
    a revoked token, an unknown hash, or a missing/empty token all map to
    :class:`UnauthenticatedError` — the error never discloses whether a
    developer exists [AC-12, AC-15].
    """
    if not token or not token.strip():
        raise UnauthenticatedError()
    token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()

    async def _run(c: asyncpg.Connection) -> asyncpg.Record | None:
        return await c.fetchrow(
            """
            SELECT d.developer_id, d.display_name
              FROM mcp_tokens t
              JOIN developers d ON d.developer_id = t.developer_id
             WHERE t.token_hash = $1
               AND t.revoked_at IS NULL
            """,
            token_hash,
        )

    if isinstance(conn, asyncpg.Pool):
        async with conn.acquire() as c:
            row = await _run(c)
    else:
        row = await _run(conn)

    if row is None:
        # Do not log the token; do not reveal existence (or revocation status).
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
