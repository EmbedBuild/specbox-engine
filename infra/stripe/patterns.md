# Stripe - Patrones de Infraestructura

> SpecBox Engine v3.9.0 | Referencia de patrones para integracion de pagos con Stripe

---

## 1. Modelo Product / Price

### Estructura recomendada

```
Product (lo que vendes)
  |-- Price (como lo cobras)
       |-- recurring (suscripcion mensual/anual)
       |-- one_time (pago unico)
```

### Reglas

- Un Product puede tener multiples Prices (mensual, anual, por uso).
- Crear Products y Prices desde el Dashboard o via API, nunca hardcodear IDs en el cliente.
- Almacenar `price_id` y `product_id` en la base de datos del proyecto.
- Sincronizar cambios de precios mediante webhooks, no polling.

---

## 2. Flujo de Checkout Session

### Backend: Crear sesion

```typescript
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

const session = await stripe.checkout.sessions.create({
    mode: 'subscription',  // o 'payment' para pago unico
    customer: customerId,  // si ya existe
    line_items: [
        { price: '{price_id}', quantity: 1 }
    ],
    success_url: '{base_url}/checkout/success?session_id={CHECKOUT_SESSION_ID}',
    cancel_url: '{base_url}/checkout/cancel',
    metadata: {
        user_id: userId,
        project: '{project}',
    },
});

return { url: session.url };
```

### Flujo completo

```
1. Cliente solicita checkout -> Backend crea Session
2. Cliente redirige a session.url (Stripe hosted)
3. Stripe procesa pago
4. Stripe envia webhook checkout.session.completed
5. Backend actualiza estado en base de datos
6. Cliente es redirigido a success_url
```

**Regla:** Nunca confiar en el redirect a success_url para activar funcionalidad. Siempre usar el webhook como fuente de verdad.

---

## 3. Manejo de webhooks

### Endpoint de webhook

```typescript
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);
const endpointSecret = process.env.STRIPE_WEBHOOK_SECRET!;

export async function handleWebhook(req: Request) {
    const body = await req.text();
    const signature = req.headers.get('stripe-signature')!;

    let event: Stripe.Event;

    try {
        event = stripe.webhooks.constructEvent(body, signature, endpointSecret);
    } catch (err) {
        return new Response('Firma invalida', { status: 400 });
    }

    switch (event.type) {
        case 'checkout.session.completed':
            await handleCheckoutComplete(event.data.object);
            break;
        case 'customer.subscription.updated':
            await handleSubscriptionUpdate(event.data.object);
            break;
        case 'customer.subscription.deleted':
            await handleSubscriptionCanceled(event.data.object);
            break;
        case 'invoice.payment_failed':
            await handlePaymentFailed(event.data.object);
            break;
    }

    return new Response('OK', { status: 200 });
}
```

### Verificacion de firma (seguridad)

- Siempre verificar la firma del webhook usando `stripe.webhooks.constructEvent`.
- Nunca procesar un evento sin verificacion.
- El `STRIPE_WEBHOOK_SECRET` se obtiene del Dashboard de Stripe al crear el endpoint.
- Para desarrollo local, usar `stripe listen --forward-to localhost:3000/api/webhooks/stripe`.

### Eventos criticos a escuchar

| Evento | Accion |
|--------|--------|
| `checkout.session.completed` | Activar suscripcion / entregar producto |
| `customer.subscription.updated` | Actualizar plan del usuario |
| `customer.subscription.deleted` | Revocar acceso |
| `invoice.payment_failed` | Notificar al usuario, marcar cuenta |
| `invoice.paid` | Confirmar renovacion |

---

## 4. Ciclo de vida de suscripciones

### Estados de suscripcion

```
active -> past_due -> canceled -> (fin)
active -> trialing -> active
active -> paused -> active
```

### Tabla de sincronizacion en base de datos

```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    stripe_customer_id TEXT NOT NULL,
    stripe_subscription_id TEXT UNIQUE NOT NULL,
    stripe_price_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Regla de acceso

```typescript
function hasActiveSubscription(subscription: Subscription): boolean {
    return ['active', 'trialing'].includes(subscription.status)
        && new Date(subscription.current_period_end) > new Date();
}
```

---

## 5. Customer Portal

### Crear sesion del portal

```typescript
const portalSession = await stripe.billingPortal.sessions.create({
    customer: stripeCustomerId,
    return_url: '{base_url}/settings/billing',
});

return { url: portalSession.url };
```

El Customer Portal permite al usuario gestionar su suscripcion (cambiar plan, cancelar, actualizar metodo de pago) sin necesidad de construir UI personalizada.

---

## 6. Integracion Flutter (stripe_flutter)

### Dependencia

```yaml
dependencies:
    flutter_stripe: ^10.0.0
```

### Inicializacion

```dart
void main() async {
    Stripe.publishableKey = const String.fromEnvironment('STRIPE_PK');
    await Stripe.instance.applySettings();
    runApp(const App());
}
```

### Flujo con Payment Sheet

```dart
// 1. Obtener client_secret del backend
final response = await api.createPaymentIntent(amount: 1000, currency: 'eur');

// 2. Inicializar Payment Sheet
await Stripe.instance.initPaymentSheet(
    paymentSheetParameters: SetupPaymentSheetParameters(
        paymentIntentClientSecret: response.clientSecret,
        merchantDisplayName: '{project}',
    ),
);

// 3. Presentar Payment Sheet
await Stripe.instance.presentPaymentSheet();
```

---

## 7. Integracion React (@stripe/react-stripe-js)

### Instalacion

```bash
npm install @stripe/stripe-js @stripe/react-stripe-js
```

### Provider

```tsx
import { Elements } from '@stripe/react-stripe-js';
import { loadStripe } from '@stripe/stripe-js';

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PK!);

function App({ children }: { children: React.ReactNode }) {
    return (
        <Elements stripe={stripePromise}>
            {children}
        </Elements>
    );
}
```

### Redireccion a Checkout (metodo preferido)

```typescript
const stripe = await loadStripe(process.env.NEXT_PUBLIC_STRIPE_PK!);

// Redirigir a Stripe Checkout (session creada en backend)
await stripe?.redirectToCheckout({ sessionId });
```

---

## 8. Buenas practicas generales

- Usar modo test (`sk_test_`, `pk_test_`) durante desarrollo.
- Nunca exponer `STRIPE_SECRET_KEY` en el cliente.
- Almacenar `stripe_customer_id` en la tabla de usuarios al crear el customer.
- Usar `metadata` en Sessions y Subscriptions para vincular con el user_id interno.
- Implementar idempotencia en los handlers de webhook (el mismo evento puede llegar mas de una vez).
- Probar webhooks localmente con `stripe listen` antes de desplegar.
