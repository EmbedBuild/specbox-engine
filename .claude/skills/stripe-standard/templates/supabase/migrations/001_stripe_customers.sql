-- ============================================================================
-- 001_stripe_customers.sql — SpecBox /stripe-standard template
--
-- Maps Supabase auth.users (1) ↔ (1) Stripe Customer. One row per user.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.stripe_customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_customer_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT stripe_customers_user_unique UNIQUE (user_id),
    CONSTRAINT stripe_customers_stripe_id_unique UNIQUE (stripe_customer_id)
);

CREATE INDEX IF NOT EXISTS idx_stripe_customers_user_id
    ON public.stripe_customers(user_id);

-- updated_at auto-trigger
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_stripe_customers_updated_at ON public.stripe_customers;
CREATE TRIGGER trg_stripe_customers_updated_at
    BEFORE UPDATE ON public.stripe_customers
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.stripe_customers IS
    'Stripe Customer mapping for /stripe-standard. 1:1 with auth.users.';
