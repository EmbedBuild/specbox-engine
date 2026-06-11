-- 0019_organization_id_not_null.sql
-- SpecBox NativeBackend — seal the org tenancy anchor (US-13 / UC-1304).
--
-- WHY: this is the THIRD and final pass of the two-pass NOT NULL strategy that
-- 0017 + 0018 deliberately split (see the header of 0017). 0017 added
-- `projects.organization_id` as NULLABLE so that INSERTs into `projects` running
-- between the schema change and the data backfill would not break. 0018 backfilled
-- every existing project to its real organization. Now that no project has a NULL
-- organization_id, this migration sets the column NOT NULL so the org anchor can
-- never again be left dangling — tenancy isolation (UC-1304) depends on every
-- project belonging to exactly one organization.
--
-- ORDER OF SEALING (UC-1304): the NOT NULL constraint is the schema-level
-- guarantee that the isolation predicate `projects.organization_id = <org>` can
-- never silently match a NULL row. It is the first step of UC-1304 (org isolation)
-- because every WHERE-by-org filter added in the panel and the native queries
-- assumes the column is always populated.
--
-- SAFETY: before flipping the constraint we assert there are zero NULL rows and
-- RAISE a readable exception if not — turning Postgres's generic
-- "column contains null values" into an actionable message that names how many
-- projects are still unassigned and points back at the 0018 backfill. Verified
-- against production (Supabase SpecBox-Cloud) on 2026-06-11: 7 projects, 0 NULL.
--
-- Idempotency [matches 0001/0009/0017]: guarded by an information_schema check on
-- `is_nullable`. Re-applying on a DB where the column is already NOT NULL is a
-- no-op. Wrapped in a single transaction by the runner.
--
-- Mirror of server/db/migrations/0019_organization_id_not_null.sql.
--
-- ROLLBACK (manual, documented — run as a one-off, NOT auto-applied):
--   ALTER TABLE projects ALTER COLUMN organization_id DROP NOT NULL;

DO $$
DECLARE
    null_count BIGINT;
BEGIN
    -- Only act if the column is still NULLABLE (idempotent re-apply guard).
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'projects'
          AND column_name  = 'organization_id'
          AND is_nullable  = 'YES'
    ) THEN
        -- Pre-flight: refuse to seal if any project is still unassigned, with a
        -- message that tells the operator exactly what to fix (re-run 0018).
        SELECT count(*) INTO null_count
        FROM projects
        WHERE organization_id IS NULL;

        IF null_count > 0 THEN
            RAISE EXCEPTION
                '0019: cannot SET NOT NULL — % project(s) still have organization_id IS NULL. Re-run the 0018 backfill to assign every project to an organization first.',
                null_count;
        END IF;

        ALTER TABLE projects ALTER COLUMN organization_id SET NOT NULL;
    END IF;
END $$;
