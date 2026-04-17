// ----------------------------------------------------------------------------
// rider-onboarding-button.tsx — SpecBox /stripe-connect template
//
// CTA for riders: creates the Stripe Connect Express account (if needed) and
// redirects to Stripe-hosted onboarding (Account Link). The redirect is the
// ONLY part of the billing flow that leaves the app — Connect embedded
// components aren't clean in Flutter so we keep the flow uniform across stacks.
//
// IMPORTANT: Before sending the rider to Stripe, show a warning about the
// legal/fiscal requirement (alta autónomo in Spain). The warning copy is
// intentionally in the component so the project can reuse it in modals, etc.
// ----------------------------------------------------------------------------

import React, { useState } from 'react';

interface RiderOnboardingButtonProps {
  /** Rider's id in the project's DB. */
  riderId: string;
  /** Absolute URL Stripe redirects to after onboarding finishes. */
  returnUrl: string;
  /** Absolute URL Stripe redirects to if the link expires. */
  refreshUrl: string;
  /** Supabase project URL. */
  supabaseUrl: string;
  /** Platform anon key. */
  supabaseAnonKey: string;
  /** Fan/rider JWT from Supabase Auth. */
  accessToken: string;
  /** If true, show the fiscal warning inline before triggering the link. */
  showFiscalWarning?: boolean;
}

export function RiderOnboardingButton({
  riderId,
  returnUrl,
  refreshUrl,
  supabaseUrl,
  supabaseAnonKey,
  accessToken,
  showFiscalWarning = true,
}: RiderOnboardingButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acknowledged, setAcknowledged] = useState(!showFiscalWarning);

  async function handleClick() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${supabaseUrl}/functions/v1/create-rider-account-link`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            apikey: supabaseAnonKey,
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            rider_id: riderId,
            return_url: returnUrl,
            refresh_url: refreshUrl,
          }),
        },
      );
      if (!res.ok) {
        throw new Error(`create-rider-account-link ${res.status}`);
      }
      const { onboarding_url } = (await res.json()) as {
        onboarding_url: string;
      };
      window.location.assign(onboarding_url);
    } catch (e) {
      setError((e as Error).message ?? 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rider-onboarding-panel">
      {showFiscalWarning && (
        <div role="region" aria-label="Advertencia fiscal" className="fiscal-notice">
          <h3>Antes de continuar</h3>
          <p>
            Para recibir patrocinios a través de esta plataforma necesitas estar
            dado de alta como <strong>autónomo</strong> en España o disponer de una
            sociedad. Stripe te solicitará tu NIF y una cuenta bancaria a tu nombre.
          </p>
          <p>
            Si aún no estás dado de alta, puedes completar este proceso en la Agencia
            Tributaria (modelo 036/037) y la Seguridad Social (RETA) antes de volver.
          </p>
          <label>
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(e) => setAcknowledged(e.target.checked)}
            />{' '}
            Entiendo los requisitos y quiero continuar.
          </label>
        </div>
      )}

      <button
        type="button"
        onClick={handleClick}
        disabled={loading || !acknowledged}
        className="primary-cta"
      >
        {loading ? 'Preparando…' : 'Completar onboarding con Stripe'}
      </button>

      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
    </div>
  );
}
