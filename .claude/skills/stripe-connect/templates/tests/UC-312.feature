# language: es
Característica: UC-312 — Apple Pay / Google Pay / Express Checkout Element
  Como fan
  Quiero pagar con mi método nativo preferido (Apple/Google Pay)
  Para terminar el checkout en 2 taps con biometría

  Escenario: Apple Pay en iOS Safari (React)
    Dado que estoy en Safari iOS con Apple Pay configurado
    Cuando el modal de suscripción renderiza ExpressCheckoutElement
    Entonces aparece el botón Apple Pay nativo con el glyph oficial
    Cuando pulso el botón y autorizo con Face ID
    Entonces el PaymentIntent se confirma in-sheet sin redirect
    Y el webhook invoice.paid marca sponsorships.status="active"

  Escenario: Google Pay en Android Chrome (React)
    Dado que estoy en Chrome Android con Google Pay configurado
    Cuando el modal renderiza ExpressCheckoutElement
    Entonces aparece el botón Google Pay
    Y el flujo completa igual que Apple Pay

  Escenario: Link (de Stripe) aparece para usuarios con cuenta
    Dado que tengo una cuenta Link con tarjeta guardada
    Cuando el modal renderiza ExpressCheckoutElement
    Entonces aparece el botón Link junto a Apple/Google Pay

  Escenario: Payment Sheet en Flutter iOS
    Dado que tengo la app móvil en iOS y Apple Pay configurado
    Cuando invoco initPaymentSheet + presentPaymentSheet
    Entonces la Payment Sheet nativa incluye opción Apple Pay arriba
    Y la biometría se solicita in-sheet sin abrir Safari

  Escenario negativo: Dispositivo sin Apple/Google Pay
    Dado que estoy en desktop Firefox sin wallets
    Cuando el modal renderiza
    Entonces ExpressCheckoutElement simplemente no muestra botones de wallets
    Y el fan puede seguir usando PaymentElement con tarjeta manual
