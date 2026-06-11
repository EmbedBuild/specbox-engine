-- 0017_organizations.sql
-- SpecBox NativeBackend — Organization tenancy layer (US-13 / UC-1301).
--
-- WHY: until now the tenant root was `project_id`. A SuperAdmin saw every
-- developer in the system because there was no grouping above the project. This
-- migration introduces the ORGANIZATION as the new tenant level ABOVE
-- `projects`: an org groups several projects, developers belong to orgs (N:N),
-- and isolation between orgs is strict. It is the foundation of the public SaaS
-- model (self-service signup creates the user's own org).
--
-- IDENTITY MODEL: N:N. A developer can belong to several organizations (their
-- own + ones they were invited to). That is why membership lives in a separate
-- table `organization_members`, mirroring the shape of `project_members`
-- (0002): composite PK (organization_id, developer_id), FKs ON DELETE CASCADE.
--
-- ANCHOR POINT: `projects.organization_id` is the single place tenancy hangs
-- from. Child tables (user_stories, use_cases, ...) inherit the org transitively
-- via their existing `project_id` FK — no per-table org column is added.
--
-- TWO-PASS NOT NULL: this migration adds `projects.organization_id` as NULLABLE.
-- The data backfill (0018) assigns every existing project to its org, and only
-- THEN a follow-up sets the column NOT NULL. Doing NOT NULL here would break
-- every INSERT into `projects` that runs between this migration and the backfill
-- (e.g. setup_board / provision_native_project), so the constraint is deferred.
--
-- ROLES: organization membership role is constrained to {org_admin, member} via
-- a CHECK, matching the VALID_PROJECT_ROLES discipline in
-- server/coordination/identity.py (the project-level analogue is project_admin /
-- member; org level is org_admin / member).
--
-- Idempotency [matches 0001/0009]: every statement uses IF NOT EXISTS or a
-- pg_constraint / information_schema catalog guard, so the whole file is safe to
-- re-apply on a populated DB. Wrapped in a single transaction by the runner.

-- ── organizations ────────────────────────────────────────────────────
-- One row per organization (tenant root above projects). `slug` is the
-- URL-safe, unique handle; `name` is the human display name. `created_by`
-- references the developer that created it (org_admin at creation time); kept
-- ON DELETE SET NULL so deleting a developer never deletes their org.
CREATE TABLE IF NOT EXISTS organizations (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    slug          TEXT NOT NULL,
    created_by    TEXT REFERENCES developers (developer_id) ON DELETE SET NULL,
    meta          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The slug must be unique across the whole instance — it is the public,
-- URL-safe identifier of the org.
CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_slug ON organizations (slug);

-- ── organization_members ─────────────────────────────────────────────
-- N:N edge between developers and organizations [UC-1301 AC-01]. A developer
-- may be a member of several orgs (their own + invited). Role is restricted to
-- {org_admin, member} by the CHECK below. project_members (0002) is the
-- analogous table one level down (developer ↔ project).
CREATE TABLE IF NOT EXISTS organization_members (
    organization_id  TEXT NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    developer_id     TEXT NOT NULL REFERENCES developers (developer_id) ON DELETE CASCADE,
    role             TEXT NOT NULL DEFAULT 'member',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, developer_id)
);

-- Reverse-lookup index: "which orgs does this developer belong to?" — the hot
-- path for the active-org selector and isolation filters (UC-1304/UC-1305).
CREATE INDEX IF NOT EXISTS idx_organization_members_developer_id
    ON organization_members (developer_id);

-- Role whitelist [UC-1301 AC-03]: only {org_admin, member}. Guarded so the
-- migration is idempotent (re-adding a named CHECK would otherwise error).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'organization_members_role_check'
    ) THEN
        ALTER TABLE organization_members
            ADD CONSTRAINT organization_members_role_check
            CHECK (role IN ('org_admin', 'member'));
    END IF;
END $$;

-- ── projects.organization_id ─────────────────────────────────────────
-- The anchor column [UC-1301 AC-02]. NULLABLE in this migration (two-pass NOT
-- NULL — see header). FK to organizations(id); ON DELETE RESTRICT so an org with
-- projects cannot be deleted out from under them by accident.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'projects'
          AND column_name  = 'organization_id'
    ) THEN
        ALTER TABLE projects ADD COLUMN organization_id TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'projects_organization_id_fkey'
    ) THEN
        ALTER TABLE projects
            ADD CONSTRAINT projects_organization_id_fkey
            FOREIGN KEY (organization_id)
            REFERENCES organizations (id) ON DELETE RESTRICT;
    END IF;
END $$;

-- Composite index for the org-scoped project listing — the hot path for
-- `GET /api/projects` once isolation filters by org (UC-1304).
CREATE INDEX IF NOT EXISTS idx_projects_organization_id
    ON projects (organization_id, project_id);
