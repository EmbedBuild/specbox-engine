-- ============================================================================
-- 003_stripe_processed_events.sql — SpecBox /stripe-standard template
--
-- Webhook idempotency table. The stripe-webhook Edge Function inserts a row
-- here BEFORE processing each event. The unique constraint on event_id
-- guarantees each event is processed at most once even when Stripe retries.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.stripe_processed_events (
    event_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stripe_processed_events_type
    ON public.stripe_processed_events(type);

COMMENT ON TABLE public.stripe_processed_events IS
    'Webhook deduplication for /stripe-standard. service_role only — no RLS.';
