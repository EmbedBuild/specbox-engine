# language: es
Característica: UC-304 — Fan ve el perfil del piloto y elige un plan
  Como fan autenticado
  Quiero ver los tres planes de patrocinio del piloto (10/15/20€)
  Para decidir cuál me encaja

  Escenario: Fan visita el perfil público de un piloto activo
    Dado que existe un piloto con onboarding_status "enabled" y 3 precios configurados en Stripe
    Cuando visito /riders/{slug}
    Entonces veo los 3 planes con precio mensual y beneficios
    Y el botón CTA de cada plan abre el modal de suscripción (UC-305)

  Escenario: Fan anónimo ve el perfil pero no puede suscribirse
    Dado que no estoy autenticado
    Cuando visito /riders/{slug}
    Entonces veo los 3 planes
    Y al pulsar un CTA me redirige a login conservando la intención

  Escenario negativo: Piloto en onboarding pending no tiene perfil público
    Dado que existe un piloto con onboarding_status "pending"
    Cuando visito /riders/{slug}
    Entonces recibo HTTP 404
