// ----------------------------------------------------------------------------
// paywall_gate.dart — SpecBox /stripe-standard template
//
// Wrap any premium feature with [PaywallGate] and the user is redirected to
// /pricing if they don't have an active subscription. Reuse on iOS/Android/Web.
// ----------------------------------------------------------------------------

import 'package:flutter/material.dart';
import 'billing_controller.dart';

class PaywallGate extends StatelessWidget {
  const PaywallGate({
    super.key,
    required this.controller,
    required this.child,
    this.requireTier,
    this.fallback,
    this.loadingBuilder,
  });

  final BillingController controller;
  final Widget child;
  final String? requireTier;
  final Widget? fallback;
  final WidgetBuilder? loadingBuilder;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        if (controller.loading && controller.sub == null) {
          return loadingBuilder?.call(context) ?? const _PaywallSkeleton();
        }
        final allowed = controller.isActive &&
            (requireTier == null || controller.hasTier(requireTier!));

        if (!allowed) {
          if (fallback != null) return fallback!;
          // Default: navigate to /pricing on the next frame.
          WidgetsBinding.instance.addPostFrameCallback((_) {
            Navigator.of(context).pushReplacementNamed('/pricing');
          });
          return const SizedBox.shrink();
        }
        return child;
      },
    );
  }
}

class _PaywallSkeleton extends StatelessWidget {
  const _PaywallSkeleton();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: SizedBox(
        height: 120,
        child: LinearProgressIndicator(),
      ),
    );
  }
}
