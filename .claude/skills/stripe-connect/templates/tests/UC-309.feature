# language: es
Característica: UC-309 — Fan cancela suscripción desde la app
  Como fan
  Quiero cancelar mi patrocinio sin hablar con soporte
  Para no sentirme atrapado en la suscripción

  Escenario: Cancelación at period end (default)
    Dado que tengo un sponsorship activo con current_period_end en 15 días
    Cuando pulso "Cancelar" en mi gestión de suscripciones
    Entonces llama a cancel-fan-subscription con immediate=false
    Y la subscription en Stripe queda con cancel_at_period_end=true
    Y sponsorships.cancel_at queda con la fecha current_period_end
    Y el status sigue "active" hasta que llegue el fin de periodo

  Escenario: Cancelación inmediata con proration
    Cuando pulso "Cancelar ahora y pedir reembolso"
    Entonces llama a cancel-fan-subscription con immediate=true
    Y stripe.subscriptions.cancel se ejecuta con prorate=true
    Y llega customer.subscription.deleted
    Y sponsorships.status="canceled"
    Y el fan ve el reembolso parcial en su tarjeta (Stripe lo procesa)

  Escenario: Fan intenta cancelar dos veces
    Dado que ya cancelé y recibí respuesta
    Cuando vuelvo a llamar cancel-fan-subscription con el mismo sponsorship_id
    Entonces recibo HTTP 409 "already_canceled"
    Y no se emite segunda llamada a Stripe

  Escenario negativo: Fan intenta cancelar sponsorship de otro fan
    Dado que RLS filtra por fan_id = auth.uid()
    Cuando llamo cancel-fan-subscription con sponsorship_id de otro usuario
    Entonces la query inicial no encuentra la fila
    Y recibo HTTP 404 "sponsorship_not_found"
