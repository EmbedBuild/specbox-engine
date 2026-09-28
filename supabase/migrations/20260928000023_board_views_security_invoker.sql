-- 20260928000023_board_views_security_invoker.sql — Supabase mirror of server/db/migrations/0023_board_views_security_invoker.sql
-- SpecBox Engine — the board's views and its indicator / lifecycle functions
-- are closed by default (UC-4001, US-40).
--
-- Origin: the six board views ran with their owner's privileges
-- (security_invoker = off, the Postgres default) and kept the SELECT that
-- Supabase grants anon / authenticated on every new object in public, so the
-- project's public (anon) key could read every tenant's board through
-- PostgREST (audit of 2026-09-28). The production hotfix of that day
-- (hotfix_p0_board_views_and_lifecycle_fns +
-- hotfix_p0_fix_public_execute_grants) closed it without code; this migration
-- versions it and completes it:
--   * every board view evaluates the privileges and RLS of the role that
--     queries it (security_invoker = on) and PUBLIC / anon / authenticated
--     lose every privilege on it;
--   * the indicator and lifecycle functions (and the append-only guard of
--     0022) run only for server-side roles and have their search_path pinned.
--
-- Worth knowing:
--   * service_role keeps SELECT on the views (the cloud API reads
--     project_kpis): it bypasses RLS and holds the base-table grants Supabase
--     gives it. The engine connects as the owner and is not affected.
--   * specbox_analytics_ro (0014) keeps its grants, but with invoker's rights
--     the views no longer lend it the owner's privileges: a LOGIN user attached
--     to it reads nothing until it is granted SELECT on the base tables and RLS
--     lets it through. No such user exists today.
--   * Trigger functions still fire for writers without EXECUTE on them
--     (Postgres checks EXECUTE only when the trigger is created), so revoking
--     it from PUBLIC does not break any write.
--   * CREATE OR REPLACE VIEW resets the view options and CREATE OR REPLACE
--     FUNCTION resets its SET clauses (verified on Postgres 16): a later
--     migration that redefines one of these objects must repeat
--     WITH (security_invoker = on) / SET search_path. The surface check of
--     UC-4003 fails the build otherwise.
--
-- Idempotent: ALTER ... SET and REVOKE / GRANT are re-appliable, and the
-- statements that name anon / authenticated / service_role only run where
-- those roles exist (Supabase), not in the throwaway test database.

-- ── Views: invoker's rights, nothing for the public roles ────────────
ALTER VIEW project_kpis           SET (security_invoker = on);
ALTER VIEW v_uc_lifecycle         SET (security_invoker = on);
ALTER VIEW v_lifecycle_kpis       SET (security_invoker = on);
ALTER VIEW v_us_progress          SET (security_invoker = on);
ALTER VIEW v_weekly_throughput    SET (security_invoker = on);
ALTER VIEW v_active_time_estimate SET (security_invoker = on);

REVOKE ALL ON project_kpis, v_uc_lifecycle, v_lifecycle_kpis, v_us_progress,
              v_weekly_throughput, v_active_time_estimate
    FROM PUBLIC;

-- ── Functions: pinned search_path, server-side roles only ────────────
ALTER FUNCTION fn_lifecycle_kpis(TEXT)              SET search_path = public, pg_temp;
ALTER FUNCTION fn_backfill_lifecycle(TEXT, BOOLEAN) SET search_path = public, pg_temp;
ALTER FUNCTION fn_recompute_lifecycle_columns(TEXT) SET search_path = public, pg_temp;
ALTER FUNCTION uc_lifecycle_columns()               SET search_path = public, pg_temp;
ALTER FUNCTION uc_record_transition()               SET search_path = public, pg_temp;
ALTER FUNCTION tool_access_log_append_only()        SET search_path = public, pg_temp;

REVOKE ALL ON FUNCTION fn_lifecycle_kpis(TEXT),
                       fn_backfill_lifecycle(TEXT, BOOLEAN),
                       fn_recompute_lifecycle_columns(TEXT),
                       uc_lifecycle_columns(),
                       uc_record_transition(),
                       tool_access_log_append_only()
    FROM PUBLIC;
-- specbox_analytics_ro keeps EXECUTE on fn_lifecycle_kpis (0014): explicit
-- grants survive a REVOKE ... FROM PUBLIC.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON project_kpis, v_uc_lifecycle, v_lifecycle_kpis, v_us_progress,
                      v_weekly_throughput, v_active_time_estimate
            FROM anon;
        REVOKE ALL ON FUNCTION fn_lifecycle_kpis(TEXT),
                               fn_backfill_lifecycle(TEXT, BOOLEAN),
                               fn_recompute_lifecycle_columns(TEXT),
                               uc_lifecycle_columns(),
                               uc_record_transition(),
                               tool_access_log_append_only()
            FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON project_kpis, v_uc_lifecycle, v_lifecycle_kpis, v_us_progress,
                      v_weekly_throughput, v_active_time_estimate
            FROM authenticated;
        REVOKE ALL ON FUNCTION fn_lifecycle_kpis(TEXT),
                               fn_backfill_lifecycle(TEXT, BOOLEAN),
                               fn_recompute_lifecycle_columns(TEXT),
                               uc_lifecycle_columns(),
                               uc_record_transition(),
                               tool_access_log_append_only()
            FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT ON project_kpis, v_uc_lifecycle, v_lifecycle_kpis, v_us_progress,
                        v_weekly_throughput, v_active_time_estimate
            TO service_role;
        GRANT EXECUTE ON FUNCTION fn_lifecycle_kpis(TEXT),
                                  fn_backfill_lifecycle(TEXT, BOOLEAN),
                                  fn_recompute_lifecycle_columns(TEXT)
            TO service_role;
    END IF;
END $$;
