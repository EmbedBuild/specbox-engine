// ----------------------------------------------------------------------------
// sponsor-rider-form.tsx — SpecBox /stripe-connect template
//
// The checkout form. Uses <PaymentElement> (40+ payment methods auto-detected
// per locale) + <ExpressCheckoutElement> (Apple Pay, Google Pay, Link native
// buttons). Everything stays inside the app — no redirect to stripe.com.
//
// Flow:
//   1. Parent calls create-fan-subscription Edge Function via useSponsorship
//   2. Edge Function returns { client_secret, stripe_account_id }
//   3. Parent wraps this form in <StripeProvider clientSecret stripeAccount>
//   4. User fills PaymentElement or taps Apple/Google Pay
//   5. On submit, stripe.confirmPayment handles 3DS in-app if needed
//   6. On success, we redirect to /sponsorship/success inline
//
// This component is intentionally UI-light — wire it up to your project's
// component library (shadcn/ui, MUI, Tailwind) instead of styling inline.
// ----------------------------------------------------------------------------

import React, { useState, type FormEvent } from 'react';
import {
  useStripe,
  useElements,
  PaymentElement,
  ExpressCheckoutElement,
} from '@stripe/react-stripe-js';

interface SponsorRiderFormProps {
  /** URL the user lands on after successful payment. Absolute or relative. */
  successReturnUrl: string;
}

type Status = 'idle' | 'loading' | 'error';

export function SponsorRiderForm({ successReturnUrl }: SponsorRiderFormProps) {
  const stripe = useStripe();
  const elements = useElements();
  const [status, setStatus] = useState<Status>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const disabled = !stripe || !elements || status === 'loading';

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!stripe || !elements) return;

    setStatus('loading');
    setErrorMessage(null);

    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: absoluteUrl(successReturnUrl),
      },
      // `redirect: 'if_required'` keeps the user in-app when no 3DS challenge is needed
      redirect: 'if_required',
    });

    if (error) {
      // Errors are displayed inline; PaymentElement also shows its own field errors
      setErrorMessage(error.message ?? 'Ocurrió un error procesando el pago.');
      setStatus('error');
      return;
    }

    // Success without redirect (most common): navigate manually
    window.location.assign(absoluteUrl(successReturnUrl));
  }

  return (
    <form onSubmit={handleSubmit} className="sponsor-rider-form" noValidate>
      {/* Apple Pay / Google Pay / Link buttons — shown only if the device supports them */}
      <ExpressCheckoutElement
        onConfirm={async () => {
          // ExpressCheckoutElement handles confirmation itself; we just
          // let Stripe drive. The same confirmParams.return_url applies.
        }}
      />

      <div className="form-divider" aria-hidden="true">
        <span>o paga con tarjeta</span>
      </div>

      {/* Full Payment Element — cards, SEPA, iDEAL, etc. auto-resolved by locale */}
      <PaymentElement
        options={{
          layout: 'tabs',
        }}
      />

      {errorMessage && (
        <div role="alert" className="form-error">
          {errorMessage}
        </div>
      )}

      <button type="submit" disabled={disabled} className="primary-cta">
        {status === 'loading' ? 'Procesando…' : 'Suscribirme'}
      </button>
    </form>
  );
}

function absoluteUrl(urlOrPath: string): string {
  if (/^https?:\/\//.test(urlOrPath)) return urlOrPath;
  return `${window.location.origin}${urlOrPath.startsWith('/') ? '' : '/'}${urlOrPath}`;
}
