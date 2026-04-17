// ----------------------------------------------------------------------------
// stripe_service.dart — SpecBox /stripe-connect template
//
// Initializes flutter_stripe with the platform publishable key and configures
// Payment Sheet appearance from the project's Brand Kit (tokens substituted
// by /stripe-connect during skill execution).
//
// Apple Pay + Google Pay are enabled by default. If the device doesn't
// support them the Payment Sheet silently omits those payment methods.
// ----------------------------------------------------------------------------

import 'package:flutter/foundation.dart';
import 'package:flutter_stripe/flutter_stripe.dart';

class StripeService {
  StripeService._();

  static final StripeService instance = StripeService._();

  bool _initialized = false;

  /// Call once at app startup (e.g. in main() before runApp).
  Future<void> init({
    required String publishableKey,
    String merchantIdentifier = 'merchant.com.example.marketplace', // TODO: your Apple Pay Merchant ID
    String urlScheme = 'marketplace',                                // TODO: your app's URL scheme for 3DS return
  }) async {
    if (_initialized) return;

    Stripe.publishableKey = publishableKey;
    Stripe.merchantIdentifier = merchantIdentifier;
    Stripe.urlScheme = urlScheme;
    await Stripe.instance.applySettings();

    _initialized = true;

    if (kDebugMode) {
      debugPrint('StripeService initialized (test mode: ${publishableKey.startsWith('pk_test_')})');
    }
  }

  /// Presents the Payment Sheet for a subscription created on a connected account.
  /// Returns true if the payment succeeded, false otherwise.
  Future<bool> presentPaymentSheetForSponsorship({
    required String clientSecret,
    required String stripeAccountId,
    required String merchantDisplayName,
    String merchantCountryCode = 'ES', // {default_country}
  }) async {
    await Stripe.instance.initPaymentSheet(
      paymentSheetParameters: SetupPaymentSheetParameters(
        paymentIntentClientSecret: clientSecret,
        merchantDisplayName: merchantDisplayName,
        // Direct charges: scope Payment Sheet to the connected account
        // so SCA / 3DS runs in the correct context.
        stripeAccountId: stripeAccountId,

        // Apple Pay (iOS) — default on
        applePay: PaymentSheetApplePay(
          merchantCountryCode: merchantCountryCode,
        ),

        // Google Pay (Android) — default on
        googlePay: PaymentSheetGooglePay(
          merchantCountryCode: merchantCountryCode,
          testEnv: publishableKeyIsTest,
        ),

        // Appearance tokens — {brand_kit} parametrizado por /stripe-connect
        appearance: const PaymentSheetAppearance(
          colors: PaymentSheetAppearanceColors(
            primary: Color(0xFF635BFF),     // TODO: Brand Kit primary
            background: Color(0xFFFFFFFF),
            componentText: Color(0xFF1F2937),
            icon: Color(0xFF6B7280),
          ),
          shapes: PaymentSheetShape(
            borderRadius: 12,
          ),
          primaryButton: PaymentSheetPrimaryButtonAppearance(
            shapes: PaymentSheetPrimaryButtonShape(
              borderRadius: 12,
            ),
          ),
        ),
      ),
    );

    try {
      await Stripe.instance.presentPaymentSheet();
      return true;
    } on StripeException catch (e) {
      if (e.error.code == FailureCode.Canceled) {
        return false; // user dismissed
      }
      // Let callers decide UX — rethrow so controller can show error
      rethrow;
    }
  }

  bool get publishableKeyIsTest => Stripe.publishableKey.startsWith('pk_test_');
}

/// Minimal Color shim — delete if your project already imports flutter/material.
class Color {
  const Color(this.value);
  final int value;
}
