#!/usr/bin/env node
/**
 * stripe-safety-guard.mjs — PreToolUse hook for Write/Edit on Stripe billing files
 * BLOCKING: Detects and blocks 5 common Stripe anti-patterns that cause production bugs.
 *
 * Scope: files under src/billing/, lib/billing/, supabase/functions/stripe-*,
 *        supabase/functions/create-*-subscription/, supabase/functions/*-webhook/
 *
 * Detected anti-patterns (each with exit code 2 + actionable message):
 *   1. sk_live_* hardcoded in code (not in .env* or .md)
 *   2. Webhook handler without constructEvent/constructEventAsync (no signature verification)
 *   3. Webhook handler without stripe_processed_events reference (no idempotency)
 *   4. redirectToCheckout import or ui_mode: 'hosted' (hosted Checkout breaks embedded UX)
 *   5. Payment Link URL (https://buy.stripe.com/) — same reason as #4
 *
 * Escape hatch: place `// stripe-safety-guard:ignore` on the line ABOVE the offending pattern
 *               to skip the check. Use sparingly, document why.
 *
 * v5.25.0 — Stripe Connect skill
 */

import { readFileSync, existsSync } from 'fs';
import { readStdin } from './lib/utils.mjs';

const input = readStdin();

// --- Extract file path and file content from tool input ---
let filePath = '';
let fileContent = '';
try {
  const parsed = JSON.parse(input);
  filePath = parsed.file_path || parsed.tool_input?.file_path || '';
  // For Write: full content is in `content` or `tool_input.content`
  // For Edit: the new content is in `new_string` — we need to scan that + existing file
  fileContent =
    parsed.content ||
    parsed.tool_input?.content ||
    parsed.new_string ||
    parsed.tool_input?.new_string ||
    '';
} catch {
  // Permissive fallback — still try to extract file_path
  const pathMatch = input.match(/"file_path"\s*:\s*"([^"]*)"/);
  filePath = pathMatch ? pathMatch[1] : '';
}

if (!filePath) process.exit(0);

// --- Only guard billing-related files ---
const BILLING_PATH_RE =
  /(^|\/)(src\/billing|lib\/billing|supabase\/functions\/(stripe-|create-.*-subscription|cancel-.*-subscription|.*-webhook))/;

if (!BILLING_PATH_RE.test(filePath)) process.exit(0);

// --- Skip files that are legitimately allowed to contain these patterns ---
// .env* files: CAN contain sk_test_/sk_live_ references (though we still flag sk_live_ hardcoded in .env.example)
// .md files: documentation, allowed to reference everything
// test files: may reference patterns intentionally
if (/(\.env(\..*)?$|\.md$|\.test\.|\.spec\.|(^|\/)tests?\/)/.test(filePath)) process.exit(0);

// --- Build the content to scan ---
// Prefer the new content being written; fall back to existing file if empty
let content = fileContent;
if (!content && existsSync(filePath)) {
  try {
    content = readFileSync(filePath, 'utf-8');
  } catch {
    content = '';
  }
}

if (!content) process.exit(0);

// --- Check for escape hatch marker to disable the hook entirely for this file ---
// (Line-level escapes are handled per-rule below.)
if (/\/\/\s*stripe-safety-guard:disable-file/i.test(content)) process.exit(0);

// --- Helper: line-by-line scan with escape-hatch awareness ---
const lines = content.split('\n');

function lineIsIgnored(lineIdx) {
  if (lineIdx <= 0) return false;
  const prev = lines[lineIdx - 1] || '';
  return /\/\/\s*stripe-safety-guard:ignore/i.test(prev);
}

function findLineMatches(regex) {
  const hits = [];
  for (let i = 0; i < lines.length; i++) {
    if (regex.test(lines[i]) && !lineIsIgnored(i)) {
      hits.push({ line: i + 1, text: lines[i].trim() });
    }
  }
  return hits;
}

// --- Anti-pattern #1: sk_live_* hardcoded ---
const SK_LIVE_RE = /sk_live_[A-Za-z0-9]{10,}/;
const skLiveHits = findLineMatches(SK_LIVE_RE);
if (skLiveHits.length > 0) {
  block(
    'sk_live_* hardcoded in code',
    [
      `Found Stripe LIVE secret key hardcoded in ${filePath}:`,
      ...skLiveHits.slice(0, 3).map(h => `  L${h.line}: ${h.text.slice(0, 120)}`),
      '',
      'Why this is blocked:',
      '  Live secret keys in code leak via git history, CI logs, build artifacts',
      '  and distributed bundles. A leaked sk_live_* gives full API access to',
      '  your Stripe account (move money, refund, read all customer data).',
      '',
      'Correct pattern:',
      '  const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, { ... });',
      '  // Set STRIPE_SECRET_KEY in .env (never committed) or Supabase project secrets',
    ].join('\n'),
  );
}

