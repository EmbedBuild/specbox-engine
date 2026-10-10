# Revisión ciega P2: landing de «Propuestas» (K, M, Q, R, T). Revisor A

Revisión a ciegas de cinco variantes de la landing pública de Propuestas contra `P2-BRIEF.md` y `RUBRICA.md`. No sé qué proceso produjo cada una y no lo he intentado averiguar. Escala de 0 a 5 por criterio; un 5 solo cuando no he encontrado nada que reprochar en ese criterio (misma severidad que la revisión de calibración).

## Método

- **Capturas**: he leído `X-1440.png` y `X-390.png` de página completa, troceadas en tramos legibles para ver el detalle.
- **Criterio 2** (jerarquía): adaptado a página comercial. Mido si un visitante responde en menos de un minuto a las tres preguntas del brief: qué gano frente al PDF, qué ve y qué hace mi cliente (enlace y PIN, sin cuenta), y cómo empiezo y qué cuesta (acceso anticipado gratis, precios sin decidir).
- **Criterio 7** (responsive): uso `X-medidas.json`. Hay scroll horizontal a 390 si `scrollWidth > 390`. Resultado: **K, M y T: 390 (sin scroll); Q y R: 399 (con scroll)**.
- **Tells** (criterio 3): he comprobado en el código cada aviso de `X-tells.txt` y he buscado el resto de patrones de la rúbrica. El detector acierta en lo que señala, pero no detecta el glass de M y T, las flechas en botones, los puntos medios ni la numeración.
- **Contraste**: calculado con la fórmula WCAG 2.x sobre los pares reales de cada fichero (tabla abajo).
- **Una observación de partida**: K, Q y R comparten el mismo texto y el mismo marcado. Las diferencias están en el CSS y en un par de líneas de JS. Por eso sus notas de especificidad coinciden y el resto se explica por esas diferencias.

## Contraste WCAG de los pares que importan

| Variante | Par | Ratio | Resultado |
|---|---|---|---|
| K / Q / R | tinta `#1c2a6e` / blanco (cuerpo) | 13,08:1 | AA |
| K / Q / R | tinta-2 `#4e5880` / blanco (secundario) | 6,93:1 | AA |
| K / Q / R | tinta-2 / mesa `#eef1f7` (pies de figura) | 6,12:1 | AA |
| K / Q / R | blanco / tinta (botón) | 13,08:1 | AA |
| K / Q / R | tinta / fluorescente `#ffe45c` | 10,28:1 | AA |
| K / Q / R | error `#b42318` / fondo de error `#fdecea` | 5,75:1 | AA |
| K / Q / R | aceptada `#17694a` / `#e4f3eb` | 5,80:1 | AA |
| K / Q / R | borde de campo `#7d85a6` / blanco | 3,63:1 | ≥3:1 (límite de control) |
| Q / R | borde de la casilla vacía del PIN `#d3d9e8` / blanco | 1,41:1 | <3:1 |
| M | ink `#16161B` / papel `#F6F3EC` | 16,27:1 | AA |
| M | muted `#5C5952` / papel | 6,30:1 | AA |
| M | muted / papel-2 `#EEE9DD` | 5,77:1 | AA |
| M | placeholder `#6E6A62` / blanco | 5,38:1 | AA |
| M | blanco / acento `#2B3CCB` (botón) | 8,04:1 | AA |
| M | acento / acento suave `#E7EAFB` | 6,72:1 | AA |
| M | hora `#DDE1FA` / burbuja acento | 6,21:1 | AA |
| M | borde de campo `#857E70` / blanco | 4,03:1 | ≥3:1 |
| T | ink `#1A1915` / papel `#F7F4EC` | 16,00:1 | AA |
| T | ink-2 `#46433B` / papel | 8,99:1 | AA |
| T | ink-3 `#69655B` (placeholder) / blanco | 5,81:1 | AA |
| T | error `#B0261D` / `#FBEAE7` | 5,74:1 | AA |
| T | ink-2 / amarillo suave `#FFF1BC` | 8,73:1 | AA |
| T | borde de campo y chip `#C9C0AC` / blanco | 1,81:1 | **<3:1 (falla 1.4.11)** |

