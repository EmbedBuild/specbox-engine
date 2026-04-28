// ----------------------------------------------------------------------------
// billing_controller.dart — SpecBox /stripe-standard template
//
// ChangeNotifier-based state for billing. Reads stripe_subscriptions via
// Supabase. Wire it once at app startup; UI listens via ListenableBuilder.
//
// Replace the supabase getter with whatever your project uses (Riverpod
// provider, get_it singleton, etc.).
// ----------------------------------------------------------------------------

import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

enum SubscriptionStatus {
  none,
  incomplete,
  trialing,
  active,
  pastDue,
  canceled,
  unpaid,
  paused,
}

class StripeSubscriptionRow {
  StripeSubscriptionRow({
    required this.id,
    required this.stripeSubscriptionId,
    required this.priceId,
    required this.status,
    required this.currentPeriodEnd,
    required this.cancelAtPeriodEnd,
    required this.metadata,
  });

  final String id;
  final String stripeSubscriptionId;
  final String? priceId;
  final SubscriptionStatus status;
  final DateTime? currentPeriodEnd;
  final bool cancelAtPeriodEnd;
  final Map<String, dynamic> metadata;

  factory StripeSubscriptionRow.fromMap(Map<String, dynamic> row) {
    return StripeSubscriptionRow(
      id: row['id'] as String,
      stripeSubscriptionId: row['stripe_subscription_id'] as String,
      priceId: row['price_id'] as String?,
      status: _statusFromString(row['status'] as String),
      currentPeriodEnd: row['current_period_end'] != null
          ? DateTime.parse(row['current_period_end'] as String).toLocal()
          : null,
      cancelAtPeriodEnd: row['cancel_at_period_end'] as bool? ?? false,
      metadata: (row['metadata'] as Map?)?.cast<String, dynamic>() ?? const {},
    );
  }

  bool get isActive =>
      status == SubscriptionStatus.active || status == SubscriptionStatus.trialing;

  bool hasTier(String tierKey) => metadata['tier_key'] == tierKey;
}

SubscriptionStatus _statusFromString(String s) {
  switch (s) {
    case 'incomplete':
    case 'incomplete_expired':
      return SubscriptionStatus.incomplete;
    case 'trialing':
      return SubscriptionStatus.trialing;
    case 'active':
      return SubscriptionStatus.active;
    case 'past_due':
      return SubscriptionStatus.pastDue;
    case 'canceled':
      return SubscriptionStatus.canceled;
    case 'unpaid':
      return SubscriptionStatus.unpaid;
    case 'paused':
      return SubscriptionStatus.paused;
    default:
      return SubscriptionStatus.none;
  }
}

class BillingController extends ChangeNotifier {
  BillingController(this._supabase);

  final SupabaseClient _supabase;
  StripeSubscriptionRow? _sub;
  bool _loading = false;
  Object? _error;

  StripeSubscriptionRow? get sub => _sub;
  bool get loading => _loading;
  Object? get error => _error;
  bool get isActive => _sub?.isActive ?? false;
  bool hasTier(String tierKey) => _sub?.hasTier(tierKey) ?? false;

  Future<void> refresh() async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      // RLS limits to current user's rows.
      final rows = await _supabase
          .from('stripe_subscriptions')
          .select()
          .order('updated_at', ascending: false)
          .limit(1);
      _sub = (rows is List && rows.isNotEmpty)
          ? StripeSubscriptionRow.fromMap(rows.first as Map<String, dynamic>)
          : null;
    } catch (err) {
      _error = err;
      _sub = null;
    } finally {
      _loading = false;
      notifyListeners();
    }
  }
}
