# Stripe Connect — configuración detallada

Referencia para el setup completo de Connect. Complemento de [infra-stripe-README.md](./infra-stripe-README.md).

---

## Activar Connect (una vez por cuenta Stripe)

1. https://dashboard.stripe.com/test/connect/overview → **Get started with Connect**
2. Selecciona tu país (plataforma) y el país de tus sellers (puede ser el mismo)
3. Elige tu modelo:
   - **SaaS platform** — para plataformas que cobran a negocios
   - **Marketplace** — para plataformas que conectan compradores y vendedores (este es tu caso si haces micropatrocinios)
4. Declara que procesas pagos vía Direct charges

---

## Branding del onboarding Express

Los pilotos ven tu marca durante el KYC. Configura:

- **Dashboard → Settings → Connect → Branding**
- Logo (PNG cuadrado, fondo transparente, mínimo 128×128)
- Icon (32×32 para favicon del Express Dashboard)
- Primary color (hex; se usa para botones y acentos)
- Platform name

---

## Configurar Platform settings

- **Dashboard → Settings → Connect → Platform settings**
- **Charge type**: selecciona "Direct charges" (**no** "Destination charges" ni "Separate charges and transfers")
- **Fees**: Stripe mostrará tu fee en el Express Dashboard del rider como "marketplace fee"
- **Payouts**: deja el default (automático 2 días rolling) salvo que tengas requerimientos específicos
- **Collect tax ID**: activa esto si tus sellers son residentes fiscales en países que lo requieran

---

## Test sellers (sandbox)

En modo test puedes crear "conectados" rápidamente con datos de prueba:

- **DNI español (test)**: usa el test data de Stripe → https://docs.stripe.com/connect/testing
- **IBAN español (test)**: `ES0700120345030000067890`
- **Fecha de nacimiento**: cualquiera mayor de 18
- **Address**: cualquiera válida en España

Para disparar rápido transiciones del estado del connected account:

```bash
# Forzar un connected account a charges_enabled=true
stripe accounts update acct_XXX --charges-enabled=true --payouts-enabled=true
```

---

## URLs de retorno y refresh

En `create-rider-account-link` (Edge Function) pasas `return_url` y `refresh_url`. Recomendaciones:

- **return_url**: `https://app.example.com/rider/onboarding/complete?account_id={CHECKOUT_SESSION_ID}`
  - El frontend detecta la URL, lee `account_id` y muestra pantalla de "procesando" mientras espera el webhook `account.updated` con `charges_enabled=true`
- **refresh_url**: `https://app.example.com/rider/onboarding/refresh`
  - El Account Link expira (~5 min). Si el rider lo abre tarde, aterriza aquí y tú reintentas el `create-rider-account-link`

---

## Deep links (Flutter)

Si usas la skill con stack Flutter, configura el URL scheme en `ios/Runner/Info.plist` y `android/app/src/main/AndroidManifest.xml` para que el deep link `marketplace://billing/onboarding-complete` abra tu app de vuelta cuando el rider acabe.

Stripe no tiene deep link callbacks nativos — usas URLs https normales y un sistema de Universal Links / App Links para que la plataforma re-abra tu app en iOS/Android. Alternativa simple: el rider vuelve manualmente a la app.

---

## Referencias oficiales

- https://docs.stripe.com/connect/express-accounts
- https://docs.stripe.com/connect/direct-charges
- https://docs.stripe.com/connect/testing
- https://docs.stripe.com/connect/subscriptions
