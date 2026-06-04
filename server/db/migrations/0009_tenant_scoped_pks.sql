-- 0009_tenant_scoped_pks.sql
-- SpecBox NativeBackend — tenant-scope the spec-table primary keys (UC-707).
--
-- BUG (blocking): the atomic ingest of a FreeForm→Native migration collided on
-- user_stories_pkey because the PK was the LOGICAL id alone ("US-01"), not
-- namespaced by project. In a shared multi-tenant Postgres two projects cannot
-- both hold a "US-01", so any migration whose us_id already exists in ANOTHER
-- tenant failed with `duplicate key value violates unique constraint
-- "user_stories_pkey" DETAIL: Key (id)=(US-01) already exists`.
--
-- ROOT CAUSE: schema only. The whole application layer (native_backend.py) was
-- ALREADY written tenant-scoped — every lookup filters `WHERE project_id = $1
-- AND id = $2` and every INSERT passes project_id. The single thing lagging was
-- the PRIMARY KEY constraint, declared on (id) in 0001_native_schema.sql.
--
-- FIX: move the PK of user_stories / use_cases / acceptance_criteria to the
-- COMPOSITE (project_id, id). Rewire the two child foreign keys to be composite
-- too, so a child can only reference a parent IN THE SAME TENANT:
--   use_cases (project_id, us_id)        -> user_stories (project_id, id)
--   acceptance_criteria (project_id, uc_id) -> use_cases (project_id, id)
--
-- DATA: existing rows already carry a populated project_id (NOT NULL since
-- 0001), so there is no backfill — only the constraints are recabled. No row is
-- rewritten, no id changes; logical ids stay "US-01" etc.
--
-- Idempotency [matches 0001]: safe to re-apply. Each constraint swap is guarded
-- by a catalog lookup (pg_constraint) so re-running is a no-op once the
-- composite shape is in place. Wrapped in a single transaction by the runner.
--
-- NULL semantics: use_cases.us_id stays nullable (an orphan UC after a US
-- delete). A composite FK with a NULL column is NOT enforced under the default
-- MATCH SIMPLE — so `us_id IS NULL` keeps working exactly as the old
-- `ON DELETE SET NULL` intended.

-- ── user_stories: drop child FKs that point at the old single-col PK ──────────
-- (Postgres forbids dropping a PK still referenced by a FK; drop the FKs first.)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'use_cases_us_id_fkey') THEN
        ALTER TABLE use_cases DROP CONSTRAINT use_cases_us_id_fkey;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'acceptance_criteria_uc_id_fkey') THEN
        ALTER TABLE acceptance_criteria DROP CONSTRAINT acceptance_criteria_uc_id_fkey;
    END IF;
END $$;

-- ── user_stories: PK (id) -> PK (project_id, id) ─────────────────────────────
DO $$
DECLARE
    pk_cols text;
BEGIN
    SELECT string_agg(a.attname, ',' ORDER BY array_position(c.conkey, a.attnum))
      INTO pk_cols
      FROM pg_constraint c
      JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
     WHERE c.conrelid = 'user_stories'::regclass AND c.contype = 'p';
    IF pk_cols IS DISTINCT FROM 'project_id,id' THEN
        IF EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'user_stories'::regclass AND contype = 'p') THEN
            ALTER TABLE user_stories DROP CONSTRAINT user_stories_pkey;
        END IF;
        ALTER TABLE user_stories ADD PRIMARY KEY (project_id, id);
    END IF;
END $$;

-- ── use_cases: PK (id) -> PK (project_id, id) ────────────────────────────────
DO $$
DECLARE
    pk_cols text;
BEGIN
    SELECT string_agg(a.attname, ',' ORDER BY array_position(c.conkey, a.attnum))
      INTO pk_cols
      FROM pg_constraint c
      JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
     WHERE c.conrelid = 'use_cases'::regclass AND c.contype = 'p';
    IF pk_cols IS DISTINCT FROM 'project_id,id' THEN
        IF EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'use_cases'::regclass AND contype = 'p') THEN
            ALTER TABLE use_cases DROP CONSTRAINT use_cases_pkey;
        END IF;
        ALTER TABLE use_cases ADD PRIMARY KEY (project_id, id);
    END IF;
END $$;

-- ── acceptance_criteria: PK (id) -> PK (project_id, id) ──────────────────────
DO $$
DECLARE
    pk_cols text;
BEGIN
    SELECT string_agg(a.attname, ',' ORDER BY array_position(c.conkey, a.attnum))
      INTO pk_cols
      FROM pg_constraint c
      JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
     WHERE c.conrelid = 'acceptance_criteria'::regclass AND c.contype = 'p';
    IF pk_cols IS DISTINCT FROM 'project_id,id' THEN
        IF EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'acceptance_criteria'::regclass AND contype = 'p') THEN
            ALTER TABLE acceptance_criteria DROP CONSTRAINT acceptance_criteria_pkey;
        END IF;
        ALTER TABLE acceptance_criteria ADD PRIMARY KEY (project_id, id);
    END IF;
END $$;

-- ── Re-add the child FKs as COMPOSITE, same-tenant only ──────────────────────
-- Keep the original ON DELETE behaviour (US delete → orphan UC; UC delete →
-- cascade its ACs). Names preserved so a future migration can find them.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'use_cases_us_id_fkey') THEN
        ALTER TABLE use_cases
            ADD CONSTRAINT use_cases_us_id_fkey
            FOREIGN KEY (project_id, us_id)
            REFERENCES user_stories (project_id, id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'acceptance_criteria_uc_id_fkey') THEN
        ALTER TABLE acceptance_criteria
            ADD CONSTRAINT acceptance_criteria_uc_id_fkey
            FOREIGN KEY (project_id, uc_id)
            REFERENCES use_cases (project_id, id) ON DELETE CASCADE;
    END IF;
END $$;

-- ── Supporting indexes for the composite FK lookups ──────────────────────────
-- A composite FK needs an index on the referencing columns for efficient
-- cascade/SET NULL. (The referenced side is covered by the new composite PK.)
CREATE INDEX IF NOT EXISTS idx_use_cases_project_us           ON use_cases (project_id, us_id);
CREATE INDEX IF NOT EXISTS idx_acceptance_criteria_project_uc ON acceptance_criteria (project_id, uc_id);