Todo el texto pasa AA en las cinco. Fallan dos límites de control: los campos y los chips de T, y la casilla vacía del PIN en la maqueta de Q y R.

---

## K

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 5 | Toda la página gira alrededor del ejemplo del brief. El hero es la propia hoja de la propuesta a Taller Hermanos Ríos con la Inversión subrayada en fluorescente y una nota al margen: «Aquí se frenó 4 min 35 s de los 9 min» (l.336-366). El mismo caso reaparece en el panel (l.406-464) y en los dos móviles del cliente (l.482-525). También están el PIN por WhatsApp o teléfono, la calculadora de retorno (l.376), el PDF con el mismo contenido, tres `[DATO REAL]` (l.541, 545, 601) y Jerez en el pie (l.650). No inventa funciones ni cifras: los tiempos por sección suman exactamente 9 min (l.426-430). |
| 2 | Jerarquía (3 preguntas) | 5 | Las tres preguntas se responden en la primera pantalla, a 1440 y a 390. El H1 dice qué ganas (l.325). La entradilla dice qué hace el cliente: «enlace y un PIN, sin crear cuenta» (l.328). La nota pegada al CTA dice qué cuesta: «Acceso anticipado gratuito. Los precios aún no están decididos» (l.333). Las secciones siguen el orden del brief, las FAQ están abiertas en dos columnas y es la página más corta a 1440 (5.603 px). |
| 3 | Tells de IA | 5 | Ninguno (ver abajo). |
| 4 | Tipografía | 5 | Pareja deliberada: Literata (serif con eje óptico) para la lectura y Archivo (eje de anchura, `font-stretch:115%` en el PIN, l.230) para la interfaz. Escala fluida con `clamp` (l.82, 140), medida de 30-32em (l.84, 149, 257) y `tabular-nums` en todas las cifras del panel, las aperturas y el PIN (l.114, 177, 182, 184, 191, 230). `text-wrap: balance/pretty` (l.47-48) y ni una mayúscula decorativa. |
| 5 | Color | 5 | Monocromía de tinta azul con neutros entonados en azul (mesa `#eef1f7`, línea `#d3d9e8`, l.14-19) y un único acento con función: el fluorescente marca dónde se frenó (l.21, 106-110, 428). El verde es solo para aceptada y el rojo solo para error y revocar. Todo AA (secundario 6,93:1, sobre mesa 6,12:1, borde de campo 3,63:1). |
| 6 | Estados y craft | 4 | El formulario está cableado: validación al salir y al escribir con `aria-invalid` y `aria-describedby`, foco al primer error, botón deshabilitado con «Enviando solicitud…», aviso de envío con «Reintentar» que conserva los datos y foco gestionado en éxito y error (l.684-753). El bloque de estados tiene un reintento que funciona (l.612-642, 755-763). Hover solo con puntero fino (l.72-78), `:active` con escala (l.65, 168, 274) y objetivos de 44 px en táctil (l.71). Reproches: el error de envío del formulario real solo aparece sin conexión (`navigator.onLine === false`, l.735). Las acciones del panel son `span` inertes con aspecto de enlace (l.458-460). Los radios solo son concéntricos en móvil (l.39): a 1440 la mesa tiene 24 px y el objeto 14 px, con 40 px de relleno. |
| 7 | Responsive | 4 | 390 medido sin scroll (scrollWidth 390). El panel se adapta con container queries (l.205-211) y la cabecera conserva el CTA y oculta el logotipo (l.62). Reproches: los dos móviles apilados suman unos 1.150 px y «Revocar acceso» cae solo a una segunda línea. |
| 8 | Movimiento | 5 | `transition-property` explícito, 150-300 ms con ease-out propia (l.36, 64, 126-128) y entradas con `@starting-style` (l.130-134). La única animación en carga es el barrido del subrayado (300 ms) más la nota (250 ms), con `scale`, `translate` y `opacity`. Va bajo `no-preference` y enseña el dato clave (l.119-124). Con `reduce` solo queda la opacidad (l.135-137), el scroll suave está condicionado (l.43) y, con teclado, el cambio de estado no anima (l.129, 661). |

