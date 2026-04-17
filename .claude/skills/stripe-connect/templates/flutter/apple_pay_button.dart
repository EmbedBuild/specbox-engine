// ----------------------------------------------------------------------------
// apple_pay_button.dart — SpecBox /stripe-connect template
//
// Convenience wrapper showing the native Apple Pay button. Only renders on
// iOS devices where Apple Pay is available. Elsewhere returns SizedBox.shrink.
//
// Real payment flow happens through the Payment Sheet presented by
// SponsorController — this button is a shortcut that can trigger the same
// flow directly, showing the Apple Pay glyph per Apple's HIG guidelines.
// ----------------------------------------------------------------------------

import 'dart:io' show Platform;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart';

class ApplePayButton extends StatelessWidget {
  const ApplePayButton({
    super.key,
    required this.onPressed,
    this.style = PlatformButtonStyle.automatic,
  });

  final VoidCallback onPressed;
  final PlatformButtonStyle style;

  @override
  Widget build(BuildContext context) {
    if (kIsWeb || !Platform.isIOS) {
      return const SizedBox.shrink();
    }

    return PlatformPayButton(
      type: PlatformButtonType.subscribe,
      appearance: style == PlatformButtonStyle.light
          ? PlatformButtonAppearance.light
          : PlatformButtonAppearance.automatic,
      onPressed: onPressed,
    );
  }
}

enum PlatformButtonStyle { automatic, light, dark }
