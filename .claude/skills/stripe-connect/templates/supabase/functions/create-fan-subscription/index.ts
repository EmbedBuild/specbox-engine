// ----------------------------------------------------------------------------
// create-fan-subscription — SpecBox /stripe-connect template
//
// Creates a Subscription on the RIDER's connected account (Direct charge),
// with a dynamic application_fee_percent read from `riders.fee_percent` (fallback
// to DEFAULT_APPLICATION_FEE_PERCENT env var if the column is NULL).
//
// Uses `payment_behavior: 'default_incomplete'` + expanded `pending_setup_intent`
// so the client can confirm the first payment with Payment Element / Payment Sheet.
// Works with Apple Pay + Google Pay via Express Checkout Element automatically.
//
// Request body (JSON):
//   { fan_id: string, rider_id: string, price_id: string }
//
// Response (JSON):
//   { subscription_id: string, client_secret: string, stripe_account_id: string }
//
// The frontend uses `stripe_account_id` to scope `<Elements>` to the connected
// account, and `client_secret` to confirm the payment in-app.
//
// Required env vars:
//   STRIPE_SECRET_KEY
//   DEFAULT_APPLICATION_FEE_PERCENT   (e.g. "15" — used when rider.fee_percent IS NULL)
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

const DEFAULT_FEE_PERCENT = Number(
  Deno.env.get('DEFAULT_APPLICATION_FEE_PERCENT') ?? '15',
);

Deno.serve(async (req) => {
  if (req.method !== 'POST') return json({ error: 'method_not_allowed' }, 405);

  try {
    const { fan_id, rider_id, price_id } = await req.json();
    if (!fan_id || !rider_id || !price_id) {
      return json({ error: 'missing_params' }, 400);
    }

    // 1. Load rider + fee_percent + verify onboarding complete
    const { data: rider, error: riderErr } = await supabase
      .from('riders')
      .select('id, stripe_account_id, fee_percent, onboarding_status')
      .eq('id', rider_id)
      .single();

    if (riderErr || !rider) return json({ error: 'rider_not_found' }, 404);
    if (!rider.stripe_account_id) return json({ error: 'rider_not_onboarded' }, 409);
    if (rider.onboarding_status !== 'enabled') {
      return json({ error: 'rider_onboarding_incomplete' }, 409);
    }

    // 2. Load fan + find/create their Stripe Customer ON THE CONNECTED ACCOUNT
    const { data: fan, error: fanErr } = await supabase
      .from('users')
      .select('id, email')
      .eq('id', fan_id)
      .single();

    if (fanErr || !fan) return json({ error: 'fan_not_found' }, 404);

    // With Direct charges, the Customer lives on the rider's connected account.
    // We store a per-(fan,rider) customer_id mapping in the sponsorships table
    // (or a dedicated stripe_customers table). For v1 we create on-the-fly.
    const customer = await stripe.customers.create(
      { email: fan.email, metadata: { fan_id, rider_id } },
      { stripeAccount: rider.stripe_account_id },
    );

    // 3. Create Subscription with dynamic fee
    const feePercent = rider.fee_percent ?? DEFAULT_FEE_PERCENT;

    const subscription = await stripe.subscriptions.create(
      {
        customer: customer.id,
        items: [{ price: price_id }],
        application_fee_percent: feePercent,
        payment_behavior: 'default_incomplete',
        payment_settings: {
          save_default_payment_method: 'on_subscription',
        },
        expand: ['latest_invoice.payment_intent', 'pending_setup_intent'],
        metadata: { fan_id, rider_id },
      },
      { stripeAccount: rider.stripe_account_id },
    );

    // 4. Record sponsorship in incomplete state (webhook will flip to 'active')
    await supabase.from('sponsorships').insert({
      fan_id,
      rider_id,
      stripe_subscription_id: subscription.id,
      stripe_account_id: rider.stripe_account_id,
      status: 'incomplete',
    });

    // 5. Extract client_secret for frontend confirmPayment
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const invoice = subscription.latest_invoice as any;
    const clientSecret =
      invoice?.payment_intent?.client_secret ??
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (subscription.pending_setup_intent as any)?.client_secret;

    if (!clientSecret) return json({ error: 'no_client_secret' }, 500);

    return json({
      subscription_id: subscription.id,
      client_secret: clientSecret,
      stripe_account_id: rider.stripe_account_id,
    });
  } catch (e) {
    console.error('create-fan-subscription error', e);
    return json({ error: 'internal_error', message: (e as Error).message }, 500);
  }
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