**Total: 38 / 40**

**Tells encontrados:** ninguno.
Casos límite, no contados:
- El recurso «mesa gris con objeto blanco encima» (l.94, 97, 171, 260-261) es una tarjeta dentro de otra, pero es un solo recurso coherente (papel sobre la mesa), no tarjetas idénticas repetidas.
- Los numerales 1, 2 y 3 de 48 px en los pasos (l.147) sí son una secuencia.

**Fortalezas**
1. La imagen cuenta el producto sin explicarlo. La propia propuesta, con el subrayado y la nota al margen, reaparece con los mismos datos en el panel y en el móvil del cliente, y las tres preguntas se responden mirando.
2. Es la más limpia de ejecutar: estados reales con foco gestionado, hover condicionado, objetivos de 44 px, `reduce` que conserva la opacidad y cero tells. Es la que entregaría con menos arreglos.

**Problemas prioritarios**
1. El error de envío con reintento solo se puede provocar en el bloque de demostración. En el formulario real hace falta estar sin conexión.
2. Las acciones del panel (Ampliar validez, Generar PIN nuevo, Revocar acceso) parecen enlaces y no hacen nada. En una página que presenta el panel, invitan a pulsar.
3. En móvil, los dos teléfonos apilados alargan la sección del cliente y «Revocar acceso» queda huérfano. A 1440, los radios de mesa y objeto no son concéntricos.

---

## M

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 2 | La copy entiende al freelancer: el chat «Te paso la propuesta… / 3 días sin noticias / ¿has podido verla?» (l.509-525) y la tabla de PDF frente a Propuestas (l.731-763). Pero no usa los datos del brief. El ejemplo es una «clínica dental · Valencia» de 6.450 €, con una sección «Calendario» en lugar de Plazos (l.467-479), y Taller Hermanos Ríos no aparece nunca. Además inventa funciones que el producto no tiene: hasta tres opciones de precio (l.545, 633), descargas del PDF (l.582, 616), avisos por correo (l.571, 641), versiones (l.755, 875), condiciones de fundador y preaviso de 30 días (l.776, 883), y habla del «equipo que la construye» de un estudio unipersonal (l.777). Faltan las FAQ de marca y de RGPD y no hay ni un `[DATO REAL]`. |
| 2 | Jerarquía (3 preguntas) | 3 | El hero responde rápido: H1 con gancho, entradilla con enlace y PIN, y las notas «Gratis…» y «Tu cliente no necesita cuenta» (l.439-451). Pero no dice que los precios están sin decidir (habla de planes de pago, l.776). Tampoco hay sección «Lo que ve tu cliente» en el móvil: la sustituye una franja de texto (l.718-721). Y ocho secciones numeradas alargan la página a 8.341 px (13.409 a 390), con el formulario antes de las preguntas. |
| 3 | Tells de IA | 0 | Siete (ver lista). |
| 4 | Tipografía | 3 | Fraunces, Hanken Grotesk e IBM Plex Mono, con carácter, escala clara y medida controlada (33-40em, 60ch en respuestas, l.91, 345). Pero pone en mayúsculas con tracking los kickers, las etiquetas, los sellos, las insignias y las cabeceras de tabla (l.125, 128, 141, 236, 250, 254, 291, 380), usa etiquetas mono de 10,5-12,5 px y no tiene ni un `tabular-nums` (precios en Fraunces proporcional, l.123, 249). |
| 5 | Color | 3 | Papel crema con neutros cálidos y AA en todo (muted 6,30:1, placeholder 5,38:1, borde 4,03:1). Pero el azul `#2B3CCB` hace de acción, selección, barras de datos, numerales de pasos y kickers, burbujas de chat, fondos de iconos y columna destacada (l.142, 160, 173, 193, 209, 231, 295). El amarillo marca a la vez lo más leído, el titular, el aviso destacado, la etiqueta de demostración y el logotipo del pie. |
| 6 | Estados y craft | 3 | Validación por campo, resumen «Revisa los 2 campos marcados» y foco al primer error (l.1029-1036); botón con spinner y «Enviando…»; éxito con «Apuntar a otra persona» (l.843-848); demostración de aceptación con recibo (l.969-995) y PIN regenerable con aviso en vivo (l.948-953). Pero falta por completo el error de envío con reintento que pide el brief: el envío siempre acaba bien (l.1041-1048). Además, los botones del segmentado miden 38 px (l.201) y el botón-enlace unos 36 px (l.330); no hay estilo `:disabled`, solo `aria-busy` con opacidad .9 (l.72); y los radios no son concéntricos (paso de 16 px con arte de 12 px y 14 px de relleno, l.171, 176). |
| 7 | Responsive | 3 | 390 medido sin scroll. La tabla comparativa pasa a tarjetas con etiqueta (l.372-383) y los CTA del hero ocupan todo el ancho (l.403). Pero `.compare tbody th{width:24%}` (l.293) gana en especificidad a la regla móvil `.compare th{width:auto}` (l.374), y las preguntas de la tabla se parten en dos o tres líneas en una columna de 80 px («¿Quién / más la / lee?»). La página mide 13.409 px, casi 16 pantallas. |
| 8 | Movimiento | 2 | No hay `transition: all` y `reduce` lo apaga todo (l.405-408). Pero desde la carga hay un punto «pulse» que anima `box-shadow` en bucle infinito de 2,2 s (l.133-134, 488), la barra de lectura transiciona `width` en 600 ms (l.209), el icono del PIN gira 500 ms (l.190) y los botones usan `ease` por defecto (l.62). |

