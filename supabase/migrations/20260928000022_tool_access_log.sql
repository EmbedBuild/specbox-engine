-- 0022_tool_access_log.sql
-- SpecBox Engine — append-only access log per tool call (UC-3803, US-38).
--
-- Origin: the external tester's report (2026-09-24) could only be audited
-- partially because the hosted MCP kept no per-call trail: ``audit_log`` (0006)
-- covers native mutations, nothing covers "who called which tool, when, and
-- whether it succeeded". The middleware in ``server/coordination/access_log.py``
-- appends one row here for EVERY tool call, on every transport.
--
-- Schema notes (same philosophy as audit_log):
--   * ``developer_id`` has NO FK: the trail must outlive the actor. NULL means
--     the caller was not an identified developer — ``identity_kind`` says why
--     (anonymous / invalid_token / unresolved).
--   * Never a credential, never an argument value, never a returned payload
--     (AC-03): only ``arg_keys`` (argument NAMES) and an ``error_code``.
--   * Append-only (AC-01): a statement-level trigger refuses UPDATE, DELETE and
--     TRUNCATE for every role, the owner included. Retention is an operator
--     decision taken by dropping the trigger deliberately, never by accident.
--   * PostgREST roles never see it: privileges revoked from PUBLIC / anon /
--     authenticated (Supabase grants them by default on new public tables) and
--     RLS enabled with no policies. The engine connects as the table owner.
--
-- Idempotent (IF NOT EXISTS / OR REPLACE), safe to re-apply.

CREATE TABLE IF NOT EXISTS tool_access_log (
    id            BIGSERIAL PRIMARY KEY,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    tool          TEXT NOT NULL,
    identity_kind TEXT NOT NULL,          -- developer | anonymous | invalid_token | unresolved
    developer_id  TEXT NULL,              -- NO FK on purpose — see header
    project_id    TEXT NULL,              -- native session board, when any
    outcome       TEXT NOT NULL,          -- ok | error | exception
    error_code    TEXT NULL,              -- short code only, never a message
    duration_ms   INTEGER NULL,
    transport     TEXT NOT NULL DEFAULT 'stdio',
    client        TEXT NULL,              -- MCP client name/version from initialize
    remote_addr   TEXT NULL,
    session_id    TEXT NULL,              -- MCP session id (random, not a credential)
    arg_keys      TEXT[] NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_tool_access_log_dev_occurred
    ON tool_access_log (developer_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_access_log_occurred
    ON tool_access_log (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_access_log_tool_occurred
    ON tool_access_log (tool, occurred_at DESC);

-- ── Append-only guard ────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION tool_access_log_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'tool_access_log is append-only: % is not allowed', TG_OP
        USING ERRCODE = '42501';
END;
$$;

DROP TRIGGER IF EXISTS trg_tool_access_log_append_only ON tool_access_log;
CREATE TRIGGER trg_tool_access_log_append_only
    BEFORE UPDATE OR DELETE OR TRUNCATE ON tool_access_log
    FOR EACH STATEMENT EXECUTE FUNCTION tool_access_log_append_only();

-- ── Never readable through PostgREST ─────────────────────────────────
REVOKE ALL ON TABLE tool_access_log FROM PUBLIC;
REVOKE ALL ON SEQUENCE tool_access_log_id_seq FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE tool_access_log FROM anon;
        REVOKE ALL ON SEQUENCE tool_access_log_id_seq FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE tool_access_log FROM authenticated;
        REVOKE ALL ON SEQUENCE tool_access_log_id_seq FROM authenticated;
    END IF;
END $$;
ALTER TABLE tool_access_log ENABLE ROW LEVEL SECURITY;
