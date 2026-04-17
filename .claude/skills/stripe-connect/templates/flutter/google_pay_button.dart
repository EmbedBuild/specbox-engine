// ----------------------------------------------------------------------------
// google_pay_button.dart — SpecBox /stripe-connect template
//
// Convenience wrapper showing the native Google Pay button. Only renders on
// Android devices where Google Pay is available.
// ----------------------------------------------------------------------------

import 'dart:io' show Platform;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart';

class GooglePayButton extends StatelessWidget {
  const GooglePayButton({
    super.key,
    required this.onPressed,
  });

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    if (kIsWeb || !Platform.isAndroid) {
      return const SizedBox.shrink();
    }

    return PlatformPayButton(
      type: PlatformButtonType.subscribe,
      appearance: PlatformButtonAppearance.automatic,
      onPressed: onPressed,
    );
  }
}
