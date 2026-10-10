# Crítica de diseño: P2 / V3 (landing de «Propuestas»)

## 1. Tabla de notas

| # | Criterio | Nota | Motivo |
|---|---|---|---|
| 1 | Especificidad | 5 | Todo es del producto: la hoja de Taller Hermanos Ríos con el fluorescente sobre Inversión, el panel con los datos del brief, el PIN que llega por WhatsApp, «Ya sabes de qué hablar cuando le llames», Jerez en el pie. Los datos que no existen van como `[DATO REAL]`, sin inventar nada. |
| 2 | Jerarquía y escaneabilidad | 4 | Las tres preguntas se responden en la primera pantalla a los dos anchos: frente al PDF (h1 y entradilla), qué ve el cliente («enlace y PIN, sin crear cuenta») y qué cuesta («Acceso anticipado gratuito. Los precios aún no están decididos.»), con la llamada a la acción visible. Pierde un punto porque en tres secciones el título y los párrafos van pegados (defecto 3) y porque a 1440 px «Lo que ve tu cliente» deja unos 900 px vacíos (defecto 2). |
| 3 | Tells de IA | 2 | Tres tells: glass decorativo en la cabecera (l.59), borde lateral de 2 px en `.comentario` por debajo de 40rem (l.113) y tarjetas idénticas anidadas en «Así responde el formulario» (l.284-291; el mismo patrón en `.formulario-zona` > `.formulario`, l.254-255). No hay eyebrows, gradientes, flechas en botones, `·` encadenados, emojis ni Acme. La numeración 1-2-3 es una secuencia real. |
| 4 | Tipografía | 4 | Literata para la lectura y Archivo para la interfaz: una pareja con carácter y bien repartida. La escala es clara, la medida está limitada (30-32em), las cifras del panel y del PIN usan tabular-nums y no hay mayúsculas sostenidas. Lo penaliza el ritmo vertical roto entre párrafos (defecto 3). |
| 5 | Color | 4 | La paleta es tinta azul marino sobre papel, con neutros entonados en azul (`--mesa` #eef1f7). El fluorescente amarillo tiene una función, que es señalar dónde se frenó el cliente, y verde y rojo solo se usan para estados. El texto secundario #4e5880 da 6,9:1 sobre blanco. El reproche: la caja vacía del PIN (#d3d9e8, l.224) queda a 1,4:1 y casi no se ve. |
| 6 | Estados y craft | 4 | El formulario es completo: error inline con icono, `aria-invalid` y `aria-describedby`, foco en el primer campo inválido, botón «Enviando solicitud…» deshabilitado, error de envío con «Reintentar» y éxito que recibe el foco. Los tres estados se ven en la demo, el foco es visible (3 px), las áreas de pulsación son de 40-48 px, los radios son concéntricos (también en móvil) y las sombras están entonadas, con desplazamiento. Lo penalizan los botones falsos del panel (defecto 7) y el espaciado anulado. |
| 7 | Responsive | 2 | A 390 px hay scroll horizontal (scrollWidth 399) y el texto de «Lo que ve tu cliente» queda cortado en el borde (defecto 1). A 1440 px la composición de los dos móviles se rompe y se apilan (defecto 2). Lo que sí funciona: el panel se recompone bien con la container query y la cabecera se puede usar. |
| 8 | Movimiento | 3 | Las transiciones de interacción están bien hechas: propiedades explícitas (sin `transition: all`), 150-300 ms, ease-out, `@starting-style` y respeto a prefers-reduced-motion. Pero hay una animación decorativa de carga en la primera pantalla de 0,7 s y 0,4 s, con 1,2 s de retraso, que anima `clip-path` y `filter: blur` con ease-in-out (defecto 4). |
| | **Total** | **28 / 40** | |

## 2. Veredicto

**Block.**

La página desborda a 390 px (scrollWidth 399 frente a 390), cuando el brief exige expresamente que no haya scroll horizontal y la mitad de las visitas llegan desde el móvil. A 1440 px, además, la sección del cliente pierde su composición. Las dos cosas se arreglan en una sola ronda, con cambios de una o dos líneas cada una. El resto (contenido, estados, accesibilidad del formulario, especificidad) está muy cerca de poder aprobarse. Cuando estén corregidos los defectos 1 a 3 y comprobado `scrollWidth = clientWidth` a 390 px, pasaría a Needs changes o a Approve.

## 3. Defectos (por severidad)

1. **Alta: scroll horizontal a 390 px en «Lo que ve tu cliente»** (l.151 y l.462-523; captura 390, tramo y≈4.000-5.400; medidas: `div.dos-col__texto@399`).
   - Qué falla: `.dos-col` no declara columnas en móvil, así que su pista `auto` crece hasta el min-content de la escena. Ese min-content lo infla la fila de pestañas del móvil, que tiene `white-space:nowrap` (l.233-234). El resultado es que el texto llega al píxel 399, queda cortado unos 9 px en el borde («ni de», «se abre en», «si está de») y la escena de los móviles se queda sin margen derecho.
   - Qué hacer: dar a `.dos-col` `grid-template-columns:minmax(0,1fr)` en la regla base (o `min-width:0` a sus hijos) y volver a medir hasta que scrollWidth sea 390.

2. **Alta: los dos móviles se apilan a 1440 px** (l.156-157, l.211-214; captura 1440, tramo y≈2.700-4.000).
   - Qué falla: el interior de la escena mide unos 550,7 px (7 columnas menos 2 × 40 px de padding) y los móviles necesitan 2 × 16,5rem + 1,5rem = 552 px. No caben por 1,3 px, así que el segundo baja. La escena llega a unos 1.300 px de alto, con el texto arriba a la derecha y unos 900 px vacíos a su lado. El `margin-top:3.5rem` de `.movil--bajo` muestra que la intención era colocarlos lado a lado.
   - Qué hacer: reducir el `gap` de `.moviles` a 1rem (l.211) o el ancho de `.movil` a 16rem (l.212), y comprobar que quedan en una sola fila a partir de 60rem.

3. **Media: el espaciado entre bloques de `.texto` no se aplica** (l.141 frente a l.45; capturas de «Lo que ves tú», «Lo que ve tu cliente» y «Pide acceso anticipado» a los dos anchos).
   - Qué falla: `:where(.texto) > * + *` tiene especificidad 0 y pierde frente a `p{margin:0}`. El h2 queda pegado al primer párrafo, los tres párrafos de «Lo que ves tú» se leen como uno solo y la lista numerada y la nota del PDF se pegan al texto.
   - Qué hacer: escribir la regla como `.texto > * + *` o envolver el reset de la l.45 en `:where()`.

4. **Media: animación decorativa en la carga de la primera pantalla** (l.119-124, l.126-127, l.131-132).
   - Qué falla: `barrido` dura 0,7 s con ease-in-out sobre `clip-path`, y `aparece` dura 0,4 s con 1,2 s de retraso sobre `filter: blur`. La anotación clave («Aquí se frenó 4 min 35 s») tarda 1,6 s en aparecer. `.aparece` también transiciona `filter`.
   - Qué hacer: bajar las duraciones a 300 ms o menos, usar ease-out, quitar el retraso (o dejarlo en 150 ms como mucho) y animar solo `opacity` y `transform` (por ejemplo, `scaleX` con `transform-origin:left` para el fluorescente). Hay que quitar `filter` de las transiciones.

5. **Media: tarjetas anidadas idénticas en «Así responde el formulario»** (l.284-291 y l.610-634; captura 1440, tramo final).
   - Qué falla: hay tres `.estado` con anillo y sombra, y cada uno contiene otra caja con borde (`.exito`, `.falso-campo` o `.aviso`). Es un marco dentro de otro marco, repetido tres veces.
   - Qué hacer: quitar el anillo, la sombra y el fondo de `.estado` y dejar el nombre del estado como rótulo encima de su caja.

6. **Baja: cabecera con glass y borde lateral de 2 px** (l.59 y l.113).
   - Qué falla: el `backdrop-filter: blur` de la cabecera es decorativo, porque el fondo ya es casi opaco. `.comentario` lleva `border-left: 2px` por debajo de 40rem.
   - Qué hacer: borrar el bloque `@supports` de la l.59 y dejar el fondo `rgba(255,255,255,.96)`. En móvil, sustituir el borde lateral por la misma raya guía horizontal que ya se usa en escritorio (l.117), o bajarlo a 1 px.

7. **Baja: botones falsos en la maqueta del panel** (l.200-202 y l.451-455; captura 1440, panel, fila inferior).
   - Qué falla: «Ampliar validez», «Generar PIN nuevo» y «Revocar acceso» son `span` con anillo, sombra y unos 30 px de alto. Al lado de un conmutador que sí funciona, invitan a pulsar y no hacen nada.
   - Qué hacer: quitarles la sombra y el anillo para que se lean como parte de la maqueta, o convertirlos en elementos sin apariencia pulsable.

8. **Baja: casilla vacía del PIN casi invisible** (l.224 y l.489; captura del primer móvil).
   - Qué falla: el borde `#d3d9e8` sobre blanco da 1,4:1, por debajo del 3:1 que se pide a un componente de interfaz. La cuarta casilla apenas se distingue.
   - Qué hacer: usar `--borde-campo` (#7d85a6, 3,6:1) como borde de `.pin__caja`.
