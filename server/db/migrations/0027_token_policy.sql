-- 0027_token_policy.sql
-- SpecBox Engine — token policy: idle tokens are revoked and a person holds at
-- most five devices (UC-3902 AC-03 and AC-04, US-39).
--
-- Origin: the audit of 2026-09-29 found 85 active tokens held by 16 people,
-- 25 of them never used and one person holding 26. Since migration 0025 every
-- token belongs to a device and expires; this migration adds the two rules the
-- operator decided on top of that (2026-09-30):
--
--   * Inactivity (AC-03). ``public.revoke_idle_mcp_tokens(p_idle_days, p_floor)``
--     revokes, with ``revoked_reason = 'idle'``, every active token whose last
--     real use is older than ``p_idle_days`` (60 by default) and writes one
--     ``audit_log`` row per token. ``last_used_at`` only reflects MCP use since
--     the engine started recording it (0025, deployed 2026-09-29): before that
--     only the panel's ``/api/whoami`` wrote it, so a token nobody touched from
--     the panel could look idle while it was used every day. ``p_floor``
--     (default 2026-09-29) is the earliest "last use" the function believes:
--     the 60 days count from that date at the earliest, so nothing is revoked
--     before 2026-11-28 and nobody is cut off on data the engine never had.
--     Expired tokens are left alone (they already do not authenticate and the
--     panel shows them as expired, not revoked).
--
--     Where pg_cron is available (Supabase), the job ``revoke-idle-mcp-tokens``
--     runs the function every day at 03:17 UTC. On a Postgres without pg_cron
--     (CI, local) the function exists and nothing is scheduled.
--
--   * Device limit (AC-04). ``public.issue_device_token`` refuses to issue a
--     token for a NEW device when the person already has five active,
--     unexpired device tokens, raising ``DEVICE_LIMIT`` (SQLSTATE 53400,
--     configuration_limit_exceeded). Signing in again on a known device,
--     renewing or replacing its token never trips the limit, tokens without a
--     device (before 0025) and expired ones do not take a slot, and the
--     exception rolls back the revocation the function had already done. The
--     cloud API turns the error into ``409 device_limit`` with the list of
--     devices, so the person chooses which one to disconnect.
--
-- Idempotent (OR REPLACE, named cron job, guarded extension), safe to re-apply.
-- Reversible: ``SELECT cron.unschedule('revoke-idle-mcp-tokens')``, drop the
-- idle function and re-apply 0025 to restore the previous issuing function.

-- ── AC-03: idle revocation ───────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.revoke_idle_mcp_tokens(
    p_idle_days integer     DEFAULT 60,
    p_floor     timestamptz DEFAULT timestamptz '2026-09-29 00:00:00+00'
)
RETURNS TABLE (revoked_token_id text, revoked_developer_id text)
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    IF p_idle_days IS NULL OR p_idle_days < 1 THEN
        RAISE EXCEPTION 'INVALID_IDLE_DAYS' USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    WITH idle AS (
        UPDATE mcp_tokens t
           SET revoked_at = now(),
               revoked_reason = 'idle'
         WHERE t.revoked_at IS NULL
           AND (t.expires_at IS NULL OR t.expires_at > now())
           AND GREATEST(coalesce(t.last_used_at, t.created_at), coalesce(p_floor, t.created_at))
               < now() - make_interval(days => p_idle_days)
        RETURNING t.token_id, t.developer_id
    ), noted AS (
        INSERT INTO audit_log (developer_id, project_id, operation, target_id, metadata)
        SELECT idle.developer_id, '', 'revoke_mcp_token', idle.token_id,
               jsonb_build_object('via', 'idle', 'idle_days', p_idle_days)
          FROM idle
    )
    SELECT idle.token_id, idle.developer_id FROM idle ORDER BY idle.token_id;
END
$$;

-- Only the operator (postgres, via pg_cron) and the cloud API (service_role)
-- may run it; Supabase grants EXECUTE on new functions to anon and
-- authenticated by default, so take it back.
REVOKE ALL ON FUNCTION public.revoke_idle_mcp_tokens(integer, timestamptz) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION public.revoke_idle_mcp_tokens(integer, timestamptz) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION public.revoke_idle_mcp_tokens(integer, timestamptz) FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT EXECUTE ON FUNCTION public.revoke_idle_mcp_tokens(integer, timestamptz) TO service_role;
    END IF;
END $$;

