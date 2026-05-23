-- 0005_mcp_tokens.sql
-- SpecBox NativeBackend — MCP token store + token_hash move (UC-501 AC-02, AC-03).
--
-- Purpose:
--   1. [AC-02] Introduce ``mcp_tokens`` so a developer can hold N tokens
--      (rotation, revocation, multi-host) instead of the single ``token_hash``
--      column on ``developers`` (introduced in 0002). Each token is identified
--      by ``token_id`` (an opaque short id surfaced to the user) and matched
--      via a UNIQUE ``token_hash`` (SHA-256 hex of the clear token, NEVER the
--      clear token itself — same rule as 0002).
--   2. [AC-03] Atomically drop ``developers.token_hash`` and its unique index
--      ``idx_developers_token_hash``. Token storage moves to ``mcp_tokens``
--      entirely. Because UC-501 ships with no production Native data, no data
--      migration is required — this is a hard cut. The DROP order
--      (``DROP INDEX`` then ``ALTER TABLE ... DROP COLUMN``) is the safe one;
--      ``DROP COLUMN`` would also drop the index implicitly, but being
--      explicit makes the intent clear in code review.
--
-- ``github_user_id`` is an OPTIONAL link from a token to the GitHub identity
-- that minted it (e.g. via a GitHub OAuth flow). ON DELETE SET NULL because if
-- the GitHub identity is unlinked we keep the token row for audit; the
-- ``developer_id`` link still anchors the token to the human owner.
--
-- Idempotent (IF NOT EXISTS / IF EXISTS), safe to re-apply.

-- ── mcp_tokens ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mcp_tokens (
    token_id        TEXT PRIMARY KEY,
    developer_id    TEXT NOT NULL REFERENCES developers (developer_id) ON DELETE CASCADE,
    github_user_id  BIGINT NULL REFERENCES github_identities (github_user_id) ON DELETE SET NULL,
    token_hash      TEXT NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at    TIMESTAMPTZ NULL,
    revoked_at      TIMESTAMPTZ NULL
);

-- Hot path: token → row lookup during ``resolve_developer``. The UNIQUE on the
-- column already backs an index, but we name it explicitly so the identity
-- resolver and any future ANALYZE output reference a stable name. IF NOT
-- EXISTS makes it a no-op when the implicit unique index already covers it.
CREATE UNIQUE INDEX IF NOT EXISTS idx_mcp_tokens_token_hash
    ON mcp_tokens (token_hash);

-- Reverse lookup: "which tokens does this dev have?" Used by rotation/list
-- operations in UC-504. Not unique.
CREATE INDEX IF NOT EXISTS idx_mcp_tokens_developer_id
    ON mcp_tokens (developer_id);

-- ── [AC-03] Drop legacy ``developers.token_hash`` column + its index ─
-- Token storage moved to mcp_tokens above. Hard cut — UC-501 ships with no
-- production Native data so no backfill is needed. Drop the index FIRST, then
-- the column. Both statements are IF EXISTS so re-runs are no-ops.
DROP INDEX IF EXISTS idx_developers_token_hash;
ALTER TABLE developers DROP COLUMN IF EXISTS token_hash;
