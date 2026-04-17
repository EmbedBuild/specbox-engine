# language: es
Característica: UC-303 — Piloto incompleto no aparece en listado público
  Como fan
  Quiero ver solo pilotos que pueden recibir patrocinios
  Para no suscribirme a alguien que no se puede cobrar

  Escenario: Listado público excluye onboarding_status != enabled
    Dado que existen 3 pilotos con is_public=true:
      | onboarding_status | visible esperado |
      | enabled           | sí               |
      | pending           | no               |
      | restricted        | no               |
    Cuando hago GET a "/api/riders/public"
    Entonces solo recibo el piloto con onboarding_status "enabled"

  Escenario: RLS policy aplica también con rol anon
    Cuando hago SELECT directo con rol anon en la tabla riders
    Entonces solo puedo leer filas donde onboarding_status='enabled' AND is_public=true

  Escenario negativo: Piloto deauthorized queda oculto inmediatamente
    Dado que un piloto estaba enabled y public
    Cuando recibo el webhook "account.application.deauthorized"
    Entonces onboarding_status pasa a "deauthorized"
    Y el piloto desaparece del listado público en la siguiente request
