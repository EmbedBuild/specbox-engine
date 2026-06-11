-- 0020_organization_id_nullable_again.sql
-- SpecBox NativeBackend — relax projects.organization_id back to NULLABLE.
--
-- WHY (layer correction): migration 0019 set `projects.organization_id` NOT
-- NULL to seal the org-tenancy anchor. That sealing was placed in the WRONG
-- LAYER. "Organization" is a concept of the SpecBox Manager / Cloud panel — it
-- is NOT part of the generic, open-source engine. The engine's `projects` table
-- is multi-tenant by `project_id` alone; a plain clone of the engine has no
-- organizations at all. Forcing NOT NULL here coupled the generic engine to a
-- manager-only abstraction and broke ~99 tests that legitimately create
-- projects without an org (which is how the engine works on its own).
--
-- WHERE THE INVARIANT LIVES NOW: "every project belongs to an organization" is
-- enforced by the PANEL, not by the engine schema:
--   * `provision_native_project` resolves and writes the org on project
--     creation (explicit org → existing project's org → the creator's org);
--   * the UC-1304 isolation filters scope every tenant query by org — a project
--     with a NULL org is simply invisible to every tenant (only a platform
--     SuperAdmin sees it), a safe degradation rather than a hard failure.
--
-- This migration does NOT touch data: existing rows keep their org. It only
-- removes the column-level NOT NULL constraint that 0019 added.
--
-- Idempotency [matches 0017/0019]: guarded by an information_schema check on
-- `is_nullable`. Re-applying on a DB where the column is already NULLABLE is a
-- no-op. Wrapped in a single transaction by the runner.
--
-- Mirrored byte-for-byte in supabase/migrations/20260611000020_organization_id_nullable_again.sql.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'projects'
          AND column_name  = 'organization_id'
          AND is_nullable  = 'NO'
    ) THEN
        ALTER TABLE projects ALTER COLUMN organization_id DROP NOT NULL;
    END IF;
END $$;
