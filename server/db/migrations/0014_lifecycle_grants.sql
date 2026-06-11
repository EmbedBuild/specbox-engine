-- 0014_lifecycle_grants.sql
-- SpecBox NativeBackend — read-only analytics role (US-12 / UC-1204).
--
-- The panel (specbox_cloud) reads the lifecycle views DIRECTLY from Postgres.
-- This role is its security boundary: SELECT on the v_ lifecycle views and
-- EXECUTE on fn_lifecycle_kpis — and NOTHING else. Base tables stay
-- unreachable (the views run with their owner's privileges — default
-- security_invoker = false — so the role never needs table grants).
--
-- NOLOGIN on purpose: this is a privilege bundle, not a user. The panel's
-- LOGIN user is created operationally (panel concern, never in this repo)
-- and inherits via GRANT specbox_analytics_ro TO <panel_user>.
--
-- Idempotent: the role is created only if absent (CREATE ROLE has no IF NOT
-- EXISTS); GRANTs are naturally re-appliable no-ops.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'specbox_analytics_ro') THEN
        CREATE ROLE specbox_analytics_ro NOLOGIN;
    END IF;
END $$;

-- Name resolution only (not table access): without schema USAGE the role sees
-- "relation does not exist" even for granted views. Not implied by default on
-- this database (public is owned by the service user with an empty ACL).
GRANT USAGE ON SCHEMA public TO specbox_analytics_ro;

GRANT SELECT ON v_uc_lifecycle,
                v_lifecycle_kpis,
                v_us_progress,
                v_weekly_throughput
    TO specbox_analytics_ro;

GRANT EXECUTE ON FUNCTION fn_lifecycle_kpis(TEXT) TO specbox_analytics_ro;
