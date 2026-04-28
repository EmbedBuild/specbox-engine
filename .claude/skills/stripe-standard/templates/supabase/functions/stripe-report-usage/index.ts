// ----------------------------------------------------------------------------
// stripe-report-usage — SpecBox /stripe-standard template (metered mode only)
//
// Reports a usage record to Stripe for the user's metered subscription item.
// Called from the consumer's app whenever the user consumes a meterable unit
// (API call, message sent, MB transferred, etc.).
//
// Idempotency: Stripe deduplicates usage records by
// (subscription_item, timestamp). The action='increment' default sums all
// records in the period. To overwrite use action='set'.
//
// Body: { quantity: number, timestamp?: number (epoch sec), action?: 'increment'|'set' }
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

  let body: { quantity?: number; timestamp?: number; action?: 'increment' | 'set' };
  try {
    body = await req.json();
  } catch {
    return new Response('invalid_body', { status: 400 });
  }
  if (!body.quantity || body.quantity < 0) {
    return new Response('invalid_quantity', { status: 400 });
  }

  // Find user's customer + active subscription with a metered item.
  const { data: customerRow } = await supabase
    .from('stripe_customers')
    .select('stripe_customer_id')
    .eq('user_id', user.id)
    .single();

  if (!customerRow) return new Response('customer_not_found', { status: 404 });

  const { data: subRow } = await supabase
    .from('stripe_subscriptions')
    .select('stripe_subscription_id, status, metadata')
    .eq('customer_id', customerRow.stripe_customer_id)
    .in('status', ['active', 'trialing'])
    .maybeSingle();

  if (!subRow) return new Response('no_active_subscription', { status: 404 });

  // Resolve the metered subscription_item_id. We look at the live Stripe
  // subscription because the metered item may have been added or replaced.
  const sub = await stripe.subscriptions.retrieve(subRow.stripe_subscription_id);
  const meteredItem = sub.items.data.find(
    (item) => item.price.recurring?.usage_type === 'metered',
  );
  if (!meteredItem) {
    return new Response('no_metered_item', { status: 404 });
  }

  try {
    const record = await stripe.subscriptionItems.createUsageRecord(meteredItem.id, {
      quantity: body.quantity,
      timestamp: body.timestamp ?? 'now',
      action: body.action ?? 'increment',
    });
    return Response.json({
      usage_record_id: record.id,
      quantity: record.quantity,
      timestamp: record.timestamp,
    });
  } catch (err) {
    console.error('stripe.subscriptionItems.createUsageRecord failed', err);
    return new Response('stripe_unavailable', { status: 503 });
  }
});
