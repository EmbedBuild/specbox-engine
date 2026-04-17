// ----------------------------------------------------------------------------
// cancel-fan-subscription — SpecBox /stripe-connect template
//
// Cancels a fan's subscription on the rider's connected account.
// Default: cancel at period end (fan keeps access until billing period ends).
// Optional: `immediate: true` for immediate cancellation + proration refund.
//
// Request body (JSON):
//   { sponsorship_id: string, immediate?: boolean }
//
// Response (JSON):
//   { subscription_id: string, status: string, cancel_at: number | null }
//
// Called by the fan's self-service UI. Authorization (fan owns the
// sponsorship) MUST be enforced by Supabase RLS, not by this function —
// this function uses service_role and trusts the caller was authenticated
// by Supabase Auth upstream.
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
    const { sponsorship_id, immediate = false } = await req.json();
    if (!sponsorship_id) return json({ error: 'missing_params' }, 400);

    // 1. Load sponsorship (RLS should have filtered by fan_id upstream via JWT)
    const { data: sp, error: spErr } = await supabase
      .from('sponsorships')
      .select('id, stripe_subscription_id, stripe_account_id, status')
      .eq('id', sponsorship_id)
      .single();

    if (spErr || !sp) return json({ error: 'sponsorship_not_found' }, 404);
    if (sp.status === 'canceled') return json({ error: 'already_canceled' }, 409);

    // 2. Cancel on Stripe (Direct charge → pass stripeAccount)
    let updated;
    if (immediate) {
      updated = await stripe.subscriptions.cancel(
        sp.stripe_subscription_id,
        { prorate: true },
        { stripeAccount: sp.stripe_account_id },
      );
    } else {
      updated = await stripe.subscriptions.update(
        sp.stripe_subscription_id,
        { cancel_at_period_end: true },
        { stripeAccount: sp.stripe_account_id },
      );
    }

    // 3. Reflect in DB (webhook will confirm; this is optimistic UX)
    await supabase
      .from('sponsorships')
      .update({
        status: immediate ? 'canceled' : sp.status,
        cancel_at: updated.cancel_at ? new Date(updated.cancel_at * 1000).toISOString() : null,
      })
      .eq('id', sponsorship_id);

    return json({
      subscription_id: updated.id,
      status: updated.status,
      cancel_at: updated.cancel_at,
    });
  } catch (e) {
    console.error('cancel-fan-subscription error', e);
    return json({ error: 'internal_error', message: (e as Error).message }, 500);
  }
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
