-- 0002_developers.sql
-- SpecBox NativeBackend — developer identity (H2: UC-201, UC-202, UC-203).
--
-- Scope: identity only. The claim tables (uc_claims, branch_registry) live in
-- the H3 migration 0003 — NOT here.
--
-- FRONTIER 1 [AC-10, AC-12, AC-13]: a developer authenticates with a token. The
-- token is NEVER stored in clear — only its SHA-256 hash lands in token_hash.
-- Authorization is project-scoped via project_members (a dev may only touch
-- projects it is a member of).
--
-- Idempotency [mirrors 0001]: every statement uses IF NOT EXISTS, so the whole
-- file is safe to re-apply on a populated DB.

-- ── developers ───────────────────────────────────────────────────────
-- One row per human developer. developer_id is stable and human-readable
-- (e.g. 'jesus', 'alice'); token_hash is the SHA-256 hex digest of the dev's
-- token. The clear token is never persisted [AC-10].
CREATE TABLE IF NOT EXISTS developers (
    developer_id  TEXT PRIMARY KEY,
    display_name  TEXT NOT NULL,
    token_hash    TEXT NOT NULL,
    meta          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A token resolves to exactly one developer. UNIQUE on token_hash makes the
-- token → developer lookup unambiguous and lets resolve_developer use an index.
CREATE UNIQUE INDEX IF NOT EXISTS idx_developers_token_hash ON developers (token_hash);

-- ── project_members ──────────────────────────────────────────────────
-- Authorization edge [AC-13]: a developer is associated with the projects it
-- may operate on. A native tool call to a project the dev is not a member of is
-- rejected with FORBIDDEN. (project_id is the tenant root from 0001.)
CREATE TABLE IF NOT EXISTS project_members (
    project_id    TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    developer_id  TEXT NOT NULL REFERENCES developers (developer_id) ON DELETE CASCADE,
    role          TEXT NOT NULL DEFAULT 'member',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, developer_id)
);

CREATE INDEX IF NOT EXISTS idx_project_members_developer_id ON project_members (developer_id);
