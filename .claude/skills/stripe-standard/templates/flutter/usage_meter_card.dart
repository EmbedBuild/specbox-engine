// ----------------------------------------------------------------------------
// usage_meter_card.dart — SpecBox /stripe-standard template (metered mode only)
//
// Displays current period usage + projected invoice. Polls every 30s. The
// fetcher is consumer-provided since the usage data lives in the project's
// own backend (not part of /stripe-standard scaffold).
// ----------------------------------------------------------------------------

import 'dart:async';
import 'package:flutter/material.dart';

class UsageData {
  UsageData({
    required this.quantity,
    required this.unitLabel,
    required this.unitAmountCents,
    required this.currency,
    required this.periodEnd,
  });

  final int quantity;
  final String unitLabel;
  final int unitAmountCents;
  final String currency;
  final DateTime periodEnd;

  int get projectedCents => quantity * unitAmountCents;
}

class UsageMeterCard extends StatefulWidget {
  const UsageMeterCard({
    super.key,
    required this.fetchUsage,
    this.softLimit,
    this.pollInterval = const Duration(seconds: 30),
  });

  final Future<UsageData> Function() fetchUsage;
  final int? softLimit;
  final Duration pollInterval;

  @override
  State<UsageMeterCard> createState() => _UsageMeterCardState();
}

class _UsageMeterCardState extends State<UsageMeterCard> {
  Timer? _timer;
  UsageData? _data;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tick();
    _timer = Timer.periodic(widget.pollInterval, (_) => _tick());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _tick() async {
    try {
      final next = await widget.fetchUsage();
      if (!mounted) return;
      setState(() {
        _data = next;
        _error = null;
      });
    } catch (err) {
      if (!mounted) return;
      setState(() => _error = err.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return Card(child: Padding(padding: const EdgeInsets.all(12), child: Text(_error!)));
    }
    final data = _data;
    if (data == null) {
      return const Card(child: Padding(padding: EdgeInsets.all(12), child: Text('Cargando uso...')));
    }
    final projected = (data.projectedCents / 100).toStringAsFixed(2);
    final overSoftLimit = widget.softLimit != null && data.quantity >= widget.softLimit!;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${data.quantity} ${data.unitLabel}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text('Factura proyectada: $projected ${data.currency.toUpperCase()}'),
            const SizedBox(height: 4),
            Text(
              'Cierre: ${data.periodEnd.toLocal().toIso8601String().substring(0, 10)}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (overSoftLimit) ...[
              const SizedBox(height: 8),
              Text(
                'Te acercas al límite de ${widget.softLimit} ${data.unitLabel}.',
                style: const TextStyle(color: Colors.orange),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
