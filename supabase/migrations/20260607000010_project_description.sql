-- 0010_project_description.sql
-- SpecBox NativeBackend — add description + tagline to projects (US-08 / UC-802).
--
-- Additive, non-destructive [PRD AC-06, AC-07]: two NULLABLE TEXT columns with
-- no default. Applying this over the populated production DB rewrites no row and
-- deletes nothing — existing projects simply get NULL in both columns. The panel
-- Cloud owns editing (PATCH + RLS project_admin, JR-V2.3); the engine only owns
-- the schema. setup_board / provision_native_project are intentionally NOT
-- changed: they keep inserting (project_id, name) and leave the new columns NULL.
--
-- Idempotent (ADD COLUMN IF NOT EXISTS), safe to re-apply — a no-op where the
-- columns already exist (matches the 0008 pattern).
--
-- Mirrored byte-for-byte in server/db/migrations/0010_project_description.sql,
-- the local dev / test ledger. See server/db/migrate.py.

ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS tagline     TEXT;
