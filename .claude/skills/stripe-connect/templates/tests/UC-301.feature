# language: es
Característica: UC-301 — Onboarding del piloto con advertencia fiscal
  Como piloto no profesional
  Quiero completar el onboarding de Stripe Connect Express
  Para poder recibir patrocinios de fans

  Antecedentes:
    Dado que estoy registrado en la plataforma como piloto
    Y mi perfil no tiene cuenta Stripe vinculada todavía

  Escenario: Aceptación de la advertencia fiscal y redirect a Stripe
    Cuando entro en "Mi cuenta > Pagos"
    Entonces veo la advertencia de alta autónomo en España
    Y el botón "Completar onboarding con Stripe" está deshabilitado
    Cuando marco el checkbox "Entiendo los requisitos y quiero continuar"
    Entonces el botón "Completar onboarding con Stripe" se habilita
    Cuando pulso el botón
    Entonces el backend llama a create-rider-account-link
    Y mi fila en "riders" obtiene un "stripe_account_id" no nulo
    Y "riders.onboarding_status" queda en "pending"
    Y el navegador se redirige a una URL "https://connect.stripe.com/express/onboarding/..."

  Escenario: Rechazo del consentimiento fiscal (negativo)
    Cuando entro en "Mi cuenta > Pagos"
    Y pulso el botón sin marcar el checkbox
    Entonces el botón permanece deshabilitado y no se hace ninguna llamada al backend

  # Comandos de prueba manual
  # curl -X POST $SUPABASE_URL/functions/v1/create-rider-account-link \
  #   -H "Authorization: Bearer $RIDER_JWT" \
  #   -d '{"rider_id":"...","return_url":"...","refresh_url":"..."}'
