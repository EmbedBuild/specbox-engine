# language: es
Característica: UC-307 — Sincronización DB sponsorships
  Como sistema
  Quiero reflejar el estado real de las suscripciones de Stripe en la tabla sponsorships
  Para que los queries de la app devuelvan datos correctos sin llamar a Stripe

  Escenario: invoice.paid marca status=active y last_paid_at
    Dado que existe sponsorship con stripe_subscription_id="sub_ABC" y status="incomplete"
    Cuando llega webhook invoice.paid con subscription=sub_ABC
    Entonces sponsorships.status="active"
    Y sponsorships.last_paid_at=NOW()

  Escenario: invoice.payment_failed marca past_due
    Dado que la subscription era active
    Cuando llega invoice.payment_failed
    Entonces sponsorships.status="past_due"
    Y el fan puede ver banner "actualiza tu método de pago"

  Escenario: customer.subscription.updated actualiza current_period_end
    Cuando llega subscription.updated con current_period_end=1234567890
    Entonces sponsorships.current_period_end se actualiza a la fecha correspondiente

  Escenario negativo: subscription_id desconocido no rompe el handler
    Cuando llega invoice.paid con subscription="sub_UNKNOWN"
    Entonces el handler no falla y procesa sin crear fila nueva (update sobre 0 filas)
    Y processed_at queda registrado (para evitar retries eternos)
