// ----------------------------------------------------------------------------
// stripe-webhook — SpecBox /stripe-connect template
//
// Handles BOTH platform webhooks and Connect webhooks in a single endpoint.
// Stripe supports this by using TWO different signing secrets: one for the
// platform endpoint (`WHSEC_PLATFORM`) and one for the Connect endpoint
// (`WHSEC_CONNECT`). We try verification against both; the one that succeeds
// tells us which audience the event belongs to.
//
// IDEMPOTENCY: every event's `event.id` is recorded in `stripe_processed_events`
// BEFORE processing. Stripe retries events on timeouts or non-2xx responses,
// so the same event may arrive multiple times. We deduplicate by event.id.
//
// 10 critical events handled in v1:
//   Platform:
//     account.updated                             — seller onboarding progress
//     capability.updated                          — card_payments/transfers enabled
//     account.application.deauthorized            — seller disconnected the account
//   Connect (received on behalf of the seller):
//     customer.subscription.created               — new sponsorship created
//     customer.subscription.updated               — sponsorship changed
//     customer.subscription.deleted               — sponsorship canceled
//     invoice.paid                                — monthly renewal succeeded
//     invoice.payment_failed                      — renewal failed, start retry UX
//     charge.refunded                             — manual refund happened
//     application_fee.created                     — platform revenue recorded
//
// Required env vars:
//   STRIPE_SECRET_KEY
//   STRIPE_WEBHOOK_SECRET_PLATFORM
//   STRIPE_WEBHOOK_SECRET_CONNECT
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

const WHSEC_PLATFORM = Deno.env.get('STRIPE_WEBHOOK_SECRET_PLATFORM')!;
const WHSEC_CONNECT = Deno.env.get('STRIPE_WEBHOOK_SECRET_CONNECT')!;

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('method_not_allowed', { status: 405 });

  const rawBody = await req.text();
  const signature = req.headers.get('stripe-signature');
  if (!signature) return new Response('missing_signature', { status: 400 });

  // ---- Verify signature against BOTH secrets to determine audience ----
  let event: Stripe.Event | null = null;
  let source: 'platform' | 'connect' | null = null;

  try {
    event = await stripe.webhooks.constructEventAsync(
      rawBody,
      signature,
      WHSEC_PLATFORM,
    );
    source = 'platform';
  } catch {
    try {
      event = await stripe.webhooks.constructEventAsync(
        rawBody,
        signature,
        WHSEC_CONNECT,
      );
      source = 'connect';
    } catch (err) {
      console.warn('signature verification failed against both secrets', err);
      return new Response('invalid_signature', { status: 400 });
    }
  }

  // ---- IDEMPOTENCY: check if we've already processed this event.id ----
  const { data: existing } = await supabase
    .from('stripe_processed_events')
    .select('event_id')
    .eq('event_id', event.id)
    .maybeSingle();

  if (existing) {
    // Already processed — acknowledge with 200 to stop Stripe retrying
    return new Response('ok_duplicate', { status: 200 });
  }

  // Record receipt BEFORE processing. If processing fails after this,
  // the event is effectively "dropped" — that's the correct trade-off for
  // idempotency. Re-processing can be done manually via the Stripe dashboard
  // ("resend event") combined with deleting the row here.
  await supabase.from('stripe_processed_events').insert({
    event_id: event.id,
    event_type: event.type,
    source,
    received_at: new Date().toISOString(),
  });

  // ---- Route event ----
  try {
    await routeEvent(event, source);
    await supabase
      .from('stripe_processed_events')
      .update({ processed_at: new Date().toISOString() })
      .eq('event_id', event.id);
    return new Response('ok', { status: 200 });
  } catch (e) {
    console.error(`error processing ${event.type}`, e);
    // Still return 200 so Stripe doesn't keep retrying. The row in
    // stripe_processed_events without processed_at is a marker for
    // operations to investigate.
    return new Response('ok_with_errors', { status: 200 });
  }
});

async function routeEvent(event: Stripe.Event, source: 'platform' | 'connect' | null) {
  switch (event.type) {
    // ----- Platform events -----
    case 'account.updated': {
      const account = event.data.object as Stripe.Account;
      const onboardingStatus =
        account.charges_enabled && account.payouts_enabled
          ? 'enabled'
          : account.requirements?.disabled_reason
            ? 'restricted'
            : 'pending';
      await supabase
        .from('riders')
        .update({ onboarding_status: onboardingStatus })
        .eq('stripe_account_id', account.id);
      break;
    }

    case 'capability.updated': {
      // Capability transitions can trigger onboarding_status recalc. For v1
      // we rely on the account.updated event to be the source of truth.
      break;
    }

    case 'account.application.deauthorized': {
      const accountId = (event.account || (event.data.object as Stripe.Account).id) as string;
      await supabase
        .from('riders')
        .update({ onboarding_status: 'deauthorized' })
        .eq('stripe_account_id', accountId);
      break;
    }

    // ----- Connect events (the account id is in event.account) -----
    case 'customer.subscription.created':
    case 'customer.subscription.updated': {
      const sub = event.data.object as Stripe.Subscription;
      await supabase
        .from('sponsorships')
        .update({
          status: mapSubscriptionStatus(sub.status),
          current_period_end: new Date(sub.current_period_end * 1000).toISOString(),
          cancel_at: sub.cancel_at ? new Date(sub.cancel_at * 1000).toISOString() : null,
          updated_at: new Date().toISOString(),
        })
        .eq('stripe_subscription_id', sub.id);
      break;
    }

    case 'customer.subscription.deleted': {
      const sub = event.data.object as Stripe.Subscription;
      await supabase
        .from('sponsorships')
        .update({ status: 'canceled', updated_at: new Date().toISOString() })
        .eq('stripe_subscription_id', sub.id);
      break;
    }

    case 'invoice.paid': {
      const invoice = event.data.object as Stripe.Invoice;
      if (invoice.subscription) {
        await supabase
          .from('sponsorships')
          .update({
            status: 'active',
            last_paid_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          })
          .eq('stripe_subscription_id', invoice.subscription as string);
      }
      break;
    }

    case 'invoice.payment_failed': {
      const invoice = event.data.object as Stripe.Invoice;
      if (invoice.subscription) {
        await supabase
          .from('sponsorships')
          .update({
            status: 'past_due',
            updated_at: new Date().toISOString(),
          })
          .eq('stripe_subscription_id', invoice.subscription as string);
        // TODO(project): send email/push to fan with update-payment-method CTA
      }
      break;
    }

    case 'charge.refunded': {
      const charge = event.data.object as Stripe.Charge;
      // Record refund for audit; actual sponsorship status handled by
      // subscription.updated event that Stripe emits together with refunds.
      console.log(`refund recorded for charge ${charge.id}`);
      break;
    }

    case 'application_fee.created': {
      const fee = event.data.object as Stripe.ApplicationFee;
      // Platform revenue event — can be persisted for accounting dashboards.
      // For v1 we just log; UC-311 (admin dashboard) reads Balance API directly.
      console.log(`application_fee recorded: ${fee.amount} ${fee.currency}`);
      break;
    }

    default:
      // Unhandled event type — ignore. Stripe sends many events we don't care about.
      break;
  }
}

function mapSubscriptionStatus(stripeStatus: Stripe.Subscription.Status): string {
  // Our domain statuses: active | incomplete | past_due | canceled | trialing | paused
  return stripeStatus;
}
