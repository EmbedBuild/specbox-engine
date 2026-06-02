"""Transport integrity helpers for batch ingestion (UC-681).

A single source of truth for the SHA-256 hashing used to verify (a) each chunk
of a fragmented ``items.json`` as it arrives, and (b) the reassembled blob
against the hash the client declared at ``start_migration_session``. Keeping the
encoding in one place means the chunk-check, the global pre-flight, and the E2E
test can never disagree about how a string is hashed.
"""

from __future__ import annotations

import hashlib


def sha256_hex(text: str) -> str:
    """Return the lowercase hex SHA-256 of ``text`` encoded as UTF-8.

    The client computes the same digest over each chunk (and over the whole
    ``items.json``) before transport; the server recomputes it on arrival to
    detect silent truncation/corruption — the exact failure the large-blob
    transport gap risked.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
