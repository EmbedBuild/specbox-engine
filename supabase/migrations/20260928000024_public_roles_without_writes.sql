-- 20260928000024_public_roles_without_writes.sql — Supabase mirror of server/db/migrations/0024_public_roles_without_writes.sql
-- SpecBox Engine — the public roles lose every write privilege on the board and
-- the deny policies become restrictive (UC-4002, US-40).
--
-- Origin: Supabase's default privileges for the migration role hand anon and
-- authenticated ALL on every new table of public (INSERT, UPDATE, DELETE,
-- TRUNCATE, REFERENCES, TRIGGER, MAINTAIN). On the board only row-level
-- security held them back, and on five sensitive tables (audit_log,
-- github_identities, mcp_tokens, organizations, organization_members) the deny
-- policy was PERMISSIVE: any permissive policy added later would have been
-- OR-ed with it and opened the table (audit of 2026-09-28).
--
-- What this migration leaves in place:
--   * Board tables (the fifteen created by these migrations): no privilege at
--     all for PUBLIC, anon or authenticated, RLS enabled, and one RESTRICTIVE
--     deny-all policy for anon and authenticated (specbox_deny_anon_<table>,
--     the name production already uses). Nothing legitimate reads the board
--     with the public key: the engine connects as the owner, the cloud API as
--     service_role, and the portal through its SECURITY DEFINER read gate.
--   * Every other table of public (the site's inventory and event tables):
--     anon and authenticated keep SELECT, which their RLS policies govern, and
--     lose every write privilege. The site writes through the SECURITY DEFINER
--     RPC ingest_site_event and the publisher uses service_role.
--   * Sequences of public: no privilege for anon or authenticated.
--   * Default privileges of the role that runs the migrations (postgres on
--     Supabase): tables created from now on grant anon and authenticated
--     SELECT only, and sequences nothing, so the next table does not depend on
--     anyone remembering this.
--
-- service_role and the owner are untouched. Idempotent: REVOKE / GRANT and
-- DROP POLICY IF EXISTS + CREATE POLICY are re-appliable, and everything that
-- names anon / authenticated only runs where those roles exist (Supabase),
-- not in the throwaway test database.

DO $$
DECLARE
    board_tables CONSTANT text[] := ARRAY[
        'acceptance_criteria', 'audit_log', 'branch_registry', 'developers',
        'github_identities', 'mcp_tokens', 'organization_members', 'organizations',
        'project_members', 'projects', 'tool_access_log', 'uc_reservations',
        'uc_state_transitions', 'use_cases', 'user_stories'
    ];
    has_anon  CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon');
    has_auth  CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated');
    has_maintain CONSTANT boolean := current_setting('server_version_num')::int >= 170000;
    t         text;
    policy    text;
BEGIN
    -- ── Board tables: closed to the public roles ─────────────────────
    FOREACH t IN ARRAY board_tables LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC', t);
        IF has_anon THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon', t);
        END IF;
        IF has_auth THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM authenticated', t);
        END IF;
        IF has_anon AND has_auth THEN
            policy := 'specbox_deny_anon_' || t;
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', policy, t);
            EXECUTE format(
                'CREATE POLICY %I ON public.%I AS RESTRICTIVE FOR ALL TO anon, authenticated '
                'USING (false) WITH CHECK (false)',
                policy, t
            );
        END IF;
    END LOOP;

    -- ── Every other table of public: read stays, writes go ───────────
    FOR t IN
        SELECT c.relname FROM pg_class c
         WHERE c.relkind IN ('r', 'p')
           AND c.relnamespace = 'public'::regnamespace
           AND c.relname <> ALL (board_tables)
    LOOP
        IF has_anon THEN
            EXECUTE format(
                'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE public.%I FROM anon', t
            );
            IF has_maintain THEN
                EXECUTE format('REVOKE MAINTAIN ON TABLE public.%I FROM anon', t);
            END IF;
        END IF;
        IF has_auth THEN
            EXECUTE format(
                'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE public.%I FROM authenticated', t
            );
            IF has_maintain THEN
                EXECUTE format('REVOKE MAINTAIN ON TABLE public.%I FROM authenticated', t);
            END IF;
        END IF;
    END LOOP;

    -- ── Sequences and default privileges ─────────────────────────────
    IF has_anon AND has_auth THEN
        EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated';
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated';
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO anon, authenticated';
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated';
    END IF;
END $$;
