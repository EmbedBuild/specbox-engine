# Catálogo de eventos webhook — v1

> 10 eventos críticos que el handler en `supabase/functions/stripe-webhook/index.ts` procesa. Todo lo demás se ignora silenciosamente (Stripe envía muchos eventos que no son relevantes para tu dominio).

Leyenda:

- **Endpoint**: `Platform` = webhook de tu cuenta plataforma · `Connect` = webhook recibido en nombre de un connected account (el piloto). Stripe permite usar un único URL para ambos, como hace este template.
- **Idempotencia**: ya garantizada para todos por la tabla `stripe_processed_events`. La columna "Acción backend" asume que el evento no es duplicado.

---

## Eventos de plataforma

### `account.updated`

| Campo | Valor |
|-------|-------|
| **Disparado cuando** | Un connected account cambia algo relevante: KYC avanza, Stripe pide más info, bancos se verifican, estado `charges_enabled` / `payouts_enabled` cambia |
| **Endpoint** | Platform |
| **Acción backend** | Recalcular `riders.onboarding_status` basado en `charges_enabled + payouts_enabled + requirements.disabled_reason`. Posibles valores: `pending`, `restricted`, `enabled` |
| **Fila DB modificada** | `riders.onboarding_status`, `riders.updated_at` |
| **UX relacionada** | Si pasa a `enabled`, puedes enviar push/email al piloto diciéndole "ya puedes recibir patrocinios" y marcarlo como visible en el listado |

### `capability.updated`

| Campo | Valor |
|-------|-------|
| **Disparado cuando** | Una capability (`card_payments`, `transfers`) del connected account cambia de estado |
| **Endpoint** | Platform |
| **Acción backend** | En v1 se ignora — el `account.updated` es source-of-truth suficiente. Si necesitas granularidad por capability, reaccionar aquí |
| **Fila DB modificada** | Ninguna en v1 |
| **UX relacionada** | - |

### `account.application.deauthorized`

| Campo | Valor |
|-------|-------|
| **Disparado cuando** | El rider desconectó su cuenta Stripe de tu plataforma (botón en su Express Dashboard) |
| **Endpoint** | Platform |
| **Acción backend** | Marcar `riders.onboarding_status = 'deauthorized'`. Puedes opcionalmente cancelar todas sus suscripciones activas |
| **Fila DB modificada** | `riders.onboarding_status`. Opcionalmente `sponsorships.status` para todas las del rider |
| **UX relacionada** | Enviar email a fans avisando que el rider ya no está disponible (si decides cancelar sus subs) |

---

## Eventos Connect

### `customer.subscription.created`

| Campo | Valor |
|-------|-------|
| **Disparado cuando** | `create-fan-subscription` Edge Function creó la Subscription (inmediatamente después) |
| **Endpoint** | Connect |
| **Acción backend** | Actualizar `sponsorships.status` al status real de Stripe (`incomplete` inicialmente, pasa a `active` tras invoice.paid). Guardar `current_period_end` |
| **Fila DB modificada** | `sponsorships.status`, `sponsorships.current_period_end` |
| **UX relacionada** | Ninguna directa — el fan ya ve el éxito en `confirmPayment` |

### `customer.subscription.updated`

| Campo | Valor |
|-------|-------|
| **Disparado cuando** | La subscription cambia: status, cancel_at_period_end, price cambia, etc. |
| **Endpoint** | Connect |
| **Acción backend** | Replicar el nuevo `status` y `cancel_at` a la fila correspondiente |
| **Fila DB modificada** | `sponsorships.status`, `sponsorships.cancel_at`, `sponsorships.updated_at` |
| **UX relacionada** | Si status pasa a `past_due`, UI puede mostrar banner "Tu método de pago falló, actualízalo" |

### `customer.subscription.deleted`

| Campo | Valor |
|-------|-------|
| **Disparado cuando** | La subscription se canceló (immediate o cuando llegó al cancel_at) |
| **Endpoint** | Connect |
| **Acción backend** | `sponsorships.status = 'canceled'` |
| **Fila DB modificada** | `sponsorships.status` |
| **UX relacionada** | Revocar beneficios del fan (contenido exclusivo, etc.). Notif opcional al piloto "X fan canceló" |

### `invoice.paid`

| Campo | Valor |
|-------|-------|
| **Disparado cuando** | Una factura (primer pago o renovación mensual) se cobró con éxito |
| **Endpoint** | Connect |
| **Acción backend** | `sponsorships.status = 'active'`, `last_paid_at = NOW()`. Si era una renovación, esto "ratea" el sponsorship por otro periodo |
| **Fila DB modificada** | `sponsorships.status`, `sponsorships.last_paid_at`, `sponsorships.updated_at` |
| **UX relacionada** | Ninguna obligatoria. Opcional: email "gracias por seguir sponsoreando a {rider}" |

### `invoice.payment_failed`

| Campo | Valor |
|-------|-------|
| **Disparado cuando** | Intento de cobro falló: tarjeta rechazada, fondos insuficientes, tarjeta caducada |
| **Endpoint** | Connect |
| **Acción backend** | `sponsorships.status = 'past_due'`. **TODO del proyecto**: enviar email al fan con link para actualizar método de pago. Stripe reintentará automáticamente (smart retries) durante varios días antes de cancelar |
| **Fila DB modificada** | `sponsorships.status = 'past_due'` |
| **UX relacionada** | Banner UX "Tu último pago falló, actualiza tu tarjeta" + email |

### `charge.refunded`

| Campo | Valor |
|-------|-------|
| **Disparado cuando** | Se hizo un refund manual desde el dashboard Stripe (o desde una Edge Function opcional) |
| **Endpoint** | Connect |
| **Acción backend** | En v1 solo se loguea para audit. Cambios reales al sponsorship llegan vía `subscription.updated` paralelo |
| **Fila DB modificada** | Ninguna en v1 (logging only) |
| **UX relacionada** | Email al fan "se te reembolsó X€" |

### `application_fee.created`

| Campo | Valor |
|-------|-------|
| **Disparado cuando** | Se cobró un `application_fee` (tu fee de marketplace) en una transacción |
| **Endpoint** | Connect |
| **Acción backend** | En v1 solo logging. El UC-311 (admin dashboard) lee el Balance API en vez de agregarlo aquí. Si quieres reporting fiscal propio, puedes persistir en una tabla `platform_fees` |
| **Fila DB modificada** | Ninguna en v1 |
| **UX relacionada** | Dashboard admin en /admin/fees (no crítico en v1) |

---

## Eventos que se ignoran intencionalmente en v1

Para referencia rápida cuando veas en logs "no handler for event X":

- `customer.created`, `customer.updated` — no necesitamos replicar customers; con Direct charges viven en el connected account
- `invoice.created`, `invoice.finalized`, `invoice.upcoming` — no bloquean nada; `invoice.paid` es suficiente
- `payment_intent.*` — tenemos visibilidad via `invoice.paid` / `invoice.payment_failed`
- `charge.succeeded`, `charge.failed` — idem
- `payout.*` — el rider ve sus payouts en Express Dashboard; no necesitamos replicarlo
- `charge.dispute.*` — queda fuera de v1, se añade cuando tengas un dispute real

Si en producción ves un evento ignorado que deberías haber manejado, añádelo al switch del webhook y actualiza este catálogo.
