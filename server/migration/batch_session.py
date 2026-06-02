"""Server-side migration session + chunk staging (UC-680, UC-681).

The large-source transport gap (v6.9.2): ``switch_project_backend`` with
``source_type='freeform'`` took the whole ``items.json`` as one ``source_content``
string, and a real board (133 KB / hundreds of items) does not fit reliably in a
single tool parameter — risking silent truncation. This module is the transport
fix: a multi-call **migration session** where the client sends the source in
small, individually-verifiable chunks that the server accumulates in an ephemeral
in-memory staging area until a deferred, atomic commit (UC-682).

Design decisions (from discovery):
  * Staging is **ephemeral** (TTL). A session that is never committed simply
    expires; the client restarts ``start → append → commit`` from scratch. There
    is NO resume — the commit is the only point that touches Postgres, so a
    half-sent session leaves nothing to reconcile.
  * Every chunk is hash-verified on arrival (UC-681); the reassembled blob is
    hash + count verified before any write (UC-682). Corruption is caught in
    transport, not mid-write.

The store holds NO database connection and performs NO I/O — identity validation
and the atomic write live in the tool layer (``server/tools/migration.py``) and
``NativeBackend.ingest_atomic`` respectively. This keeps the staging unit-testable
without Postgres.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

from .integrity import sha256_hex

#: Default time-to-live for an open session, in seconds. A session older than
#: this is pruned and treated as not-found (the client restarts cleanly).
DEFAULT_SESSION_TTL_SECONDS = 600  # 10 min — generous for a multi-chunk upload.


@dataclass
class MigrationSession:
    """An open batch-migration session accumulating chunks for one target.

    The session is bound to the authenticated developer and the target project
    (tenant) at ``start``; appends and the commit re-check that the caller is the
    same owner so a leaked ``session_id`` cannot be driven by another developer.
    """

    session_id: str
    developer_id: str
    target_project_id: str
    source_type: str
    declared_items: int
    declared_bytes: int
    source_sha256: str
    chunks_expected: int
    created_at: float
    expires_at: float
    chunks: dict[int, str] = field(default_factory=dict)

    @property
    def chunks_received(self) -> int:
        return len(self.chunks)

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at

    def reassemble(self) -> str:
        """Concatenate the staged chunks in ascending index order.

        Caller is responsible for verifying completeness/hash first; this only
        joins what is present.
        """
        return "".join(self.chunks[i] for i in sorted(self.chunks))


class SessionStore:
    """In-memory registry of open migration sessions, keyed by ``session_id``.

    Pure and synchronous — no DB, no async. ``time_fn`` is injectable so tests
    can drive TTL expiry deterministically without sleeping.
    """

    def __init__(
        self,
        *,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        time_fn: Callable[[], float] = time.monotonic,
        id_fn: Callable[[], str] | None = None,
    ) -> None:
        self._ttl = ttl_seconds
        self._now = time_fn
        self._id = id_fn or (lambda: uuid.uuid4().hex)
        self._sessions: dict[str, MigrationSession] = {}

    # ── UC-680: open a session ───────────────────────────────────────
    def open(
        self,
        *,
        developer_id: str,
        target_project_id: str,
        source_type: str,
        declared_items: int,
        declared_bytes: int,
        source_sha256: str,
        chunk_count: int,
    ) -> MigrationSession:
        """Create and register a new open session; returns it.

        Does NOT validate identity (the tool layer does that before calling) and
        does NOT touch Postgres — opening a session never writes spec rows.
        """
        self._prune_expired()
        now = self._now()
        session = MigrationSession(
            session_id=self._id(),
            developer_id=developer_id,
            target_project_id=target_project_id,
            source_type=source_type,
            declared_items=declared_items,
            declared_bytes=declared_bytes,
            source_sha256=source_sha256,
            chunks_expected=chunk_count,
            created_at=now,
            expires_at=now + self._ttl,
        )
        self._sessions[session.session_id] = session
        return session

    # ── UC-681: accumulate a chunk ───────────────────────────────────
    def append_chunk(
        self,
        *,
        session_id: str,
        chunk_index: int,
        chunk_data: str,
        chunk_sha256: str,
    ) -> dict[str, object]:
        """Verify and stage one chunk; return an envelope dict (never raises).

        Status values:
          * ``SESSION_NOT_FOUND`` — unknown / expired / already-closed session.
          * ``CHUNK_HASH_MISMATCH`` — computed digest != declared; not staged.
          * ``DUPLICATE_CHUNK_INDEX`` — index already present; not overwritten.
          * ``accepted`` — staged; reports ``chunks_received`` / ``chunks_expected``.
        """
        session = self._get_live(session_id)
        if session is None:
            return {"status": "SESSION_NOT_FOUND", "session_id": session_id}

        actual = sha256_hex(chunk_data)
        if actual != chunk_sha256:
            return {
                "status": "CHUNK_HASH_MISMATCH",
                "chunk_index": chunk_index,
                "expected": chunk_sha256,
                "actual": actual,
            }

        if chunk_index in session.chunks:
            return {"status": "DUPLICATE_CHUNK_INDEX", "chunk_index": chunk_index}

        session.chunks[chunk_index] = chunk_data
        return {
            "status": "accepted",
            "chunk_index": chunk_index,
            "chunks_received": session.chunks_received,
            "chunks_expected": session.chunks_expected,
        }

    # ── lookup / lifecycle ───────────────────────────────────────────
    def get(self, session_id: str) -> MigrationSession | None:
        """Return a live session (pruning if expired) or ``None``."""
        return self._get_live(session_id)

    def close(self, session_id: str) -> None:
        """Remove a session from the store (idempotent). Frees the staging."""
        self._sessions.pop(session_id, None)

    def _get_live(self, session_id: str) -> MigrationSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.is_expired(self._now()):
            # Lazily evict an expired session — it reads as not-found.
            self._sessions.pop(session_id, None)
            return None
        return session

    def _prune_expired(self) -> None:
        now = self._now()
        expired = [sid for sid, s in self._sessions.items() if s.is_expired(now)]
        for sid in expired:
            self._sessions.pop(sid, None)


#: Process-wide store shared by the batch-ingestion tools. A single MCP server
#: process owns its sessions; if it restarts mid-session the staging is lost and
#: the client restarts cleanly (ephemeral by design).
_STORE = SessionStore()


def get_session_store() -> SessionStore:
    """Return the process-wide session store (test seam: monkeypatch this)."""
    return _STORE
