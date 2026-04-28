// ----------------------------------------------------------------------------
// subscription_screen.dart — SpecBox /stripe-standard template
//
// Initiates a subscription via the stripe-create-subscription Edge Function
// and presents the PaymentSheet to confirm. Apple Pay + Google Pay show up
// automatically when the device supports them. 3DS is handled by the sheet.
// ----------------------------------------------------------------------------

import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class SubscriptionScreen extends StatefulWidget {
  const SubscriptionScreen({
    super.key,
    required this.priceId,
    this.merchantDisplayName = 'SpecBox',
  });

  final String priceId;
  final String merchantDisplayName;

  @override
  State<SubscriptionScreen> createState() => _SubscriptionScreenState();
}

class _SubscriptionScreenState extends State<SubscriptionScreen> {
  bool _busy = false;
  String? _error;

  Future<void> _subscribe() async {
    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      final supabase = Supabase.instance.client;
      final session = supabase.auth.currentSession;
      if (session == null) {
        throw Exception('Not authenticated');
      }

      // 1. Ask the Edge Function to create the subscription.
      final response = await supabase.functions.invoke(
        'stripe-create-subscription',
        body: {'price_id': widget.priceId},
      );

      if (response.status == 409) {
        throw Exception('Ya tienes una suscripción activa');
      }
      if (response.status != 200 || response.data == null) {
        throw Exception(
            'Error creating subscription (status ${response.status})');
      }

      final data = Map<String, dynamic>.from(response.data as Map);
      final clientSecret = data['client_secret'] as String?;
      if (clientSecret == null) {
        throw Exception('Stripe did not return a client_secret');
      }

      // 2. Initialize and present PaymentSheet.
      await Stripe.instance.initPaymentSheet(
        paymentSheetParameters: SetupPaymentSheetParameters(
          paymentIntentClientSecret: clientSecret,
          merchantDisplayName: widget.merchantDisplayName,
          // Apple/Google Pay defaults are picked up from publishable key + merchant id.
          applePay: const PaymentSheetApplePay(merchantCountryCode: 'ES'),
          googlePay: const PaymentSheetGooglePay(
            merchantCountryCode: 'ES',
            testEnv: true,
          ),
        ),
      );
      await Stripe.instance.presentPaymentSheet();

      // 3. Success — webhook will have updated stripe_subscriptions.
      if (!mounted) return;
      Navigator.of(context).pushReplacementNamed('/welcome');
    } on StripeException catch (err) {
      if (err.error.code == FailureCode.Canceled) {
        // User canceled; not an error worth surfacing prominently.
        if (mounted) setState(() => _busy = false);
        return;
      }
      if (mounted) {
        setState(() => _error = err.error.localizedMessage ?? 'Pago cancelado');
      }
    } catch (err) {
      if (mounted) {
        setState(() => _error = err.toString());
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Suscripción')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ElevatedButton(
              onPressed: _busy ? null : _subscribe,
              child: Text(_busy ? 'Procesando...' : 'Suscribirse'),
            ),
            if (_error != null) ...[
              const SizedBox(height: 16),
              Text(_error!, style: const TextStyle(color: Colors.red)),
            ],
          ],
        ),
      ),
    );
  }
}