**Total: 19 / 40**

**Tells encontrados (7):**
1. Eyebrows en mayúsculas con tracking: `.kicker` (l.141, usado en l.504, 532, 580, 628, 693, 728, 770, 856), `.float-label` (l.128), `.tag` «DEMOSTRACIÓN» (l.236), `.badge` «RECOMENDADA» (l.250), sellos (l.125, 254), cabecera de tabla (l.291) y etiquetas móviles (l.380).
2. Numeración 01/02/03 sin secuencia real: «01 El problema» … «08 Preguntas» (l.504-856). Las secciones de una landing no son pasos.
3. `→` en botones: flecha en el CTA principal del hero (l.443).
4. Glass decorativo: cabecera con `backdrop-filter: saturate(1.4) blur(10px)` (l.76).
5. Borde lateral de color >1px: `.callout{border-left:4px solid var(--ink)}` (l.151, usado en l.507).
6. Puntos medios encadenados: «Nuevo en embed.build · acceso anticipado» (l.438), «Propuesta 031 · versión 3» (l.464, 650, 675), «clínica dental · Valencia» (l.467), «9 oct 2026 · 10:42» (l.483), «Propuesta 031 · lun 5 – mié 7 oct» (l.588), horas del historial (l.614-618) y el `<title>` (l.6).
7. Tarjetas anidadas: el paso en tarjeta (l.171) contiene el lienzo `.art` con borde y trama (l.176), que contiene filas-tarjeta `.art-row` (l.177); además hay tarjetas de opción dentro del panel (l.239).

No listados, pero del mismo repertorio: tramas de puntos decorativas (l.98, 176), logotipo gigante en el pie (l.348, 893) y una rejilla de cuatro iconos en cuadrado redondeado (l.231, 696-717).

**Fortalezas**
1. Tiene el mejor argumento de venta del grupo. El chat de «3 días sin noticias» y la tabla «PDF adjunto frente a Propuestas» responden a «¿qué gano frente a un PDF?» mejor que cualquier lista de ventajas.
2. Las demostraciones recalculan datos. El segmentado Total / 1.ª visita / 2.ª visita cambia barras, tiempos y la nota de lectura (l.918-943), y la aceptación genera un recibo con la fecha real.

**Problemas prioritarios**
1. No respeta el contenido del brief: inventa funciones, cliente y cifras (clínica dental, 6.450 €, tres opciones, versiones, avisos, condiciones de fundador), ignora a Taller Hermanos Ríos, omite las FAQ de marca y RGPD con su `[DATO REAL]`, y cambia «a qué te dedicas» por tamaño de equipo y volumen (l.806-824).
2. Faltan piezas obligatorias: el estado de error de envío con reintento, la sección de lo que ve el cliente en el móvil y el dispositivo de cada apertura en el panel (l.614-618).
3. Siete tells y 13.409 px a 390, con la tabla comparativa móvil rota por una regla de especificidad.

