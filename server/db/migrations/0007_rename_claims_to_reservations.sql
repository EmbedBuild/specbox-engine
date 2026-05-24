-- 0007_rename_claims_to_reservations.sql
-- SpecBox NativeBackend — rename uc_claims → uc_reservations (US-CLAIM-RENAME / UC-601).
--
-- Background
-- ==========
-- The "claim" concept (one developer temporarily holding exclusive rights to
-- work on a UC) was introduced in 0003_claims.sql. "Claim" is jargon to
-- non-technical users; "reservation" is universally understood (table, room,
-- library) and fits the actual semantics. This migration renames the table,
-- its timestamp column, its index, and the RLS deny policy so the schema
-- speaks the new vocabulary end-to-end.
--
-- Renames (all idempotent, see below):
--   table  uc_claims                          -> uc_reservations
--   column claimed_at                         -> reserved_at
--   index  idx_uc_claims_developer_id         -> idx_uc_reservations_developer_id
--   policy specbox_deny_anon_uc_claims        -> specbox_deny_anon_uc_reservations
--
-- Idempotency contract [AC-01, AC-03]
-- ====================================
-- Each rename is guarded so re-applying the migration after a successful run
-- is a NO-OP, not an error:
--   * Tables  — guarded with to_regclass('public.uc_claims') IS NOT NULL.
--   * Columns — guarded with information_schema.columns lookup.
--   * Indexes — guarded with to_regclass('public.idx_uc_claims_developer_id').
--   * Policies — guarded with pg_policies lookup.
--
-- Data preservation [AC-01]
-- =========================
-- ALTER TABLE RENAME preserves every row, every FK, every constraint, and
-- the table OID. RLS policies on the table follow the rename automatically
-- (they reference the table by OID, not by name) — we rename the policy's
-- own identifier separately to keep the project's naming convention
-- (specbox_deny_anon_<table>) consistent.
--
-- Production parity
-- =================
-- This file is mirrored byte-for-byte in supabase/migrations/<ts>_rename_claims_to_reservations.sql,
-- which is the source of truth for the production Supabase database. See
-- server/db/migrate.py — this local runner is for dev / tests only.

DO $$
DECLARE
    legacy_row_count BIGINT;
BEGIN
    -- ── table rename ─────────────────────────────────────────────────
    -- Three relevant states:
    --   (a) only uc_claims exists → first-time rename, ALTER TABLE.
    --   (b) only uc_reservations exists → already renamed, no-op.
    --   (c) BOTH exist → re-apply scenario: the migration runner replays
    --       every *.sql in order, so 0003_claims.sql ran again and its
    --       CREATE TABLE IF NOT EXISTS uc_claims (...) recreated a fresh,
    --       empty uc_claims alongside the already-renamed uc_reservations.
    --       The freshly-recreated uc_claims has no rows (the real data is
    --       in uc_reservations); drop it so the rename below is a no-op.
    --       If for some reason uc_claims is NOT empty (out-of-band insert
    --       between 0003 and 0007 on a re-apply), surface a hard error
    --       rather than silently destroy rows.
    IF to_regclass('public.uc_claims') IS NOT NULL
       AND to_regclass('public.uc_reservations') IS NOT NULL THEN
        EXECUTE 'SELECT count(*) FROM public.uc_claims' INTO legacy_row_count;
        IF legacy_row_count = 0 THEN
            DROP TABLE public.uc_claims;
        ELSE
            RAISE EXCEPTION
                'Both uc_claims (% rows) and uc_reservations exist. '
                'Refusing to drop uc_claims because it has data. '
                'Manual reconciliation required.',
                legacy_row_count;
        END IF;
    END IF;

    IF to_regclass('public.uc_claims') IS NOT NULL THEN
        ALTER TABLE public.uc_claims RENAME TO uc_reservations;
    END IF;

    -- ── column rename (claimed_at → reserved_at) ─────────────────────
    -- Guarded against information_schema.columns so a re-run finds the
    -- already-renamed column and skips silently.
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'uc_reservations'
          AND column_name  = 'claimed_at'
    ) THEN
        ALTER TABLE public.uc_reservations RENAME COLUMN claimed_at TO reserved_at;
    END IF;

    -- ── index rename ─────────────────────────────────────────────────
    IF to_regclass('public.idx_uc_claims_developer_id') IS NOT NULL THEN
        ALTER INDEX public.idx_uc_claims_developer_id
            RENAME TO idx_uc_reservations_developer_id;
    END IF;

    -- ── RLS policy rename ────────────────────────────────────────────
    -- The policy was created by 20260522000004_rls_policies.sql as
    -- specbox_deny_anon_uc_claims ON public.uc_claims. After the table
    -- rename above, it lives on public.uc_reservations but its literal
    -- name still references "claims". Rename it so the naming convention
    -- specbox_deny_anon_<table> holds for the new table name. Guarded
    -- against pg_policies for idempotency.
    IF EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename  = 'uc_reservations'
          AND policyname = 'specbox_deny_anon_uc_claims'
    ) THEN
        ALTER POLICY specbox_deny_anon_uc_claims
            ON public.uc_reservations
            RENAME TO specbox_deny_anon_uc_reservations;
    END IF;
END
$$;
