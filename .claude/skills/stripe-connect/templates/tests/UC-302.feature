# language: es
Característica: UC-302 — Retorno post-onboarding y activación del perfil
  Como sistema
  Quiero detectar cuándo un piloto completa su onboarding Stripe
  Para activar su visibilidad en el marketplace

  Escenario: Piloto completa el KYC y pasa a onboarding_status=enabled
    Dado que existe un piloto con stripe_account_id "acct_test_123" y onboarding_status "pending"
    Cuando Stripe envía el webhook "account.updated" con charges_enabled=true y payouts_enabled=true
    Y la firma del webhook coincide con STRIPE_WEBHOOK_SECRET_PLATFORM
    Entonces la fila en "riders" actualiza onboarding_status a "enabled"
    Y la fila aparece en "stripe_processed_events" con processed_at no nulo

  Escenario: Stripe requiere información adicional (restricted)
    Dado que existe un piloto con onboarding_status "pending"
    Cuando Stripe envía "account.updated" con requirements.disabled_reason="requirements.past_due"
    Entonces onboarding_status queda en "restricted"
    Y el piloto NO aparece en el listado público (ver UC-303)

  Escenario negativo: Webhook con firma inválida
    Cuando llega una petición a /stripe-webhook con una firma manipulada
    Entonces el handler devuelve HTTP 400 "invalid_signature"
    Y no se crea fila en "stripe_processed_events"
    Y "riders.onboarding_status" no cambia

  # stripe accounts update acct_test_123 --charges-enabled=true --payouts-enabled=true
