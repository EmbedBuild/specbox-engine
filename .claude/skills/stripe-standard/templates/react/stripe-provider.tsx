// ----------------------------------------------------------------------------
// stripe-provider.tsx — SpecBox /stripe-standard template
//
// Wrap your billing UI with <StripeProvider> at the app root or in the
// section that needs Stripe Elements. Uses VITE_STRIPE_PUBLISHABLE_KEY
// (Vite) or NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY (Next.js) — pick the one
// matching your bundler.
// ----------------------------------------------------------------------------

import { Elements } from '@stripe/react-stripe-js';
import { loadStripe, type Stripe } from '@stripe/stripe-js';
import type { ReactNode } from 'react';

const PK =
    // Vite
    (import.meta as any).env?.VITE_STRIPE_PUBLISHABLE_KEY ??
    // Next.js
    (typeof process !== 'undefined' && (process as any).env?.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY) ??
    '';

if (!PK) {
    // eslint-disable-next-line no-console
    console.warn(
        '[stripe-provider] Stripe publishable key missing. Set VITE_STRIPE_PUBLISHABLE_KEY or NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY.',
    );
}

// loadStripe returns a Promise — share a single instance across the app.
let stripePromise: Promise<Stripe | null> | null = null;
function getStripe() {
    if (!stripePromise) {
        stripePromise = loadStripe(PK);
    }
    return stripePromise;
}

export interface StripeProviderProps {
    /** When mounting for an existing PaymentIntent / SetupIntent / Subscription */
    clientSecret?: string;
    /** Stripe Appearance API config — extracted from brand-kit if present */
    appearance?: Record<string, unknown>;
    children: ReactNode;
}

export function StripeProvider({ clientSecret, appearance, children }: StripeProviderProps) {
    return (
        <Elements
            stripe={getStripe()}
            options={{
                clientSecret,
                appearance: {
                    theme: 'stripe',
                    variables: {
                        // These values can be overridden by /stripe-standard at scaffold
                        // time when doc/design/brand-kit.md is present.
                        colorPrimary: '#0570de',
                        fontFamily: 'system-ui, sans-serif',
                        borderRadius: '8px',
                    },
                    ...(appearance ?? {}),
                },
            }}
        >
            {children}
        </Elements>
    );
}
