# language: es
Característica: UC-305 — Fan se suscribe con Payment Element embedded + fee dinámico
  Como fan autenticado
  Quiero completar el pago sin salir de la app
  Para patrocinar al piloto usando mi tarjeta, Apple Pay o Google Pay

  Antecedentes:
    Dado que el piloto tiene onboarding_status "enabled" y fee_percent=15
    Y existe un precio Stripe de 15€ mensuales en su connected account
    Y estoy autenticado como fan

  Escenario: Pago con tarjeta 4242 (caso feliz)
    Cuando pulso "Suscribirme" en el plan de 15€
    Entonces el backend llama create-fan-subscription con application_fee_percent=15
    Y recibo client_secret + stripe_account_id
    Y se renderiza Payment Element dentro del modal (sin redirect a stripe.com)
    Cuando introduzco la tarjeta 4242 4242 4242 4242 y confirmo
    Entonces stripe.confirmPayment resuelve sin error
    Y el webhook invoice.paid actualiza sponsorships.status='active'
    Y el application_fee visible en dashboard Stripe es 2.25€ (15% de 15€)

  Escenario: Pago con ambassador (fee reducido)
    Dado que el piloto es ambassador con fee_percent=8
    Cuando completo el pago igual que el escenario anterior
    Entonces el application_fee cobrado es 1.20€ (8% de 15€)

  Escenario: Apple Pay desde iOS
    Dado que estoy en Safari iOS con Apple Pay configurado
    Cuando pulso el botón Apple Pay del Express Checkout Element
    Entonces la biometría se solicita in-sheet
    Y tras autorizar, confirmPayment resuelve y el webhook marca sponsorships.status='active'

  Escenario negativo: Tarjeta con SCA requerida
    Cuando introduzco la tarjeta 4000 0025 0000 3155
    Entonces aparece el challenge 3DS in-sheet
    Y si completo el challenge, el pago continúa como el caso feliz
    Y si cancelo el challenge, sponsorships.status permanece "incomplete"
    Y confirmPayment devuelve error "authentication_required"

  Escenario negativo: Piloto en onboarding restricted bloquea la suscripción
    Dado que el piloto tiene onboarding_status "restricted"
    Cuando llamo a create-fan-subscription
    Entonces recibo HTTP 409 "rider_onboarding_incomplete"
    Y no se crea ninguna fila en sponsorships