---

## Q

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 5 | Mismo contenido que K: la hoja de Taller Hermanos Ríos con la nota al margen, el panel, los dos móviles y las FAQ con `[DATO REAL]` (l.535, 539, 595). No inventa ningún dato. |
| 2 | Jerarquía (3 preguntas) | 4 | El hero responde a las tres preguntas igual que K. Pero `:where(.texto) > * + *` (l.141) tiene especificidad cero y pierde contra `p{margin:0}` (l.45). En «Lo que ves tú», «Lo que ve tu cliente» y «Pide acceso anticipado», el titular se pega al texto y los párrafos se funden en un bloque. Además, a 1440 los dos móviles se apilan (l.214: no caben por 1 px) y dejan media sección vacía. |
| 3 | Tells de IA | 2 | Tres (ver lista). |
| 4 | Tipografía | 3 | Misma pareja Literata y Archivo, con `tabular-nums`. Pero el ritmo vertical está roto en tres secciones por el fallo de `:where`, como se ve en las capturas de 1440 y 390: H2 sin aire y párrafos sin separación. |
| 5 | Color | 4 | Paleta de K y texto AA en todo (secundario 6,93:1). Pero la casilla vacía del PIN pasa a `var(--linea)` (l.224), con 1,41:1 sobre blanco: en la maqueta del cliente, el cuarto dígito casi no se ve. |
| 6 | Estados y craft | 3 | Conserva los estados cableados de K: validación, reintento, foco, `:active`, hover con puntero fino y 44 px en táctil. Pero las acciones del panel pasan a parecer botones con anillo y sombra (l.201) y siguen siendo `span` inertes (l.452-454). Además, el bloque de estados mete cada mensaje en una segunda tarjeta (l.286-288). |
| 7 | Responsive | 2 | **Scroll horizontal: scrollWidth 399 a 390 px.** `.hero__rejilla` y `.dos-col` no tienen `minmax(0,1fr)` ni `min-width:0` (l.82, 151), así que la columna de texto de «Lo que ve tu cliente» mide 399 px. Las medidas lo confirman (div.dos-col__texto, h2, p, ol, li y nota a 399) y en la captura el texto toca el borde derecho. |
| 8 | Movimiento | 2 | La animación de carga del hero dura 700 ms con ease-in-out y 400 ms de retraso, y anima `clip-path` (l.120, 123). La nota entra a los 1,2 s con `filter: blur` (l.121, 124) y los mensajes del formulario transicionan `filter` (l.126-132). Se respeta `reduce` (l.119, 135-137). |

**Total: 25 / 40**

**Tells encontrados (3):**
1. Glass decorativo: cabecera `rgba(255,255,255,.86)` con `backdrop-filter: blur(10px)` (l.59).
2. Borde lateral de color >1px: `.comentario{border-left:2px solid var(--tinta)}` (l.113), visible a 390 junto a «Aquí se frenó».
3. Tarjetas idénticas anidadas: tres `.estado` con anillo y sombra (l.286), cada una con su `.exito` o `.aviso` con borde propio dentro (l.288).

**Fortalezas**
1. Hereda la mejor narrativa del grupo: el caso de Taller Hermanos Ríos atraviesa la hoja, el panel y el móvil, y las tres preguntas se responden en el hero.
2. El formulario sigue completo: validación inline, error de envío con reintento que conserva los datos, foco gestionado y objetivos de 44 px.

**Problemas prioritarios**
1. Scroll horizontal a 390 (399 px) por dos rejillas sin `minmax(0,1fr)`. Incumple un requisito duro del brief.
2. Ritmo de texto roto por un `:where()` de especificidad cero, y móviles apilados a 1440. La página pierde el aire que la hacía escaneable.
3. Animación de carga lenta y con propiedades caras (`clip-path`, `blur`), y botones falsos en el panel que invitan a pulsar.

