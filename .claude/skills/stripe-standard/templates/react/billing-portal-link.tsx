// ----------------------------------------------------------------------------
// billing-portal-link.tsx — SpecBox /stripe-standard template
//
// Button that opens the Stripe Customer Portal in a new tab. The portal is
// hosted by Stripe and configured in their dashboard; we just request a
// session URL via the Edge Function.
// ----------------------------------------------------------------------------

import { useState } from 'react';
import { supabase } from '@/lib/supabase';

export interface BillingPortalLinkProps {
    children?: React.ReactNode;
    /** Optional return URL when the user closes the portal. Defaults to /account. */
    returnUrl?: string;
    className?: string;
}

export function BillingPortalLink({
    children = 'Manage subscription',
    returnUrl,
    className,
}: BillingPortalLinkProps) {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const open = async () => {
        setLoading(true);
        setError(null);
        try {
            const { data: sessionData } = await supabase.auth.getSession();
            const jwt = sessionData.session?.access_token;
            if (!jwt) throw new Error('Not authenticated');

            const res = await fetch('/functions/v1/stripe-create-portal-session', {
                method: 'POST',
                headers: {
                    'content-type': 'application/json',
                    authorization: `Bearer ${jwt}`,
                },
                body: JSON.stringify({ return_url: returnUrl }),
            });
            if (!res.ok) throw new Error(`portal session failed (${res.status})`);
            const data = await res.json();
            if (!data.url) throw new Error('Portal URL missing in response');
            window.open(data.url, '_blank', 'noopener,noreferrer');
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Unknown error';
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <button type="button" onClick={open} disabled={loading} className={className}>
                {loading ? 'Abriendo...' : children}
            </button>
            {error && <p role="alert">{error}</p>}
        </>
    );
}
