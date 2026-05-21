-- 20260522000003_claims.sql
-- SpecBox NativeBackend — UC claims + branch registry (H3: UC-301..304),
-- ported to the Supabase migration ledger in UC-402.
--
-- Mirrors server/db/migrations/0003_claims.sql verbatim. Builds on the schema
-- and developers migrations. Idempotent (IF NOT EXISTS) [AC-29].

-- ── uc_claims ────────────────────────────────────────────────────────
-- Mutual exclusion on a UC [AC-16]: at most one active claim per (project_id,
-- uc_id). Two concurrent claims on the same pair → exactly one INSERT wins.
CREATE TABLE IF NOT EXISTS uc_claims (
    project_id    TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    uc_id         TEXT NOT NULL,
    developer_id  TEXT NOT NULL REFERENCES developers (developer_id) ON DELETE CASCADE,
    branch        TEXT NOT NULL DEFAULT '',
    claimed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    meta          JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (project_id, uc_id)
);

CREATE INDEX IF NOT EXISTS idx_uc_claims_developer_id ON uc_claims (developer_id);

-- ── branch_registry ──────────────────────────────────────────────────
-- Branch ↔ UC mapping [AC-23]: a branch name is unique per project.
CREATE TABLE IF NOT EXISTS branch_registry (
    project_id    TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    branch        TEXT NOT NULL,
    uc_id         TEXT NOT NULL,
    developer_id  TEXT NOT NULL REFERENCES developers (developer_id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, branch)
);

CREATE INDEX IF NOT EXISTS idx_branch_registry_uc_id ON branch_registry (project_id, uc_id);
