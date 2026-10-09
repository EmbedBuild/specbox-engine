# P2 · V1 — Landing de Propuestas: notas de diseño

## Idea
Una propuesta es un documento, así que la estética es de papel y tinta. El rotulador fosforito sirve
de metáfora del producto: marca lo que se lee y dónde se frena el cliente (Inversión).

## Paleta (modo claro, AA comprobado a mano)
- Papel `#F7F4EC` y papel hondo `#EFEADE` para alternar bandas; tarjetas en blanco.
- Tinta `#1A1915` para el texto y la CTA principal; `#46433B` para el texto secundario (≥ 8:1).
- Fosforito `#FFD84D` / `#FFF1BC`: solo para resaltar (titular, «se frenó en Inversión», marcadores).
- Verde `#1C6A44` solo para aceptar/enviado; rojo `#B0261D` solo para errores y revocar; foco azul
  `#2347D6` (anillo de 3 px con separación).

## Tipografía (Google Fonts)
Fraunces (titulares y cifras), Instrument Sans (texto e interfaz), IBM Plex Mono (etiquetas y tiempos).

## Estructura
1. Cabecera fija: marca (documento con una línea resaltada) + «Pedir acceso anticipado».
2. Hero: «Deja el PDF. Envía una propuesta que te cuenta qué se lee», dos CTA y, a la derecha,
   el contraste «Antes» (correo con PDF, «Ni idea») frente a «Con Propuestas» (3 aperturas, 9 min,
   4 min 35 s en Inversión). Debajo, una franja que responde a las tres preguntas del visitante.
3. Cómo funciona: tres pasos con miniaturas en HTML/CSS (secciones + PDF, enlace + PIN, seguimiento).
4. Lo que ves tú: panel completo de «Taller Hermanos Ríos» con KPI, barras por sección (suman 9 min),
   aperturas con fecha, hora y dispositivo, aceptación pendiente y notas numeradas 1-4.
5. Lo que ve tu cliente: dos móviles en CSS (pantalla del PIN y propuesta abierta con «Aceptar»).
6. FAQ con `<details>`: seis preguntas, las cuatro obligatorias incluidas.
7. Acceso anticipado: formulario (nombre, email, oficio en chips) + bloque de demostración de estados.

## Decisiones clave
- Datos solo del brief. Las fechas y horas de las tres aperturas y la validez (31/10/2026) son de
  ejemplo, coherentes entre sí; el reparto por sección se cuadró para sumar 9 min exactos.
- Sin inventar: marca, RGPD, privacidad y volumen de uso van como `[DATO REAL]` / `[CIFRA REAL]`;
  única prueba social, verdadera: embed.build ya envía así sus propuestas. El ejemplo queda
  «Pendiente de aceptación» para contar la historia: «ya sabes de qué hablar cuando le llames».
- JS mínimo: botones del panel como demostración (ampliar validez, PIN nuevo, revocar) y estados
  del formulario (validación de email, enviado con foco en el título, fallo con «Reintentar»).
  Un interruptor fuerza el fallo del siguiente envío; los tres estados se ven también en estático.
- Móvil (390 px): una columna, CTA a todo el ancho, barras con etiqueta y valor arriba y la barra
  debajo, KPI en 2+1, móviles apilados; el `overflow-x: clip` del hero contiene las tarjetas giradas.
- Accesibilidad: enlace de salto, etiquetas reales, `aria-invalid`, avisos `alert`/`status`, maquetas con `aria-hidden` o `role="img"`.
