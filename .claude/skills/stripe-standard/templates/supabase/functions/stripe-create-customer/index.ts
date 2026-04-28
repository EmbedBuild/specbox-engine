// ----------------------------------------------------------------------------
// stripe-create-customer — SpecBox /stripe-standard template
//
// Creates (or returns existing) Stripe Customer for the authenticated user.
// Idempotent: if stripe_customers already has a row for this user, return it
// without calling Stripe.
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

  // ---- JWT auth ----
  const authHeader = req.headers.get('Authorization');
  if (!authHeader?.startsWith('Bearer ')) {
    return new Response('unauthorized', { status: 401 });
  }
  const jwt = authHeader.slice(7);
  const { data: { user }, error: authErr } = await supabase.auth.getUser(jwt);
  if (authErr || !user) return new Response('unauthorized', { status: 401 });

  // ---- Idempotency: existing customer? ----
  const { data: existing } = await supabase
    .from('stripe_customers')
    .select('id, stripe_customer_id')
    .eq('user_id', user.id)
    .maybeSingle();

  if (existing) {
    return Response.json({
      customer_id: existing.stripe_customer_id,
      created: false,
    });
  }

  // ---- Create in Stripe + persist ----
  let customer: Stripe.Customer;
  try {
    customer = await stripe.customers.create({
      email: user.email ?? undefined,
      metadata: {
        user_id: user.id,
        source: 'specbox-standard',
      },
    });
  } catch (err) {
    console.error('stripe.customers.create failed', err);
    return new Response('stripe_unavailable', { status: 503 });
  }

  const { error: insertErr } = await supabase
    .from('stripe_customers')
    .insert({
      user_id: user.id,
      stripe_customer_id: customer.id,
    });

  if (insertErr) {
    // Race condition: another request created it in the meantime.
    // Re-read and return the existing one.
    if (insertErr.code === '23505') {
      const { data: race } = await supabase
        .from('stripe_customers')
        .select('stripe_customer_id')
        .eq('user_id', user.id)
        .single();
      return Response.json({
        customer_id: race?.stripe_customer_id ?? customer.id,
        created: false,
      });
    }
    console.error('failed to persist stripe_customers', insertErr);
    return new Response('internal_error', { status: 500 });
  }

  return Response.json({
    customer_id: customer.id,
    created: true,
  });
});