// --- Anti-pattern #2: Webhook handler without constructEvent / constructEventAsync ---
// Trigger only on files whose path identifies them as webhook handlers
const IS_WEBHOOK_HANDLER = /(^|\/)supabase\/functions\/.*-webhook\/index\.(ts|js)$|(^|\/)(src|lib)\/billing\/.*webhook.*\.(ts|js|dart)$/i.test(
  filePath,
);
if (IS_WEBHOOK_HANDLER) {
  const hasSignatureVerification =
    /constructEvent(Async)?\s*\(/.test(content) ||
    /\/\/\s*stripe-safety-guard:ignore-signature/i.test(content);
  if (!hasSignatureVerification) {
    block(
      'Webhook handler without signature verification',
      [
        `File ${filePath} looks like a Stripe webhook handler but never calls`,
        '  stripe.webhooks.constructEvent(...) or constructEventAsync(...).',
        '',
        'Why this is blocked:',
        '  Without signature verification, anyone who discovers your webhook URL can',
        '  send forged events (fake invoice.paid, fake subscription.deleted) and',
        '  manipulate your database. Verification is mandatory per Stripe docs.',
        '',
        'Correct pattern (Deno / Edge Function):',
        '  const signature = req.headers.get("stripe-signature")!;',
        '  const event = await stripe.webhooks.constructEventAsync(',
        '    await req.text(),',
        '    signature,',
        '    Deno.env.get("STRIPE_WEBHOOK_SECRET")!,',
        '  );',
      ].join('\n'),
    );
  }

  // --- Anti-pattern #3: Webhook handler without idempotency table reference ---
  const hasIdempotencyRef =
    /stripe_processed_events/.test(content) ||
    /\/\/\s*stripe-safety-guard:ignore-idempotency/i.test(content);
  if (!hasIdempotencyRef) {
    block(
      'Webhook handler without idempotency check',
      [
        `File ${filePath} is a webhook handler but never references the`,
        '  stripe_processed_events table.',
        '',
        'Why this is blocked:',
        '  Stripe retries webhooks on non-2xx responses and on network timeouts.',
        '  Without idempotency, the same event (e.g. invoice.paid) can be processed',
        '  multiple times → double provisioning, double emails, double side effects.',
        '  This is the #1 cause of billing bugs in production Stripe integrations.',
        '',
        'Correct pattern:',
        '  // Check BEFORE processing',
        '  const { data: existing } = await supabase',
        '    .from("stripe_processed_events")',
        '    .select("event_id").eq("event_id", event.id).maybeSingle();',
        '  if (existing) return new Response("OK", { status: 200 });',
        '  // ... process event ...',
        '  await supabase.from("stripe_processed_events").insert({',
        '    event_id: event.id, event_type: event.type, received_at: new Date().toISOString(),',
        '  });',
      ].join('\n'),
    );
  }
}

// --- Anti-pattern #4: redirectToCheckout / hosted Checkout mode ---
const HOSTED_CHECKOUT_PATTERNS = [
  /\bredirectToCheckout\s*\(/,
  /ui_mode\s*:\s*['"]hosted['"]/,
  /mode\s*:\s*['"]hosted['"].*checkout/i,
];
for (const re of HOSTED_CHECKOUT_PATTERNS) {
  const hits = findLineMatches(re);
  if (hits.length > 0) {
    block(
      'Hosted Checkout redirect detected (embedded-only policy)',
      [
        `Found hosted Checkout pattern in ${filePath}:`,
        ...hits.slice(0, 3).map(h => `  L${h.line}: ${h.text.slice(0, 120)}`),
        '',
        'Why this is blocked:',
        '  /stripe-connect generates embedded-only integrations by design:',
        '  Payment Element (React) / Payment Sheet (Flutter) + Apple/Google Pay.',
        '  Redirecting the user out of your app to stripe.com breaks UX, prevents',
        '  native payment methods (Apple Pay sheet), and shows Stripe branding',
        '  in the browser URL during checkout. Direct charges + embedded also',
        '  give you full control over error handling and retry UX.',
        '',
        'Correct pattern (React):',
        '  <Elements stripe={stripePromise} options={{ clientSecret }}>',
        '    <PaymentElement />',
        '    <ExpressCheckoutElement />',
        '  </Elements>',
        '  // submit via stripe.confirmPayment({ elements, ... })',
      ].join('\n'),
    );
  }
}

// --- Anti-pattern #5: Payment Link URL hardcoded ---
const PAYMENT_LINK_RE = /https:\/\/buy\.stripe\.com\/[A-Za-z0-9_]+/;
const paymentLinkHits = findLineMatches(PAYMENT_LINK_RE);
if (paymentLinkHits.length > 0) {
  block(
    'Payment Link URL detected (embedded-only policy)',
    [
      `Found Stripe Payment Link in ${filePath}:`,
      ...paymentLinkHits.slice(0, 3).map(h => `  L${h.line}: ${h.text.slice(0, 120)}`),
      '',
      'Why this is blocked:',
      '  Payment Links are hosted checkout — same UX problem as redirectToCheckout.',
      '  They also bypass your own subscription/fee logic (no application_fee_percent,',
      '  no Direct charge routing to connected accounts). They are the wrong tool',
      '  for a marketplace integration.',
      '',
      'Correct pattern:',
      '  Create a Subscription or PaymentIntent on your backend with:',
      '    application_fee_percent: rider.fee_percent,',
      '    transfer_data: { destination: rider.stripe_account_id },  // if destination charges',
      '    // OR pass Stripe-Account header for Direct charges',
      '  Then confirm payment with PaymentElement on the client.',
    ].join('\n'),
  );
}

// All checks passed
process.exit(0);

// ===== helpers =====
function block(title, body) {
  console.log('');
  console.log('============================================================');
  console.log(`  ⛔ STRIPE SAFETY GUARD: ${title}`);
  console.log('============================================================');
  console.log(body);
  console.log('');
  console.log('Escape hatch (use sparingly, document why):');
  console.log('  Add `// stripe-safety-guard:ignore` on the line ABOVE the pattern');
  console.log('  Or `// stripe-safety-guard:disable-file` at the top of the file');
  console.log('============================================================');
  console.log('');
  process.exit(2);
}
