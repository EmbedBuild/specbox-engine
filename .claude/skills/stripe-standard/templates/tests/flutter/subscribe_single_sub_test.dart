// ----------------------------------------------------------------------------
// subscribe_single_sub_test.dart — SpecBox /stripe-standard test template
//
// Patrol v4 test for the single-subscription flow on iOS/Android. Uses Stripe
// test mode + tarjeta 4242. The PaymentSheet is system-native, so we drive
// it via Patrol's native_automator.
// ----------------------------------------------------------------------------

import 'package:flutter_test/flutter_test.dart';
import 'package:patrol/patrol.dart';

void main() {
  patrolTest(
    'UC-402: subscribe with test card 4242 → PaymentSheet → success',
    ($) async {
      // 1. Boot the app to the pricing screen.
      await $.pumpWidgetAndSettle(/* MyApp() */);
      await $.tap(find.text('Iniciar sesión'));
      await $.enterText(find.byKey(const ValueKey('email-field')), 'test@example.com');
      await $.enterText(find.byKey(const ValueKey('password-field')), 'password123');
      await $.tap(find.text('Entrar'));

      // 2. Pick a tier and trigger subscribe.
      await $.tap(find.text('Suscribirse'));

      // 3. PaymentSheet is native — Patrol native_automator types into it.
      await $.native.tap(Selector(text: 'Add card'));
      await $.native.enterText(Selector(text: 'Card number'), text: '4242424242424242');
      await $.native.enterText(Selector(text: 'MM/YY'), text: '12/34');
      await $.native.enterText(Selector(text: 'CVC'), text: '123');
      await $.native.tap(Selector(text: 'Pay'));

      // 4. Back to the app — verify success state.
      await $.waitUntilVisible(find.text('¡Listo!'));
    },
  );
}
