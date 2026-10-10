# Revisión ciega P2: landing de «Propuestas» (variantes K, M, Q, R y T)

He revisado a ciegas cinco variantes de la misma página contra el brief `P2-BRIEF.md` y la rúbrica `RUBRICA.md`, con la severidad de la revisión de calibración. Puntúo cada criterio de 0 a 5 y solo pongo un 5 cuando no he encontrado nada que reprochar. No sé qué proceso produjo cada variante y no lo he intentado averiguar. El orden de revisión es el pedido: T, R, Q, M y K.

## Método

- **Capturas.** He recortado las capturas de página completa (`X-1440.png` y `X-390.png`) en tramos para leerlas a tamaño real. Las capturas de 390 de R y Q tienen 399 px de ancho, lo que confirma el desbordamiento medido.
- **Criterio 7.** He usado `X-medidas.json`. A 390 px, T, M y K miden `scrollWidth` 390 y no desbordan. R y Q miden 399, así que tienen 9 px de scroll horizontal y los elementos que sobresalen son los de la sección «Lo que ve tu cliente» (`div.dos-col__texto`, `h2`, `p`, `ol`, `li` a 399).
- **Criterio 2.** Lo juzgo como pide el encargo: si un freelancer responde en menos de un minuto a las tres preguntas del brief (qué gano frente al PDF, qué ve y qué hace mi cliente, cómo empiezo y cuánto cuesta). También cuentan la densidad y la longitud de la página.
- **Contraste.** He aplicado la fórmula WCAG 2.x a los pares reales de cada fichero: texto, secundarios, placeholder, avisos y botones. Para los bordes de controles uso el umbral de 3:1 de componentes no textuales.
- **Tells (criterio 3).** He comprobado en el código la salida del detector y he leído el CSS. La nota es 5 menos el número de tells, con un mínimo de 0, igual que en la calibración. Los mismos casos límite se tratan igual en las cinco variantes:
  - **No cuento como «glass decorativo»** la cabecera fija con `backdrop-filter` (T l.71, R l.50, Q l.59, M l.76). Es funcional, porque mantiene la legibilidad al desplazarse.
  - **No cuento como tarjetas anidadas** las vitrinas de estados del formulario, porque las pide el brief.
  - **Sí cuento una flecha SVG** al final de un botón como el patrón «`→` en botones».
- **Parecido entre R, Q y K.** Comparten texto y estructura casi línea a línea. Difieren en el acabado: Q pule la interacción de R, y K corrige además la rejilla, el espaciado, el movimiento y el borde lateral. Las puntúo por separado.

---

