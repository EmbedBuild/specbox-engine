// ----------------------------------------------------------------------------
// use-sponsorship.ts — SpecBox /stripe-connect template
//
// React hook that manages the lifecycle of a sponsorship checkout:
//   idle → loading → ready_to_confirm → confirming → success | error
//
// The hook calls the create-fan-subscription Edge Function to obtain a
// client_secret + stripe_account_id, which the parent then feeds into
// <StripeProvider> so the PaymentElement can render.
//
// Authentication: this hook assumes your app uses Supabase Auth and that
// the session is available via the project's auth context. We read the
// access_token and send it as Bearer, which activates RLS.
// ----------------------------------------------------------------------------

import { useCallback, useState } from 'react';

interface CreateSubscriptionResponse {
  subscription_id: string;
  client_secret: string;
  stripe_account_id: string;
}

type State =
  | { status: 'idle' }
  | { status: 'loading' }
  | {
      status: 'ready_to_confirm';
      clientSecret: string;
      stripeAccountId: string;
      subscriptionId: string;
    }
  | { status: 'error'; message: string };

interface UseSponsorshipOptions {
  /** Project Supabase URL, e.g. https://abcd.supabase.co */
  supabaseUrl: string;
  /** Platform anon key (safe in the client). */
  supabaseAnonKey: string;
  /** Authenticated access token from Supabase Auth (JWT of the fan). */
  accessToken: string;
}

export function useSponsorship({
  supabaseUrl,
  supabaseAnonKey,
  accessToken,
}: UseSponsorshipOptions) {
  const [state, setState] = useState<State>({ status: 'idle' });

  const startSponsorship = useCallback(
    async (input: { riderId: string; priceId: string }) => {
      setState({ status: 'loading' });
      try {
        const res = await fetch(
          `${supabaseUrl}/functions/v1/create-fan-subscription`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              apikey: supabaseAnonKey,
              Authorization: `Bearer ${accessToken}`,
            },
            body: JSON.stringify({
              rider_id: input.riderId,
              price_id: input.priceId,
              fan_id: parseJwt(accessToken)?.sub,
            }),
          },
        );

        if (!res.ok) {
          const body = await res.text();
          throw new Error(`create-fan-subscription ${res.status}: ${body}`);
        }

        const data = (await res.json()) as CreateSubscriptionResponse;
        setState({
          status: 'ready_to_confirm',
          clientSecret: data.client_secret,
          stripeAccountId: data.stripe_account_id,
          subscriptionId: data.subscription_id,
        });
      } catch (e) {
        setState({
          status: 'error',
          message: (e as Error).message ?? 'Unknown error',
        });
      }
    },
    [supabaseUrl, supabaseAnonKey, accessToken],
  );

  const reset = useCallback(() => setState({ status: 'idle' }), []);

  return { state, startSponsorship, reset };
}

function parseJwt(token: string): { sub?: string } | null {
  try {
    const payload = token.split('.')[1];
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}
