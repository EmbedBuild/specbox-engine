-- ============================================================================
-- 004_rls_policies.sql — SpecBox /stripe-standard template
--
-- RLS over stripe_customers and stripe_subscriptions:
--   - Authenticated users can SELECT only their own rows.
--   - service_role (Edge Functions) can do everything.
--
-- stripe_processed_events stays without RLS — only Edge Functions touch it.
-- ============================================================================

ALTER TABLE public.stripe_customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stripe_subscriptions ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- stripe_customers
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS "users_read_own_customer" ON public.stripe_customers;
CREATE POLICY "users_read_own_customer"
    ON public.stripe_customers
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "service_role_full_customers" ON public.stripe_customers;
CREATE POLICY "service_role_full_customers"
    ON public.stripe_customers
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- stripe_subscriptions
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS "users_read_own_subscriptions" ON public.stripe_subscriptions;
CREATE POLICY "users_read_own_subscriptions"
    ON public.stripe_subscriptions
    FOR SELECT
    TO authenticated
    USING (
        customer_id IN (
            SELECT id FROM public.stripe_customers WHERE user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "service_role_full_subscriptions" ON public.stripe_subscriptions;
CREATE POLICY "service_role_full_subscriptions"
    ON public.stripe_subscriptions
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

COMMENT ON POLICY "users_read_own_customer" ON public.stripe_customers IS
    'Users can only read their own Stripe customer row. Writes go through service_role via Edge Functions.';

COMMENT ON POLICY "users_read_own_subscriptions" ON public.stripe_subscriptions IS
    'Users can only read their own subscriptions. The join through stripe_customers makes ownership transitive.';
