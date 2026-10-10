# Revisión ciega P1: «Participantes de la prueba» (K, M, Q, R, T, W, Z)

Revisor B. Siete variantes de la misma pantalla de PaddockManager contra `P1-BRIEF.md` y `RUBRICA.md`. No sé qué proceso o herramienta produjo cada una y no lo he intentado averiguar. Puntuación de 0 a 5 por criterio; un 5 solo cuando no he encontrado nada que reprochar en ese criterio. Orden de revisión: Z, W, T, R, Q, M, K.

## Método

- **Código**: leído entero en cada variante; las líneas citadas son las del fichero `X.html`.
- **Capturas**: `X-1440.png` y `X-390.png` de página completa. Las de 390 px las he troceado en tramos de 1.400 px para leerlas (copias temporales, ya borradas; los originales no se han tocado). Las capturas de W y Q a 390 miden 795 y 1.106 px de ancho: la propia captura ya enseña el desbordamiento.
- **Criterio 7**: uso `X-medidas.json`. Hay scroll horizontal a 390 si `scrollWidth` > 390, salvo que lo sobrante quede recortado y oculto. K informa de `tr@404` y `th@404` sobresaliendo, pero son la cabecera de tabla visualmente oculta (`clip`, l.225) y `scrollWidth` es 390: no cuenta.
- **Datos**: cada cifra, nombre, equipo, box y hora contrastados con las tablas del brief. Una cifra que el brief no da cuenta como defecto del criterio 1.
- **Contraste**: fórmula WCAG 2.x (luminancia relativa) sobre los pares reales de cada fichero. Tabla al final.
- **Tells**: la salida de `X-tells.txt` comprobada línea a línea. Descarto los puntos medios que reproducen el texto del brief y los falsos positivos (p. ej., «Roboto» como último recurso del `font-family` de K, l.32, donde la fuente real es Archivo). Como en la calibración, la barra interior de 3-4 px que marca la fila o el elemento seleccionado es un indicador de selección y no un borde lateral decorativo.
- **Pila técnica**: no puntúa. W y Q cargan Tailwind por CDN y Material Symbols, cosa que el brief no permite; lo cito solo en problemas.

---

