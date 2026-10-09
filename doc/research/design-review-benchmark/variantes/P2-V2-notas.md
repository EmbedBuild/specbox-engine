# P2 V2: landing de Propuestas, notas de diseño

## Idea central
Las propuestas son documentos que alguien lee y marca. Por eso el lenguaje visual es el de la papelería:
papel blanco, tinta de bolígrafo azul (la de firmar) y rotulador fluorescente. El fluorescente nunca
decora: marca solo dónde se frenó el cliente. Una misma propuesta (Taller Hermanos Ríos) recorre toda
la página: la hoja del hero, el panel y el móvil del cliente.

## Paleta
- Papel `#FFFFFF`: fondo de página y de los objetos (hoja, panel, formulario).
- Mesa `#EEF1F7`: gris azulado frío, solo como superficie donde descansan los objetos.
- Tinta `#1C2A6E`: todo el texto, botones y barras de datos (13:1 sobre blanco).
- Tinta suave `#4E5880`: notas y texto secundario (6,9:1).
- Fluor `#FFE45C`: el subrayado de «aquí se frenó» y la selección de texto.
- Estados: aceptada `#17694A`, error `#B42318` (los dos superan AA).

## Tipografía
- Literata (serif para leer en pantalla): titulares, prosa y contenido de la propuesta; el producto mide lectura.
- Archivo: todo lo que es herramienta (botones, panel, formulario, móvil). Su eje de anchura se usa
  expandido en los dígitos del PIN.
- Escala clásica: 14, 16, 18, 21, 36 y 60 px (34 px el H1 en móvil). Prosa a 18 px con interlineado 1,6.

## Layout
- Alineación a la izquierda en todo, como un documento.
- Hero: H1 a 10 columnas arriba; debajo, texto y CTA (5 col.) junto a la «mesa» con la hoja (7 col.).
- La hoja tiene margen de comentarios como un procesador de textos: el comentario «Aquí se frenó 4 min
  35 s de los 9 min de lectura» se une con una línea al bloque Inversión subrayado.
- Cómo funciona: tres pasos con numeral y regla de tinta (es una secuencia real); solo texto.
- Lo que ves tú: texto 4 col. + panel 8 col.; Lo que ve tu cliente: dos móviles 7 col. + texto 5 col.
- A 390 px todo pasa a una columna; el comentario baja bajo el bloque subrayado.

## Revisión del plan contra lo que haría por defecto
1. Hero «texto a la izquierda y captura del panel en una ventana de navegador a la derecha»: lo cambié
   por un H1 que ocupa casi todo el ancho y, debajo, la propuesta tal como la lee el cliente, con el
   subrayado. El panel espera a su sección.
2. Pensé usar el amarillo también como color del CTA: lo descarté para que el fluorescente signifique
   una sola cosa (dónde se frenó). El CTA va en tinta.
3. Cómo funciona en tres tarjetas con icono: lo cambié por una línea temporal tipográfica sin cajas.
4. FAQ en acordeón: las dejé abiertas en dos columnas, porque el visitante tiene menos de un minuto.
5. Radio de borde distinto según el objeto (hoja 3 px, panel 14, móvil 40, mesa 24, opciones en
   píldora); sombra solo en objetos físicos y teñida de tinta. Quité la sombra del formulario al revisar.
6. Sin etiquetas en mayúsculas sobre los títulos, sin puntos medios, sin flechas en botones y sin
   monoespaciada para datos.

## Decisiones clave
- Movimiento: un solo momento orquestado (el rotulador barre Inversión al cargar y aparece el
  comentario). El sello de «Aceptada» solo se anima cuando el visitante lo pide. Todo se desactiva con
  `prefers-reduced-motion`.
- Datos: solo los del brief. Los tiempos de Resumen (1:05), Alcance (2:10), Plazos (0:50) y Condiciones
  (0:20) los repartí para que sumen exactamente 9 min con los 4:35 de Inversión; las fechas de apertura
  (5, 6 y 8 de octubre de 2026) y la validez (5/11/2026) son de ejemplo y coherentes con el calendario.
- No inventé funciones: nada de avisos por email, ni descarga del PDF desde la página, ni personalización
  de marca. «¿Puedo usar mi marca?», el RGPD y el aviso legal del formulario llevan `[DATO REAL]`.
- Panel: el conmutador Pendiente/Aceptada enseña la tercera capacidad (aceptación online) sin inventar
  una fecha de aceptación. Las acciones del panel son representaciones, no botones enfocables.
- Formulario: funciona de verdad (validación, envío simulado, éxito con foco). El error de envío salta
  sin conexión; además, los tres estados se ven al pie y el «Reintentar» de la demostración funciona.
- Mismo verbo en todo el flujo: «Pedir acceso anticipado» y, al terminar, «Has pedido acceso anticipado».
- Cabecera fija con el CTA visible; bajo 448 px se oculta el icono del logotipo para que quepa el botón.
