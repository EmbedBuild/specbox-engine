/**
 * Tests for stripe-safety-guard.mjs
 *
 * Runs the hook as a child process for each synthetic case and asserts exit code:
 *   - exit 2 → hook blocked the pattern (desired for positive cases)
 *   - exit 0 → hook allowed the write (desired for negative cases)
 *
 * Run: node --test .quality/hooks/stripe-safety-guard.test.mjs
 *
 * NFR (PRD AC-29): false positive rate < 5% on 30 cases.
 * Positive cases = 10, negative cases = 20, expected: all 30 produce correct verdict.
 */

import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const HOOK_PATH = resolve(__dirname, '../../.claude/hooks/stripe-safety-guard.mjs');

/**
 * Run the hook with a synthetic tool input payload.
 * Returns { code, stdout, stderr }.
 */
function runHook({ filePath, content = '', newString = '' }) {
  const payload = JSON.stringify({
    tool_name: 'Write',
    tool_input: { file_path: filePath, content, new_string: newString },
    file_path: filePath,
    content,
    new_string: newString,
  });
  const result = spawnSync('node', [HOOK_PATH], {
    input: payload,
    encoding: 'utf-8',
  });
  return {
    code: result.status,
    stdout: result.stdout || '',
    stderr: result.stderr || '',
  };
}

// ---------------------------------------------------------------------------
// Synthetic "looks-like-a-Stripe-key" string builder.
// We NEVER embed the full `sk_live_*` literal in this file — GitHub's secret
// scanner would flag it (and it does, even for clearly fake strings). Instead,
// we build the test strings at runtime from harmless parts. The hook's regex
// still matches them at runtime because the regex is evaluated against the
// concatenated string, not against the source code of this test.
// ---------------------------------------------------------------------------
const LIVE_PREFIX = ['sk', 'live'].join('_') + '_';
const TEST_PREFIX = ['sk', 'test'].join('_') + '_';

/** Build a synthetic live-key-like string. */
function liveKey(suffix) {
  return LIVE_PREFIX + suffix;
}
/** Build a synthetic test-key-like string. */
function testKey(suffix) {
  return TEST_PREFIX + suffix;
}

// ============================================================
// POSITIVE CASES (hook MUST block — exit 2)
// ============================================================

test('POS-01: sk_live_ hardcoded in billing file blocks', () => {
  const content = `const stripe = new Stripe("${liveKey('51AbcDefGhIjKlMnOpQrStUvWxYz')}");`;
  const { code } = runHook({ filePath: 'src/billing/client.ts', content });
  assert.equal(code, 2);
});

test('POS-02: webhook handler without constructEvent blocks', () => {
  const content = `
import Stripe from 'stripe';
export async function handler(req) {
  const body = await req.text();
  const event = JSON.parse(body); // naive — no signature verification
  if (event.type === 'invoice.paid') { /* ... */ }
  return new Response('OK');
}
`;
  const { code } = runHook({
    filePath: 'supabase/functions/stripe-webhook/index.ts',
    content,
  });
  assert.equal(code, 2);
});

test('POS-03: webhook handler with constructEvent but without idempotency blocks', () => {
  const content = `
import Stripe from 'stripe';
const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY'));
export async function handler(req) {
  const sig = req.headers.get('stripe-signature');
  const event = await stripe.webhooks.constructEventAsync(
    await req.text(), sig, Deno.env.get('STRIPE_WEBHOOK_SECRET')
  );
  // Bug: processes without any idempotency check at all
  if (event.type === 'invoice.paid') await provision(event.data.object);
  return new Response('OK');
}
`;
  const { code } = runHook({
    filePath: 'supabase/functions/stripe-webhook/index.ts',
    content,
  });
  assert.equal(code, 2);
});

test('POS-04: redirectToCheckout import blocks', () => {
  const content = `
import { loadStripe } from '@stripe/stripe-js';
const stripe = await loadStripe(process.env.PK);
await stripe.redirectToCheckout({ sessionId });
`;
  const { code } = runHook({
    filePath: 'src/billing/checkout.ts',
    content,
  });
  assert.equal(code, 2);
});

test('POS-05: ui_mode hosted blocks', () => {
  const content = `
const session = await stripe.checkout.sessions.create({
  ui_mode: 'hosted',
  mode: 'subscription',
});
`;
  const { code } = runHook({
    filePath: 'supabase/functions/create-fan-subscription/index.ts',
    content,
  });
  assert.equal(code, 2);
});

test('POS-06: Payment Link URL hardcoded blocks', () => {
  const content = `
export const UPGRADE_URL = 'https://buy.stripe.com/test_abcdef123456';
`;
  const { code } = runHook({
    filePath: 'src/billing/constants.ts',
    content,
  });
  assert.equal(code, 2);
});

