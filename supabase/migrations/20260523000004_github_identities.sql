-- 0004_github_identities.sql
-- SpecBox NativeBackend — GitHub identity linkage (UC-501 AC-01).
--
-- Purpose: bind a GitHub user (numeric, stable) to a SpecBox developer. The
-- GitHub login is mutable (users rename); the numeric ``github_user_id`` is
-- not, so it is the natural primary key. The relation is 1:1 today (one
-- developer per GitHub user), enforced by ``github_user_id`` being a PK and by
-- ``developer_id`` having an FK to ``developers`` with ON DELETE CASCADE — if
-- the developer row is removed, the linkage row goes with it.
--
-- This migration is the first of three (0004/0005/0006) that compose UC-501
-- "Native Security Schema". 0005 introduces ``mcp_tokens`` and references
-- ``github_user_id`` here via FK ON DELETE SET NULL.
--
-- Idempotent (IF NOT EXISTS), like every prior migration. Safe to re-apply.

-- ── github_identities ────────────────────────────────────────────────
-- One row per linked GitHub account. ``github_user_id`` is GitHub's numeric
-- account id (BIGINT — fits well beyond INT4). ``github_login`` is captured
-- for human display only; it must not be used as a lookup key (GitHub allows
-- rename). ``linked_at`` is the moment the identity was attached, for audit.
CREATE TABLE IF NOT EXISTS github_identities (
    github_user_id  BIGINT PRIMARY KEY,
    github_login    TEXT NOT NULL,
    developer_id    TEXT NOT NULL REFERENCES developers (developer_id) ON DELETE CASCADE,
    linked_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Reverse lookup: "which GitHub identities does this dev have?" Used by the
-- identity resolver in UC-504. Not unique — leaves room for a future "one dev,
-- multiple GitHub accounts" without a destructive migration.
CREATE INDEX IF NOT EXISTS idx_github_identities_developer_id
    ON github_identities (developer_id);