## T: Fraunces + Instrument Sans + Plex Mono, crema y rotulador amarillo

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 5 | Todo es de este producto. El «Antes / Con Propuestas» enfrenta el correo con `Propuesta_Taller_Rios.pdf` y «¿La ha abierto? ¿Hasta dónde ha leído? *Ni idea.*» a la misma propuesta medida (l.474-503). Muestra la burbuja «Por WhatsApp · Tu PIN: 4817» (l.539) y un panel con los datos del brief que cuadran (1 min 20 s + 2 min 5 s + 4 min 35 s + 40 s + 20 s = 9 min, l.597-601). Incluye «Hecho por quien lo usa… Jerez de la Frontera» con `[CIFRA REAL]` (l.759-763) y un PIN nuevo que indica el canal de envío (l.911). La FAQ trae las cuatro preguntas obligatorias con `[DATO REAL]` (l.724, 728). |
| 2 | Jerarquía y escaneabilidad | 4 | Las tres respuestas están en la primera pantalla a los dos anchos: el titular, la entradilla con enlace, PIN y «sin crear ninguna cuenta» (l.464) y la nota «Gratis… Los precios aún no están decididos» (l.469). Además, una franja de tres respuestas explícitas (l.508-512). Pero el remate del «Antes» («Ni idea.») queda tapado por la tarjeta superpuesta (margen negativo, l.112 y l.132) a 1440 y a 390. La franja «01-03» choca con la numeración «01-05» de las secciones. La página es larga y repetitiva: 11.778 px a 390, y el trío 3 aperturas / 9 min / Inversión aparece cinco veces. |
| 3 | Tells de IA | 0 | Cinco tells (lista abajo). |
| 4 | Tipografía | 4 | Fraunces con `opsz` 144 y cursiva para el énfasis, Instrument Sans para el texto y Plex Mono para los datos. Escala con `clamp`, medida de 36em, 40em y 62ch (l.95, 152, 319) y `tabular-nums` en KPI y tiempos (l.201, 215). Pega: mayúsculas con tracking en nueve clases y mono a 10-11,5 px (`.62-.72rem`, l.103, 123, 171, 279). |
| 5 | Color | 4 | Papel crema y tinta cálida, verde solo para lo correcto, rojo para el error y azul solo para el foco. Todo el texto pasa AA: ink-2 sobre papel 8,99:1, placeholder ink-3 sobre blanco 5,81:1, err sobre err-soft 5,74:1, ok sobre ok-soft 5,60:1, tinta sobre amarillo 12,7:1. Pegas: el amarillo marca el freno pero también decora (sombra de hover l.62, insignia l.86, subrayados l.79 y l.254, fondo del candado l.278, marcadores `[DATO REAL]` l.58). El borde de campos y chips (#C9C0AC sobre blanco) da **1,81:1** (l.342, 353), por debajo de 3:1. |
| 6 | Estados y craft | 4 | El formulario está completo. Valida en línea con `aria-invalid` y lleva el foco al primer error (l.962-1032). Al enviar, el botón pasa a `disabled` + `aria-busy` + «Enviando…» (l.997-1002). Un interruptor provoca un **fallo real**, y el reintento conserva los datos y gestiona el foco (l.823, 1004-1014). El éxito lleva el foco al título y ofrece «Enviar otra solicitud». La demo del panel amplía la fecha, da un PIN con instrucción de canal y revoca deshabilitando el resto (l.902-922). Áreas de 44-54 px; hover, active y disabled definidos; foco de 3 px. Pegas: doble hueco en el botón de cabecera («Pedir acceso␣␣anticipado»: `gap:10px` más el espacio inicial del `span`, l.60 y l.452). Las ilustraciones de los pasos salen cortadas por `height:164px; overflow:hidden` (l.158). Los marcadores del panel van en orden 2-1-3-4 (l.595, 606). |
| 7 | Responsive | 4 | 390 medido sin desbordar. La cabecera conserva el CTA y acorta el texto por debajo de 360 px (l.81). Los KPI pasan a 2+1 y las barras se reconvierten en etiqueta/valor con la barra debajo (l.213-226); los móviles se apilan. Pegas: la superposición que tapa «Ni idea.» sigue en móvil, no hay navegación por debajo de 1120 px (l.77, 83) y la página mide 11.778 px a 390. |
| 8 | Movimiento | 4 | Transiciones de 150-200 ms con propiedades explícitas y sin `all` (l.60, 239, 316, 381). El scroll suave se anula con `reduce` (l.41, 409), no hay animaciones en carga y `reduce` lo corta todo (l.408-412). Pegas: curva `ease` en lugar de ease-out y `box-shadow` animado en el hover del botón principal (l.60-62). |

**Total: 29 / 40**

**Tells encontrados (5)**
1. Mayúsculas con tracking:
   - `.eyebrow` (l.85), usado en l.462, 519, 566, 645, 714, 751 y 819.
   - `.tag` (l.103), `.live-client` (l.114), `.answers-k` (l.138), `.step-n` (l.159, «PASO 1»), `.art-bubble small` (l.171), `.panel-client` (l.190), `.scr-kicker` (l.279) y `.state-name` (l.389).
2. Puntos medios encadenados como sistema:
   - «01 · Frente al PDF»… (l.509-511) y «01 · Cómo funciona»… (l.519, 566, 645, 714, 751).
   - «Portátil · la última» y «miércoles 07/10/2026 · 9:03» (l.608-610), además de l.871 y del `<title>` (l.6).
3. Numeración 01/02/03 sin secuencia: la franja «01 · 02 · 03» (l.509-511) va seguida de «01 · Cómo funciona … 05 · Acceso anticipado» (l.519-751), una numeración decorativa que no es un recorrido. En el panel, los marcadores salen 2, 1, 3, 4 (l.595, 606, 612, 618).
4. Flecha en botones: el icono `i-arrow` (l.420) en «Pedir acceso anticipado» (l.466, 802) y en «Quiero esto en mis propuestas» (l.635).
5. Tarjetas idénticas anidadas:
   - Tres `.step` (l.156), cada una con un `.step-art` enmarcado (l.158) que contiene otra tarjeta (`.art-doc` l.162, `.art-row` l.174).
   - En el panel, `.kpi` ×3 y `.pcard` ×2 dentro de `.panel` (l.199, 207).

Casos límite que no cuento:
- La cabecera con `backdrop-filter` (l.71).
- `.hl` con `linear-gradient` como rotulador (l.57): no es gradient text.
- Los KPI «3 / 9 min / Inversión» (l.587-591): son los datos del brief en la maqueta del panel.
- Crema + amarillo: no es una de las combinaciones listadas.

**Fortalezas**
1. Es la propuesta de valor mejor argumentada. El «Antes / Con Propuestas» con el mismo cliente y la franja de tres respuestas resuelven las preguntas del brief sin bajar. La demo del panel tiene consecuencias reales: amplía la fecha, da un PIN con su canal y revoca bloqueando lo demás.
2. Es el formulario de referencia del grupo. Es el único donde el error de envío se provoca desde la página (interruptor) y el reintento conserva los datos y lleva el foco donde toca.

**Problemas prioritarios**
1. Repertorio de plantilla editorial. Rótulos mono en mayúsculas en cada sección, puntos medios, una numeración 01-05 que choca con la 01-03 de la franja, flechas y tarjetas dentro de tarjetas: cinco tells que llevan el criterio 3 a cero.
2. Fallos visibles de acabado: «Ni idea.» queda tapado a los dos anchos, el botón de cabecera tiene doble hueco y las ilustraciones de los pasos salen cortadas.
3. Longitud y redundancia: 11.778 px a 390 y el mismo trío de cifras cinco veces. Además, los bordes de los campos dan 1,81:1.

---

## R: Literata + Archivo, tinta marina, «mesa» y fluorescente

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 5 | La hoja de la propuesta a Taller Hermanos Ríos lleva Inversión subrayada en fluorescente y una nota al margen: «Aquí se frenó 4 min 35 s de los 9 min de lectura» (l.303-331). El panel usa los datos del brief, que suman 9 min (l.392-396), y aperturas con dispositivo (l.406-408). Hay un conmutador Pendiente/Aceptada (l.363-369). La FAQ trae `[DATO REAL]` para marca, RGPD y tratamiento (l.507, 511, 567) y explica con honradez qué se registra. El logotipo de cuatro casillas con dos llenas evoca el PIN (l.275-280). |
| 2 | Jerarquía y escaneabilidad | 4 | El titular es la promesa («Envía la propuesta. Mira qué se lee y cuándo se acepta.», l.291). La entradilla cubre enlace, PIN y «sin crear cuenta» (l.294) y la nota cubre el precio (l.299): las tres preguntas caben antes de 600 px a 390. La página es compacta (6.241 / 8.622 px). Pegas: los bloques `.texto` pierden el espacio entre párrafos. `:where(.texto) > * + *` tiene especificidad 0 y el reset `h1,h2,h3,p…{margin:0}` lo anula (l.115 frente a l.37), así que «Lo que ves tú», «Lo que ve tu cliente» y «Pide acceso» son muros de texto con el `h2` pegado. El precio solo se responde en una nota gris de 15 px. |
| 3 | Tells de IA | 4 | Un tell. |
| 4 | Tipografía | 4 | Literata con `opsz` para texto y titulares y Archivo con eje de anchura para la interfaz (`font-stretch:115%` en el PIN, l.196). Sin mayúsculas, con `tabular-nums` en los datos (l.148, 153, 155, 162, 196), `text-wrap: balance/pretty` (l.38-39) y medida de 30-32em. Pega: el ritmo vertical se rompe por el fallo de márgenes de `.texto`. |
| 5 | Color | 4 | Tinta marina sobre blanco y «mesa» azul grisácea entonada. Un único acento, el fluorescente, solo para el freno (l.315, 394) y la selección; verde solo para aceptar y rojo para el error. Todo el texto pasa AA: tinta-2 sobre blanco 6,93:1, sobre mesa 6,12:1; error sobre fondo 5,75:1; acepta sobre fondo 5,80:1; tinta sobre fluorescente 10,28:1. Borde de campos a 3,63:1. Pega: las casillas del PIN de la maqueta usan `--linea` a **1,41:1** (l.196) y la vacía casi desaparece. |
| 6 | Estados y craft | 3 | Valida en línea con `aria-invalid` y foco al primer error (l.664-716). Al enviar, el botón se deshabilita con «Enviando solicitud…»; el éxito recibe el foco y la vitrina tiene un reintento que funciona (l.719-727). El aviso real solo aparece sin conexión (l.699). Pegas: no hay `:active` y el hover no se condiciona al puntero fino. «Ver cómo funciona» es un enlace en línea de unos 26 px de alto (l.63); el botón pequeño y el conmutador miden 40 px (l.59, 139). Hay dos fallos de maquetación sin revisar: los párrafos pegados y los móviles apilados en escritorio (abajo). |
| 7 | Responsive | 2 | **Desborda: `scrollWidth` 399 a 390 px.** La rejilla `.dos-col` no fija `minmax(0,1fr)` (l.125), y la escena de los móviles ensancha la columna de «Lo que ve tu cliente» a 399 px: el texto y la lista tocan o pasan el borde. A 1440, la escena de 7 columnas no tiene sitio para dos móviles de 16,5rem y los apila (l.183-186), con un vacío de unos 900 px de alto a la derecha. A favor: el panel se adapta por container queries (l.175-181) y la cabecera conserva el CTA. |
| 8 | Movimiento | 2 | Animación decorativa en la carga: el fluorescente barre con `clip-path` durante 0,9 s tras 0,6 s de espera, y la nota entra en 0,5 s a 1,45 s (l.104-111). El sello de aceptación rebota (`cubic-bezier(.2,.9,.3,1.2)`, l.107) y las curvas son `ease` o `ease-in-out`. A favor: todo está condicionado a `no-preference`, también el scroll suave (l.35, 104), y las transiciones de botón son de 150 ms sin `all` (l.56). |

**Total: 28 / 40**

**Tells encontrados (1)**
1. Borde lateral de color de más de 1 px: `.comentario{border-left:2px solid var(--tinta)}` (l.98). Actúa por debajo de 40rem; en escritorio lo sustituye un conector horizontal (l.100-103).

No cuento la cabecera con `backdrop-filter` (l.50) ni los numerales grandes de los pasos (l.120), que son una secuencia real.

**Fortalezas**
1. Es la mejor imagen de la propuesta de valor. La propia propuesta, con el rotulador en Inversión y una nota al margen, enseña «dónde se frenó» sin obligar a leer una cifra.
2. Contención: un acento con una sola función, sin mayúsculas ni repertorio de plantilla, y una copy ceñida al brief, incluida la respuesta honesta sobre qué datos se registran.

**Problemas prioritarios**
1. Incumple el brief a 390 px: hay 9 px de scroll horizontal en «Lo que ve tu cliente».
2. Maquetación de escritorio sin revisar: los párrafos quedan pegados por un `:where()` sin especificidad y los móviles se apilan dejando media sección vacía.
3. Movimiento de carga lento y decorativo (`clip-path` de 900 ms, nota a 1,45 s, sello con rebote) y áreas de pulsación de 26-40 px.

---

## Q: la misma página que R con la interacción pulida

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 5 | El mismo contenido que R: hoja con fluorescente y nota al margen «Aquí se frenó 4 min 35 s de los 9 min» (l.331-359); panel con los datos del brief y el dispositivo de cada apertura (l.422, 434-436); conmutador Pendiente/Aceptada (l.393); FAQ con `[DATO REAL]` (l.535, 539, 595). |
| 2 | Jerarquía y escaneabilidad | 4 | Las tres preguntas quedan respondidas en la primera pantalla (l.319, 322, 327) en una página compacta (6.208 / 8.593 px). Arrastra el mismo fallo de márgenes que R (`:where(.texto)` en l.141 frente al reset de l.45): los textos de sección salen sin aire. El precio sigue en una nota de 15 px. |
| 3 | Tells de IA | 4 | Un tell. |
| 4 | Tipografía | 4 | La misma pareja que R, con `text-wrap: pretty` extendido a `li`, `figcaption` y `dd` (l.46-48) y `tabular-nums` en los datos. Pega: el mismo ritmo vertical roto. |
| 5 | Color | 4 | La misma paleta y los mismos ratios AA que R; los bordes pasan a anillos de tinta translúcida más sombra (l.33-35, 201). Pega: las casillas del PIN siguen a 1,41:1 (l.224). |
| 6 | Estados y craft | 4 | Sobre R añade:<br>• hover solo con `(hover:hover) and (pointer:fine)` (l.73-79);<br>• 44 px en puntero grueso (l.72) y un enlace secundario de 2,75rem (l.71);<br>• `:active` con `scale:.96` (l.66, 166, 268);<br>• radios concéntricos por variable (`--r-escena` = `--r-objeto` + relleno en móvil, l.39);<br>• sin animación al alternar el panel con teclado (l.129, 655).<br>Pegas: los mismos fallos de maquetación que R y un aviso real que solo aparece sin conexión (l.729). |
| 7 | Responsive | 2 | **Desborda: `scrollWidth` 399 a 390 px**, por la misma causa que R (`.dos-col` sin `minmax`, l.151). A 1440, los móviles se apilan igual y dejan el vacío a la derecha (l.211-214). |
| 8 | Movimiento | 3 | Curvas ease-out propias (l.36-37); transiciones de opacidad, desplazamiento y escala de ≤300 ms (l.126-128) con entradas por `@starting-style` (l.130-134); `reduce` lo deja en un fundido (l.135-137) y el scroll suave está condicionado (l.43). Pegas: la carga sigue siendo decorativa (barrido con `clip-path` de 0,7 s tras 0,4 s y nota de 0,4 s a 1,2 s, l.119-124). Las entradas animan `filter: blur(4px)` (l.124-132), que no es ni transform ni opacity. |

**Total: 30 / 40**

**Tells encontrados (1)**
1. Borde lateral de color de más de 1 px: `.comentario{border-left:2px solid var(--tinta)}` (l.113), por debajo de 40rem.

No cuento la cabecera con `backdrop-filter` (l.59).

**Fortalezas**
1. La misma idea visual de R: la propuesta subrayada con la nota al margen responde a «qué gano frente al PDF» de un vistazo.
2. Junto con K, el mejor acabado táctil del grupo: 44 px con puntero grueso, hover solo con ratón, `:active` con escala y entradas que con `reduce` se quedan en un fundido.

**Problemas prioritarios**
1. Incumple el brief a 390 px (9 px de scroll horizontal), por el mismo motivo que R.
2. Se ha pulido la interacción, pero no se han revisado los dos fallos de maquetación de R: párrafos pegados y móviles apilados en escritorio.
3. Animación de carga lenta (0,7 s, nota a 1,2 s) y desenfoque animado con `filter`.

---

## M: Fraunces + Hanken Grotesk + Plex Mono, crema, azul cobalto y amarillo

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 2 | La copy es viva y suena natural en castellano: «Deja de preguntar «¿Has podido verla?»» (l.439) y un chat de lunes a viernes con tres días de silencio (l.509-525). Pero no describe este producto:<br>• **Ignora los datos del brief**: usa una clínica dental de Valencia, 6.450 € y 5 min 20 s en Inversión (l.467-480, 598-602).<br>• **Inventa funciones que hoy no existen**: tres opciones de precio (l.545, 633, 655-657), logotipo y colores (l.534, 545, 775), medición de descargas (l.582, 616, 715, 867), avisos por correo (l.571, 641), versiones (l.637, 755, 875) y condiciones de fundador con 30 días de aviso (l.776, 883).<br>• **Habla de un equipo**: «el equipo que la construye» (l.777), cuando es un estudio unipersonal.<br>• **No usa ningún marcador** `[DATO REAL]`. |
| 2 | Jerarquía y escaneabilidad | 3 | La primera pantalla responde con fuerza a la pregunta 1, y a la 2 y la 3 con dos notas de 14,5 px (l.447-451). «Los precios no están decididos» no aparece en ninguna parte, y la FAQ de precio promete condiciones (l.883). Faltan piezas del brief:<br>• la vista del cliente en el móvil con el PIN (solo hay un aviso de privacidad, l.718-721);<br>• las preguntas de marca y de datos/RGPD;<br>• el dispositivo de cada apertura (l.614-618).<br>Ocho secciones numeradas, una tabla y dos demos suman 8.341 / 13.409 px. |
| 3 | Tells de IA | 0 | Seis tells (lista abajo). |
| 4 | Tipografía | 3 | Fraunces (peso 560, `opsz`) con Hanken Grotesk y Plex Mono, escala con `clamp` y medida de 33-40em y 60ch (l.91, 145, 345). Pero:<br>• mayúsculas con tracking en rótulos, etiquetas, sellos, cabecera de tabla y etiquetas móviles (l.125, 128, 141, 236, 250, 254, 291, 380);<br>• secundarios de 10,5 a 12,5 px (l.80, 111, 126, 128, 159, 250);<br>• ni un `tabular-nums`: las cifras dependen de la mono;<br>• un wordmark decorativo de 11rem en el pie (l.348). |
| 5 | Color | 4 | Crema y tinta cálidas; verde y rojo con función. Todo pasa AA: muted sobre papel 6,30:1 y sobre paper-2 5,77:1, placeholder 5,38:1, blanco sobre azul 8,04:1, hora del chat 6,21:1, borde de campo 4,03:1. Pega: el azul cobalto significa acción, barras de datos, burbujas del chat, iconos decorativos, números de sección, selección de opción y enlaces (l.26, 142, 160, 193, 209, 231, 242, 335). Con el amarillo y el verde, compiten tres acentos. |
| 6 | Estados y craft | 3 | Valida campo a campo con un resumen «Revisa los N campos marcados» y foco al primero (l.1029-1036). Al enviar muestra spinner, `disabled` y `aria-busy` (l.1037-1040); el éxito recibe el foco. La demo de aceptación valida y emite recibo (l.969-987) y el PIN nuevo se anuncia en una región viva (l.948-953). Pero **falta el estado obligatorio «error de envío con reintento»**: el envío siempre acaba bien (l.1041-1048) y no hay vitrina. Además, el segmentado mide 38 px (l.201), no hay estilo `:disabled` y el sello «Aceptada» tapa el botón «Aceptar propuesta» de la maqueta (l.124-125, 482-483). |
| 7 | Responsive | 4 | 390 medido sin desbordar. La tabla comparativa se convierte en fichas con etiqueta (l.372-383), las filas de lectura pasan a dos niveles (l.393), la maqueta del hero se reordena (l.385-390) y los CTA ocupan todo el ancho (l.403). Pegas: 13.409 px de alto, la más larga, y navegación oculta por debajo de 900 px sin alternativa (l.369). |
| 8 | Movimiento | 2 | Barras con `transition: width .6s` (l.209), pulso infinito de `box-shadow` en el hero desde la carga (l.133-134), spinner (l.73), giro de 0,5 s del botón de PIN (l.190) y transiciones sin curva definida (l.62). `reduce` actúa a brocha gorda, aunque corta el pulso (l.405-408). |

**Total: 21 / 40**

**Tells encontrados (6)**
1. Mayúsculas con tracking:
   - `.kicker` (l.141), usado en l.504, 532, 580, 628, 693, 728, 770 y 856.
   - `.float-label` (l.128), `.tag` (l.236), `.badge` (l.250), `.compare thead th` (l.291), `.compare td::before` (l.380), `.stamp` (l.125) y `.done-stamp` (l.254).
2. Borde lateral de color de más de 1 px: `.callout{border-left:4px solid var(--ink)}` (l.151).
3. Numeración 01/02/03 sin secuencia: las secciones van numeradas de «01 El problema» a «08 Preguntas» (l.504-856), y dentro de la 02 los pasos vuelven a contar 1-2-3 (l.544, 562, 570).
4. Flecha en botones: SVG de flecha en «Pedir acceso anticipado» (l.443).
5. Puntos medios encadenados:
   - l.438 y l.464 («Propuesta 031 · versión 3»), l.478, 483, 568 y 588.
   - Las horas de la línea de tiempo (l.614-618).
   - l.650, l.655-657 («A · Esencial»), l.675 y el `<title>` (l.6).
6. Tarjetas idénticas anidadas: tres `.step` (l.171) con un `.art` enmarcado (l.176) que contiene más tarjetas `.art-row` (l.177); opciones `.opt` (l.239) dentro del `.panel` del formulario.

No cuento la cabecera con `backdrop-filter` (l.76) ni las tramas de puntos decorativas (l.98, 176), que no están en la lista. El pulso infinito lo valoro en movimiento.

**Fortalezas**
1. El mejor titular del grupo para el dolor real («Deja de preguntar «¿Has podido verla?»») y un chat que escenifica el silencio que deja un PDF adjunto.
2. Demos ricas y accesibles: lectura por visita con una nota que cambia según la visita (l.918-943), aceptación con recibo y validación con resumen de errores.

**Problemas prioritarios**
1. No respeta el brief en lo esencial: cambia los datos de ejemplo, presenta como hechos funciones inventadas y no usa ningún marcador, en un producto que aún no está abierto a terceros.
2. Faltan piezas obligatorias: la vista del cliente en el móvil con el PIN, dos preguntas de la FAQ, el campo «a qué te dedicas» (pregunta el tamaño del equipo, incluido «más de 15 personas», l.806-813), el error de envío con reintento y el dispositivo de cada apertura.
3. Repertorio de plantilla (seis tells) y movimiento de reclamo: pulso infinito y barras animadas por `width` durante 600 ms.

---

## K: la misma página que Q con la rejilla, el espaciado y el movimiento corregidos

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 5 | El mismo contenido que R y Q:<br>• hoja con fluorescente y la nota «Aquí se frenó 4 min 35 s de los 9 min de lectura» (l.337-365);<br>• panel con los datos del brief y el dispositivo de cada apertura (l.428, 440-442);<br>• conmutador Pendiente/Aceptada (l.399);<br>• FAQ con los tres `[DATO REAL]` (l.541, 545, 601);<br>• logotipo-PIN (l.309). |
| 2 | Jerarquía y escaneabilidad | 4 | Las tres preguntas quedan respondidas en la primera pantalla (l.325, 328, 333). Es la página más compacta (5.603 / 8.669 px) y los textos de sección ya respiran (l.141-142). Pegas: el precio solo está en una nota gris de 15 px (l.86); el hero enseña el freno, pero las aperturas y la aceptación solo aparecen en el pie de figura de 14 px; a 1440 la columna izquierda del hero queda vacía bajo los botones. |
| 3 | Tells de IA | 5 | Ninguno. La nota al margen usa un conector horizontal de 1,5 px (l.112-113, 117) en lugar del borde lateral de R y Q, y la cabecera es opaca y sin desenfoque (l.58). |
| 4 | Tipografía | 5 | Literata para leer la propuesta como un documento y Archivo ensanchado para la interfaz y el PIN (l.230). Sin mayúsculas, con `tabular-nums` en todos los datos (l.114, 184 y siguientes), `text-wrap: balance/pretty`, medida de 30-32em y ritmo vertical correcto (l.141-142). El único texto de 12 px está dentro de la maqueta del móvil (l.236). |
| 5 | Color | 5 | La paleta de R y Q, con todos los pares AA ya citados. Las casillas del PIN pasan a `--borde-campo`, con 3,63:1 (l.230). Un solo acento con una sola función (el freno), neutros entonados, verde solo para aceptar y rojo solo para el error. |
| 6 | Estados y craft | 4 | Tiene todo lo de Q: 44 px con puntero grueso (l.71), hover solo con ratón (l.72), `:active` con escala (l.65, 168, 274), foco de 3 px (l.51) y radios concéntricos (l.39). Y no tiene sus fallos de maquetación. Pegas: en el formulario real el error de envío solo aparece sin conexión (l.735), así que el reintento solo se prueba en la vitrina (l.755-763). Las acciones del panel son texto inerte con aspecto de enlace (l.202-203). El botón pequeño y el conmutador miden 40 px con ratón (l.67, 167). |
| 7 | Responsive | 5 | 390 medido sin desbordar, gracias a `minmax(0,1fr)` y `min-width:0` (l.81, 152-153). A 1440 los dos móviles van lado a lado (l.216-220), el panel se adapta por container queries y la vitrina se apila con sentido. «Revocar acceso» cae solo a una segunda línea en la maqueta del panel, que es estática. |
| 8 | Movimiento | 4 | La carga dura 300 ms o menos y anima transform: el barrido por `scale` desde la izquierda y la nota por `translate` + `opacity` en 250 ms (l.119-124). Las entradas van por `@starting-style` con opacidad, desplazamiento y escala de ≤300 ms y ease-out propio (l.126-134); `reduce` las deja en un fundido (l.135-137) y el scroll suave está condicionado (l.43). Sin `all`. Pega: sigue habiendo animación en la carga del hero, aunque breve y con propósito. |

**Total: 37 / 40**

**Tells encontrados:** ninguno de los listados en la rúbrica.

**Fortalezas**
1. Es la única que cumple a la vez todos los requisitos duros del brief sin un solo tell: sin scroll horizontal, cuatro preguntas con marcadores, formulario con sus tres estados, cliente en el móvil con PIN y datos del brief.
2. Acabado de interacción cuidadoso y discreto: 44 px en pantallas táctiles, hover solo con ratón, entradas de ≤300 ms que con `reduce` se quedan en un fundido y un panel que se adapta a su contenedor.

**Problemas prioritarios**
1. La tercera pregunta (cómo empiezo y cuánto me cuesta) y el «sin cuenta» dependen de texto pequeño: una nota de 15 px y un pie de figura de 14 px, sin peso visual.
2. El error de envío del formulario real solo se ve sin conexión; para quien visita la página solo existe en la vitrina. Las acciones del panel son texto inerte.
3. Una sobriedad que roza lo plano: «Cómo funciona» son tres columnas de texto sin imagen y el hero de escritorio deja media columna vacía. Persuade menos que T.

---

## Ranking final

| Puesto | Variante | Total | Veredicto |
|---|---|---|---|
| 1 | **K** | 37 / 40 | La más correcta y la única sin fallos técnicos ni tells; persuade menos que T. |
| 2 | **Q** | 30 / 40 | Buena idea y buen pulido táctil, pero desborda 9 px a 390 y arrastra los fallos de maquetación de R. |
| 3 | **T** | 29 / 40 | La más persuasiva y la mejor cableada, hundida por el repertorio de plantilla y tres fallos visibles. |
| 4 | **R** | 28 / 40 | La idea de Q con menos acabado: desborda a 390, párrafos pegados y animación de carga lenta. |
| 5 | **M** | 21 / 40 | Buen titular y demos ricas, pero cambia los datos, inventa funciones y omite piezas obligatorias. |

**Qué separa a las de arriba de las de abajo.** R, Q y K son la misma página con tres niveles de acabado. Entre ellas, la diferencia es la que sale al abrir el resultado en un navegador:
- una rejilla sin `minmax(0,1fr)` que desborda 9 px a 390;
- un `:where()` que anula el espacio entre párrafos;
- dos móviles que no caben en su columna.

K lo corrige todo y además quita el único tell, por eso saca siete puntos a Q. T está en otra liga como pieza comercial: es la que mejor responde a «¿qué gano frente al PDF?» y la que mejor demuestra el producto, pero se apoya en el repertorio editorial de plantilla (rótulos mono en mayúsculas, numeración decorativa, flechas, tarjetas dentro de tarjetas) y la rúbrica lo castiga con un cero en el criterio 3. M es la única que se sale del brief en el contenido, no en la forma: es una landing creíble de *otro* producto de propuestas más maduro.

## Patrones comunes

1. **Las acciones del panel solo funcionan en T.** «Ampliar validez», «PIN nuevo» y «Revocar» son texto o botones inertes en R, Q y K; M las menciona en prosa. Solo T dice por qué canal se envía el PIN nuevo (l.911); M lo regenera, pero solo avisa de que el anterior deja de funcionar (l.952).
2. **El error de envío real solo se puede provocar en T.** R, Q y K lo condicionan a `navigator.onLine === false` y lo enseñan en la vitrina; M no lo tiene.
3. **La respuesta al precio es siempre la más débil visualmente:** una nota secundaria de 14,5-15 px en las cinco. Solo T la repite con peso en la franja de tres respuestas.
4. **Ninguna ofrece navegación en móvil.** T y M ocultan los enlaces sin alternativa; R, Q y K no tienen menú. En una landing de una sola página es aceptable porque las cinco conservan el CTA en la cabecera.
5. **Animación en la carga en cuatro de cinco.** R, Q y K animan el rotulador del hero y M mantiene un pulso infinito; solo T carga quieta. De las cuatro, solo K se queda dentro de 300 ms y con transform.