---

## R

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 5 | Mismo contenido que K: el caso de Taller Hermanos Ríos de punta a punta, PIN por otro canal, PDF, calculadora y `[DATO REAL]` (l.507, 511, 567). |
| 2 | Jerarquía (3 preguntas) | 4 | El hero responde a las tres preguntas. Pero, como en Q, `:where(.texto)` (l.115) pierde frente al reset y los bloques de texto quedan sin separación, y a 1440 los móviles se apilan (l.186). |
| 3 | Tells de IA | 2 | Tres (ver lista). |
| 4 | Tipografía | 3 | Misma pareja y `tabular-nums`, pero con el ritmo roto por `:where` (l.115). Además, `balance` queda solo en h1-h3 (l.38-39), y en los títulos de las maquetas se pierde («Web de citas para / el taller»). |
| 5 | Color | 4 | Paleta de K, texto AA. La casilla vacía del PIN tiene 1,41:1 (l.196). |
| 6 | Estados y craft | 2 | El formulario y el reintento funcionan, pero la ejecución se degrada. No hay ni una regla `:active` en el fichero. El hover ya no se condiciona al puntero fino (l.57, 61, 64). «Ver cómo funciona» y el logotipo pierden su altura mínima y se quedan en unos 26 px y 20 px (l.52, 63). El botón Reintentar no tiene ancho mínimo y cambia de tamaño al pasar a «Enviando…» (l.246). Los radios se invierten en los estados: una tarjeta de 12 px contiene otra de 14 px (l.258-260 con l.248). Y las acciones del panel parecen botones sin serlo (l.173, 424-426). |
| 7 | Responsive | 2 | **Scroll horizontal: scrollWidth 399 a 390 px** (rejillas sin `minmax(0,1fr)`, l.67, 125); la columna de «Lo que ve tu cliente» se sale. |
| 8 | Movimiento | 2 | Barrido de 900 ms con 600 ms de retraso animando `clip-path` (l.105, 109), nota a los 1,45 s con `ease` (l.106) y sello de aceptada con rebote y giro, `cubic-bezier(.2,.9,.3,1.2)` (l.107, 111). Todo bajo `no-preference`. |

**Total: 24 / 40**

**Tells encontrados (3):**
1. Glass decorativo: cabecera con `backdrop-filter: blur(10px)` (l.50).
2. Borde lateral de color >1px: `.comentario{border-left:2px solid var(--tinta)}` (l.98).
3. Tarjetas idénticas anidadas: tres `.estado` con borde (l.258), cada una con un `.exito` o `.aviso` con borde dentro (l.260).

**Fortalezas**
1. Contenido fiel y específico: el ejemplo del brief, sin una cifra inventada, con las FAQ obligatorias y sus marcadores.
2. Lo esencial sigue funcionando: validación inline, error de envío con reintento, éxito con foco y conmutador Pendiente/Aceptada en el panel.

**Problemas prioritarios**
1. Scroll horizontal a 390 (399 px): incumple el brief.
2. Craft degradado: sin `:active`, objetivos de 20-26 px en el logotipo y el enlace secundario del hero, hover también en táctil y radios invertidos.
3. La animación de carga dura casi 2 s, termina con rebote y anima `clip-path`.

---

