-- 20260604000008_audit_log_metadata.sql
-- Mirror of server/db/migrations/0008_audit_log_metadata.sql (UC-606).
--
-- Adds the ``metadata`` JSONB column to ``audit_log`` so provisioning events
-- can carry their case (``created`` / ``adopted_orphan``). The managed
-- production DB already carries the column; this keeps the Supabase migration
-- ledger in sync so a fresh project provisions an identical schema.
--
-- Idempotent (IF NOT EXISTS) — a no-op where the column already exists.

ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
