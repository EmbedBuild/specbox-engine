// ----------------------------------------------------------------------------
// api_interceptor.dart — SpecBox /stripe-connect template
//
// Dio interceptor that adds the current rider's `Stripe-Account` header when
// requests target Stripe-Connect-routed endpoints. This is required for Direct
// charges — without it, SCA challenges are scoped to the platform account
// instead of the connected account and confirmPayment fails.
//
// Also injects the Supabase auth headers (apikey + Bearer JWT) for Edge
// Function calls — otherwise RLS blocks the request.
//
// If your project uses http/Chopper instead of Dio, adapt the base class;
// the logic is trivial to port (single header injection per request).
// ----------------------------------------------------------------------------

import 'package:dio/dio.dart';

class StripeConnectInterceptor extends Interceptor {
  StripeConnectInterceptor({
    required this.supabaseAnonKey,
    required this.getAccessToken,
    required this.getStripeAccountId,
  });

  final String supabaseAnonKey;
  final Future<String?> Function() getAccessToken;
  final String? Function() getStripeAccountId;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    // Supabase Edge Functions always need these:
    options.headers['apikey'] = supabaseAnonKey;
    final token = await getAccessToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }

    // Stripe-Account header is required for any direct Stripe API call
    // (not for Supabase Edge Function calls — those pass it in the body).
    if (options.uri.host == 'api.stripe.com') {
      final accountId = getStripeAccountId();
      if (accountId != null) {
        options.headers['Stripe-Account'] = accountId;
      }
    }

    handler.next(options);
  }
}