## Z — `Z.html` (IBM Plex Sans + Barlow Condensed, neutros cálidos, ámbar/violeta/verde)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 4 | Datos fieles al brief (9 categorías con verificados calculados bien, 23/21/11/11/10/9/8/8/3, l.413-421; las 8 filas con sus horas, boxes y avisos; las 3 filas del Excel) y copy de producto: «Aún no ha pasado. Está en Carpas Paddock» (l.620), «Resolver en oficina antes de que salga a pista» (l.654), «Ver dorsal 7» para el duplicado (l.696), definición explícita de «verificado» (l.409). Inventa el estado de la pegatina del casco de Mateo («Sin poner», l.643), que el brief no da, y supone «RFME» como licencia. |
| 2 | Jerarquía (Operate) | 4 | Las tres preguntas tienen respuesta arriba: rejilla de categorías con barra y «N pendientes» (P3), columnas Moto/Equipo con chip ámbar y columna Box (P1), columna «Oficina» con chip violeta y filtro «Con aviso de oficina» (P2), y la lista empieza a ~540 px a 1440. Pero la tabla de 8 columnas junto a un panel de 380 px queda apretada: los chips de oficina ocupan 3-4 líneas («Corría en Superbike la prueba anterior») y las filas van de 60 a 110 px. |
| 3 | Tells de IA | 2 | Tres tells (ver lista). |
| 4 | Tipografía | 3 | Pareja con intención (Plex para la interfaz, Barlow Condensed en dorsales tipo placa, l.165, y cifras), `tabular-nums` global (l.45), medida acotada (70ch, 34ch). En contra: tres estilos en mayúsculas con tracking (l.72, 96, 236), muchos secundarios a 11-12,5 px, y `overflow-wrap:break-word` (l.45) con una columna de licencia del 9 % (l.154) parte «Provisional» en «Provision/al» a 1440. |
| 5 | Color | 4 | Neutros cálidos entonados (#F4F3EF, #15171C), acción en tinta negra, azul solo para foco y selección, ámbar = pendiente, violeta = oficina, verde = verificado, rojo = error, con leyenda (l.431-435). Todo el texto pasa AA (muted 5,4-6,0:1; pend 6,3:1; off 7,4:1). Reproches: borde del buscador y de los chips #C8C5BC a 1,73:1 (l.81, 141), por debajo de 3:1 para el límite de un control; en la barra, verde y ámbar están a 1,49:1 de luminancia (solo se distinguen por el tono). |
| 6 | Estados y craft | 3 | Los mejores textos de estado del conjunto: el vacío enseña los filtros activos como chips y da dos salidas (l.713-725); el error explica la causa, ofrece dos acciones y tranquiliza («No se ha cambiado nada… La lista sigue con los 129», l.748, 755); skeleton con la forma de la fila. Accesibilidad de base cuidada: enlace de salto (l.356), `caption`, `aria-sort` (l.476, 482), horas con texto oculto «Verificada el». En contra: ni una línea de JS (los chips y selects no filtran, la fila no cambia el detalle; el brief lo permite, pero los controles parecen funcionales), sin `:active`, sin `disabled`, botones pequeños, chips y selects de 32 px en escritorio (l.89, 92, 141, 151). |
| 7 | Responsive | 4 | 390 px medido sin desbordar. La tabla se convierte en rejilla con etiquetas por celda (l.300-315), el buscador ocupa todo el ancho, los botones secundarios pasan a icono de 44 px con `aria-label` (l.289-290, 390-391). Pero el resumen ocupa ~1.000 px antes de la lista, los selects truncan su texto («Todas las catego», «Dorsal, de menor») y tras pulsar una fila no hay vuelta a la lista: la página llega a 7.341 px. |
| 8 | Movimiento | 2 | Ninguna transición: el hover cambia a saltos. La única animación es el brillo del skeleton por `background-position`, 1,4 s lineal (l.248, 253), y `reduce` solo la apaga (l.262). |

**Total: 26 / 40**

**Tells encontrados (3):**
1. Eyebrows en mayúsculas con tracking: `.eyebrow` l.72 (usado en l.376 y l.587), `.h3` l.96 (l.612, 626, 639, 650), `.state-cap` l.236 (l.711, 731, 742).
2. Hero-metric: «81 %» a 64 px (l.104, l.402), la cifra más grande de la página (el h1 mide 30 px), seguido de tres cifras de 28 px con etiqueta (l.111, l.405-407).
3. Puntos medios encadenados como patrón: l.376, 381, las nueve tarjetas de categoría («23 de 29 verificados · 79 %», l.413-421), l.598, 677, 685, 693.

No contados: `border-right:2px solid #fff` en la barra (l.107, que el detector marca) es un separador interno; `inset 4px` en la fila seleccionada (l.162) es selección; el título (l.6) solo reordena el texto del brief; degradado sutil en la cabecera del detalle (l.191), que no es morado ni azul.

**Fortalezas**
1. Es la variante que mejor redacta el trabajo de la oficina de carrera: la fila dice dónde está quien falta, el aviso dice cuándo hay que resolverlo, la fila del Excel dice qué hacer, y el error deja claro que no se ha perdido nada.
2. Responde a las tres preguntas del brief en el primer pantallazo de escritorio con datos que cuadran al 100 %, y separa visual y semánticamente «resolver en oficina» (violeta, con icono) de «información» (gris).

**Problemas prioritarios**
1. Maqueta estática: filtros, orden, selección y navegación del detalle no hacen nada. Además no hay `:active` ni `disabled` y los controles de escritorio miden 32 px.
2. Tres tells de plantilla: eyebrows en mayúsculas en tres sitios, el «81 %» de 64 px como hero y el punto medio como separador universal.
3. Tabla apretada a 1440: «Provision/al» partido, chips de oficina a 3-4 líneas y filas irregulares. En móvil hay 1.000 px de resumen antes de la primera fila.

---

## W — `W.html` (Tailwind por CDN, Atkinson Hyperlegible Next + Barlow/Saira Condensed, grafito + naranja + violeta)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 1 | Vocabulario de paddock (pips por participante, «carpa», «transponder»), pero muchos datos no cuadran con el brief. Hora 11:42 CEST en vez de 09:40 (l.172). Equipo verificado de Bruno a las 08:45 y no 08:42 (l.472). Pau con «Team Ferrandis» y moto a las 09:10, cuando el brief da Llobet Motorsport y 09:05 (l.479, 482). Hugo con el box en la columna de equipo y «Carpas Paddock» como box (l.493, 495). Lucía con «Arranz Motorsport», 07:55/08:05 y un «Tutor OK» inventado (l.509-515). Mateo con «Beon PreMoto3» a las 08:30 (l.524-526). Théo con «French Junior Team» a las 09:00 (l.537-540). Nerea a las 08:50 en vez de 09:30 (l.557). En el detalle, cilindrada, número de licencia, guantes y botas, ficha médica y fianza (l.596-642). En el pie, IP, MyLaps y «14 comisarios» (l.726-732). Y jerga en inglés: «Scrutineering», «Import Aborted», «Warm-Up». |
| 2 | Jerarquía (Operate) | 2 | Buen titular operativo («Faltan 25 por verificar», l.235) y matriz de pips que deja ver la P3 de un vistazo. Pero el orden es el del «Registro oficial RFME» y no el dorsal (l.563), no hay control de orden, los avisos de oficina se mezclan con los estados de verificación en las mismas celdas (l.485, 498), la cabecera a 1440 se monta sobre el contenido y el detalle no tiene cascos, país ni fecha de las verificaciones. |
| 3 | Tells de IA | 2 | Tres tells (ver lista). |
| 4 | Tipografía | 2 | Fuentes elegidas con intención (Atkinson para leer, condensadas para cifras), pero h1 y etiquetas en mayúsculas, texto base a 12 px y mucho texto a 9-11 px (l.168, 369, 470, 581, 618), sin `tabular-nums` y con monoespaciada de sistema en «Box 12» (l.457). |
| 5 | Color | 2 | Paleta con carácter, pero el naranja hace de pendiente y también de acción principal («Marcar verificado manualmente», l.648). Texto naranja a 11 px sobre blanco con 3,33:1, que no llega a AA (l.255, 267…). Neutros casi grises puros (#F9F9F9, #EDEFF1). |
| 6 | Estados y craft | 1 | Los estados se ven con un conmutador en la cabecera («[Vista Vacía (Sin resultados)]», l.186-194). El vacío es genérico, y el error inventa causas (UTF-16, «Moto4/PreMoto3») y pone el skeleton en la misma vista (l.682-719). Los filtros no filtran y las filas no seleccionan. Botones de 22-32 px (`py-1` con texto de 11 px). Los checkboxes quitan el anillo de foco (`focus:ring-0`, l.419, 423). Los botones de icono tienen como nombre accesible la ligadura en inglés («print», «refresh», l.204-209). |
| 7 | Responsive | 0 | **Desborda en los dos anchos: `scrollWidth` 795 a 390 y 1.511 a 1440**, con `overflow-x-hidden` en el body (l.159). A 390, «Importar Excel RFME» y «Añadir participante» quedan fuera de alcance. El buscador desaparece por debajo de 1.024 px (l.197). La tabla de 8 columnas no se reconvierte (solo `overflow-x-auto`, l.435). |
| 8 | Movimiento | 1 | `transition-none` en todo (cambios a saltos). El skeleton usa `animate-pulse` de 2 s en bucle sin respetar `prefers-reduced-motion` (l.707-715). |

**Total: 11 / 40**

**Tells encontrados (3):**
1. Mayúsculas con tracking: l.167, 168, 235 (h1 en mayúsculas), 575, 581 (`tracking-widest`), 613, 633; etiquetas en mayúsculas en l.367, 374, 381, 618, 626, 689, 717.
2. Puntos medios encadenados: l.236 («129 inscritos · 104 verificados · 81% completado»), 376, 383, 563, 717, 727, 728, 732 (la l.172 reproduce en parte el brief y no la cuento).
3. Borde lateral de color de más de 1 px: `border-l-2` en las nueve celdas de categoría (l.252, 264, 276, 287, 298, 309, 320, 331, 342) y `border-l-4 border-l-rfme-orange` en los dos bloques de verificación del detalle (l.615, 623).

No contado: `border-l-4` en la fila seleccionada (l.489), que es selección.

**Fortalezas**
1. Titular en forma de tarea («Faltan 25 por verificar») y una matriz de un pip por participante que hace comparables las categorías sin leer números.
2. Densidad de escritorio: filas de 32 px, con las verificaciones en dos columnas y las filas del Excel con su código de motivo al lado del resumen.

**Problemas prioritarios**
1. Los datos no son los del brief: horas, equipos, boxes y modelos cambiados en siete de las ocho filas, más hechos inventados en el detalle y en el pie. En una herramienta de comisarios esto invalida la pantalla.
2. Rota en los dos anchos: la cabecera mide 1.511 px en escritorio y 795 en móvil. Las acciones principales quedan cortadas, el buscador se oculta en móvil y la tabla no se reconvierte.
3. Accesibilidad e idioma: texto de 9-11 px, naranja a 3,33:1, foco eliminado en los checkboxes, nombres accesibles en inglés y jerga inglesa. Además, Tailwind por CDN (l.15), Material Symbols cargado dos veces (l.12-13) y comentarios de andamiaje («Shared Component TopNavBar», «defined in TopNavBar JSON», «THE SIGNATURE PIECE», l.161, 175, 227) que rozan la prohibición del brief de mencionar guías.

---

## T — `T.html` (Atkinson Hyperlegible + Saira Condensed, asfalto/hormigón + naranja + tinta violeta)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 4 | Datos del brief exactos en lista, detalle y Excel; «Mostrar los 121 restantes» cuadra (l.451). Copy de oficina: «Pídela al piloto y añádelo a mano», «Fila repetida: ya está en la lista. No hay que hacer nada» (l.295, 303), «Licencia provisional: falta la de su federación autonómica» (l.543). Supone cosas que el brief no da: licencia «Nacional» para casi todos (l.366…) y la regla «la pegatina del casco se pone al verificar el equipo» (l.479, 597). |
| 2 | Jerarquía (Operate) | 4 | La P3 se responde con tiras de una marca por participante que además filtran la lista (l.265-275). P1 y P2 se resuelven con columnas Moto/Equipo/Box y «Avisos», donde la oficina va en violeta con cuadro y la nota en gris (l.126-128), y con los chips «Falta verificar moto/equipo/Para oficina». Pero a 1440 el resumen y el Excel ocupan hasta ~880 px y la lista empieza bajo el pliegue de un portátil; la rejilla de categorías (máx. 820 px, l.69) deja un hueco a la derecha. |
| 3 | Tells de IA | 4 | Un tell: borde lateral de 4 px en el error (l.162). |
| 4 | Tipografía | 4 | Atkinson a 16 px de base con Saira Condensed para títulos y dorsales, `tabular-nums` global (l.29), sin mayúsculas, medida de 62ch (l.68). El cero barrado de Atkinson hace que «Superstock 1000» y «2026» se lean «1ØØØ», «2Ø26» en nombres de categoría, y la escala tiene ocho pasos (36/28/24/21/18/16/15/14). |
| 5 | Color | 5 | Un color por significado: naranja = pendiente, violeta = oficina, rojo = solo error, asfalto = acción y selección. Neutros pizarra entonados. Todo AA: grafito 6,28:1 sobre blanco y 5,45:1 sobre hormigón, tinta 7,27:1 y 6,31:1, «Pendiente» 4,75:1, bordes de control #7D868E a 3,70:1. Las tiras gris/naranja solo se distinguen por el tono (1,11:1), pero siempre llevan el texto «faltan N de M». |
| 6 | Estados y craft | 3 | Lista cableada: búsqueda por dorsal exacto o por nombre sin tildes (l.556-562), categoría, cuatro vistas, orden, vacío vivo que repite la búsqueda (l.572), detalle que se repinta y «Ver a Iker Valdemoro», que limpia filtros, selecciona y enfoca (l.635-641). Foco global de 3 px, botones y chips de 42-44 px. Faltan `:active`, cualquier estado `disabled` y cualquier transición. Categorías y enlaces se quedan en 36 px (l.70, 87). |
| 7 | Responsive | 5 | 390 px medido sin desbordar. Tabla en rejilla con áreas con sentido («d p p / d c c / d l b / d vm ve / d a a», l.183). Las filas sin avisos ocultan la celda vacía (l.196). Cabecera con buscador a todo el ancho y botones de icono de 44 px con `aria-label`. Enlace «Volver a la lista» y desplazamiento al detalle al elegir (l.609). |
| 8 | Movimiento | 3 | Sin transiciones (todo a saltos). El skeleton anima `background-position` 1,4 s en bucle (l.157, 161) y `reduce` lo apaga (l.168-170). El `scrollIntoView` consulta `prefers-reduced-motion` antes de suavizar (l.554-555). |

**Total: 32 / 40**

**Tells encontrados (1):**
1. Borde lateral de color de más de 1 px: `.error{border-left:4px solid var(--rojo)}` (l.162).

No contados: `inset 3px` en la categoría pulsada (l.72) e `inset 4px` en la fila seleccionada (l.112), que son selección.

**Fortalezas**
1. La tira de unidades («cada marca es un participante») es a la vez el gráfico de la P3 y el filtro de la lista: un toque en «Yamaha R7 Cup» deja solo esa categoría y la marca como pulsada.
2. Las filas del Excel terminan siempre en el siguiente paso concreto, y el duplicado lleva al participante ya importado con el foco puesto.

**Problemas prioritarios**
1. A 1440 la lista, que es la pantalla, empieza bajo el pliegue: el resumen ocupa demasiado alto para una herramienta que se abre varias veces al día.
2. Interacción sin acabado: ni `:active`, ni `disabled`, ni transiciones, y blancos de 36 px en categorías y enlaces.
3. Supuestos no pedidos (licencia «Nacional», regla de la pegatina del casco), «Importar Excel RFME» relegado a secundario y solo icono en móvil (l.255), y el cero barrado de Atkinson en nombres de categoría.

---

## R — `R.html` (mismo armazón que T, con capa de interacción)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 3 | Todo lo bueno de T (copy y datos del brief), pero añade un noveno participante que el brief no da, con cifras propias: Adrián Sopeña Gil, dorsal 11, Ducati Panigale V2, box 9, verificaciones a las 08:05 y 08:11 (l.402-411, l.571). Mantiene los supuestos de licencia «Nacional» y la regla de la pegatina (l.509, 633). |
| 2 | Jerarquía (Operate) | 4 | Igual que T, más contadores coherentes con el contexto («1 de 29 en Yamaha R7 Cup», «Mostrar los 28 restantes de Yamaha R7 Cup», l.600-607). Mismo problema: a 1440 la lista empieza a ~890 px. |
| 3 | Tells de IA | 4 | Un tell: borde lateral de 4 px en el error (l.167). |
| 4 | Tipografía | 4 | Como T, con `tabular-nums` solo donde hay cifras (l.40) y `text-wrap: balance/pretty` (l.38-39). Mantiene el cero barrado en nombres de categoría. |
| 5 | Color | 5 | Paleta y ratios idénticos a T (todo AA; un color por significado). |
| 6 | Estados y craft | 4 | Todo lo cableado de T, más hover solo con puntero fino (l.173-181), `:active` con escala (l.62, 104), categorías y enlaces de 40 px y todo a 44 px en móvil (l.76, 92, 223), y skeleton por `transform` (l.160-165). No hay ningún estado `disabled` en el fichero. |
| 7 | Responsive | 5 | 390 px medido sin desbordar; misma reconversión que T, con `volver` de 44 px (l.225). |
| 8 | Movimiento | 4 | Transiciones acotadas (color de fondo 100 ms, escala 150 ms con curva de salida propia, l.25, 61), barrido del skeleton por `transform`, `reduce` que quita la escala y cambia el barrido por un pulso de opacidad (l.183-187). `scrollIntoView` condicionado (l.588). Reproches: `ease` y no `ease-out` en los colores, bucle de 1,4 s en carga y el pulso infinito que sigue bajo `reduce`. |

**Total: 33 / 40**

**Tells encontrados (1):**
1. Borde lateral de color de más de 1 px: `.error{border-left:4px solid var(--rojo)}` (l.167).

**Fortalezas**
1. La capa de interacción está bien resuelta: hover condicionado a `(hover:hover) and (pointer:fine)`, `:active` táctil que se apaga con `reduce`, y áreas de pulsación de 40-44 px en todo lo que se toca.
2. Los contadores cuentan la verdad del filtro: «N de 129», «N de 29 en Yamaha R7 Cup», «Mostrar los X restantes de [categoría]».

**Problemas prioritarios**
1. Un participante inventado con horas y box que el brief no da: rompe la regla de usar los datos de la prueba.
2. La lista sigue bajo el pliegue a 1440 por el alto del resumen.
3. Sin estados `disabled`; el skeleton sigue animando en bucle (también con `reduce`) y el cero barrado aparece en «Superstock 1ØØØ».

---

## Q — `Q.html` (Tailwind por CDN, Chivo + Hanken Grotesk + JetBrains Mono, rojo + azul + paleta de categorías)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 0 | Vocabulario de carrera abundante, pero los datos contradicen el brief en casi todas las filas. Bruno, equipo a las 08:45 (l.522). Pau con «Ferrandis Motorsport» a las 07:50 (l.555, 560). Hugo con el box como equipo y una «Carpa #4» inventada (l.598-599). Lucía con «Arranz Talent Team» a las 08:10 (l.639, 644). Mateo con «Beon 250», «Piloto privado» y 08:00 (l.680-686). Théo con «French Tech Racing» a las 08:30 (l.723, 728). Nerea con «Olmedilla Competición» a las 08:50 (l.764, 774). Más cifras inventadas: cierre de verificaciones 11:00 (l.245), recuentos de filtro 14/18/5 (l.399-401), bastidor, toma de 380 V, transponder, jefe técnico (l.897-918), un peso de 168,2 kg sobre un límite de 168 kg marcado «PASS» (l.937), FP1 a las 10:15, temperatura del asfalto, nombres de comisarios (l.973, 1009-1014). El reloj muestra la hora real del equipo con «CET» (l.1304-1311). |
| 2 | Jerarquía (Operate) | 2 | La tabla densa cabe entera a 1440 y lleva Box y Moto/Equip. en columna. Pero las filas del Excel están plegadas tras «Ver detalles» (l.341), el orden no es por dorsal y no se puede ordenar, «Página 1 de 1» contradice «8 de 129» (l.854) y el panel de detalle conserva la verificación «2/2 SELLADAS» y «AUTORIZADO» de Iker para cualquier piloto (l.887-965 no se actualizan en `selectRider`, l.1182-1208). |
| 3 | Tells de IA | 0 | Seis tells (ver lista). |
| 4 | Tipografía | 1 | Tres voces, mayúsculas con tracking en cabeceras, botones, chips y etiquetas, texto de 9-11 px por todas partes (l.149, 168, 259, 346, 433) y `tabular-nums` solo en el reloj. |
| 5 | Color | 1 | Cada categoría tiene un color distinto (azul, cian, ámbar, violeta, naranja, verde azulado, índigo, rojo; l.256-304). El rojo primario hace de marca, acción, selección, error y Superbike. Placeholder #D2D9F4 a 1,40:1 (l.392). «Pendiente Boxes» en ámbar-600 a 3,19:1 (l.232). Botón blanco sobre esmeralda-600 a 3,77:1 con texto de 11 px (l.986). |
| 6 | Estados y craft | 1 | Vacío genérico, y error y skeleton juntos en una vista de demostración. Hay filtros y selección, pero la selección deja el detalle incoherente. Botones de 22-28 px y dorsales de 28 px. Botones de paginación con `cursor-not-allowed` sin `disabled` (l.859-861). Iconos con ligaduras en inglés como nombre accesible (l.193-197). Los selects de 32 px cortan su propio texto («Todos los Estados (129)» se ve truncado en vertical a 1440). |
| 7 | Responsive | 0 | **Desborda: `scrollWidth` 1.106 a 390.** Cabecera de altura fija sin reflujo (l.140), banner del Excel con el texto en columna estrecha, tabla de 10 columnas con scroll interno. A 1440 las píldoras de categoría ya no caben (cortadas en «SUPERSTO…»). |
| 8 | Movimiento | 0 | `transition-all` (l.185, 251, 312, 392), `duration-500` en las barras (l.235, 238), `animate-pulse` en el chip «PENDIENTE» de Bruno (l.514) y en el punto del reloj (l.166), `animate-ping` en «AUTORIZADO» (l.888) y ninguna consulta a `prefers-reduced-motion`. |

**Total: 5 / 40**

**Tells encontrados (6):**
1. Emojis como iconos: banderas 🇪🇸/🇫🇷 en cada fila y en el detalle (l.456, 500, 544, 588, 630, 672, 713, 755, 878).
2. Mayúsculas con tracking: l.148, 149, 168, 173-179, 185, 244, 251-307 (píldoras), 433 (cabeceras de tabla `label-caps`).
3. Puntos medios encadenados: l.148, 345, 358, 371 («FILA 46 · #52»), 1009, 1017; viñetas «•» en l.223, 855, 1018 (la l.156-157 reproduce el brief y no la cuento).
4. Sombra gris uniforme: `shadow-sm` en la cabecera, las secciones, el panel, los dorsales y los botones (l.139, 185, 208, 386, 450, 866).
5. Borde lateral de color de más de 1 px: `border-l-4 border-error` en el error (l.806).
6. Tarjetas idénticas anidadas: cuatro cajas iguales dentro de la tarjeta del detalle (l.894-919) y tres tarjetas dentro del banner del Excel (l.342-380).

**Fortalezas**
1. En escritorio, la tabla de ocho filas cabe entera con las columnas que pide el brief y las horas en chip verde.
2. Hay cableado básico: búsqueda y categoría filtran, y el vacío aparece solo al no haber coincidencias (l.1228-1232).

**Problemas prioritarios**
1. Datos falsos e incoherentes: siete de ocho filas contradicen el brief y el detalle declara «AUTORIZADO» a pilotos con verificaciones pendientes. Es lo más grave que puede tener esta herramienta.
2. Móvil roto (1.106 px) y cabecera de escritorio saturada, con el texto de marca y los selects cortados.
3. Repertorio completo de tells, animaciones decorativas en bucle sin `reduce`, contraste por debajo de AA en placeholder y secundarios. Además, Tailwind por CDN (l.15) y comentarios de andamiaje («Tailwind Theme Configuration Verbatim», l.16).

---

## M — `M.html` (mismo armazón que T y R, resumen compacto y estados completos)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 3 | Copy y datos del brief en las ocho filas, el detalle y el Excel, con la copy más económica del trío («Dorsal 7. Duplicada: ya está en la lista», l.334). Pero inventa cifras: los recuentos de los chips «Moto pendiente 11 · Equipo pendiente 17 · Para oficina 8» (l.371-373), que el brief no da, y el mismo noveno participante de R con box y horas propias (l.413-422, l.583). |
| 2 | Jerarquía (Operate) | 5 | Las tres preguntas en el primer pantallazo de 1440. Resumen compacto con título y frase en línea (l.78-84) y tiras a 28 px de alto. Lista con recuento y orden en la cabecera (l.340-351) a ~535 px. Chips de vista con recuento que responden a la P1 en agregado. Columna Avisos que distingue oficina (violeta) de nota (gris). Excel condensado con la acción en línea. Detalle al lado. Es la mejor relación densidad/legibilidad del conjunto. |
| 3 | Tells de IA | 5 | Ninguno. El error lleva un borde de 1 px alrededor (l.182) y no lateral. Sin mayúsculas, sin puntos medios, sin sombras ni cifras-héroe. |
| 4 | Tipografía | 4 | Como R (Atkinson 16 px + Saira Condensed, `tabular-nums` dirigido, `text-wrap`), con una escala algo más contenida en el resumen. Mantiene el cero barrado en «Superstock 1ØØØ» y «2Ø26». |
| 5 | Color | 5 | Paleta y ratios de T y R: un color por significado y todo AA. El estado `disabled` usa grafito sobre blanco (6,28:1), así que el texto sigue siendo legible. |
| 6 | Estados y craft | 4 | El modelo de estados más completo: `disabled` definido para botones y chips (l.68, 121-122) y mostrado en la demo de carga (l.558); `:active`; hover solo con puntero fino (l.189-197); zona de pulsación ampliada por `::after` en los enlaces en línea (l.98, 244); los recuentos de los chips se ocultan cuando el contexto de filtro los haría falsos (l.120, 618); vacío vivo y contadores exactos. Reproche: los botones de categoría miden 28 px de alto en escritorio (l.81). |
| 7 | Responsive | 5 | 390 px medido sin desbordar. Cabecera reordenada: buscador, «Añadir participante» a todo el ancho e «Importar» e «Imprimir PDF» en dos mitades con texto (l.237-242). Tabla en rejilla como T y R, chips de 44 px y «Volver a la lista». |
| 8 | Movimiento | 4 | Como R: transiciones de 100-150 ms, `:active` por escala con curva de salida, barrido por `transform`, `reduce` que quita la escala y pasa a pulso de opacidad (l.199-203), scroll condicionado. Mismos reproches: `ease` en el color (l.63), bucle de carga de 1,4 s y pulso infinito bajo `reduce` (l.201). |

**Total: 35 / 40**

**Tells encontrados:** ninguno de los listados en la rúbrica.
No contados: `inset 3px` en la categoría pulsada (l.82) e `inset 4px` en la fila seleccionada (l.129), que son selección.

**Fortalezas**
1. Es la que mejor encaja en un portátil de oficina de carrera: resumen, filtros con recuento, lista y detalle a la vista sin desplazarse, con las tres preguntas resueltas en ~550 px.
2. Los estados tienen las consecuencias resueltas: `disabled` visible y legible, recuentos que desaparecen cuando dejarían de ser ciertos y zonas de pulsación ampliadas sin engordar los enlaces.

**Problemas prioritarios**
1. Cifras inventadas en el sitio más visible: 11/17/8 en los chips de filtro y un participante extra con box y horas. El brief no da esos datos y el organizador tomaría decisiones con ellos.
2. Botones de categoría de 28 px de alto en escritorio y animación de carga en bucle que sigue (como pulso) con `reduce`.
3. Supuestos heredados (licencia «Nacional», regla de la pegatina del casco, l.520, 649) y el cero barrado de Atkinson en los nombres de categoría.

---

## K — `K.html` (Archivo con eje de anchura, barra superior en tinta, acento rojo)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 1 | Está pensada para un paddock (plazos de verificación, «rueda a las 15:10», transpondedores, «Avisar al equipo»), pero no es la prueba del brief. Es «ESBK 2026 · Ronda 6 · Jerez», del 9 al 11 de octubre (l.302, 335), con 24 participantes en tres categorías, verificaciones administrativa/técnica/transpondedor y no de moto y equipo, y ningún participante, cifra ni categoría del brief salvo Superbike, Supersport y Supersport 300. Todo dato es inventado. |
| 2 | Jerarquía (Operate) | 2 | Para su propio planteamiento la jerarquía es muy buena: banda de plazo con línea de tiempo «Ahora · 10:42» (l.343-356) y panel «Requieren atención» ordenado por la primera salida a pista (l.732-807). Frente al brief, la P1 no se puede responder (no hay box ni verificación de moto y equipo), la P2 sí (incidencias), y la P3 solo a medias (cabecera de grupo «9 inscritos · 4 listos»). Faltan las filas del Excel y el panel de detalle (las flechas enlazan a `#piloto-N`, que no existen, l.432). |
| 3 | Tells de IA | 2 | Tres tells (ver lista). |
| 4 | Tipografía | 4 | Archivo variable con anchura del 75 % en dorsales y cifras (l.111, 159) y del 87,5 % en títulos: voz propia. `tabular-nums` dirigido (l.103, 111, 136, 159, 204), sin mayúsculas, base de 15 px, medida de 36ch en el vacío. Los secundarios bajan a 12,5-13 px. |
| 5 | Color | 4 | Neutros cálidos (#F4F3EF, #15171C), acción en tinta, estados verde/ámbar/rojo/gris con fondo, todo el texto AA (muted 5,58:1 sobre el fondo, placeholder 4,94:1, warn 5,41:1, err 5,75:1). Reproches: el acento de marca #C4161C y el rojo de «Incidencia» #B42318 son el mismo tono (marca y alarma se confunden), y los bordes de los chips #C9C6BE quedan a 1,71:1. |
| 6 | Estados y craft | 2 | Vacío vivo con «Quitar filtros» que devuelve el foco al buscador (l.871-879). Confirmación de «Aviso enviado · 10:43» con `aria-disabled` y región `status` (l.890-899). Foco adaptado a la barra oscura (l.40). Pero no hay skeleton ni error de importación (el brief pide los tres estados). Sin `:active`, sin transiciones. Chips y botones pequeños de 32 px (l.90, 143). |
| 7 | Responsive | 5 | 390 px medido sin desbordar. Barra superior con menú plegable y `aria-expanded` (l.881-888), segmentado con abreviaturas SBK/SSP (l.395-397), KPI en 2×2, filas en rejilla con áreas (l.229-237), panel de atención debajo, todo legible. |
| 8 | Movimiento | 2 | Ninguna transición. La única animación es decorativa: el punto «Verificaciones abiertas» anima `box-shadow` en bucle de 2,4 s (l.55-56), aunque se apaga con `reduce` (l.57). No hay skeleton que animar. |

**Total: 22 / 40**

**Tells encontrados (3):**
1. Puntos medios encadenados: l.302, 353, 355, 370, 376, 382, 390, 421, 533, 633 (tres segmentos: «9 inscritos · 4 listos · Libres 1 a las 16:40»), 660, 742-801 («Administrativa · detectada a las 09:02 · rueda a las 15:10»), 897. Ninguno reproduce el brief.
2. Hero-metric: `.kpi--hero` negro con «11/24 Listos para pista» y tres KPI más de 38 px con etiqueta y barra (l.108-121, 360-383).
3. Borde lateral de color de más de 1 px: `.deadline{border-left:4px solid var(--ink)}` (l.94).

No contados: `border-left:3px` en la sección activa del menú móvil (l.248), que indica la sección actual; los cuatro KPI son tarjetas idénticas, pero no anidadas; «Roboto» en l.32 es solo el último recurso del `font-family`.

**Fortalezas**
1. Mejores patrones de operación del conjunto, aunque para otra pregunta: cuánto queda para el cierre, quién rueda primero y qué incidencia hay que resolver antes, con acción por fila y confirmación accesible.
2. Ejecución limpia en los dos anchos, con una tipografía que tiene carácter (Archivo estrecha en las placas de dorsal) y contraste AA en todo el texto.

**Problemas prioritarios**
1. No responde al brief: otra prueba, otras fechas, otros participantes y otras verificaciones, y faltan la importación del Excel, «Imprimir PDF», el box, el panel de detalle y las filas que no entraron.
2. Faltan dos de los tres estados exigidos (skeleton y error de importación).
3. Lenguaje de panel de KPI (tarjeta héroe negra más tres KPI), puntos medios como separador en cada metadato y acento rojo que se confunde con «Incidencia».

---

## Contraste WCAG de los pares que importan

| Variante | Par | Ratio | Resultado |
|---|---|---|---|
| Z | muted #5D6371 / blanco · / fondo #F4F3EF | 6,02 · 5,42 | AA |
| Z | pend #874A00 / #FFF2D4 · off #5A32A8 / #F1ECFB · ok #1B6B3A / #E4F2E8 | 6,28 · 7,38 · 5,66 | AA |
| Z | borde de input/chip #C8C5BC / blanco | 1,73 | < 3:1 (límite de control) |
| Z | barra verde #2E7D4F / ámbar #C27C0E | 1,49 | solo tono |
| W | grafito #59616A / blanco · / #EDEFF1 | 6,28 · 5,45 | AA |
| W | naranja #F25C05 como texto de 11 px / blanco | 3,33 | **falla AA** |
| W | asfalto #1E2329 / naranja #F25C05 (chip pendiente) | 4,75 | AA |
| T · R · M | grafito #59616A / blanco · / hormigón #EDEFF1 | 6,28 · 5,45 | AA |
| T · R · M | tinta #5B3CC4 / blanco · / hormigón | 7,27 · 6,31 | AA |
| T · R · M | asfalto / naranja («Pendiente») | 4,75 | AA |
| T · R · M | borde de control #7D868E / blanco | 3,70 | ≥ 3:1 |
| T · R · M | tira verificado #7D868E / pendiente #F25C05 | 1,11 | solo tono (con texto al lado) |
| Q | placeholder #D2D9F4 / blanco | 1,40 | **falla AA** |
| Q | ámbar-600 #D97706 / blanco (11 px) | 3,19 | **falla AA** |
| Q | blanco / esmeralda-600 #059669 (botón de 11 px) | 3,77 | **falla AA** |
| Q | on-surface-variant #5C403C / blanco | 9,32 | AA |
| K | muted #5B6170 / fondo #F4F3EF · placeholder #6B7080 / blanco | 5,58 · 4,94 | AA |
| K | warn #8A5A00 / #FFF4D6 · err #B42318 / #FDECEA | 5,41 · 5,75 | AA |
| K | borde de chip #C9C6BE / blanco · control #8F8C85 / blanco | 1,71 · 3,36 | chip < 3:1 · control ≥ 3:1 |

---

## Ranking final

| Puesto | Variante | Total | Veredicto |
|---|---|---|---|
| 1 | **M** | 35 / 40 | La más usable y mejor acabada: todo a la vista en un portátil y estados completos; pierde por cifras inventadas en los chips y un participante de más. |
| 2 | **R** | 33 / 40 | El mismo armazón con buena capa de interacción y movimiento; la lista queda bajo el pliegue y también inventa un participante. |
| 3 | **T** | 32 / 40 | Datos impecables y lista cableada; resumen demasiado alto y sin `:active`, `disabled` ni transiciones. |
| 4 | **Z** | 26 / 40 | La copy de producto mejor escrita y los mejores textos de estado, sobre una maqueta estática con eyebrows, cifra-héroe y tabla apretada. |
| 5 | **K** | 22 / 40 | Bien diseñada y bien construida, pero para otra prueba: no usa los datos del brief y le faltan el Excel, el detalle y dos estados. |
| 6 | **W** | 11 / 40 | Buena idea de matriz de pips, enterrada bajo datos cambiados, desbordamiento en los dos anchos y texto diminuto. |
| 7 | **Q** | 5 / 40 | Datos falsos, un detalle que autoriza a quien no debe, móvil roto y todo el repertorio de tells y animaciones. |

**Qué separa a las de arriba de las de abajo.** Las cuatro primeras cumplen los dos requisitos duros (ningún desbordamiento a 390 y los tres estados presentes con recuperación) y respetan los datos del brief salvo detalles. Entre ellas decide el acabado: M, R y T comparten armazón (misma paleta, mismas fuentes, mismo modelo de tabla y detalle) y se ordenan por compacidad del resumen y por la capa de interacción. Z escribe mejor que todas, pero no conecta nada y arrastra tres tells. K demuestra que una pantalla bien hecha puntúa poco si no es la pantalla pedida. W y Q comparten tres síntomas: datos que no son los del brief, una cabecera que no cabe ni en escritorio y texto de 9-11 px. Lo que distingue a arriba de abajo no es el estilo: es (a) usar los datos que da el brief sin rellenar huecos con cifras propias, (b) mirar el resultado a 390 y a 1440, y (c) un color por significado frente a una paleta por categoría.

## Patrones comunes

1. **Cifras inventadas como relleno.** Solo Z y T se limitan a los datos del brief (con supuestos menores: licencia «RFME» o «Nacional», estado de la pegatina del casco). R y M añaden un noveno participante con horas y box, y M además recuentos de filtro. W y Q cambian horas y equipos de las filas dadas. K sustituye la prueba entera.
2. **Ninguna dice qué es «verificado» salvo Z y T.** Z lo define con una nota (l.409) y T con su frase («tienen la moto y el equipo verificados», l.265). Las demás muestran 104/129 sin explicar que hacen falta las dos verificaciones.
3. **Skeleton solo en la vitrina** en todas las que lo tienen (Z, T, R, M en el bloque de estados; W y Q tras un conmutador de vista). Ninguna lo coloca en el sitio real de la lista. K no lo tiene.
4. **Brillo de carga en bucle.** Z y T por `background-position`, R y M por `transform` (y con `reduce` pasan a pulso de opacidad infinito), W y Q con `animate-pulse` sin `reduce`.
5. **Resumen antes que lista en móvil.** Z, T, R y M ponen las nueve categorías (700-1.000 px) antes de la primera fila. Para el uso ocasional en el paddock, un resumen plegable o la lista primero ahorraría la mitad del recorrido.
6. **La regla de los cascos se adivina.** El brief pide «cascos (pegatina y QR FIM)» pero solo da el dato del QR de Mateo. Z se inventa «Sin poner», T, R y M una regla («se pone al verificar el equipo»), W omite la sección y Q describe un casco inventado (HJC RPHA 1, adhesivo #042).
