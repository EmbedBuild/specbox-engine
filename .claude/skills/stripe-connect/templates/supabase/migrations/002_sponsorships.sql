-- ----------------------------------------------------------------------------
-- 002_sponsorships.sql
--
-- Main table linking fans to the riders they sponsor via Stripe subscriptions
-- on the rider's connected account. One row per (fan, rider, subscription).
--
-- Status lifecycle (mirrors Stripe Subscription.status):
--   incomplete   → initial state right after create-fan-subscription
--   active       → invoice.paid received (sponsorship granted)
--   past_due     → invoice.payment_failed (retry UX)
--   canceled     → customer.subscription.deleted or fan cancels
--   trialing     → (unused in v1, kept for forward-compat)
--   paused       → (unused in v1, kept for forward-compat)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sponsorships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    fan_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    rider_id UUID NOT NULL REFERENCES riders(id) ON DELETE CASCADE,

    stripe_subscription_id TEXT UNIQUE NOT NULL,
    stripe_account_id TEXT NOT NULL,

    amount INTEGER, -- price in cents (informational; source of truth is Stripe)
    currency TEXT NOT NULL DEFAULT 'eur',

    status TEXT NOT NULL DEFAULT 'incomplete'
        CHECK (status IN ('incomplete', 'active', 'past_due', 'canceled', 'trialing', 'paused')),

    current_period_end TIMESTAMPTZ,
    cancel_at TIMESTAMPTZ,
    last_paid_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Fast lookups for the webhook (by subscription id)
CREATE INDEX IF NOT EXISTS idx_sponsorships_stripe_subscription_id
    ON sponsorships (stripe_subscription_id);

-- Fast lookups for fan's "my subscriptions" view
CREATE INDEX IF NOT EXISTS idx_sponsorships_fan_status
    ON sponsorships (fan_id, status);

-- Fast lookups for rider's "my sponsors" dashboard
CREATE INDEX IF NOT EXISTS idx_sponsorships_rider_status
    ON sponsorships (rider_id, status);

COMMENT ON TABLE sponsorships IS 'Fan-to-rider recurring sponsorships via Stripe Connect Direct charges';
COMMENT ON COLUMN sponsorships.stripe_account_id IS 'Denormalized from riders for faster webhook routing';
