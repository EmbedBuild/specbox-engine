# Test scenarios — `/stripe-connect`

Comandos listos para copiar. Asume que tienes `stripe listen` corriendo en otra terminal contra `http://localhost:54321/functions/v1/stripe-webhook`.

---

## Tarjetas de test útiles

| Número | Comportamiento |
|--------|----------------|
| `4242 4242 4242 4242` | Succeeds always |
| `4000 0025 0000 3155` | Requires authentication (3DS) — SCA flow |
| `4000 0000 0000 9995` | Insufficient funds → `payment_intent.payment_failed` |
| `4000 0000 0000 0002` | Card declined (generic) |
| `4000 0000 0000 0069` | Expired card |
| `4100 0000 0000 0019` | Works for initial payment, DECLINES on recurrence → `invoice.payment_failed` |

Cualquier fecha futura + cualquier CVC.

---

## Por UC

### UC-301 — Onboarding del piloto

```bash
# Ejecutar el flow manualmente:
curl -X POST http://localhost:54321/functions/v1/create-rider-account-link \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer $FAN_JWT' \
  -d '{"rider_id": "<uuid>", "return_url": "http://localhost:3000/onboarding/complete", "refresh_url": "http://localhost:3000/onboarding/refresh"}'

# Simular que Stripe terminó el KYC exitosamente:
stripe accounts update acct_XXX \
  --charges-enabled=true \
  --payouts-enabled=true \
  --requirements.currently_due=''

# Esto dispara account.updated → webhook → riders.onboarding_status='enabled'
```

### UC-302 — Retorno post-onboarding

```bash
# Forzar evento para verificar el handler:
stripe trigger account.updated

# Verificar en DB:
psql $DATABASE_URL -c "SELECT id, stripe_account_id, onboarding_status FROM riders ORDER BY updated_at DESC LIMIT 5;"
```

### UC-305 — Fan se suscribe (Direct charge + fee dinámico)

```bash
# Ejecutar create-fan-subscription:
curl -X POST http://localhost:54321/functions/v1/create-fan-subscription \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer $FAN_JWT' \
  -d '{"fan_id": "<uuid>", "rider_id": "<uuid>", "price_id": "price_XXX"}'

# Devuelve client_secret — normalmente el frontend confirma con Payment Element
# Para test end-to-end usar Playwright / Patrol, no curl

# Simular que el primer cobro fue exitoso:
stripe trigger invoice.paid

# Verificar:
psql $DATABASE_URL -c "SELECT fan_id, rider_id, status, last_paid_at FROM sponsorships ORDER BY created_at DESC LIMIT 5;"
```

### UC-306 — Webhook idempotencia (CRÍTICO)

```bash
# Disparar el mismo evento 3 veces:
stripe trigger invoice.paid --override invoice:id=in_test_duplicate

# Stripe reenvía el mismo event.id en retries automáticos — simularlo así:
EVENT_ID=$(stripe events list --limit 1 --json | jq -r '.data[0].id')
stripe events resend $EVENT_ID
stripe events resend $EVENT_ID
stripe events resend $EVENT_ID

# Verificar que la tabla stripe_processed_events tiene UNA sola fila para ese event_id:
psql $DATABASE_URL -c "SELECT event_id, COUNT(*) FROM stripe_processed_events WHERE event_id='$EVENT_ID' GROUP BY event_id;"
# Debería devolver 1

# Verificar que la sponsorship NO se procesó 4 veces:
psql $DATABASE_URL -c "SELECT last_paid_at FROM sponsorships WHERE stripe_subscription_id LIKE 'sub_%' ORDER BY updated_at DESC LIMIT 1;"
```

### UC-308 — Payment failed + retry

```bash
# Método 1: disparar evento directamente
stripe trigger invoice.payment_failed

# Método 2: crear una subscription con tarjeta que falla en recurrence
# (requiere flujo end-to-end con Payment Element en navegador)
# Tarjeta: 4100 0000 0000 0019

# Verificar sponsorship en past_due:
psql $DATABASE_URL -c "SELECT status FROM sponsorships WHERE status='past_due';"
```

### UC-309 — Cancelación por el fan

```bash
# Cancelar at_period_end:
curl -X POST http://localhost:54321/functions/v1/cancel-fan-subscription \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer $FAN_JWT' \
  -d '{"sponsorship_id": "<uuid>"}'

# Cancelar immediate (prorated refund):
curl -X POST http://localhost:54321/functions/v1/cancel-fan-subscription \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer $FAN_JWT' \
  -d '{"sponsorship_id": "<uuid>", "immediate": true}'

# Verificar:
psql $DATABASE_URL -c "SELECT status, cancel_at FROM sponsorships WHERE id='<uuid>';"
```

---

## Test Clocks — simular el tiempo

Renovación mensual en segundos en vez de esperar 30 días:

```bash
# 1. Crear un test clock frozen en hoy:
CLOCK=$(stripe test_helpers test_clocks create --frozen-time=$(date +%s) | jq -r '.id')

# 2. Crear customer asociado al clock (en el connected account):
stripe customers create \
  --test-clock=$CLOCK \
  --stripe-account=acct_RIDER

# 3. Crear subscription como de costumbre (create-fan-subscription Edge Function)
#    usando ese customer

# 4. Avanzar el tiempo 31 días para simular renovación:
stripe test_helpers test_clocks advance $CLOCK \
  --frozen-time=$(date -v+31d +%s)   # macOS
# En Linux: --frozen-time=$(date -d '+31 days' +%s)

# 5. Stripe automáticamente emitirá invoice.upcoming, invoice.finalized, invoice.paid
#    al avanzar el clock

# 6. Verificar que el webhook procesó todo:
psql $DATABASE_URL -c "SELECT event_type, COUNT(*) FROM stripe_processed_events GROUP BY event_type ORDER BY 2 DESC;"

# 7. Limpiar:
stripe test_helpers test_clocks delete $CLOCK
```

---

## Script `e2e-smoke.sh` recomendado

Copia este script a `.scripts/` de tu proyecto y lo lanzas para validar la integración completa:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "1. Verificar que las Edge Functions están desplegadas..."
curl -sf "$SUPABASE_URL/functions/v1/stripe-webhook" -X POST \
  -H 'Content-Type: application/json' -d '{}' | grep -q 'missing_signature' || {
    echo "❌ stripe-webhook no responde"; exit 1;
}

echo "2. Disparar eventos de smoke..."
stripe trigger account.updated
stripe trigger invoice.paid
stripe trigger invoice.payment_failed

echo "3. Verificar que los 3 eventos se procesaron (processed_at IS NOT NULL)..."
psql "$DATABASE_URL" -c "
  SELECT event_type, processed_at IS NOT NULL AS processed
  FROM stripe_processed_events
  ORDER BY received_at DESC
  LIMIT 3;
"

echo "✅ Smoke test passed"
```

---

## Gotchas conocidas

- `stripe trigger` crea eventos con datos sintéticos — los IDs (subscription_id, customer_id) NO existen en tu DB a menos que hayas creado las filas previamente. Para validar flujos end-to-end, primero crea las entidades manualmente.
- En un mismo `stripe listen`, los eventos se reenvían al primer endpoint listado. Si tienes varios handlers en paralelo, Stripe CLI solo forwardea a uno.
- `stripe events resend` reusa el event.id original — perfecto para testear idempotencia.
