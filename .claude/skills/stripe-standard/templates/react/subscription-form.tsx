// ----------------------------------------------------------------------------
// subscription-form.tsx — SpecBox /stripe-standard template
//
// Single + tiered subscription flow with PaymentElement + ExpressCheckoutElement.
// Apple Pay, Google Pay and Link appear automatically when the device supports
// them. Confirms in-page (no redirect) and handles 3DS challenges.
//
// Usage:
//   <SubscriptionForm priceId="price_123" onSuccess={(subId) => navigate(`/welcome?sub=${subId}`)} />
// ----------------------------------------------------------------------------

import {
    ExpressCheckoutElement,
    PaymentElement,
    useElements,
    useStripe,
} from '@stripe/react-stripe-js';
import { useState } from 'react';
import { supabase } from '@/lib/supabase';
import { StripeProvider } from './stripe-provider';

export interface SubscriptionFormProps {
    priceId: string;
    onSuccess?: (subscriptionId: string) => void;
    onError?: (message: string) => void;
}

/**
 * Two-stage component: first call the Edge Function to get a client_secret,
 * then mount StripeProvider with that secret and render the form inside.
 */
export function SubscriptionForm(props: SubscriptionFormProps) {
    const [clientSecret, setClientSecret] = useState<string | null>(null);
    const [subId, setSubId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [bootstrapping, setBootstrapping] = useState(false);

    const bootstrap = async () => {
        setBootstrapping(true);
        setError(null);
        try {
            const { data: sessionData } = await supabase.auth.getSession();
            const jwt = sessionData.session?.access_token;
            if (!jwt) throw new Error('Not authenticated');

            const res = await fetch('/functions/v1/stripe-create-subscription', {
                method: 'POST',
                headers: {
                    'content-type': 'application/json',
                    authorization: `Bearer ${jwt}`,
                },
                body: JSON.stringify({ price_id: props.priceId }),
            });
            if (res.status === 409) {
                const body = await res.json();
                throw new Error(`Already subscribed: ${body.subscription_id}`);
            }
            if (!res.ok) throw new Error(`Subscription creation failed (${res.status})`);
            const data = await res.json();
            if (!data.client_secret) throw new Error('Stripe did not return a client_secret');
            setClientSecret(data.client_secret);
            setSubId(data.subscription_id);
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Unknown error';
            setError(msg);
            props.onError?.(msg);
        } finally {
            setBootstrapping(false);
        }
    };

    if (!clientSecret) {
        return (
            <div>
                <button onClick={bootstrap} disabled={bootstrapping} type="button">
                    {bootstrapping ? 'Preparando...' : 'Continuar'}
                </button>
                {error && <p role="alert">{error}</p>}
            </div>
        );
    }

    return (
        <StripeProvider clientSecret={clientSecret}>
            <ConfirmInner subscriptionId={subId!} onSuccess={props.onSuccess} onError={props.onError} />
        </StripeProvider>
    );
}

interface ConfirmInnerProps {
    subscriptionId: string;
    onSuccess?: (id: string) => void;
    onError?: (message: string) => void;
}

function ConfirmInner({ subscriptionId, onSuccess, onError }: ConfirmInnerProps) {
    const stripe = useStripe();
    const elements = useElements();
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const submit = async () => {
        if (!stripe || !elements) return;
        setSubmitting(true);
        setError(null);
        const { error: confirmErr } = await stripe.confirmPayment({
            elements,
            confirmParams: {
                return_url: `${window.location.origin}/billing/return?sub=${subscriptionId}`,
            },
            redirect: 'if_required',
        });
        if (confirmErr) {
            const msg = confirmErr.message ?? 'Pago no confirmado';
            setError(msg);
            onError?.(msg);
        } else {
            // 3DS may have happened in-page. The webhook will have updated the
            // status; the consumer can refresh useBilling() in onSuccess.
            onSuccess?.(subscriptionId);
        }
        setSubmitting(false);
    };

    return (
        <form
            onSubmit={(e) => {
                e.preventDefault();
                void submit();
            }}
        >
            <ExpressCheckoutElement onConfirm={submit} />
            <PaymentElement />
            <button type="submit" disabled={!stripe || submitting}>
                {submitting ? 'Procesando...' : 'Suscribirse'}
            </button>
            {error && <p role="alert">{error}</p>}
        </form>
    );
}
