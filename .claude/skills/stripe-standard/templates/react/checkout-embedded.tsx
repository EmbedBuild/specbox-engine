// ----------------------------------------------------------------------------
// checkout-embedded.tsx — SpecBox /stripe-standard template
//
// One-shot purchases via Stripe Embedded Checkout. ui_mode='embedded' is
// hard-coded server-side; the safety hook blocks 'hosted' mode. Apple/Google
// Pay and Link are enabled automatically.
//
// Usage:
//   <CheckoutEmbedded
//     mode="payment"
//     lineItems={[{ price: 'price_123', quantity: 1 }]}
//     onSuccess={() => navigate('/thank-you')}
//   />
// ----------------------------------------------------------------------------

import { EmbeddedCheckout, EmbeddedCheckoutProvider } from '@stripe/react-stripe-js';
import { loadStripe, type Stripe } from '@stripe/stripe-js';
import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';

const PK =
    (import.meta as any).env?.VITE_STRIPE_PUBLISHABLE_KEY ??
    (typeof process !== 'undefined' && (process as any).env?.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY) ??
    '';

let stripePromise: Promise<Stripe | null> | null = null;
function getStripe() {
    if (!stripePromise) stripePromise = loadStripe(PK);
    return stripePromise;
}

export interface CheckoutEmbeddedProps {
    mode: 'payment' | 'subscription';
    lineItems: Array<{ price: string; quantity?: number }>;
    onSuccess?: () => void;
    onError?: (message: string) => void;
}

export function CheckoutEmbedded({ mode, lineItems, onSuccess, onError }: CheckoutEmbeddedProps) {
    const [clientSecret, setClientSecret] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        const bootstrap = async () => {
            try {
                const { data: sessionData } = await supabase.auth.getSession();
                const jwt = sessionData.session?.access_token;
                if (!jwt) throw new Error('Not authenticated');
                const res = await fetch('/functions/v1/stripe-create-checkout-session', {
                    method: 'POST',
                    headers: {
                        'content-type': 'application/json',
                        authorization: `Bearer ${jwt}`,
                    },
                    body: JSON.stringify({ mode, line_items: lineItems }),
                });
                if (!res.ok) throw new Error(`checkout session failed (${res.status})`);
                const data = await res.json();
                if (cancelled) return;
                setClientSecret(data.client_secret);
            } catch (err) {
                const msg = err instanceof Error ? err.message : 'Unknown error';
                if (cancelled) return;
                setError(msg);
                onError?.(msg);
            }
        };
        void bootstrap();
        return () => {
            cancelled = true;
        };
    }, [mode, lineItems, onError]);

    if (error) return <p role="alert">{error}</p>;
    if (!clientSecret) return <p>Cargando checkout...</p>;

    return (
        <EmbeddedCheckoutProvider
            stripe={getStripe()}
            options={{
                clientSecret,
                onComplete: () => onSuccess?.(),
            }}
        >
            <EmbeddedCheckout />
        </EmbeddedCheckoutProvider>
    );
}
