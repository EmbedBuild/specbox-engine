// ----------------------------------------------------------------------------
// billing_portal_button.dart — SpecBox /stripe-standard template
//
// Opens the Stripe-hosted Customer Portal in the device browser.
// ----------------------------------------------------------------------------

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:url_launcher/url_launcher.dart';

class BillingPortalButton extends StatefulWidget {
  const BillingPortalButton({
    super.key,
    this.label = 'Manage subscription',
    this.returnUrl,
  });

  final String label;
  final String? returnUrl;

  @override
  State<BillingPortalButton> createState() => _BillingPortalButtonState();
}

class _BillingPortalButtonState extends State<BillingPortalButton> {
  bool _busy = false;
  String? _error;

  Future<void> _open() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final response = await Supabase.instance.client.functions.invoke(
        'stripe-create-portal-session',
        body: {
          if (widget.returnUrl != null) 'return_url': widget.returnUrl,
        },
      );
      if (response.status != 200 || response.data == null) {
        throw Exception('Portal session failed (${response.status})');
      }
      final url = (response.data as Map)['url'] as String?;
      if (url == null) throw Exception('Missing portal url');
      final uri = Uri.parse(url);
      if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
        throw Exception('Cannot launch URL');
      }
    } catch (err) {
      if (mounted) setState(() => _error = err.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        ElevatedButton(
          onPressed: _busy ? null : _open,
          child: Text(_busy ? 'Abriendo...' : widget.label),
        ),
        if (_error != null) ...[
          const SizedBox(height: 8),
          Text(_error!, style: const TextStyle(color: Colors.red)),
        ],
      ],
    );
  }
}
