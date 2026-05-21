-- 20260522000002_developers.sql
-- SpecBox NativeBackend — developer identity (H2: UC-201/202/203), ported to
-- the Supabase migration ledger in UC-402.
--
-- Mirrors server/db/migrations/0002_developers.sql verbatim. Identity stays
-- SpecBox-owned (token_hash), NOT Supabase Auth — independent of the DB host.
--
-- FRONTIER 1 [AC-10, AC-12, AC-13]: token authenticates; only the SHA-256 hash
-- is stored; authorization is project-scoped via project_members.
-- Idempotent (IF NOT EXISTS) [AC-29].

-- ── developers ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS developers (
    developer_id  TEXT PRIMARY KEY,
    display_name  TEXT NOT NULL,
    token_hash    TEXT NOT NULL,
    meta          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_developers_token_hash ON developers (token_hash);

-- ── project_members ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS project_members (
    project_id    TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    developer_id  TEXT NOT NULL REFERENCES developers (developer_id) ON DELETE CASCADE,
    role          TEXT NOT NULL DEFAULT 'member',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, developer_id)
);

CREATE INDEX IF NOT EXISTS idx_project_members_developer_id ON project_members (developer_id);
