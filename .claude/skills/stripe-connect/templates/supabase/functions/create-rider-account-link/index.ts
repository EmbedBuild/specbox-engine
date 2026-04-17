// ----------------------------------------------------------------------------
// create-rider-account-link — SpecBox /stripe-connect template
//
// Creates a Stripe Connect Express account for a rider (if not exists) and
// returns an Account Link URL for onboarding. Frontend redirects the rider
// to this URL; Stripe handles KYC, bank details, tax forms.
//
// On return, the rider lands on {RETURN_URL}?account_id={acct}. The frontend
// should then poll `account.updated` via webhook (Paso 0.5 of the flow) or
// call a status endpoint to detect `charges_enabled` + `payouts_enabled`.
//
// Request body (JSON):
//   { rider_id: string, return_url: string, refresh_url: string }
//
// Response (JSON):
//   { account_id: string, onboarding_url: string }
//
// Required env vars:
//   STRIPE_SECRET_KEY           (platform account)
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
  if (req.method !== 'POST') {
    return json({ error: 'method_not_allowed' }, 405);
  }

  try {
    const { rider_id, return_url, refresh_url } = await req.json();
    if (!rider_id || !return_url || !refresh_url) {
      return json({ error: 'missing_params' }, 400);
    }

    // 1. Load rider + check if Stripe account already exists
    const { data: rider, error: riderErr } = await supabase
      .from('riders')
      .select('id, email, stripe_account_id')
      .eq('id', rider_id)
      .single();

    if (riderErr || !rider) return json({ error: 'rider_not_found' }, 404);

    let accountId = rider.stripe_account_id;

    // 2. Create Express account if missing
    if (!accountId) {
      const account = await stripe.accounts.create({
        type: 'express',
        country: 'ES', // {default_country} — change if needed
        email: rider.email,
        capabilities: {
          card_payments: { requested: true },
          transfers: { requested: true },
        },
        metadata: { rider_id },
      });
      accountId = account.id;

      await supabase
        .from('riders')
        .update({
          stripe_account_id: accountId,
          onboarding_status: 'pending',
        })
        .eq('id', rider_id);
    }

    // 3. Create Account Link for onboarding
    const link = await stripe.accountLinks.create({
      account: accountId,
      refresh_url,
      return_url,
      type: 'account_onboarding',
    });

    return json({ account_id: accountId, onboarding_url: link.url });
  } catch (e) {
    console.error('create-rider-account-link error', e);
    return json({ error: 'internal_error', message: (e as Error).message }, 500);
  }
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
