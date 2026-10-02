-- 0003_claims.sql
-- SpecBox NativeBackend — UC claims + branch registry (H3: UC-301..304).
--
-- Builds on 0001 (projects/specs) and 0002 (developers). Coordination tables
-- for multi-developer work: who is working on which UC, and which branch maps
-- to which UC, so two devs never collide.
--
-- Idempotent (IF NOT EXISTS), like the prior migrations.

-- ── uc_claims ────────────────────────────────────────────────────────
-- Mutual exclusion on a UC [AC-16]: at most one active claim per UC within a
-- project. AC-16 specifies UNIQUE(uc_id); in a multi-tenant DB the same uc_id
-- string ("UC-101") exists across projects, so the exclusion key is the
-- (project_id, uc_id) pair — that is what "this UC" means here. Two concurrent
-- claim_uc on the same (project_id, uc_id) → exactly one INSERT wins, the other
-- hits the unique violation and is rejected with ALREADY_CLAIMED.
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
-- Branch ↔ UC mapping [AC-23]: a branch name is unique per project. Trying to
-- register a branch name already used (for any UC, by any dev) is rejected, so
-- two devs cannot collide on a branch. The suggested naming feature/{uc_id}-...
-- is computed in branches.py, not stored here.
CREATE TABLE IF NOT EXISTS branch_registry (
    project_id    TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    branch        TEXT NOT NULL,
    uc_id         TEXT NOT NULL,
    developer_id  TEXT NOT NULL REFERENCES developers (developer_id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, branch)
);

CREATE INDEX IF NOT EXISTS idx_branch_registry_uc_id ON branch_registry (project_id, uc_id);
