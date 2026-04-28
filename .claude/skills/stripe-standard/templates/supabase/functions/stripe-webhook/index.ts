// ----------------------------------------------------------------------------
// stripe-webhook — SpecBox /stripe-standard template
//
// SINGLE webhook endpoint for Stripe Standard accounts (no Connect). All
// events arrive at the same URL signed with the same STRIPE_WEBHOOK_SECRET.
// Compared to /stripe-connect's template this is simpler — no platform vs
// connect routing — but the idempotency + signature verification layer is
// identical because the anti-patterns are universal.
//
// IDEMPOTENCY: every event's `event.id` is recorded in `stripe_processed_events`
// BEFORE processing. Stripe retries events on timeouts or non-2xx responses,
// so the same event may arrive multiple times. We deduplicate by event.id.
//
// Events handled in v1 (Standard account):
//   customer.created                 — log only
//   customer.subscription.created    — upsert in stripe_subscriptions
//   customer.subscription.updated    — upsert (also handles cancel_at_period_end)
//   customer.subscription.deleted    — mark canceled (post-period-end)
//   invoice.paid                     — log + opt email
//   invoice.payment_failed           — start dunning (status = past_due / unpaid)
//   payment_intent.succeeded         — one-shot confirmation hook
//   checkout.session.completed       — fallback hosted checkout flow
//   charge.refunded                  — generic, log + opt revoke access
//
// Required env vars (3 — Standard mode, no _CONNECT/_PLATFORM split):
//   STRIPE_SECRET_KEY
//   STRIPE_WEBHOOK_SECRET
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

const WHSEC = Deno.env.get('STRIPE_WEBHOOK_SECRET')!;

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('method_not_allowed', { status: 405 });

  const rawBody = await req.text();
  const signature = req.headers.get('stripe-signature');
  if (!signature) return new Response('missing_signature', { status: 400 });

  // ---- Verify signature ----
  let event: Stripe.Event;
  try {
    event = await stripe.webhooks.constructEventAsync(rawBody, signature, WHSEC);
  } catch (err) {
    console.warn('signature verification failed', String(err).slice(0, 200));
    return new Response('invalid_signature', { status: 400 });
  }

  // ---- Idempotency: insert event.id BEFORE processing ----
  const { error: dedupErr } = await supabase
    .from('stripe_processed_events')
    .insert({ event_id: event.id, type: event.type });

  if (dedupErr) {
    // Unique-violation on event_id → already processed. Stripe retried.
    if (dedupErr.code === '23505') {
      return new Response(JSON.stringify({ duplicate: true, event_id: event.id }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    }
    console.error('failed to record event.id', dedupErr);
    return new Response('internal_error', { status: 500 });
  }

  // ---- Route to handler ----
  try {
    switch (event.type) {
      case 'customer.created':
        // No-op: stripe-create-customer handles persistence explicitly. Logged
        // here for observability only.
        console.log('customer.created', event.data.object.id);
        break;

      case 'customer.subscription.created':
      case 'customer.subscription.updated': {
        const sub = event.data.object as Stripe.Subscription;
        await supabase.from('stripe_subscriptions').upsert(
          {
            stripe_subscription_id: sub.id,
            customer_id: await resolveCustomerId(sub.customer as string),
            price_id: sub.items.data[0]?.price.id ?? null,
            status: sub.status,
            current_period_end: new Date(sub.current_period_end * 1000).toISOString(),
            cancel_at_period_end: sub.cancel_at_period_end,
            metadata: sub.metadata ?? {},
          },
          { onConflict: 'stripe_subscription_id' },
        );
        break;
      }

      case 'customer.subscription.deleted': {
        const sub = event.data.object as Stripe.Subscription;
        await supabase
          .from('stripe_subscriptions')
          .update({ status: 'canceled', cancel_at_period_end: false })
          .eq('stripe_subscription_id', sub.id);
        break;
      }

      case 'invoice.paid': {
        const invoice = event.data.object as Stripe.Invoice;
        if (invoice.subscription) {
          // Restore active status if dunning had marked the sub past_due/unpaid.
          await supabase
            .from('stripe_subscriptions')
            .update({ status: 'active' })
            .eq('stripe_subscription_id', invoice.subscription as string);
        }
        break;
      }

      case 'invoice.payment_failed': {
        const invoice = event.data.object as Stripe.Invoice;
        if (invoice.subscription) {
          // attempt_count==1 → past_due; later attempts → unpaid until Stripe
          // gives up and emits subscription.updated → status='unpaid'.
          const newStatus = invoice.attempt_count === 1 ? 'past_due' : 'unpaid';
          await supabase
            .from('stripe_subscriptions')
            .update({ status: newStatus })
            .eq('stripe_subscription_id', invoice.subscription as string);
        }
        // Optional: trigger Resend dunning email here when project has Resend wired.
        break;
      }

      case 'payment_intent.succeeded': {
        // One-shot purchases land here. The /stripe-standard scaffold leaves
        // the `orders` table for the consumer to add — they decide the schema
        // for their own product. Logged for observability.
        const pi = event.data.object as Stripe.PaymentIntent;
        console.log('payment_intent.succeeded', pi.id, pi.amount, pi.currency);
        break;
      }

      case 'checkout.session.completed': {
        // Fallback path when consumer used stripe-create-checkout-session.
        const session = event.data.object as Stripe.Checkout.Session;
        console.log('checkout.session.completed', session.id, session.mode);
        // For mode='subscription' the subscription.created event covers persistence.
        // For mode='payment' the payment_intent.succeeded event covers persistence.
        break;
      }

      case 'charge.refunded': {
        const charge = event.data.object as Stripe.Charge;
        console.log('charge.refunded', charge.id, charge.amount_refunded);
        // Consumer-specific: revoke access, update orders, etc.
        break;
      }

      default:
        // Unhandled event types are still recorded in stripe_processed_events
        // (dedup), but we just log them. Stripe sends many events; handle the
        // ones you care about and ignore the rest.
        console.log('unhandled event', event.type);
    }
  } catch (err) {
    console.error('handler failed for', event.id, event.type, err);
    // Note: event.id is already in stripe_processed_events. Returning 500 will
    // make Stripe retry, which will hit the unique-violation path and return
    // 200 immediately. To force re-processing, delete the row manually.
    return new Response('handler_error', { status: 500 });
  }

  return new Response(JSON.stringify({ received: true, event_id: event.id }), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
});

// ---- Helpers ----

async function resolveCustomerId(stripeCustomerId: string): Promise<string | null> {
  const { data, error } = await supabase
    .from('stripe_customers')
    .select('id')
    .eq('stripe_customer_id', stripeCustomerId)
    .single();
  if (error || !data) {
    console.warn('resolveCustomerId: no row for', stripeCustomerId);
    return null;
  }
  return data.id;
}
