# Stripe Connect — setup del proyecto `{project_name}`

> Generado por `/stripe-connect` el {generated_date}. Marketplace Connect Express + Direct charges + subscriptions embedded.

Este README es tu **checklist operativo**. Rellénalo de arriba a abajo. Cuando termines, tu integración de pagos está lista para el primer `/plan UC-301`.

---

## 1. Variables de entorno

Crea `.env.local` (o añade a tu `.env` existente) con:

```bash
# Plataforma (tu cuenta Stripe principal)
STRIPE_SECRET_KEY=sk_test_...            # Dashboard Stripe → Developers → API keys
STRIPE_PUBLISHABLE_KEY=pk_test_...        # Se expone al frontend (safe)

# Webhooks — DOS secretos distintos (platform + Connect)
STRIPE_WEBHOOK_SECRET_PLATFORM=whsec_...  # Se crea al añadir endpoint en Webhooks → "Endpoint" → Add endpoint
STRIPE_WEBHOOK_SECRET_CONNECT=whsec_...   # Mismo dashboard → Webhooks → "Connect" tab → Add endpoint

# Fee default para sellers sin override (riders.fee_percent IS NULL)
DEFAULT_APPLICATION_FEE_PERCENT={fee_default}

# Supabase
SUPABASE_URL=...                          # Ya lo tienes si el proyecto usa Supabase
SUPABASE_ANON_KEY=...                     # Idem
SUPABASE_SERVICE_ROLE_KEY=...             # ⚠️ Backend only. Nunca en cliente.
```

Para los frontends, también:

```bash
# React (Vite)
VITE_STRIPE_PUBLISHABLE_KEY=$STRIPE_PUBLISHABLE_KEY
VITE_SUPABASE_URL=$SUPABASE_URL
VITE_SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY

# Flutter (pasa por --dart-define)
flutter run --dart-define=STRIPE_PK=$STRIPE_PUBLISHABLE_KEY
```

---

## 2. Activar Connect en Stripe

1. Ve a https://dashboard.stripe.com/test/connect/overview
2. Activa Connect (el wizard te pregunta país, modelo de negocio, URL)
3. En **Settings → Connect → Branding** configura logo, color y display name para el onboarding Express. Esto es lo que los pilotos verán al dar de alta su cuenta
4. En **Settings → Connect → Platform settings**:
   - **Cobro**: selecciona "Direct charges" (no Destination)
   - **Fees**: configura cómo se mostrará tu fee en el Express Dashboard del rider

Detalles adicionales en [connect-setup.md](./connect-setup.md).

---

## 3. Aplicar las migraciones

```bash
# Revisa primero lo que va a aplicar
supabase db diff --linked

# Aplica
supabase db push
```

Las 4 migraciones son idempotentes (`CREATE IF NOT EXISTS` + `ALTER ADD IF NOT EXISTS`). Si te arrepientes, puedes revertir manualmente eliminando las columnas añadidas a `riders` y dropping las tablas nuevas — pero guarda backup antes.

---

## 4. Desplegar las Edge Functions

```bash
# Una por una:
supabase functions deploy create-rider-account-link
supabase functions deploy create-fan-subscription
supabase functions deploy cancel-fan-subscription
supabase functions deploy create-rider-dashboard-link
supabase functions deploy stripe-webhook --no-verify-jwt  # ⚠️ Webhook NO tiene JWT
```

> El flag `--no-verify-jwt` en `stripe-webhook` es obligatorio — Stripe firma con `Stripe-Signature` en lugar de JWT. La seguridad la aporta la verificación de firma dentro del handler.

Después, configura los secretos en Supabase:

```bash
supabase secrets set \
  STRIPE_SECRET_KEY=$STRIPE_SECRET_KEY \
  STRIPE_WEBHOOK_SECRET_PLATFORM=$STRIPE_WEBHOOK_SECRET_PLATFORM \
  STRIPE_WEBHOOK_SECRET_CONNECT=$STRIPE_WEBHOOK_SECRET_CONNECT \
  DEFAULT_APPLICATION_FEE_PERCENT={fee_default}
```

---

## 5. Registrar los webhooks en Stripe

Vas a necesitar **DOS endpoints** (mismo URL, distintos tipos):

**Endpoint de plataforma** (https://dashboard.stripe.com/test/webhooks):

- URL: `{SUPABASE_URL}/functions/v1/stripe-webhook`
- Events:
  - `account.updated`
  - `capability.updated`
  - `account.application.deauthorized`
- Copia el `whsec_...` al `STRIPE_WEBHOOK_SECRET_PLATFORM`

**Endpoint Connect** (mismo dashboard → tab "Connect"):

- URL: `{SUPABASE_URL}/functions/v1/stripe-webhook` (misma)
- Events:
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.paid`
  - `invoice.payment_failed`
  - `charge.refunded`
  - `application_fee.created`
- Copia el `whsec_...` al `STRIPE_WEBHOOK_SECRET_CONNECT`

---

## 6. Probar en local con Stripe CLI

Desarrollo iterativo — reenvía webhooks reales a tu máquina:

```bash
# Terminal 1: Supabase local
supabase start

# Terminal 2: reenviar webhooks a la función local
stripe listen --forward-to http://localhost:54321/functions/v1/stripe-webhook

# Terminal 3: probar eventos
stripe trigger invoice.paid
stripe trigger customer.subscription.deleted
```

Comandos completos por UC en [../doc/design/billing/test-scenarios.md](../../doc/design/billing/test-scenarios.md).

---

## 7. Warning fiscal (España)

Si tus sellers son personas físicas en España, **deben estar dados de alta como autónomos** antes de conectar su cuenta Stripe — de lo contrario Hacienda puede reclamarles IRPF sin que ellos hayan facturado correctamente. El UC-301 del proyecto ya incluye el warning en la UI; verifica que lo muestras antes del redirect a Stripe.

Esta guía **no es asesoramiento legal**. Consulta con tu gestor antes de lanzar en producción.

---

## Siguiente paso

Todo listo. Ejecuta `/plan UC-301` para empezar por el onboarding del seller.
