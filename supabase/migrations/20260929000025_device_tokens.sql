-- 20260929000025_device_tokens.sql — Supabase mirror of server/db/migrations/0025_device_tokens.sql
-- SpecBox Engine — one token per device, with an expiry date (UC-3904, UC-3902 AC-01, US-39).
--
-- Origin: every sign-in from the VS Code extension minted a new token called
-- "vscode" without retiring the previous one, and no token ever expired
-- (audit of 2026-09-29: 85 active tokens held by 16 people, one of them with 26).
-- A token now belongs to a DEVICE: one person, one computer, one MCP client.
--
--   * ``device_id`` is computed by the client (SHA-256 of the machine id and the
--     client name, or of a random id kept on disk): the server never sees the
--     machine id. ``device_name`` is the readable label ("Jesús · MacBook ·
--     Claude Code"), ``client`` the MCP client and ``issued_via`` who ran the
--     sign-in (vscode, cli, manual, panel).
--   * At most one active token per (developer, device): a partial unique index
--     makes a second active token for the same device impossible, whoever
--     writes it.
--   * ``expires_at``: tokens issued from now on carry one (90 days by default);
--     the identity resolver refuses an expired token. Existing tokens keep NULL
--     (no expiry) until the owner decides their policy.
--   * ``revoked_reason`` says why a token stopped working, from a closed list.
--   * ``name`` was added in production by a panel migration that is not in any
--     repository; ADD COLUMN IF NOT EXISTS versions it here.
--
-- ``public.issue_device_token`` issues a device token in one transaction:
-- it revokes the device's active token (and, for a renewal, the token being
-- renewed, which must still be valid) and inserts the new one. Only the cloud
-- API calls it, as service_role; it runs with the caller's rights and a pinned
-- search_path, and nobody else may execute it.
--
-- Idempotent (IF NOT EXISTS, guarded constraints, OR REPLACE), safe to re-apply.

ALTER TABLE mcp_tokens ADD COLUMN IF NOT EXISTS name           TEXT NULL;
ALTER TABLE mcp_tokens ADD COLUMN IF NOT EXISTS expires_at     TIMESTAMPTZ NULL;
ALTER TABLE mcp_tokens ADD COLUMN IF NOT EXISTS device_id      TEXT NULL;
ALTER TABLE mcp_tokens ADD COLUMN IF NOT EXISTS device_name    TEXT NULL;
ALTER TABLE mcp_tokens ADD COLUMN IF NOT EXISTS client         TEXT NULL;
ALTER TABLE mcp_tokens ADD COLUMN IF NOT EXISTS issued_via     TEXT NULL;
ALTER TABLE mcp_tokens ADD COLUMN IF NOT EXISTS revoked_reason TEXT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mcp_tokens_device_id_check') THEN
        ALTER TABLE mcp_tokens ADD CONSTRAINT mcp_tokens_device_id_check
            CHECK (device_id IS NULL OR device_id ~ '^[0-9a-f]{64}$');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mcp_tokens_device_name_check') THEN
        ALTER TABLE mcp_tokens ADD CONSTRAINT mcp_tokens_device_name_check
            CHECK (device_name IS NULL OR char_length(device_name) BETWEEN 1 AND 120);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mcp_tokens_client_check') THEN
        ALTER TABLE mcp_tokens ADD CONSTRAINT mcp_tokens_client_check
            CHECK (client IS NULL OR client ~ '^[a-z0-9][a-z0-9-]{0,39}$');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mcp_tokens_issued_via_check') THEN
        ALTER TABLE mcp_tokens ADD CONSTRAINT mcp_tokens_issued_via_check
            CHECK (issued_via IS NULL OR issued_via IN ('vscode', 'cli', 'manual', 'panel'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mcp_tokens_revoked_reason_check') THEN
        ALTER TABLE mcp_tokens ADD CONSTRAINT mcp_tokens_revoked_reason_check
            CHECK (revoked_reason IS NULL OR revoked_reason IN (
                'replaced', 'renewed', 'user', 'org_admin', 'superadmin', 'banned', 'idle', 'logout'
            ));
    END IF;
END $$;

-- One active token per device (AC-01): a new sign-in replaces, never adds.
CREATE UNIQUE INDEX IF NOT EXISTS idx_mcp_tokens_one_active_per_device
    ON mcp_tokens (developer_id, device_id)
    WHERE revoked_at IS NULL AND device_id IS NOT NULL;

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
    v_expires timestamptz;
    v_revoked text[];
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

    v_expires := now() + make_interval(days => p_ttl_days);
    INSERT INTO mcp_tokens (token_id, developer_id, token_hash, name, expires_at,
                            device_id, device_name, client, issued_via)
    VALUES (p_token_id, p_developer_id, p_token_hash, p_device_name, v_expires,
            p_device_id, p_device_name, p_client, p_issued_via);

    RETURN QUERY SELECT p_token_id, v_expires, v_revoked;
END
$$;

-- Only the cloud API (service_role) issues tokens. Supabase grants EXECUTE on
-- new functions to anon and authenticated by default: take it back.
REVOKE ALL ON FUNCTION public.issue_device_token(text, text, text, text, text, text, text, text, text, integer)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION public.issue_device_token(text, text, text, text, text, text, text, text, text, integer)
            FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION public.issue_device_token(text, text, text, text, text, text, text, text, text, integer)
            FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT EXECUTE ON FUNCTION public.issue_device_token(text, text, text, text, text, text, text, text, text, integer)
            TO service_role;
    END IF;
END $$;