test('POS-07: sk_live in Edge Function blocks', () => {
  const content = `const stripe = new Stripe('${liveKey('abcdefghijklmnop1234567890')}');`;
  const { code } = runHook({
    filePath: 'supabase/functions/create-fan-subscription/index.ts',
    content,
  });
  assert.equal(code, 2);
});

test('POS-08: webhook in lib/billing without signature verification blocks', () => {
  const content = `
export class StripeWebhookHandler {
  async process(req) {
    const body = await req.text();
    const event = JSON.parse(body);
    return event;
  }
}
`;
  const { code } = runHook({
    filePath: 'lib/billing/stripe_webhook_handler.ts',
    content,
  });
  assert.equal(code, 2);
});

test('POS-09: redirectToCheckout in lib/billing blocks', () => {
  const content = `
export async function goToCheckout() {
  const s = await loadStripe(KEY);
  return s.redirectToCheckout({ sessionId: 'cs_test_123' });
}
`;
  const { code } = runHook({
    filePath: 'lib/billing/checkout.ts',
    content,
  });
  assert.equal(code, 2);
});

test('POS-10: multiple Payment Links in same file blocks', () => {
  const content = `
const URLS = {
  basic: 'https://buy.stripe.com/abc123xyz',
  pro: 'https://buy.stripe.com/pro456xyz',
};
`;
  const { code } = runHook({
    filePath: 'src/billing/plans.ts',
    content,
  });
  assert.equal(code, 2);
});

// ============================================================
// NEGATIVE CASES (hook MUST allow — exit 0)
// ============================================================

