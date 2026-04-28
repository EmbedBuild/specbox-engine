// ----------------------------------------------------------------------------
// stripe_service.dart — SpecBox /stripe-standard template
//
// Initializes flutter_stripe with the publishable key from --dart-define or
// .env. Apple Pay needs a merchant identifier in Info.plist (iOS) and Google
// Pay is enabled by default on Android when the merchant country is set.
// ----------------------------------------------------------------------------

import 'package:flutter/foundation.dart';
import 'package:flutter_stripe/flutter_stripe.dart';

class StripeService {
  StripeService._();

  static Future<void> init({String merchantCountryCode = 'ES'}) async {
    final pk = const String.fromEnvironment('STRIPE_PUBLISHABLE_KEY');
    if (pk.isEmpty) {
      debugPrint(
          '[stripe-service] STRIPE_PUBLISHABLE_KEY missing. Pass via --dart-define.');
      return;
    }
    Stripe.publishableKey = pk;
    Stripe.merchantIdentifier = const String.fromEnvironment(
      'STRIPE_APPLE_MERCHANT_ID',
      defaultValue: 'merchant.example.com',
    );
    await Stripe.instance.applySettings();

    debugPrint(
        '[stripe-service] initialized for $merchantCountryCode (publishable key set)');
  }
}