## T

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 5 | Usa el ejemplo del brief en todas partes: el correo «Antes» con `Propuesta_Taller_Rios.pdf`, la tarjeta «Con Propuestas», el panel y los móviles. Los tiempos suman exactamente 9 min (l.597-601). Al regenerar el PIN indica cómo enviarlo: «por WhatsApp o por teléfono, no en el mismo mensaje que el enlace» (l.911). Cuenta el origen real, «un estudio de software de una sola persona en Jerez… que ya envía así sus propias propuestas» (l.761), con `[CIFRA REAL]` (l.762), y deja la marca y el RGPD como `[DATO REAL: …]` explicados (l.724, 728, 803). |
| 2 | Jerarquía (3 preguntas) | 4 | Es la única que convierte las tres preguntas del brief en una franja literal: «Frente al PDF / Tu cliente / Para empezar» (l.508-512). Además las responde en el hero (l.463-469). Reproches: el remate del «Antes», «Ni idea.» (l.479), queda tapado por la tarjeta superpuesta a 1440 y a 390 (margen −26/−40 px, l.112, 132). La leyenda numerada del panel aparece en orden 2-1-3-4 (l.595, 606, 612, 618). Cada sección repite eyebrow, H2 y entradilla, y la página llega a 11.778 px a 390. |
| 3 | Tells de IA | 0 | Seis (ver lista). |
| 4 | Tipografía | 3 | Fraunces con eje óptico 144, Instrument Sans e IBM Plex Mono, con `tabular-nums` en los KPI y los tiempos (l.201, 215) y medida de 36-40em (l.95, 152). Pero el tracking negativo a tamaño display (−0,025em y −0,02em, l.93, 150) se come los espacios entre palabras: en las capturas se lee «Unenlace» y «Mandatu». Además usa mayúsculas con tracking en nueve clases y etiquetas mono de 9,9-11,5 px (l.165, 171, 279). |
| 5 | Color | 3 | Tinta casi negra, amarillo de subrayador y neutros crema cálidos, con texto AA (secundario 8,99:1, placeholder 5,81:1). Pero el amarillo hace de insignia, subrayado de titulares, sombra del hover, marcador de datos pendientes, etiqueta y, además, de «se frenó» (l.57, 58, 62, 86, 105, 119, 218). Y los bordes de los campos y los chips (`#C9C0AC`) dan 1,81:1 sobre blanco (l.342, 353), por debajo del 3:1 exigido a los límites de un control. |
| 6 | Estados y craft | 4 | Es la más interactiva. Los tres botones del panel funcionan: amplían la fecha, dan un PIN nuevo con instrucción de canal y revocan deshabilitando el resto (l.902-922). El interruptor «Simular un fallo» provoca el error real del formulario, con reintento (l.823, 1009-1014). Hay foco al título del éxito, `disabled` definido (l.69, 241) y 44 px en botones, chips, herramientas e interruptor. Reproches: «Ni idea.» queda tapado. El CTA de la cabecera muestra un hueco doble entre «acceso» y «anticipado», porque el `gap:10px` del flex sustituye al espacio (l.60, 452). Los radios no son concéntricos (panel de 20 px, tarjeta interior de 14 px, 28 px de relleno) y el enlace de texto mide unos 36 px (l.254). |
| 7 | Responsive | 4 | 390 medido sin scroll. El CTA de la cabecera solo acorta el texto por debajo de 360 px (l.81), los botones del hero ocupan todo el ancho (l.99), los KPI pasan a 2+1 con el freno a todo el ancho (l.198-204), las barras se reorganizan en dos filas (l.213-226) y los móviles se apilan. Reproches: el solapamiento del «Antes» también tapa texto a 390, y la página mide 11.778 px. |
| 8 | Movimiento | 4 | No hay animaciones en carga. Las transiciones duran 150-200 ms con propiedades explícitas, y `reduce` lo anula todo y desactiva el scroll suave (l.408-412). Reproche: el hover del botón principal anima `box-shadow` además de `transform`, con `ease` (l.60, 62). |

**Total: 27 / 40**

**Tells encontrados (6):**
1. Eyebrows en mayúsculas con tracking: `.eyebrow` (l.85; usado en l.462, 519, 566, 645, 714, 751, 819), `.tag` (l.103), `.live-client` (l.114), `.answers-k` (l.138), `.step-n` (l.159), `.art-bubble small` (l.171), `.panel-client` (l.190), `.scr-kicker` (l.279) y `.state-name` (l.389).
2. Puntos medios encadenados: «01 · Frente al PDF» (l.509-511), «01 · Cómo funciona» … «05 · Acceso anticipado» (l.519-751), «Portátil · la última» y «miércoles 07/10/2026 · 9:03» (l.608-610), el pie (l.871) y el `<title>` (l.6).
3. Numeración 01/02/03 sin secuencia: la franja de respuestas numera 01-03 (l.509-511) y justo debajo las secciones vuelven a empezar en 01 (l.519) hasta 05.
4. `→` en botones: el CTA del hero (l.466), el envío del formulario (l.802) y el enlace «Quiero esto en mis propuestas» (l.635).
5. Glass decorativo: cabecera con `backdrop-filter: saturate(1.4) blur(10px)` (l.71).
6. Tarjetas anidadas: el panel (l.181) contiene KPI (l.199) y `.pcard` (l.207); el paso (l.156) contiene `.step-art` (l.158), que contiene `.art-doc` (l.162); y `.state-box` (l.393) contiene `.alert` (l.359).

