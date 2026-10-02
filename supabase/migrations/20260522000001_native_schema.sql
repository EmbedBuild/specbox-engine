-- 0001_native_schema.sql
-- SpecBox NativeBackend — multi-tenant Postgres schema (UC-102).
--
-- Scope: schema only. The SpecBackend ABC implementation, optimistic-version
-- increment logic, and dispatch wiring live in UC-101/UC-103 — NOT here.
--
-- Tenant isolation [AC-04, AC-05]: every spec table carries project_id (FK to
-- projects). All lookups are expected to filter by project_id.
--
-- Idempotency [AC-04]: this whole file is safe to re-apply on a populated DB.
-- Every statement uses IF NOT EXISTS (tables, indexes) — re-running raises no
-- error and mutates nothing.
--
-- Optimistic concurrency [AC-03]: user_stories / use_cases / acceptance_criteria
-- each carry a `version INTEGER NOT NULL DEFAULT 1`. Only the column is defined
-- here; the increment + stale-version check is UC-101 scope.
--
-- Column shapes mirror the backend-agnostic DTOs in server/spec_backend.py
-- (ItemDTO for US/UC, ChecklistItemDTO for AC). meta/labels/raw map to JSONB.

-- ── projects ─────────────────────────────────────────────────────────
-- One row per onboarded project (tenant root).
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
    id              TEXT PRIMARY KEY,                          -- e.g. 'US-01'
    project_id      TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    state           TEXT NOT NULL DEFAULT 'user_stories',      -- workflow state key
    labels          JSONB NOT NULL DEFAULT '[]'::jsonb,        -- list[str]
    priority        TEXT NOT NULL DEFAULT 'none',
    external_source TEXT NOT NULL DEFAULT '',
    external_id     TEXT NOT NULL DEFAULT '',
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
    version         INTEGER NOT NULL DEFAULT 1,                -- optimistic concurrency [AC-03]
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── use_cases (maps to ItemDTO, child of a US) ───────────────────────
CREATE TABLE IF NOT EXISTS use_cases (
    id              TEXT PRIMARY KEY,                          -- e.g. 'UC-101'
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
    version         INTEGER NOT NULL DEFAULT 1,                -- optimistic concurrency [AC-03]
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── acceptance_criteria (maps to ChecklistItemDTO, child of a UC) ────
CREATE TABLE IF NOT EXISTS acceptance_criteria (
    id          TEXT PRIMARY KEY,                              -- e.g. 'UC-101::AC-01'
    project_id  TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    uc_id       TEXT NOT NULL REFERENCES use_cases (id) ON DELETE CASCADE,
    ac_id       TEXT NOT NULL,                                 -- short id within UC, e.g. 'AC-01'
    text        TEXT NOT NULL,
    done        BOOLEAN NOT NULL DEFAULT false,
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
    version     INTEGER NOT NULL DEFAULT 1,                    -- optimistic concurrency [AC-03]
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Indexes on project_id for tenant isolation [AC-05] ───────────────
CREATE INDEX IF NOT EXISTS idx_user_stories_project_id        ON user_stories (project_id);
CREATE INDEX IF NOT EXISTS idx_use_cases_project_id           ON use_cases (project_id);
CREATE INDEX IF NOT EXISTS idx_use_cases_us_id                ON use_cases (us_id);
CREATE INDEX IF NOT EXISTS idx_acceptance_criteria_project_id ON acceptance_criteria (project_id);
CREATE INDEX IF NOT EXISTS idx_acceptance_criteria_uc_id      ON acceptance_criteria (uc_id);
