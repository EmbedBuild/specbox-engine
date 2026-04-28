// ----------------------------------------------------------------------------
// switch_tier.spec.ts — SpecBox /stripe-standard test template
//
// E2E for tiered subscription upgrade/downgrade flow with prorations.
// ----------------------------------------------------------------------------

import { test, expect } from '@playwright/test';

const PRICE_FREE = process.env.STRIPE_TEST_PRICE_FREE ?? 'price_FREE';
const PRICE_PRO = process.env.STRIPE_TEST_PRICE_PRO ?? 'price_PRO';

test.describe('UC-403 tiered subscriptions', () => {
    test('upgrade free → pro with proration', async ({ page }) => {
        // 1. Subscribe to free first (helper from previous test).
        // ... auth flow elided — use the same as subscribe_single_sub.spec.ts ...

        await page.goto('/pricing');
        await page.click(`[data-price-id="${PRICE_FREE}"]`);
        await page.click('button:has-text("Continuar")');

        const stripeFrame = page.frameLocator('iframe[name^="__privateStripeFrame"]');
        await stripeFrame.locator('input[name="number"]').fill('4242 4242 4242 4242');
        await stripeFrame.locator('input[name="expiry"]').fill('12 / 34');
        await stripeFrame.locator('input[name="cvc"]').fill('123');
        await stripeFrame.locator('input[name="postalCode"]').fill('28001');
        await page.click('button[type="submit"]');
        await page.waitForURL(/billing\/return/);

        // 2. Upgrade to Pro from the management screen.
        await page.goto('/account/subscription');
        await page.click(`[data-tier-key="pro"][data-action="upgrade"]`);
        await page.click('button:has-text("Confirmar")');

        // 3. Verify the active price changes.
        await expect(page.locator('[data-testid="current-tier"]')).toHaveText(/pro/i, {
            timeout: 15_000,
        });

        // 4. The upcoming-invoice indicator should show a proration credit.
        await expect(page.locator('[data-testid="proration-credit"]')).toBeVisible();
    });
});