test('NEG-01: file outside billing path is ignored even with sk_live', () => {
  const content = `const LEAK = '${liveKey('abcdefghijklmnop1234567890')}';`;
  const { code } = runHook({
    filePath: 'src/utils/logger.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-02: .env file with sk_test is allowed', () => {
  const content = `STRIPE_SECRET_KEY=${testKey('abcdefghijklmnop1234567890')}\nSTRIPE_WEBHOOK_SECRET=whsec_xxx`;
  const { code } = runHook({
    filePath: 'src/billing/.env.example',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-03: markdown doc mentioning sk_live is allowed', () => {
  const content = `# Setup\n\nNEVER commit ${LIVE_PREFIX} keys to code. Use env vars.`;
  const { code } = runHook({
    filePath: 'src/billing/README.md',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-04: correct webhook handler with signature + idempotency passes', () => {
  const content = `
import Stripe from 'stripe';
const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY'));

export async function handler(req) {
  const sig = req.headers.get('stripe-signature');
  const event = await stripe.webhooks.constructEventAsync(
    await req.text(), sig, Deno.env.get('STRIPE_WEBHOOK_SECRET')
  );
  const { data: existing } = await supabase
    .from('stripe_processed_events')
    .select('event_id').eq('event_id', event.id).maybeSingle();
  if (existing) return new Response('OK', { status: 200 });
  // ... process ...
  await supabase.from('stripe_processed_events').insert({
    event_id: event.id, event_type: event.type, received_at: new Date().toISOString(),
  });
  return new Response('OK', { status: 200 });
}
`;
  const { code } = runHook({
    filePath: 'supabase/functions/stripe-webhook/index.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-05: Payment Element (correct embedded pattern) passes', () => {
  const content = `
import { Elements, PaymentElement, ExpressCheckoutElement } from '@stripe/react-stripe-js';
export function CheckoutForm({ clientSecret }) {
  return (
    <Elements stripe={stripePromise} options={{ clientSecret }}>
      <PaymentElement />
      <ExpressCheckoutElement />
    </Elements>
  );
}
`;
  const { code } = runHook({
    filePath: 'src/billing/sponsor-rider-form.tsx',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-06: stripe import using env var passes', () => {
  const content = `
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, {
  apiVersion: '2024-11-20.acacia',
});
`;
  const { code } = runHook({
    filePath: 'src/billing/stripe-client.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-07: Flutter Payment Sheet passes (no hosted, no Payment Link)', () => {
  const content = `
await Stripe.instance.initPaymentSheet(
  paymentSheetParameters: SetupPaymentSheetParameters(
    paymentIntentClientSecret: secret,
    merchantDisplayName: 'Marketplace',
  ),
);
await Stripe.instance.presentPaymentSheet();
`;
  const { code } = runHook({
    filePath: 'lib/billing/stripe_service.dart',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-08: create-subscription with transfer_data (Direct charges) passes', () => {
  const content = `
import Stripe from 'stripe';
const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY'));
export async function handler(req) {
  const { rider_id, price_id } = await req.json();
  const sub = await stripe.subscriptions.create({
    customer: customerId,
    items: [{ price: price_id }],
    application_fee_percent: rider.fee_percent,
    payment_behavior: 'default_incomplete',
  }, { stripeAccount: rider.stripe_account_id });
  return new Response(JSON.stringify(sub));
}
`;
  const { code } = runHook({
    filePath: 'supabase/functions/create-fan-subscription/index.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-09: escape hatch line-level ignore bypasses sk_live detection', () => {
  const content = `
// stripe-safety-guard:ignore
const LEGACY = '${liveKey('thisIsIntentionalForLegacyMigration123')}';
`;
  const { code } = runHook({
    filePath: 'src/billing/legacy.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-10: file-level disable bypasses all checks', () => {
  const content = `
// stripe-safety-guard:disable-file
// Legacy file under migration, ignore all checks
await stripe.redirectToCheckout({ sessionId });
`;
  const { code } = runHook({
    filePath: 'src/billing/legacy.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-11: test file is ignored', () => {
  const content = `
test('rejects sk_live', () => {
  const bad = '${liveKey('abcdefghijklmnop1234567890')}';
  expect(shouldBlock(bad)).toBe(true);
});
`;
  const { code } = runHook({
    filePath: 'src/billing/checkout.test.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-12: spec file is ignored', () => {
  const content = `
describe('webhook', () => {
  it('processes events', () => {
    // intentional ${liveKey('abcdefghijklmnop123456')} for test
  });
});
`;
  const { code } = runHook({
    filePath: 'src/billing/webhook.spec.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-13: tests/ directory is ignored', () => {
  const content = `const sample = '${liveKey('abcdefghijklmnop1234567890')}';`;
  const { code } = runHook({
    filePath: 'tests/billing/fixtures.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-14: cancel-subscription function without webhook concerns passes', () => {
  const content = `
import Stripe from 'stripe';
const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY'));
export async function handler(req) {
  const { subscription_id, stripe_account_id } = await req.json();
  await stripe.subscriptions.cancel(subscription_id, {
    stripeAccount: stripe_account_id,
  });
  return new Response('OK');
}
`;
  const { code } = runHook({
    filePath: 'supabase/functions/cancel-fan-subscription/index.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-15: React hook use-sponsorship.ts passes', () => {
  const content = `
export function useSponsorship(riderId, priceId) {
  const [state, setState] = useState({ status: 'idle' });
  const submit = async () => {
    setState({ status: 'loading' });
    const { clientSecret } = await fetch('/api/create-fan-subscription', {
      method: 'POST',
      body: JSON.stringify({ riderId, priceId }),
    }).then(r => r.json());
    const { error } = await stripe.confirmPayment({ elements, clientSecret });
    setState(error ? { status: 'error', error } : { status: 'success' });
  };
  return { state, submit };
}
`;
  const { code } = runHook({
    filePath: 'src/billing/use-sponsorship.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-16: short sk_live-like token that is not a real key passes (regex requires 10+ chars)', () => {
  // Regex requires sk_live_ followed by 10+ alphanumeric — this has only 5
  const content = `const notKey = '${liveKey('abc12')}'; // too short to match`;
  const { code } = runHook({
    filePath: 'src/billing/types.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-17: generated file .g.dart with sk_live mention passes (not in billing path)', () => {
  const content = `// GENERATED CODE — ${liveKey('abcdefghijklmnop1234567890')} in comment`;
  const { code } = runHook({
    filePath: 'lib/models/payment.g.dart',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-18: non-webhook file in billing without constructEvent passes', () => {
  const content = `
// Just a helper — not a webhook handler
export function formatAmount(cents) {
  return (cents / 100).toFixed(2);
}
`;
  const { code } = runHook({
    filePath: 'src/billing/format.ts',
    content,
  });
  assert.equal(code, 0);
});

test('NEG-19: empty content passes', () => {
  const { code } = runHook({
    filePath: 'src/billing/new-file.ts',
    content: '',
  });
  assert.equal(code, 0);
});

test('NEG-20: webhook handler with idempotency-disable escape hatch passes', () => {
  const content = `
// stripe-safety-guard:ignore-idempotency
// Justification: this endpoint only handles account.updated which is naturally idempotent
import Stripe from 'stripe';
const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY'));
export async function handler(req) {
  const sig = req.headers.get('stripe-signature');
  const event = await stripe.webhooks.constructEventAsync(
    await req.text(), sig, Deno.env.get('STRIPE_WEBHOOK_SECRET')
  );
  return new Response('OK');
}
`;
  const { code } = runHook({
    filePath: 'supabase/functions/account-updates-webhook/index.ts',
    content,
  });
  assert.equal(code, 0);
});
