-- ----------------------------------------------------------------------------
-- 001_riders_stripe_account.sql
--
-- Adds Stripe Connect fields to an existing `riders` table (or creates the
-- table if your project doesn't have one yet). All DDL is idempotent so this
-- migration can be re-run safely on a non-empty database.
--
-- Fields:
--   stripe_account_id   — acct_xxx from Stripe Connect Express
--   fee_percent         — application_fee_percent override per rider (NULL
--                         means use DEFAULT_APPLICATION_FEE_PERCENT env)
--   onboarding_status   — pending | restricted | enabled | deauthorized
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS riders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add Stripe columns if they don't exist
ALTER TABLE riders ADD COLUMN IF NOT EXISTS stripe_account_id TEXT UNIQUE;
ALTER TABLE riders ADD COLUMN IF NOT EXISTS fee_percent NUMERIC(5,2)
    CHECK (fee_percent IS NULL OR (fee_percent >= 1 AND fee_percent <= 50));
ALTER TABLE riders ADD COLUMN IF NOT EXISTS onboarding_status TEXT
    NOT NULL DEFAULT 'pending'
    CHECK (onboarding_status IN ('pending', 'restricted', 'enabled', 'deauthorized'));

-- Index for webhook lookups by stripe_account_id
CREATE INDEX IF NOT EXISTS idx_riders_stripe_account_id ON riders (stripe_account_id);

-- Partial index for public listing (UC-303: exclude incomplete riders)
CREATE INDEX IF NOT EXISTS idx_riders_public_enabled
    ON riders (is_public)
    WHERE onboarding_status = 'enabled';

COMMENT ON COLUMN riders.stripe_account_id IS 'Stripe Connect Express account id (acct_*)';
COMMENT ON COLUMN riders.fee_percent IS 'Per-rider application_fee_percent override (NULL = default)';
COMMENT ON COLUMN riders.onboarding_status IS 'pending | restricted | enabled | deauthorized';
