-- 20260522000004_rls_policies.sql
-- SpecBox NativeBackend — RLS + explicit deny policies (UC-403).
--
-- Access model: the ONLY client of these tables is the SpecBox MCP, which
-- connects with the Supabase service_role. service_role BYPASSES RLS, so the
-- MCP keeps full access. Every other role (anon, authenticated) must NOT be
-- able to read or write spec rows. [AC-32, AC-33, AC-34]
--
-- RLS is already enabled (the ensure_rls event trigger flips it on for new
-- public tables); we ENABLE it again explicitly here so the intent is in the
-- ledger and does not depend on that trigger existing. [AC-32]
--
-- Each table gets an EXPLICIT restrictive deny policy for anon + authenticated
-- (USING (false) / WITH CHECK (false)) rather than relying on "RLS on, no
-- policy" implicit-deny. Explicit policies make the intent auditable and
-- silence the rls_enabled_no_policy advisor. [AC-34]
--
-- Idempotent: ENABLE RLS is a no-op when already on; policies are dropped then
-- recreated so a re-apply does not raise "policy already exists".

DO $$
DECLARE
  t text;
  spec_tables text[] := ARRAY[
    'projects', 'user_stories', 'use_cases', 'acceptance_criteria',
    'developers', 'project_members', 'uc_claims', 'branch_registry'
  ];
BEGIN
  FOREACH t IN ARRAY spec_tables LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I',
                   'specbox_deny_anon_' || t, t);
    -- Restrictive deny for the API-facing roles. service_role bypasses RLS and
    -- is unaffected; this only governs anon + authenticated.
    EXECUTE format(
      'CREATE POLICY %I ON public.%I AS RESTRICTIVE FOR ALL '
      'TO anon, authenticated USING (false) WITH CHECK (false)',
      'specbox_deny_anon_' || t, t
    );
  END LOOP;
END $$;
