// ----------------------------------------------------------------------------
// use-billing.ts — SpecBox /stripe-standard template
//
// Centralized billing state hook used by PaywallGate, BillingPortalLink, and
// the subscription flows. Reads stripe_subscriptions via Supabase RLS, so it
// only ever returns the current user's data.
//
// Usage:
//   const { sub, loading, isActive, hasTier } = useBilling();
//   if (!isActive) return <Navigate to="/pricing" />;
// ----------------------------------------------------------------------------

import { useEffect, useState } from 'react';
// The supabase client is provided by the consumer project. Adjust the import.
// Most projects have a `lib/supabase.ts` exporting a configured client.
import { supabase } from '@/lib/supabase';

export interface SubscriptionRow {
    id: string;
    stripe_subscription_id: string;
    price_id: string | null;
    status:
        | 'incomplete'
        | 'incomplete_expired'
        | 'trialing'
        | 'active'
        | 'past_due'
        | 'canceled'
        | 'unpaid'
        | 'paused';
    current_period_end: string | null;
    cancel_at_period_end: boolean;
    metadata: Record<string, string>;
}

export interface UseBillingResult {
    sub: SubscriptionRow | null;
    loading: boolean;
    error: Error | null;
    isActive: boolean;
    hasTier: (tierKey: string) => boolean;
    refresh: () => Promise<void>;
}

const ACTIVE_STATUSES = new Set<SubscriptionRow['status']>(['active', 'trialing']);

export function useBilling(): UseBillingResult {
    const [sub, setSub] = useState<SubscriptionRow | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<Error | null>(null);

    const fetchSub = async () => {
        setLoading(true);
        setError(null);
        try {
            // RLS ensures we only see the current user's rows. We pick the most
            // recently updated row in case of multiple historical entries.
            const { data, error: queryErr } = await supabase
                .from('stripe_subscriptions')
                .select('*')
                .order('updated_at', { ascending: false })
                .limit(1)
                .maybeSingle();

            if (queryErr) throw queryErr;
            setSub((data as SubscriptionRow) ?? null);
        } catch (err) {
            setError(err instanceof Error ? err : new Error(String(err)));
            setSub(null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void fetchSub();
        // Optional: subscribe to realtime changes on stripe_subscriptions for
        // this user. Enabled per-project; not turned on by default.
    }, []);

    const isActive = sub != null && ACTIVE_STATUSES.has(sub.status);

    const hasTier = (tierKey: string): boolean => {
        if (!sub) return false;
        return sub.metadata?.tier_key === tierKey;
    };

    return {
        sub,
        loading,
        error,
        isActive,
        hasTier,
        refresh: fetchSub,
    };
}
