# Participantes de la prueba: plan de diseño

## Para quién y cuándo
Secretaría de la prueba, viernes 9/10/2026 a las 10:42, durante las verificaciones de la Ronda 6 del ESBK (Jerez).
La pregunta que responde la pantalla: «¿quién puede salir a pista hoy y qué falta para que salgan los demás?».

## Paleta
- Base papel cálido #F4F3EF y superficies blancas; tinta #15171C para el texto y la acción principal.
- Un solo acento de marca, rojo competición #C4161C: logotipo, pestaña activa y aviso de notificaciones. Nunca para estados.
- Estados semánticos con texto oscuro sobre fondo claro, todos AA (≥ 4,5:1): verde #116432/#E7F4EC, ámbar #8A5A00/#FFF4D6,
  rojo #B42318/#FDECEA y gris #4B5563/#EEF0F3. Los bordes de los controles (#8F8C85) llegan a 3:1.
- El estado nunca depende solo del color: siempre hay icono distinto (check, reloj, triángulo) y texto.

## Tipografía
- Archivo (Google Fonts, variable en anchura y peso): una sola familia para todo.
- Se usa el eje de anchura: estrecha (75 %) para dorsales y cifras grandes, como en las placas de carrera, y normal para leer.
- Cifras tabulares en dorsales, horas y contadores, para que las columnas no bailen.

## Layout
- 1440 px: barra superior oscura con la prueba activa, pestañas de la prueba, cabecera con acciones, aviso de plazo,
  4 KPI y, debajo, la lista (tabla) con una columna lateral de 320 px «Requieren atención» y «Agenda de hoy».
- 1024–1359 px: la columna lateral baja bajo la tabla en dos columnas.
- < 1024 px: cada fila de la tabla pasa a tarjeta con CSS grid (dorsal, piloto, equipo, estado y verificaciones).
- 390 px: pestañas en menú desplegable, KPI en 2×2, filtro de categoría con abreviaturas (SBK, SSP, SSP300) y
  «Exportar» como botón de icono; todo con minmax(0, 1fr) para que no haya scroll horizontal.

## Decisiones clave
1. La tabla se agrupa por categoría (tbody por categoría) con la hora de Libres 1 en la cabecera del grupo: el orden
   de salida a pista marca la prioridad del día.
2. Las tres verificaciones (administrativa, técnica, transpondedor) van en una sola columna compacta; las correctas
   son discretas y solo las incidencias llevan fondo rojo, para que lo que falla salte a la vista.
3. Un estado resumen por piloto (Listo, Pendiente, Incidencia, Sin presentar) con una línea de detalle accionable
   («Licencia caducada el 30/09/2026», «Sonómetro: 109 dB»).
4. El aviso de plazo pone la hora límite (14:00), el tiempo restante y una barra con «Ahora · 10:42».
5. La columna lateral ordena las incidencias por la primera salida a pista, no por la hora en que se detectaron.
6. Datos coherentes entre KPI, contadores de filtros, grupos y filas (24 inscritos: 11 listos, 6 pendientes,
   5 incidencias, 2 sin presentar).
7. JavaScript mínimo: filtros por categoría y estado (aria-pressed), búsqueda por dorsal o texto sin tildes, estado
   vacío con «Quitar filtros», menú móvil y «Avisar al equipo» con confirmación en una región role="status".
8. Accesibilidad: enlace para saltar a la lista, caption y scope en la tabla, aria-label en todos los botones de icono,
   foco visible de 3 px (azul claro sobre la barra oscura) y animación desactivada con prefers-reduced-motion.
