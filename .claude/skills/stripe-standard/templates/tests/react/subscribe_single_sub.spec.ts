// ----------------------------------------------------------------------------
// subscribe_single_sub.spec.ts — SpecBox /stripe-standard test template
//
// E2E acceptance test for the single-subscription flow. Uses Playwright +
// Stripe test cards. Requires a deployed Edge Function and a logged-in test
// user. The skill leaves this file at tests/acceptance/ — the consumer wires
// the env vars before running.
//
// Required env: STRIPE_TEST_PRICE_ID (price object created via stripe-cli or
// setup_products_and_prices).
// ----------------------------------------------------------------------------

import { test, expect } from '@playwright/test';

const STRIPE_PRICE = process.env.STRIPE_TEST_PRICE_ID ?? 'price_PLACEHOLDER';

test.describe('UC-402 single subscription flow', () => {
    test('signup → subscribe → verify active → cancel', async ({ page }) => {
        // 1. Login (consumer-specific helper)
        await page.goto('/login');
        await page.fill('input[name="email"]', `test-${Date.now()}@example.com`);
        await page.fill('input[name="password"]', 'password123');
        await page.click('button[type="submit"]');

        // 2. Open subscription form
        await page.goto('/pricing');
        await page.click(`[data-price-id="${STRIPE_PRICE}"]`);
        await page.click('button:has-text("Continuar")');

        // 3. Fill Stripe Payment Element with test card 4242
        const stripeFrame = page.frameLocator(
            'iframe[name^="__privateStripeFrame"]',
        );
        await stripeFrame.locator('input[name="number"]').fill('4242 4242 4242 4242');
        await stripeFrame.locator('input[name="expiry"]').fill('12 / 34');
        await stripeFrame.locator('input[name="cvc"]').fill('123');
        await stripeFrame.locator('input[name="postalCode"]').fill('28001');
        await page.click('button[type="submit"]:has-text("Suscribirse")');

        // 4. Wait for redirect to /billing/return and verify success
        await page.waitForURL(/\/billing\/return/, { timeout: 30_000 });
        await expect(page.locator('h1')).toContainText('Listo');

        // 5. Verify sub is active in the account screen
        await page.goto('/account');
        await expect(page.locator('[data-testid="sub-status"]')).toHaveText(/active|trialing/i);

        // 6. Cancel via Customer Portal (opens new tab; we just verify the link)
        const portalButton = page.locator('button:has-text("Manage subscription")');
        await expect(portalButton).toBeVisible();
    });

    test('declined card shows readable error', async ({ page }) => {
        await page.goto('/pricing');
        await page.click(`[data-price-id="${STRIPE_PRICE}"]`);
        await page.click('button:has-text("Continuar")');

        const stripeFrame = page.frameLocator(
            'iframe[name^="__privateStripeFrame"]',
        );
        // Stripe test card that always declines.
        await stripeFrame.locator('input[name="number"]').fill('4000 0000 0000 0341');
        await stripeFrame.locator('input[name="expiry"]').fill('12 / 34');
        await stripeFrame.locator('input[name="cvc"]').fill('123');
        await stripeFrame.locator('input[name="postalCode"]').fill('28001');
        await page.click('button[type="submit"]:has-text("Suscribirse")');

        await expect(page.locator('[role="alert"]')).toContainText(/declin|reject/i, {
            timeout: 30_000,
        });
    });
});
