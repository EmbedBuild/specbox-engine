# language: es
Característica: UC-311 — Admin dashboard con total de fees + export para gestor
  Como admin del marketplace
  Quiero ver el total de application_fees cobrados y exportarlo
  Para facturar mis comisiones al gestor cada mes

  Escenario: Admin ve total de fees del mes corriente
    Dado que hay N sponsorships activos con fee_percent variable
    Cuando visito /admin/fees
    Entonces veo total_fees_mes_actual leído del Balance API de Stripe
    Y veo desglose por piloto con fee_percent, MRR y fee acumulado

  Escenario: Export CSV para el gestor
    Cuando pulso "Exportar CSV"
    Entonces descargo un archivo con columnas: fecha, piloto, fan, importe_bruto, fee_percent, fee_cobrado
    Y las fechas están en formato ISO + zona horaria

  Escenario: Admin filtra por rango de fechas
    Cuando selecciono rango "2026-04-01 a 2026-04-30"
    Entonces la query al Balance API usa available_on[gte] y available_on[lte]

  Escenario negativo: Fan intenta acceder a /admin/fees
    Cuando un usuario sin rol admin visita /admin/fees
    Entonces recibo HTTP 403
    Y RLS no devuelve datos de la tabla application_fees (si la tienes)
