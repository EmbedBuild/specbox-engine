# P1 · Participantes de la prueba: notas de diseño

## Enfoque
Herramienta de oficina de carrera, densa y escaneable en segundos; cada bloque responde a una pregunta:
1. Quién falta por verificar y en qué box: columnas Box, Moto y Equipo juntas; lo pendiente es lo único que «grita».
2. Qué hay que resolver en oficina: columna «Oficina» con chips violetas (resolver) y grises (información), filtro propio y bloque de filas del Excel rechazadas.
3. Cómo va cada categoría: 81 % grande + rejilla de 9 categorías con barra verificado/pendiente y número de pendientes.

## Paleta (solo modo claro, contraste AA comprobado a mano)
- Fondo papel cálido #F4F3EF, superficies blancas, tinta #15171C, texto secundario #5D6371 (5,8:1 sobre blanco).
- Semántica separada por tipo de trabajo, nunca solo por color (siempre icono + texto):
  - Verificado: verde #1B6B3A / barra #2E7D4F, discreto (check + fecha), sin fondo.
  - Pendiente de verificar (comisarios): ámbar #874A00 sobre #FFF2D4.
  - Resolver en oficina (director): violeta #5A32A8 sobre #F1ECFB.
  - Información: gris neutro. Error de importación: rojo #A3231A sobre #FDEDEA.
- Acento de interacción azul #1F5FD1: foco visible (3 px) y fila seleccionada.

## Tipografía
- IBM Plex Sans para interfaz (14 px en escritorio, 15 px en móvil; cifras tabulares).
- Barlow Condensed 700 para dorsales y cifras grandes: el dorsal es una «placa» negra, guiño a la moto.
- IBM Plex Mono para número de box, código de país, número de fila del Excel y «SIN MARCA».

## Layout
- 1440 px: cabecera (barra con ruta y hora + prueba, buscador y acciones) → tarjeta de estado
  (resumen 300 px + rejilla 3×3) → rejilla de trabajo: lista (1fr) + panel de detalle (380 px)
  y, bajo la lista, las filas del Excel que no entraron → bloque de estados al pie (3 columnas).
- ≤1180 px el panel baja bajo la lista; ≤760 px la tabla pasa a tarjetas en rejilla con etiquetas,
  «Añadir participante» e «Imprimir PDF» pasan a botones de icono con aria-label (44 px). Sin scroll
  horizontal: tabla table-layout fixed con columnas en % y minmax(0,1fr) en todas las rejillas.

## Decisiones clave
- Seleccionado: Mateo Rubial (dorsal 8), el caso más completo: moto con fecha y hora, equipo pendiente,
  casco sin QR FIM, sin equipo y en Carpas Paddock (da sentido a «Asignar box»).
- Avisos clasificados: licencia provisional/FFM, sin pegatina, casco sin QR y marca por completar = oficina;
  menor de edad, cambio de categoría, sin equipo y dorsal 21 repetido (válido) = información.
- Las horas de verificación son todas de hoy, pero se muestra «8 may» para que siga claro el sábado.
- Acciones del panel arriba, junto a la identidad. Licencia: solo el tipo (RFME, provisional, FFM).
- Filtros: solo llevan cifra los que el brief permite saber (Todos 129, Sin verificar 25).
- Estados (vacío, carga con skeleton y error inline) como variantes visibles al pie; sin JavaScript:
  filtros como radios estilados en CSS; skeleton respeta prefers-reduced-motion. Estilos de impresión básicos.
