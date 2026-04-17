// ----------------------------------------------------------------------------
// create-rider-dashboard-link — SpecBox /stripe-connect template
//
// Returns a one-time login URL for the rider's Stripe Express Dashboard.
// The Express Dashboard is hosted by Stripe and lets the rider see: balance,
// payouts, incoming payments, tax forms, bank details. It is the recommended
// UX for Connect Express accounts — no need to build a custom dashboard.
//
// Link expires in ~5 minutes and is single-use. Frontend opens it in a new tab.
//
// Request body (JSON):
//   { rider_id: string }
//
// Response (JSON):
//   { url: string }
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
  if (req.method !== 'POST') return json({ error: 'method_not_allowed' }, 405);

  try {
    const { rider_id } = await req.json();
    if (!rider_id) return json({ error: 'missing_params' }, 400);

    const { data: rider, error } = await supabase
      .from('riders')
      .select('stripe_account_id, onboarding_status')
      .eq('id', rider_id)
      .single();

    if (error || !rider?.stripe_account_id) {
      return json({ error: 'rider_not_onboarded' }, 409);
    }
    if (rider.onboarding_status !== 'enabled') {
      return json({ error: 'onboarding_incomplete' }, 409);
    }

    const link = await stripe.accounts.createLoginLink(rider.stripe_account_id);
    return json({ url: link.url });
  } catch (e) {
    console.error('create-rider-dashboard-link error', e);
    return json({ error: 'internal_error', message: (e as Error).message }, 500);
  }
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
