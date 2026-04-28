// ----------------------------------------------------------------------------
// usage-meter.tsx — SpecBox /stripe-standard template (metered mode only)
//
// Shows current period usage + projected invoice amount, polled every 30s.
// Reads from a consumer-provided endpoint /api/usage/current. The /stripe-standard
// scaffold doesn't include that endpoint — it depends on the consumer's data
// model. The template here only renders the UI; wire `fetchUsage` to your
// own backend.
// ----------------------------------------------------------------------------

import { useEffect, useState } from 'react';

export interface UsageData {
    quantity: number;
    unitLabel: string; // e.g. 'API calls', 'MB transferred'
    unitAmountCents: number; // price per unit in cents
    currency: string; // e.g. 'eur'
    periodEnd: string; // ISO timestamp
}

export interface UsageMeterProps {
    /** Consumer-provided fetcher for the current period's usage. */
    fetchUsage: () => Promise<UsageData>;
    /** Soft limit display (optional). */
    softLimit?: number;
    /** Polling interval in ms. Default 30s. */
    pollIntervalMs?: number;
}

export function UsageMeter({ fetchUsage, softLimit, pollIntervalMs = 30_000 }: UsageMeterProps) {
    const [data, setData] = useState<UsageData | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        const tick = async () => {
            try {
                const u = await fetchUsage();
                if (!cancelled) setData(u);
            } catch (err) {
                if (!cancelled) setError(err instanceof Error ? err.message : String(err));
            }
        };
        void tick();
        const id = setInterval(tick, pollIntervalMs);
        return () => {
            cancelled = true;
            clearInterval(id);
        };
    }, [fetchUsage, pollIntervalMs]);

    if (error) return <p role="alert">{error}</p>;
    if (!data) return <p>Cargando uso...</p>;

    const projectedCents = data.quantity * data.unitAmountCents;
    const projected = (projectedCents / 100).toLocaleString(undefined, {
        style: 'currency',
        currency: data.currency.toUpperCase(),
    });
    const softLimitWarning = softLimit != null && data.quantity >= softLimit;

    return (
        <div>
            <div>
                <strong>{data.quantity.toLocaleString()}</strong> {data.unitLabel}
            </div>
            <div>
                Factura proyectada del periodo: <strong>{projected}</strong>
            </div>
            <small>Cierre: {new Date(data.periodEnd).toLocaleDateString()}</small>
            {softLimitWarning && (
                <p role="alert" style={{ color: '#d97706' }}>
                    Te acercas al límite de {softLimit?.toLocaleString()} {data.unitLabel}.
                </p>
            )}
        </div>
    );
}
