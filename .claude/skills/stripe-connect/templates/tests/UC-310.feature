# language: es
Característica: UC-310 — Rider dashboard con Express Dashboard link
  Como piloto
  Quiero ver mis sponsors activos y acceder a mi Express Dashboard
  Para entender mi MRR y gestionar cobros desde Stripe

  Escenario: Piloto ve su MRR y lista de sponsors
    Dado que tengo 5 sponsors activos (10€, 15€, 15€, 20€, 20€)
    Cuando visito "Mi dashboard de piloto"
    Entonces veo MRR bruto = 80€
    Y MRR neto = 80€ × (1 - fee_percent/100) = 68€ (si fee_percent=15)
    Y lista de los 5 sponsors con su plan y fecha de alta
    Y veo "Próximo payout" con fecha + importe estimados

  Escenario: Piloto entra en su Express Dashboard de Stripe
    Cuando pulso "Abrir mi Dashboard Stripe"
    Entonces el backend llama create-rider-dashboard-link
    Y se abre una URL "https://connect.stripe.com/express/..." en nueva pestaña
    Y la URL expira tras ~5 minutos

  Escenario negativo: Piloto sin onboarding completo no puede abrir el dashboard
    Dado que mi onboarding_status="pending"
    Cuando pulso "Abrir mi Dashboard Stripe"
    Entonces recibo HTTP 409 "onboarding_incomplete"
    Y la UI me redirige al flujo UC-301 para completar el onboarding
