// ----------------------------------------------------------------------------
// one_shot_checkout_sheet.dart — SpecBox /stripe-standard template
//
// One-shot purchase via PaymentSheet (PaymentIntent). Caller provides amount
// and currency. Apple/Google Pay enabled by default.
// ----------------------------------------------------------------------------

import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class OneShotCheckoutSheet {
  static Future<bool> present({
    required int amountCents,
    String currency = 'eur',
    String merchantDisplayName = 'SpecBox',
    Map<String, String>? metadata,
  }) async {
    final supabase = Supabase.instance.client;
    final session = supabase.auth.currentSession;
    if (session == null) {
      throw Exception('Not authenticated');
    }

    final response = await supabase.functions.invoke(
      'stripe-create-payment-intent',
      body: {
        'amount': amountCents,
        'currency': currency,
        if (metadata != null) 'metadata': metadata,
      },
    );

    if (response.status != 200 || response.data == null) {
      throw Exception('Error creating payment intent (status ${response.status})');
    }

    final data = Map<String, dynamic>.from(response.data as Map);
    final clientSecret = data['client_secret'] as String?;
    if (clientSecret == null) throw Exception('Missing client_secret');

    await Stripe.instance.initPaymentSheet(
      paymentSheetParameters: SetupPaymentSheetParameters(
        paymentIntentClientSecret: clientSecret,
        merchantDisplayName: merchantDisplayName,
        applePay: const PaymentSheetApplePay(merchantCountryCode: 'ES'),
        googlePay: const PaymentSheetGooglePay(
          merchantCountryCode: 'ES',
          testEnv: true,
        ),
      ),
    );

    try {
      await Stripe.instance.presentPaymentSheet();
      return true;
    } on StripeException catch (err) {
      if (err.error.code == FailureCode.Canceled) {
        return false;
      }
      rethrow;
    }
  }
}
