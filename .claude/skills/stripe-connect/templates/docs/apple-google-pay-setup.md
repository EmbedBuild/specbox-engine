# Apple Pay + Google Pay — setup para Flutter

> Solo aplica si tu stack es Flutter. Con React, Apple Pay / Google Pay funcionan out-of-the-box a través de `<ExpressCheckoutElement>` en Chrome/Safari/Edge sin setup extra más allá de verificar tu dominio en Stripe.

La API de flutter_stripe ya queda configurada por `/stripe-connect`. Pero cada plataforma (iOS/Android) requiere pasos manuales en el portal de desarrollo — Stripe no puede hacerlos por ti.

---

## Apple Pay (iOS)

### 1. Crear Merchant ID en Apple Developer

1. https://developer.apple.com/account → **Certificates, Identifiers & Profiles**
2. Identifiers → **+** → Merchant IDs → Continue
3. Description: `{project_name} Marketplace`
4. Identifier: `merchant.com.example.{project_name}` (copia este valor)
5. Register

### 2. Añadir capability en Xcode

1. Abre `ios/Runner.xcworkspace` en Xcode
2. Runner target → Signing & Capabilities → **+ Capability** → Apple Pay
3. Marca el Merchant ID que creaste

### 3. Vincular Merchant ID a Stripe

1. Dashboard Stripe → Settings → Payment methods → Apple Pay
2. **Add new domain** o **Add new merchant ID**
3. Pega el `merchant.com.example.{project_name}`
4. Descarga el Apple Pay Merchant Identity Certificate que Stripe te genera
5. En Apple Developer, sube el certificate al Merchant ID
6. De vuelta en Stripe, verify

### 4. Actualizar `stripe_service.dart`

El template ya tiene:

```dart
Stripe.merchantIdentifier = 'merchant.com.example.marketplace'; // TODO: tu Merchant ID
```

Cámbialo por el tuyo. La skill deja un TODO intencional para evitar cablear un valor incorrecto.

---

## Google Pay (Android)

Más simple que Apple Pay:

### 1. Google Pay API configuration

1. https://pay.google.com/business/console → Business profile
2. Activa **Google Pay API**
3. Pide producción cuando tengas la app lista (en test no hace falta)

### 2. AndroidManifest.xml

`android/app/src/main/AndroidManifest.xml` debe contener:

```xml
<meta-data
  android:name="com.google.android.gms.wallet.api.enabled"
  android:value="true" />
```

flutter_stripe puede añadirlo automáticamente vía su plugin Gradle, pero verifica.

### 3. Testing en dispositivo

Google Pay solo funciona en dispositivos físicos o en el Android Studio emulator con Google Play Services. No intentes probar en el simulator vacío.

---

## Verificación en iOS Simulator

Apple Pay **SÍ funciona en el iOS Simulator** (desde iOS 11+). En Settings → Wallet & Apple Pay puedes añadir tarjetas de prueba. El Payment Sheet las detectará automáticamente.

---

## Troubleshooting común

| Síntoma | Causa probable | Fix |
|---------|----------------|-----|
| Apple Pay button no aparece | Merchant ID mal configurado o entitlement faltante | Revisa Xcode Signing & Capabilities |
| Google Pay button no aparece | Dispositivo sin Google Play Services | Prueba en emulator con Google APIs |
| "Your merchant identifier is unregistered with Stripe" | No hiciste el Step 3 de Apple Pay | Revisa Settings → Payment methods en dashboard Stripe |
| Apple Pay aparece pero el botón submit no responde | `urlScheme` mal configurado en Stripe.urlScheme | Asegúrate de que matchea el scheme declarado en Info.plist |

---

## Referencias

- https://docs.stripe.com/apple-pay
- https://docs.stripe.com/google-pay
- https://pub.dev/packages/flutter_stripe (README del paquete tiene troubleshooting exhaustivo)
