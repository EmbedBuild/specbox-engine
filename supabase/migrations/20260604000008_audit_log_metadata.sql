-- 0008_audit_log_metadata.sql
-- SpecBox NativeBackend — add ``metadata`` JSONB to ``audit_log`` (UC-606).
--
-- Why: ``record_destructive`` (UC-501) wrote rows with no structured payload,
-- so a consumer could not tell apart the *kind* of an event sharing the same
-- ``operation``. UC-606 needs ``provision_project`` rows to carry the case
-- (``created`` vs ``adopted_orphan``) so the activity feed can distinguish a
-- real provisioning from a re-provisioning no-op (which now emits no row at
-- all). The managed production DB already carries this column (added out of
-- band); this migration brings the versioned schema — and the local dev /
-- test DB — into line, closing the drift.
--
-- Idempotent (IF NOT EXISTS), safe to re-apply. A no-op where the column
-- already exists (production).

ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
