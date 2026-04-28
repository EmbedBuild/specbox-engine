// ----------------------------------------------------------------------------
// stripe-create-portal-session — SpecBox /stripe-standard template
//
// Opens the Stripe-hosted Customer Portal where the user can manage payment
// methods, view invoices, cancel subscriptions, etc. The portal must be
// pre-configured in the Stripe Dashboard (this Edge Function only invokes it).
//
// In Standard mode the customer lives in OUR Stripe account so the portal
// works out of the box. (In Connect, customers live in connected accounts
// and the portal needs the seller to enable it.)
//
// Body: { return_url?: string }   defaults to FRONTEND_URL/account
//
// Required env vars:
//   STRIPE_SECRET_KEY
//   STRIPE_FRONTEND_URL
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

  const { data: customerRow } = await supabase
    .from('stripe_customers')
    .select('stripe_customer_id')
    .eq('user_id', user.id)
    .maybeSingle();

  if (!customerRow) {
    return new Response('customer_not_found', { status: 404 });
  }

  let body: { return_url?: string } = {};
  try {
    body = await req.json();
  } catch {
    // Body is optional; ignore parse errors.
  }

  let session: Stripe.BillingPortal.Session;
  try {
    session = await stripe.billingPortal.sessions.create({
      customer: customerRow.stripe_customer_id,
      return_url: body.return_url ?? `${FRONTEND_URL}/account`,
    });
  } catch (err) {
    console.error('stripe.billingPortal.sessions.create failed', err);
    return new Response('stripe_unavailable', { status: 503 });
  }

  return Response.json({ url: session.url });
});
