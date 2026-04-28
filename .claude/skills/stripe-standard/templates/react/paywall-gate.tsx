// ----------------------------------------------------------------------------
// paywall-gate.tsx — SpecBox /stripe-standard template
//
// Wrap any premium feature with <PaywallGate> and the user is redirected to
// /pricing if they don't have an active subscription. Optionally enforce a
// tier with `requireTier="pro"`.
//
// Usage:
//   <PaywallGate>
//     <PremiumFeature />
//   </PaywallGate>
//
//   <PaywallGate requireTier="pro" fallback={<UpgradePrompt />}>
//     <ProOnlyFeature />
//   </PaywallGate>
// ----------------------------------------------------------------------------

import type { ReactNode } from 'react';
import { useBilling } from './use-billing';

export interface PaywallGateProps {
    children: ReactNode;
    /** If set, also requires sub.metadata.tier_key === requireTier */
    requireTier?: string;
    /** Optional custom fallback when access is denied. Default: redirect to /pricing */
    fallback?: ReactNode;
    /** Optional skeleton while billing state is loading */
    loadingFallback?: ReactNode;
}

export function PaywallGate({
    children,
    requireTier,
    fallback,
    loadingFallback,
}: PaywallGateProps) {
    const { isActive, hasTier, loading } = useBilling();

    if (loading) {
        return <>{loadingFallback ?? <PaywallSkeleton />}</>;
    }

    const allowed = isActive && (requireTier == null || hasTier(requireTier));
    if (!allowed) {
        if (fallback != null) return <>{fallback}</>;
        // Default: client-side redirect. Consumers using a router should prefer
        // <Navigate to="/pricing" /> from react-router or next/navigation.
        if (typeof window !== 'undefined') {
            window.location.href = '/pricing';
        }
        return null;
    }

    return <>{children}</>;
}

function PaywallSkeleton() {
    return (
        <div
            aria-busy="true"
            aria-label="Loading subscription status"
            style={{
                width: '100%',
                minHeight: '120px',
                background: 'linear-gradient(90deg,#f3f4f6,#e5e7eb,#f3f4f6)',
                backgroundSize: '200% 100%',
                animation: 'paywall-skeleton 1.4s ease-in-out infinite',
                borderRadius: 8,
            }}
        />
    );
}
