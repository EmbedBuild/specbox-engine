-- ============================================================================
-- 002_stripe_subscriptions.sql — SpecBox /stripe-standard template
--
-- One row per active or historical Stripe Subscription. Updated by the
-- stripe-webhook Edge Function from customer.subscription.* events.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.stripe_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES public.stripe_customers(id) ON DELETE CASCADE,
    stripe_subscription_id TEXT NOT NULL,
    price_id TEXT,
    status TEXT NOT NULL,
    -- 'incomplete' | 'incomplete_expired' | 'trialing' | 'active' |
    -- 'past_due' | 'canceled' | 'unpaid' | 'paused'
    current_period_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT false,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT stripe_subscriptions_stripe_id_unique UNIQUE (stripe_subscription_id)
);

CREATE INDEX IF NOT EXISTS idx_stripe_subs_customer_status
    ON public.stripe_subscriptions(customer_id, status);

CREATE INDEX IF NOT EXISTS idx_stripe_subs_active_lookup
    ON public.stripe_subscriptions(customer_id)
    WHERE status IN ('active', 'trialing');

DROP TRIGGER IF EXISTS trg_stripe_subscriptions_updated_at ON public.stripe_subscriptions;
CREATE TRIGGER trg_stripe_subscriptions_updated_at
    BEFORE UPDATE ON public.stripe_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.stripe_subscriptions IS
    'Stripe Subscription state for /stripe-standard. Source of truth lives in Stripe; this is a webhook-driven cache.';
