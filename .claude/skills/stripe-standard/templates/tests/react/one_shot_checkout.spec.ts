// ----------------------------------------------------------------------------
// one_shot_checkout.spec.ts — SpecBox /stripe-standard test template
//
// E2E for the one-shot embedded checkout flow.
// ----------------------------------------------------------------------------

import { test, expect } from '@playwright/test';

const STRIPE_PRODUCT_PRICE = process.env.STRIPE_TEST_ONE_SHOT_PRICE_ID ?? 'price_ONESHOT';

test.describe('UC-405 one-shot checkout (embedded)', () => {
    test('embedded checkout → succeed → success page', async ({ page }) => {
        await page.goto('/login');
        await page.fill('input[name="email"]', `test-${Date.now()}@example.com`);
        await page.fill('input[name="password"]', 'password123');
        await page.click('button[type="submit"]');

        await page.goto('/buy');

        // The CheckoutEmbedded component mounts a Stripe iframe inside the page
        // (no redirect). Wait for it.
        const checkoutFrame = page.frameLocator('iframe[src*="stripe.com"]');
        await checkoutFrame.locator('input[name="cardNumber"]').fill('4242 4242 4242 4242');
        await checkoutFrame.locator('input[name="cardExpiry"]').fill('12 / 34');
        await checkoutFrame.locator('input[name="cardCvc"]').fill('123');
        await checkoutFrame
            .locator('button:has-text("Pay")')
            .or(checkoutFrame.locator('button:has-text("Pagar")'))
            .click();

        // The CheckoutEmbeddedProvider's onComplete fires when the payment
        // completes; the consumer can use that to navigate. Default route used
        // by the template is /thank-you.
        await page.waitForURL(/\/thank-you|\/checkout\/return/, { timeout: 60_000 });
        await expect(page.locator('h1')).toContainText(/Listo|Thank you/);
    });
});