Caso límite, no contado: las tarjetas de número grande con etiqueta (l.587-591 y l.490-494) siguen el patrón hero-metric, pero muestran los datos que pide el brief.

**Fortalezas**
1. Es la más fiel a las tres preguntas del visitante: franja de respuestas literal, comparación «Antes / Con Propuestas» con el caso real y un origen del producto contado con honestidad (estudio de una persona, `[CIFRA REAL]`).
2. Las demostraciones hacen lo que dicen: el panel tiene acciones vivas con mensajes de estado, y un interruptor provoca el fallo real del formulario para probar el reintento.

**Problemas prioritarios**
1. Repertorio completo de landing genérica: seis tells (eyebrows mono en mayúsculas, puntos medios, numeración que se reinicia, flechas, glass y tarjetas anidadas).
2. Defectos visibles: «Ni idea.» tapado por la tarjeta superpuesta, hueco doble en el CTA de la cabecera y titulares display con las palabras pegadas por el tracking negativo.
3. Accesibilidad del formulario: bordes de campos y chips a 1,81:1, y muchas etiquetas mono de 10-11 px.

---

## Ranking final

| Puesto | Variante | Notas (1-8) | Total | Veredicto |
|---|---|---|---|---|
| 1 | **K** | 5, 5, 5, 5, 5, 4, 4, 5 | 38 / 40 | La más sólida: cuenta el caso del brief sin un solo tell, con AA en todo y estados reales; solo le faltan el error de envío en el formulario real y acciones vivas en el panel. |
| 2 | **T** | 5, 4, 0, 3, 3, 4, 4, 4 | 27 / 40 | La más completa en demostraciones y la que mejor responde a las tres preguntas, lastrada por seis tells, titulares apretados y bordes de campo sin contraste. |
| 3 | **Q** | 5, 4, 2, 3, 4, 3, 2, 2 | 25 / 40 | El contenido de K con regresiones de CSS: scroll horizontal a 390, ritmo de texto roto y animación de carga lenta. |
| 4 | **R** | 5, 4, 2, 3, 4, 2, 2, 2 | 24 / 40 | Las regresiones de Q y un craft peor: sin `:active`, objetivos de 20-26 px y animación con rebote. |
| 5 | **M** | 2, 3, 0, 3, 3, 3, 3, 2 | 19 / 40 | El mejor argumento de venta, pero inventa producto y cliente, omite el error de envío y las FAQ obligatorias, y acumula siete tells. |

**Qué separa a las de arriba de las de abajo.**
- **K** gana porque no tiene nada que quitar. El brief ya traía el mejor material (la propuesta a Taller Hermanos Ríos que se frena en Inversión) y K lo usa como imagen, sin el repertorio de landing: sin eyebrows, sin numeración decorativa, sin flechas, sin glass.
- **T** es la página más trabajada en interacción y la más explícita con las tres preguntas, pero viste ese contenido con el uniforme completo de la landing de 2025-26, y la rúbrica lo cobra entero en el criterio 3.
- **Q y R** demuestran lo frágil que es la buena base: con el mismo texto que K, dos rejillas sin `minmax(0,1fr)` y un `:where()` de especificidad cero bastan para romper el requisito de 390 px y el ritmo de lectura. Unas animaciones de carga más largas completan la caída.
- **M** tiene la copy más persuasiva, pero persuade con un producto que no existe: inventa opciones de precio, versiones, avisos y un cliente que no está en el brief. En una página que vende a quien manda propuestas, prometer funciones inventadas es el peor fallo posible.
