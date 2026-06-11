-- 0012_uc_lifecycle_capture.sql
-- SpecBox NativeBackend — UC lifecycle capture via triggers (US-12 / UC-1201).
--
-- WHY TRIGGERS (not a Python choke point): use_cases.state has THREE writers
-- that share no common code path — start_uc_atomic's raw UPDATE
-- (coordination/reservations.py), the generic update_item (backends/
-- native_backend.py), and ingest_atomic's batch path. A trigger makes Postgres
-- the choke point by construction: every state change — present or future
-- writers, even a manual psql fix — is captured transactionally. The capture
-- CANNOT be silently lost the way the best-effort complete_uc audit event can
-- (_release_uc_native swallows every failure path by design).
--
-- WHAT IT CAPTURES:
--   * uc_state_transitions — append-only history: one row per state change
--     with from/to, a SNAPSHOT of us_id (survives the parent US's ON DELETE
--     SET NULL), and application context read from session GUCs.
--   * use_cases.started_at  — first transition INTO 'in_progress' wins
--     (COALESCE: a re-cycle never overwrites the original start).
--   * use_cases.completed_at — every transition INTO 'done' overwrites
--     (last completion wins).
--
-- APPLICATION CONTEXT (session GUCs, set per-transaction by the engine with
-- set_config(..., is_local := true) — they die with the transaction, so a
-- pooled connection never leaks them):
--   * app.developer_id  — who performed the mutation. NULL when not set:
--     honest degradation, the WHO is lost but never the WHEN/WHAT.
--   * app.change_source — 'interactive' (default) | 'import' |
--     'backfill_estimate'. Imports must NOT count as implementation time:
--     the BEFORE trigger skips the lifecycle columns for non-interactive
--     sources. (Batch ingestion INSERTs rows and never fires the UPDATE
--     trigger anyway — the GUC is defense in depth for collision-update
--     paths.)
--
-- Like audit_log (0006): NO foreign keys on purpose — history must survive
-- project/developer deletion. The metric layer (0013) joins lazily at read
-- time.
--
-- Idempotent: ADD COLUMN/CREATE TABLE/CREATE INDEX use IF NOT EXISTS,
-- functions use CREATE OR REPLACE, triggers are DROP IF EXISTS + CREATE.
-- The dev/test runner (server/db/migrate.py) re-applies every file on each
-- pass; production applies the byte-for-byte supabase/migrations mirror.

-- ── Lifecycle columns on use_cases ───────────────────────────────────

ALTER TABLE use_cases
    ADD COLUMN IF NOT EXISTS started_at   TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ NULL;

-- ── Append-only transition history ───────────────────────────────────

CREATE TABLE IF NOT EXISTS uc_state_transitions (
    id            BIGSERIAL PRIMARY KEY,
    project_id    TEXT NOT NULL,            -- no FK on purpose — see header
    uc_id         TEXT NOT NULL,
    us_id         TEXT NULL,                -- snapshot at transition time
    from_state    TEXT NULL,
    to_state      TEXT NOT NULL,
    developer_id  TEXT NULL,                -- GUC app.developer_id (honest NULL)
    source        TEXT NOT NULL DEFAULT 'interactive',
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_uc_transitions_project_occurred
    ON uc_state_transitions (project_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_uc_transitions_project_uc
    ON uc_state_transitions (project_id, uc_id, occurred_at);

-- ── BEFORE trigger: maintain started_at / completed_at ───────────────

CREATE OR REPLACE FUNCTION uc_lifecycle_columns() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_source text := COALESCE(NULLIF(current_setting('app.change_source', true), ''),
                              'interactive');
BEGIN
    -- Imports and backfill must not write implementation-time timestamps:
    -- those rows are administrative, not work (US-12 honest-metrics contract).
    IF v_source IN ('import', 'backfill_estimate') THEN
        RETURN NEW;
    END IF;
    IF NEW.state = 'in_progress' AND (OLD.state IS DISTINCT FROM NEW.state) THEN
        NEW.started_at := COALESCE(OLD.started_at, now());
    ELSIF NEW.state = 'done' AND (OLD.state IS DISTINCT FROM NEW.state) THEN
        NEW.completed_at := now();
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_uc_lifecycle_columns ON use_cases;
CREATE TRIGGER trg_uc_lifecycle_columns
    BEFORE UPDATE OF state ON use_cases
    FOR EACH ROW
    EXECUTE FUNCTION uc_lifecycle_columns();

-- ── AFTER trigger: append the transition row ─────────────────────────

CREATE OR REPLACE FUNCTION uc_record_transition() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO uc_state_transitions
        (project_id, uc_id, us_id, from_state, to_state, developer_id, source)
    VALUES (
        NEW.project_id,
        NEW.id,
        NEW.us_id,
        OLD.state,
        NEW.state,
        NULLIF(current_setting('app.developer_id', true), ''),
        COALESCE(NULLIF(current_setting('app.change_source', true), ''), 'interactive')
    );
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_uc_record_transition ON use_cases;
CREATE TRIGGER trg_uc_record_transition
    AFTER UPDATE OF state ON use_cases
    FOR EACH ROW
    WHEN (OLD.state IS DISTINCT FROM NEW.state)
    EXECUTE FUNCTION uc_record_transition();

-- ── RLS: same posture as the other spec tables (20260522000004) ──────
-- Only the MCP's service_role touches these rows; anon + authenticated get an
-- explicit restrictive deny. The anon/authenticated roles only exist on
-- Supabase (the local dev Postgres has neither — 0004_rls_policies lives only
-- in the supabase ledger for that reason), so the policy is role-guarded to
-- keep this file byte-for-byte mirrorable. ENABLE RLS itself is portable and
-- a no-op when already on.

ALTER TABLE uc_state_transitions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon')
       AND EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
        DROP POLICY IF EXISTS specbox_deny_anon_uc_state_transitions
            ON uc_state_transitions;
        CREATE POLICY specbox_deny_anon_uc_state_transitions
            ON uc_state_transitions
            AS RESTRICTIVE FOR ALL
            TO anon, authenticated
            USING (false) WITH CHECK (false);
    END IF;
END $$;
