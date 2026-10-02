-- 0006_audit_log.sql
-- SpecBox NativeBackend — append-only audit log (UC-501 AC-04).
--
-- Purpose: every mutating Native operation appends a row here. The log is the
-- ground truth for "who did what, in which project, against which target,
-- when" — independent of any spec table. It survives developer deletion: see
-- the explicit decision on ``developer_id`` below.
--
-- Schema notes:
--   * ``id`` is BIGSERIAL — monotonic, cheap to index by (project_id,
--     occurred_at) for the dashboard tail-read pattern.
--   * ``developer_id`` is NULLABLE and INTENTIONALLY HAS NO FK to
--     ``developers``. Rationale: a hard-delete of a developer (GDPR erasure,
--     offboarding) must NOT cascade into the audit log; the trail has to
--     outlive the actor. Storing the id as a free string keeps the historical
--     attribution even if the row in ``developers`` no longer exists. The
--     trade-off (orphaned reference) is acceptable for an append-only log.
--   * ``project_id`` is NOT NULL but ALSO has no FK — same reason in the
--     reverse direction would apply if projects were ever hard-deleted; for
--     now this also keeps the log fully decoupled and writeable from any
--     code path without needing the project row to be loaded.
--   * ``operation`` and ``target_id`` are free strings. The vocabulary lives
--     in the application layer (UC-502/UC-504) — keeping it out of the schema
--     means we don't migrate the DB every time a new operation is added.
--
-- Idempotent (IF NOT EXISTS), safe to re-apply.

-- ── audit_log ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id            BIGSERIAL PRIMARY KEY,
    developer_id  TEXT NULL,            -- NO FK on purpose — see header
    project_id    TEXT NOT NULL,        -- NO FK on purpose — see header
    operation     TEXT NOT NULL,
    target_id     TEXT NOT NULL,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tail-read pattern: "show me the last N events in project X". The DESC on
-- ``occurred_at`` matches the query plan we expect (ORDER BY occurred_at DESC
-- LIMIT N).
CREATE INDEX IF NOT EXISTS idx_audit_log_project_occurred
    ON audit_log (project_id, occurred_at DESC);
