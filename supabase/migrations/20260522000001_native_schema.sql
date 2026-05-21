-- 20260522000001_native_schema.sql
-- SpecBox NativeBackend — multi-tenant Postgres schema (UC-102, ported to
-- Supabase migrations in UC-402).
--
-- This is the Supabase-ledger source of truth for the native spec tables.
-- It mirrors server/db/migrations/0001_native_schema.sql verbatim (the casero
-- runner stays for local dev / tests only — see server/db/migrate.py).
--
-- Tenant isolation [AC-04, AC-05]: every spec table carries project_id (FK to
-- projects). All lookups filter by project_id.
-- Idempotency [AC-04, AC-29]: every statement uses IF NOT EXISTS, so applying
-- this through the Supabase ledger twice is a no-op.
-- Optimistic concurrency [AC-03]: US/UC/AC each carry version INTEGER.
-- RLS is added in a later migration (UC-403) — schema only here.

-- ── projects ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    project_id    TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    backend_type  TEXT NOT NULL DEFAULT 'native',
    board_url     TEXT NOT NULL DEFAULT '',
    meta          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── user_stories (maps to ItemDTO) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS user_stories (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    state           TEXT NOT NULL DEFAULT 'user_stories',
    labels          JSONB NOT NULL DEFAULT '[]'::jsonb,
    priority        TEXT NOT NULL DEFAULT 'none',
    external_source TEXT NOT NULL DEFAULT '',
    external_id     TEXT NOT NULL DEFAULT '',
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── use_cases (maps to ItemDTO, child of a US) ───────────────────────
CREATE TABLE IF NOT EXISTS use_cases (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    us_id           TEXT REFERENCES user_stories (id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    state           TEXT NOT NULL DEFAULT 'backlog',
    labels          JSONB NOT NULL DEFAULT '[]'::jsonb,
    priority        TEXT NOT NULL DEFAULT 'none',
    external_source TEXT NOT NULL DEFAULT '',
    external_id     TEXT NOT NULL DEFAULT '',
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── acceptance_criteria (maps to ChecklistItemDTO, child of a UC) ────
CREATE TABLE IF NOT EXISTS acceptance_criteria (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    uc_id       TEXT NOT NULL REFERENCES use_cases (id) ON DELETE CASCADE,
    ac_id       TEXT NOT NULL,
    text        TEXT NOT NULL,
    done        BOOLEAN NOT NULL DEFAULT false,
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
    version     INTEGER NOT NULL DEFAULT 1,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Indexes on project_id for tenant isolation [AC-05] ───────────────
CREATE INDEX IF NOT EXISTS idx_user_stories_project_id        ON user_stories (project_id);
CREATE INDEX IF NOT EXISTS idx_use_cases_project_id           ON use_cases (project_id);
CREATE INDEX IF NOT EXISTS idx_use_cases_us_id                ON use_cases (us_id);
CREATE INDEX IF NOT EXISTS idx_acceptance_criteria_project_id ON acceptance_criteria (project_id);
CREATE INDEX IF NOT EXISTS idx_acceptance_criteria_uc_id      ON acceptance_criteria (uc_id);
