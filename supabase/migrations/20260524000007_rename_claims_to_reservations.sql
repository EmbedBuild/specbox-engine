-- 20260524000007_rename_claims_to_reservations.sql
-- SpecBox NativeBackend — rename uc_claims → uc_reservations (US-CLAIM-RENAME / UC-601),
-- ported to the Supabase migration ledger.
--
-- Mirrors server/db/migrations/0007_rename_claims_to_reservations.sql verbatim
-- in intent. The Supabase ledger is the production source of truth (UC-402);
-- the local-dev runner under server/db/migrations/ is kept byte-for-byte in
-- sync so the conformance suite reproduces the same schema offline.
--
-- Renames (all idempotent):
--   table  uc_claims                          -> uc_reservations
--   column claimed_at                         -> reserved_at
--   index  idx_uc_claims_developer_id         -> idx_uc_reservations_developer_id
--   policy specbox_deny_anon_uc_claims        -> specbox_deny_anon_uc_reservations

DO $$
DECLARE
    legacy_row_count BIGINT;
BEGIN
    -- Three relevant states (see canonical file for the full rationale):
    -- (a) only uc_claims → ALTER. (b) only uc_reservations → no-op.
    -- (c) BOTH → re-apply: drop empty uc_claims, else hard error.
    IF to_regclass('public.uc_claims') IS NOT NULL
       AND to_regclass('public.uc_reservations') IS NOT NULL THEN
        EXECUTE 'SELECT count(*) FROM public.uc_claims' INTO legacy_row_count;
        IF legacy_row_count = 0 THEN
            DROP TABLE public.uc_claims;
        ELSE
            RAISE EXCEPTION
                'Both uc_claims (% rows) and uc_reservations exist. '
                'Refusing to drop uc_claims because it has data.',
                legacy_row_count;
        END IF;
    END IF;

    IF to_regclass('public.uc_claims') IS NOT NULL THEN
        ALTER TABLE public.uc_claims RENAME TO uc_reservations;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'uc_reservations'
          AND column_name  = 'claimed_at'
    ) THEN
        ALTER TABLE public.uc_reservations RENAME COLUMN claimed_at TO reserved_at;
    END IF;

    IF to_regclass('public.idx_uc_claims_developer_id') IS NOT NULL THEN
        ALTER INDEX public.idx_uc_claims_developer_id
            RENAME TO idx_uc_reservations_developer_id;
    END IF;

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
