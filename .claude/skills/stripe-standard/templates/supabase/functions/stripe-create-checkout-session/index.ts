// ----------------------------------------------------------------------------
// stripe-create-checkout-session — SpecBox /stripe-standard template
//
// Embedded Checkout fallback. Use this only when the consumer needs a
// Stripe-hosted UI as a fallback (e.g. for very legacy clients). Default
// integration uses PaymentElement / PaymentSheet (UC-402, UC-405) which
// gives more control and better UX.
//
// IMPORTANT: ui_mode='embedded' is hard-coded. The stripe-safety-guard hook
// blocks 'hosted' mode and `redirectToCheckout`. Embedded mode renders
// inside the page via the JS SDK and does not redirect.
//
// Body: { mode: 'subscription' | 'payment', line_items: [{price?, price_data?, quantity}] }
//
// Required env vars:
//   STRIPE_SECRET_KEY
//   STRIPE_FRONTEND_URL  — e.g. https://app.example.com (used for return_url)
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

const FRONTEND_URL = Deno.env.get('STRIPE_FRONTEND_URL') ?? 'http://localhost:3000';

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('method_not_allowed', { status: 405 });

  const authHeader = req.headers.get('Authorization');
  if (!authHeader?.startsWith('Bearer ')) return new Response('unauthorized', { status: 401 });
  const { data: { user }, error: authErr } = await supabase.auth.getUser(authHeader.slice(7));
  if (authErr || !user) return new Response('unauthorized', { status: 401 });

  let body: {
    mode?: 'subscription' | 'payment';
    line_items?: Array<{ price?: string; quantity?: number }>;
  };
  try {
    body = await req.json();
  } catch {
    return new Response('invalid_body', { status: 400 });
  }

  if (!body.mode || !['subscription', 'payment'].includes(body.mode)) {
    return new Response('invalid_mode', { status: 400 });
  }
  if (!body.line_items || body.line_items.length === 0) {
    return new Response('missing_line_items', { status: 400 });
  }

  const { data: customerRow } = await supabase
    .from('stripe_customers')
    .select('stripe_customer_id')
    .eq('user_id', user.id)
    .maybeSingle();

  let session: Stripe.Checkout.Session;
  try {
    session = await stripe.checkout.sessions.create({
      mode: body.mode,
      ui_mode: 'embedded',
      // 'embedded' uses return_url, NOT success_url+cancel_url.
      return_url: `${FRONTEND_URL}/checkout/return?session_id={CHECKOUT_SESSION_ID}`,
      customer: customerRow?.stripe_customer_id,
      line_items: body.line_items.map((li) => ({
        price: li.price,
        quantity: li.quantity ?? 1,
      })),
      metadata: { user_id: user.id, source: 'specbox-standard' },
    });
  } catch (err) {
    console.error('stripe.checkout.sessions.create failed', err);
    return new Response('stripe_unavailable', { status: 503 });
  }

  return Response.json({
    session_id: session.id,
    client_secret: session.client_secret,
  });
});
