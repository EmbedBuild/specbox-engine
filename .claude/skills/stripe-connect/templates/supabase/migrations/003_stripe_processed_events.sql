-- ----------------------------------------------------------------------------
-- 003_stripe_processed_events.sql
--
-- Idempotency tracking table for the Stripe webhook handler.
-- Every received event.id is recorded here BEFORE processing. When a duplicate
-- arrives (Stripe retries on timeout or non-2xx), we see it already exists
-- and return 200 without re-processing.
--
-- processed_at is NULL until processing completes. Rows with received_at set
-- but processed_at NULL are a signal for ops to investigate handler failures.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS stripe_processed_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL
        CHECK (source IN ('platform', 'connect')),
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);

-- Observability: find unprocessed events quickly
CREATE INDEX IF NOT EXISTS idx_stripe_events_unprocessed
    ON stripe_processed_events (received_at DESC)
    WHERE processed_at IS NULL;

-- Observability: recent events by type
CREATE INDEX IF NOT EXISTS idx_stripe_events_type_time
    ON stripe_processed_events (event_type, received_at DESC);

COMMENT ON TABLE stripe_processed_events IS 'Webhook idempotency — prevents processing the same event twice';
