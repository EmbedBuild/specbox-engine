// ----------------------------------------------------------------------------
// stripe-provider.tsx — SpecBox /stripe-connect template
//
// <StripeProvider> wraps any subtree that needs access to Stripe.js. The real
// magic is `stripeAccount`: for Direct charges we must scope the Stripe
// instance to the rider's connected account, otherwise PaymentElement tries
// to confirm against the platform account and fails with SCA errors.
//
// Appearance is parametrized from the project's Brand Kit (if present).
// Tokens are sustituted by /stripe-connect during skill execution; if no
// Brand Kit existed at scaffold time, they remain as neutral defaults.
// ----------------------------------------------------------------------------

import React, { type PropsWithChildren, useMemo } from 'react';
import { loadStripe, type Stripe as StripeJs } from '@stripe/stripe-js';
import { Elements, type StripeElementsOptions } from '@stripe/react-stripe-js';

// Cache per (publishableKey, stripeAccount) pair. loadStripe is expensive and
// Stripe.js shouldn't be loaded more than once per connected account.
const stripePromiseCache = new Map<string, Promise<StripeJs | null>>();

function getStripe(publishableKey: string, stripeAccount?: string): Promise<StripeJs | null> {
  const cacheKey = `${publishableKey}::${stripeAccount ?? ''}`;
  let cached = stripePromiseCache.get(cacheKey);
  if (!cached) {
    cached = loadStripe(publishableKey, stripeAccount ? { stripeAccount } : undefined);
    stripePromiseCache.set(cacheKey, cached);
  }
  return cached;
}

interface StripeProviderProps {
  /** Platform publishable key — safe to expose in the client. */
  publishableKey: string;
  /** Rider's Stripe Connect account id (acct_*). Required for Direct charges. */
  stripeAccount: string;
  /** PaymentIntent / SetupIntent client_secret returned by create-fan-subscription. */
  clientSecret: string;
}

export function StripeProvider({
  publishableKey,
  stripeAccount,
  clientSecret,
  children,
}: PropsWithChildren<StripeProviderProps>) {
  const stripe = useMemo(
    () => getStripe(publishableKey, stripeAccount),
    [publishableKey, stripeAccount],
  );

  const options = useMemo<StripeElementsOptions>(
    () => ({
      clientSecret,
      appearance: {
        theme: 'stripe',
        variables: {
          // {brand_kit_tokens} — /stripe-connect sustituye estos valores en runtime
          // leyendo doc/design/brand-kit.md del proyecto consumidor.
          // TODO: parametrizar con Brand Kit cuando exista
          colorPrimary: '#635BFF',
          colorBackground: '#FFFFFF',
          colorText: '#1F2937',
          colorDanger: '#DC2626',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          borderRadius: '8px',
        },
      },
      loader: 'auto',
    }),
    [clientSecret],
  );

  return (
    <Elements stripe={stripe} options={options}>
      {children}
    </Elements>
  );
}
