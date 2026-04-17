# language: es
Característica: UC-308 — Payment failed con retry UX
  Como fan
  Quiero saber cuándo mi pago mensual falló
  Para poder actualizar mi método de pago antes de perder el patrocinio

  Escenario: Renovación falla → banner en la UI del fan
    Dado que un sponsorship estaba activo
    Cuando llega invoice.payment_failed y sponsorships.status pasa a "past_due"
    Entonces al siguiente login del fan la UI muestra banner con CTA "Actualizar método de pago"
    Y el sponsorship sigue visible pero con indicador de "pago pendiente"

  Escenario: Stripe smart retries reanudan el cobro
    Dado que el status es past_due
    Cuando pasa el siguiente intento de smart retry y el pago tiene éxito
    Entonces llega invoice.paid
    Y sponsorships.status vuelve a "active"
    Y last_paid_at se actualiza

  Escenario: Tras 4 intentos fallidos, Stripe cancela
    Dado que smart retries no logra cobrar en ~23 días
    Cuando Stripe cancela la subscription
    Entonces llega customer.subscription.deleted
    Y sponsorships.status="canceled"
    Y TODO del proyecto: enviar email al fan avisando del desenlace

  Escenario negativo: Fan ignora el banner
    Dado que banner está visible y fan no actualiza método
    Cuando llegan 4 invoice.payment_failed consecutivos
    Entonces el sponsorship termina como canceled (no se bloquea la UX, Stripe gestiona retries)

  # stripe trigger invoice.payment_failed
  # Tarjeta test que falla en recurrence: 4100 0000 0000 0019
