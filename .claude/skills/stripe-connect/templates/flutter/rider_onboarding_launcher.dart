// ----------------------------------------------------------------------------
// rider_onboarding_launcher.dart — SpecBox /stripe-connect template
//
// Triggers the Stripe Connect Express onboarding flow:
//   1. Calls create-rider-account-link Edge Function
//   2. Opens the returned URL in an external browser
//   3. Listens for deep link `{urlScheme}://billing/onboarding-complete`
//      to know when the rider returned
//
// Before launching, shows the fiscal warning (alta autónomo required in Spain).
// The warning UI is intentionally in this file so the project can adapt it.
// ----------------------------------------------------------------------------

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

class RiderOnboardingLauncher {
  const RiderOnboardingLauncher({
    required this.api,
    required this.returnUrl,
    required this.refreshUrl,
  });

  final RiderOnboardingApi api;
  final String returnUrl;
  final String refreshUrl;

  /// Shows fiscal warning modal, then launches onboarding on acknowledgment.
  /// Returns true if the launch happened, false if dismissed.
  Future<bool> launch(BuildContext context, {required String riderId}) async {
    final acknowledged = await showDialog<bool>(
      context: context,
      builder: (_) => const _FiscalWarningDialog(),
    );
    if (acknowledged != true) return false;

    final url = await api.createRiderAccountLink(
      riderId: riderId,
      returnUrl: returnUrl,
      refreshUrl: refreshUrl,
    );

    final ok = await launchUrl(
      Uri.parse(url),
      mode: LaunchMode.externalApplication,
    );
    return ok;
  }
}

abstract class RiderOnboardingApi {
  Future<String> createRiderAccountLink({
    required String riderId,
    required String returnUrl,
    required String refreshUrl,
  });
}

class _FiscalWarningDialog extends StatefulWidget {
  const _FiscalWarningDialog();

  @override
  State<_FiscalWarningDialog> createState() => _FiscalWarningDialogState();
}

class _FiscalWarningDialogState extends State<_FiscalWarningDialog> {
  bool _acknowledged = false;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Antes de continuar'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Para recibir patrocinios a través de esta plataforma necesitas estar '
            'dado de alta como autónomo en España o disponer de una sociedad. '
            'Stripe te solicitará tu NIF y una cuenta bancaria a tu nombre.\n\n'
            'Si aún no estás dado de alta, puedes completar el proceso en la '
            'Agencia Tributaria (modelo 036/037) y la Seguridad Social (RETA) '
            'antes de volver.',
          ),
          const SizedBox(height: 12),
          CheckboxListTile(
            dense: true,
            controlAffinity: ListTileControlAffinity.leading,
            contentPadding: EdgeInsets.zero,
            value: _acknowledged,
            onChanged: (v) => setState(() => _acknowledged = v ?? false),
            title: const Text('Entiendo los requisitos y quiero continuar.'),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          onPressed: _acknowledged
              ? () => Navigator.of(context).pop(true)
              : null,
          child: const Text('Continuar a Stripe'),
        ),
      ],
    );
  }
}
