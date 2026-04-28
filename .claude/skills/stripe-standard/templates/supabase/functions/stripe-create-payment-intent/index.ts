// ----------------------------------------------------------------------------
// stripe-create-payment-intent — SpecBox /stripe-standard template
//
// One-shot purchases: creates a PaymentIntent with automatic_payment_methods
// so Apple Pay / Google Pay / Express Checkout (Link, etc.) appear automatically.
//
// Body: { amount: number (cents), currency?: string ('eur' default), metadata?: object }
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

  let body: { amount?: number; currency?: string; metadata?: Record<string, string> };
  try {
    body = await req.json();
  } catch {
    return new Response('invalid_body', { status: 400 });
  }
  if (!body.amount || body.amount < 50) {
    // Stripe min charge in EUR/USD is ~0.50.
    return new Response('amount_too_small', { status: 400 });
  }

  const { data: customerRow } = await supabase
    .from('stripe_customers')
    .select('stripe_customer_id')
    .eq('user_id', user.id)
    .maybeSingle();

  let pi: Stripe.PaymentIntent;
  try {
    pi = await stripe.paymentIntents.create({
      amount: body.amount,
      currency: body.currency ?? 'eur',
      customer: customerRow?.stripe_customer_id,
      automatic_payment_methods: { enabled: true },
      metadata: { user_id: user.id, source: 'specbox-standard', ...(body.metadata ?? {}) },
    });
  } catch (err) {
    console.error('stripe.paymentIntents.create failed', err);
    return new Response('stripe_unavailable', { status: 503 });
  }

  return Response.json({
    payment_intent_id: pi.id,
    client_secret: pi.client_secret,
    amount: pi.amount,
    currency: pi.currency,
  });
});
