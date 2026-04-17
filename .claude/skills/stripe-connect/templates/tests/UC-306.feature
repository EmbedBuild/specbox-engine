# language: es
Característica: UC-306 — Webhook handler con firma + idempotencia
  Como sistema
  Quiero procesar los webhooks de Stripe exactamente una vez
  Para evitar doble provisión y bugs silenciosos en producción

  Escenario: Firma válida del endpoint de plataforma
    Cuando Stripe envía "account.updated" firmado con STRIPE_WEBHOOK_SECRET_PLATFORM
    Entonces el handler verifica con constructEventAsync contra el secret platform y acepta
    Y registra el event.id en stripe_processed_events con source="platform"

  Escenario: Firma válida del endpoint Connect
    Cuando Stripe envía "invoice.paid" firmado con STRIPE_WEBHOOK_SECRET_CONNECT
    Entonces el handler verifica primero contra platform (falla), luego contra connect (acepta)
    Y registra el event.id con source="connect"

  Escenario: Idempotencia — evento duplicado usando stripe trigger --replay
    Dado que Stripe ya envió "invoice.paid" con event.id="evt_ABC" y fue procesado
    Y existe una fila en stripe_processed_events con ese event_id
    Cuando Stripe reenvía el mismo event.id (ejecutar `stripe events resend evt_ABC`)
    Entonces el handler detecta la fila existente y devuelve HTTP 200 "ok_duplicate"
    Y la tabla stripe_processed_events sigue teniendo exactamente 1 fila para ese event_id
    Y sponsorships NO se actualiza por segunda vez

  Escenario: Firma inválida rechaza la petición
    Cuando llega un POST a /stripe-webhook con header stripe-signature="v1=fake"
    Entonces el handler devuelve HTTP 400 "invalid_signature"
    Y no crea ninguna fila en stripe_processed_events

  Escenario: Handler devuelve 200 aunque el procesamiento falle
    Dado que Stripe envía un evento válido y registramos el event_id
    Cuando el routing del evento lanza una excepción en supabase.from('sponsorships').update
    Entonces el handler devuelve HTTP 200 "ok_with_errors"
    Y la fila en stripe_processed_events tiene received_at pero processed_at=NULL
    Y Ops puede revisar unprocessed events via índice idx_stripe_events_unprocessed

  # Comandos:
  # stripe trigger invoice.paid
  # EVT=$(stripe events list --limit 1 --json | jq -r '.data[0].id')
  # stripe events resend $EVT
  # psql -c "SELECT COUNT(*) FROM stripe_processed_events WHERE event_id='$EVT';"
