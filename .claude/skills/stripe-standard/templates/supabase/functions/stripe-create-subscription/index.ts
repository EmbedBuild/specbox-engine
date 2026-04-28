// ----------------------------------------------------------------------------
// stripe-create-subscription — SpecBox /stripe-standard template
//
// Creates a Subscription with payment_behavior='default_incomplete' so the
// frontend can confirm SCA/3DS in-page via the returned client_secret.
//
// Supports the 3 sub modalities:
//   single_sub:  body = { price_id }
//   tiered_sub:  body = { price_id }   — tier choice happens client-side
//   metered:     body = { price_id }   — usage is reported via stripe-report-usage
//
// Required env vars:
//   STRIPE_SECRET_KEY
//   SUPABASE_URL
//   SUPABASE_SERVICE_ROLE_KEY
// ----------------------------------------------------------------------------

import Stripe from 'npm:stripe@^14';
import { createClient } from 'npm:@supabase/supabase-js@^2';

const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY')!, {
  apiVersion: '2024-11-20.acacia',
});

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
);

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('method_not_allowed', { status: 405 });

  const authHeader = req.headers.get('Authorization');
  if (!authHeader?.startsWith('Bearer ')) return new Response('unauthorized', { status: 401 });
  const { data: { user }, error: authErr } = await supabase.auth.getUser(authHeader.slice(7));
  if (authErr || !user) return new Response('unauthorized', { status: 401 });

  let body: { price_id?: string };
  try {
    body = await req.json();
  } catch {
    return new Response('invalid_body', { status: 400 });
  }
  if (!body.price_id) return new Response('missing_price_id', { status: 400 });

  // Look up customer (or fail if missing — caller should have invoked
  // stripe-create-customer first).
  const { data: customerRow } = await supabase
    .from('stripe_customers')
    .select('stripe_customer_id')
    .eq('user_id', user.id)
    .single();

  if (!customerRow) {
    return new Response('customer_not_found', { status: 404 });
  }

  // Reject if user already has an active sub (UX idempotency: redirect to
  // billing portal client-side).
  const { data: existingSub } = await supabase
    .from('stripe_subscriptions')
    .select('stripe_subscription_id, status')
    .eq('customer_id', customerRow.stripe_customer_id)
    .in('status', ['active', 'trialing'])
    .maybeSingle();

  if (existingSub) {
    return Response.json(
      { error: 'subscription_already_active', subscription_id: existingSub.stripe_subscription_id },
      { status: 409 },
    );
  }

  let sub: Stripe.Subscription;
  try {
    sub = await stripe.subscriptions.create({
      customer: customerRow.stripe_customer_id,
      items: [{ price: body.price_id }],
      payment_behavior: 'default_incomplete',
      payment_settings: {
        save_default_payment_method: 'on_subscription',
      },
      expand: ['latest_invoice.payment_intent', 'pending_setup_intent'],
      metadata: { user_id: user.id, source: 'specbox-standard' },
    });
  } catch (err) {
    console.error('stripe.subscriptions.create failed', err);
    return new Response('stripe_unavailable', { status: 503 });
  }

  // The client_secret to confirm payment lives either on payment_intent
  // (for paid subs) or on pending_setup_intent (for trial-only setup).
  const latestInvoice = sub.latest_invoice as Stripe.Invoice | null;
  const pi = latestInvoice?.payment_intent as Stripe.PaymentIntent | null;
  const setupIntent = sub.pending_setup_intent as Stripe.SetupIntent | null;
  const clientSecret = pi?.client_secret ?? setupIntent?.client_secret ?? null;

  return Response.json({
    subscription_id: sub.id,
    client_secret: clientSecret,
    status: sub.status,
  });
});
