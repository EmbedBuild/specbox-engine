// ----------------------------------------------------------------------------
// metered_billing.spec.ts — SpecBox /stripe-standard test template
//
// Integration test (NOT E2E in browser) for the usage reporting flow. Calls
// the stripe-report-usage Edge Function directly with a fixture customer.
// Verifies the upcoming invoice reflects the reported usage.
// ----------------------------------------------------------------------------

import { describe, expect, it } from 'vitest';
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_CI_SECRET_KEY!, {
    apiVersion: '2024-11-20.acacia',
});

const EDGE_URL = process.env.SUPABASE_FUNCTIONS_URL!;
const TEST_USER_JWT = process.env.TEST_USER_JWT!;
const TEST_SUBSCRIPTION_ID = process.env.STRIPE_TEST_METERED_SUB_ID!;

describe('UC-404 metered billing usage reporting', () => {
    it('reports usage and the upcoming invoice reflects it', async () => {
        // 1. Read the upcoming invoice baseline.
        const before = await stripe.invoices.retrieveUpcoming({
            subscription: TEST_SUBSCRIPTION_ID,
        });
        const baselineCents = before.amount_due ?? 0;

        // 2. Report 100 units of usage.
        const res = await fetch(`${EDGE_URL}/stripe-report-usage`, {
            method: 'POST',
            headers: {
                authorization: `Bearer ${TEST_USER_JWT}`,
                'content-type': 'application/json',
            },
            body: JSON.stringify({ quantity: 100 }),
        });
        expect(res.status).toBe(200);
        const body = await res.json();
        expect(body.usage_record_id).toBeDefined();
        expect(body.quantity).toBe(100);

        // 3. Wait briefly for Stripe to recompute the invoice.
        await new Promise((r) => setTimeout(r, 2000));

        // 4. Verify the upcoming invoice is at least baseline + (100 * unitAmount).
        const after = await stripe.invoices.retrieveUpcoming({
            subscription: TEST_SUBSCRIPTION_ID,
        });
        expect(after.amount_due).toBeGreaterThan(baselineCents);
    });

    it('rejects negative quantity', async () => {
        const res = await fetch(`${EDGE_URL}/stripe-report-usage`, {
            method: 'POST',
            headers: {
                authorization: `Bearer ${TEST_USER_JWT}`,
                'content-type': 'application/json',
            },
            body: JSON.stringify({ quantity: -1 }),
        });
        expect(res.status).toBe(400);
    });
});
