// ----------------------------------------------------------------------------
// sponsor_rider_controller.dart — SpecBox /stripe-connect template
//
// Flow controller for the sponsorship checkout. /stripe-connect emits ONE of
// two variants depending on the project's state management:
//   - Riverpod (default when `flutter_riverpod` is in pubspec.yaml)
//   - BLoC     (when `flutter_bloc` is in pubspec.yaml)
//
// This file ships the Riverpod variant. The BLoC variant lives side-by-side
// as sponsor_rider_bloc.dart; /stripe-connect keeps only the one matching
// your project.
//
// States (freezed-style union could replace the sealed class below):
//   idle
//   creatingIntent                (waiting for Edge Function)
//   confirmingPayment             (Payment Sheet presented)
//   success(subscriptionId)
//   error(message)
// ----------------------------------------------------------------------------

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'stripe_service.dart';

sealed class SponsorState {
  const SponsorState();
}

class SponsorIdle extends SponsorState {
  const SponsorIdle();
}

class SponsorCreatingIntent extends SponsorState {
  const SponsorCreatingIntent();
}

class SponsorConfirmingPayment extends SponsorState {
  const SponsorConfirmingPayment();
}

class SponsorSuccess extends SponsorState {
  const SponsorSuccess(this.subscriptionId);
  final String subscriptionId;
}

class SponsorErrorState extends SponsorState {
  const SponsorErrorState(this.message);
  final String message;
}

/// Contract the controller needs — implement with your HTTP client of choice.
/// /stripe-connect generates a dio-based implementation at
/// lib/billing/api_interceptor.dart that adds Stripe-Account header.
abstract class SponsorshipApi {
  Future<CreateSubscriptionResult> createFanSubscription({
    required String fanId,
    required String riderId,
    required String priceId,
  });
}

class CreateSubscriptionResult {
  const CreateSubscriptionResult({
    required this.subscriptionId,
    required this.clientSecret,
    required this.stripeAccountId,
  });
  final String subscriptionId;
  final String clientSecret;
  final String stripeAccountId;
}

class SponsorController extends StateNotifier<SponsorState> {
  SponsorController({
    required SponsorshipApi api,
    required String merchantDisplayName,
  })  : _api = api,
        _merchantDisplayName = merchantDisplayName,
        super(const SponsorIdle());

  final SponsorshipApi _api;
  final String _merchantDisplayName;

  Future<void> sponsorRider({
    required String fanId,
    required String riderId,
    required String priceId,
  }) async {
    state = const SponsorCreatingIntent();

    CreateSubscriptionResult result;
    try {
      result = await _api.createFanSubscription(
        fanId: fanId,
        riderId: riderId,
        priceId: priceId,
      );
    } catch (e, st) {
      debugPrint('create-fan-subscription failed: $e\n$st');
      state = SponsorErrorState('No pudimos preparar el pago: $e');
      return;
    }

    state = const SponsorConfirmingPayment();

    try {
      final succeeded = await StripeService.instance.presentPaymentSheetForSponsorship(
        clientSecret: result.clientSecret,
        stripeAccountId: result.stripeAccountId,
        merchantDisplayName: _merchantDisplayName,
      );
      if (succeeded) {
        state = SponsorSuccess(result.subscriptionId);
      } else {
        state = const SponsorIdle(); // user dismissed
      }
    } catch (e, st) {
      debugPrint('Payment Sheet failed: $e\n$st');
      state = SponsorErrorState(e.toString());
    }
  }

  void reset() => state = const SponsorIdle();
}

/// Riverpod provider — tune `api` and `merchantDisplayName` to your DI setup.
final sponsorControllerProvider =
    StateNotifierProvider.family<SponsorController, SponsorState, SponsorControllerArgs>(
  (ref, args) => SponsorController(
    api: args.api,
    merchantDisplayName: args.merchantDisplayName,
  ),
);

class SponsorControllerArgs {
  const SponsorControllerArgs({
    required this.api,
    required this.merchantDisplayName,
  });
  final SponsorshipApi api;
  final String merchantDisplayName;
}