-- Daily job where pg_cron exists (Supabase). pg_cron is not relocatable (it
-- lives in pg_catalog) and ``cron.schedule`` with a job name replaces the job
-- of the same name, so re-applying keeps exactly one job.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron') THEN
        CREATE EXTENSION IF NOT EXISTS pg_cron;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
        PERFORM cron.schedule(
            'revoke-idle-mcp-tokens',
            '17 3 * * *',
            'SELECT public.revoke_idle_mcp_tokens()'
        );
    END IF;
END $$;

-- ── AC-04: at most five devices per person ───────────────────────────────────
-- Same signature as 0025 (OR REPLACE keeps the grants: only service_role).

CREATE OR REPLACE FUNCTION public.issue_device_token(
    p_developer_id        text,
    p_token_id            text,
    p_token_hash          text,
    p_device_id           text,
    p_device_name         text,
    p_client              text,
    p_issued_via          text,
    p_supersedes_token_id text    DEFAULT NULL,
    p_reason              text    DEFAULT 'replaced',
    p_ttl_days            integer DEFAULT 90
)
RETURNS TABLE (issued_token_id text, issued_expires_at timestamptz, revoked_token_ids text[])
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
    c_max_devices constant integer := 5;   -- UC-3902 AC-04
    v_expires timestamptz;
    v_revoked text[];
    v_known   boolean;
    v_devices integer;
BEGIN
    IF p_ttl_days IS NULL OR p_ttl_days < 1 OR p_ttl_days > 365 THEN
        RAISE EXCEPTION 'INVALID_TTL' USING ERRCODE = '22023';
    END IF;
    IF p_reason IS NULL OR p_reason NOT IN ('replaced', 'renewed') THEN
        RAISE EXCEPTION 'INVALID_REASON' USING ERRCODE = '22023';
    END IF;

    -- A renewal must present a token that still works: a revoked or expired
    -- one cannot mint its successor. FOR UPDATE serialises two renewals of the
    -- same token, so only the first one wins.
    IF p_supersedes_token_id IS NOT NULL THEN
        PERFORM 1
           FROM mcp_tokens t
          WHERE t.token_id = p_supersedes_token_id
            AND t.developer_id = p_developer_id
            AND t.revoked_at IS NULL
            AND (t.expires_at IS NULL OR t.expires_at > now())
          FOR UPDATE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'TOKEN_NOT_RENEWABLE' USING ERRCODE = '28000';
        END IF;
    END IF;

    -- Is this device already one of the person's devices? Signing in again,
    -- renewing or replacing its token never trips the limit (even when the
    -- current token has expired: nobody is cut off from a computer they use).
    v_known := p_device_id IS NOT NULL AND EXISTS (
        SELECT 1
          FROM mcp_tokens t
         WHERE t.developer_id = p_developer_id
           AND t.device_id = p_device_id
           AND t.revoked_at IS NULL
    );

    WITH gone AS (
        UPDATE mcp_tokens t
           SET revoked_at = now(),
               revoked_reason = p_reason
         WHERE t.developer_id = p_developer_id
           AND t.revoked_at IS NULL
           AND ((p_device_id IS NOT NULL AND t.device_id = p_device_id)
                OR t.token_id = p_supersedes_token_id)
        RETURNING t.token_id
    )
    SELECT coalesce(array_agg(gone.token_id ORDER BY gone.token_id), '{}'::text[])
      INTO v_revoked
      FROM gone;

    -- UC-3902 AC-04: a new device only fits while the person has fewer than
    -- five. Counted once the superseded token is gone; tokens without a device
    -- and expired ones do not take a slot. Raising here rolls back the
    -- revocation above, so a refused sign-in changes nothing.
    IF NOT v_known THEN
        SELECT count(*)::integer
          INTO v_devices
          FROM mcp_tokens t
         WHERE t.developer_id = p_developer_id
           AND t.device_id IS NOT NULL
           AND t.revoked_at IS NULL
           AND (t.expires_at IS NULL OR t.expires_at > now());
        IF v_devices >= c_max_devices THEN
            RAISE EXCEPTION 'DEVICE_LIMIT' USING ERRCODE = '53400',
                DETAIL = format('%s active devices; the limit is %s', v_devices, c_max_devices);
        END IF;
    END IF;

    v_expires := now() + make_interval(days => p_ttl_days);
    INSERT INTO mcp_tokens (token_id, developer_id, token_hash, name, expires_at,
                            device_id, device_name, client, issued_via)
    VALUES (p_token_id, p_developer_id, p_token_hash, p_device_name, v_expires,
            p_device_id, p_device_name, p_client, p_issued_via);

    RETURN QUERY SELECT p_token_id, v_expires, v_revoked;
END
$$;
