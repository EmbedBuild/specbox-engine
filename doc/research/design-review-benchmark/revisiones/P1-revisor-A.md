# Revisión ciega P1: «Participantes de la prueba» (K, M, Q, R, T, W, Z)

Revisor A. Siete variantes de la misma pantalla de PaddockManager contra `P1-BRIEF.md` y `RUBRICA.md`, con la severidad de la revisión de calibración: un 5 solo cuando no he encontrado nada que reprochar en ese criterio. No sé qué proceso produjo cada variante y no lo he intentado averiguar.

## Método

- **Adaptación de la rúbrica.** Los criterios 1 y 2 de la rúbrica traen el ejemplo de otro producto. Los he aplicado a este: ¿la pantalla es de PaddockManager y del ESBK, con los datos del brief?, y ¿responde en segundos a las tres preguntas del director técnico: (1) quién falta por verificar moto o equipo y en qué box, (2) quién tiene algo que resolver en oficina, (3) cómo va cada categoría?
- **Datos.** He cotejado las 8 filas de ejemplo, las cifras globales y por categoría y las 3 filas del Excel con el brief. Una cifra o un dato que el brief no da, o que lo contradice, cuenta en el criterio 1. Añadir participantes inventados no es defecto, porque el brief pide «al menos» las 8 filas y los nombres son inventados por diseño.
- **Capturas.** He mirado las capturas reales a 1440 y a 390 px. Las de 390 las he recortado en tramos, en una carpeta aparte, para poder leerlas.
- **Criterio 7.** He usado `X-medidas.json`: hay scroll horizontal si `scrollWidth` es mayor que 390. Resultado: **K, M, R, T y Z miden 390** (en K sobresalen un `tr` y un `th` de 404 px, pero son la cabecera de tabla oculta y no generan scroll). **Q mide 1106 y W 795**, y además W mide 1511 a 1440.
- **Contraste.** Lo he calculado con la fórmula WCAG 2.x sobre los hex reales de cada fichero (tabla al final). Cito el ratio donde importa.
- **Tells.** He tomado `X-tells.txt` como pista y lo he comprobado en el código. El detector no ve nada en Q y W porque usan clases de Tailwind, y he encontrado sus tells con grep. En Z ha dado un falso positivo: `border-right:2px solid #fff` (l.107) es un separador blanco dentro de la barra, no un borde lateral de color. No cuento como tell la barra interior de selección de fila (`inset 3-4px`), igual que en la calibración. Para la nota: 0 tells = 5, 1 = 4, 2 = 3, 3 = 2, 4 = 1, 5 o más = 0.
- **Pila técnica.** No la puntúo. Q y W cargan Tailwind por CDN y Material Symbols; lo menciono solo en los problemas.

---

## K: `K.html` (Archivo, tinta + rojo, «Requieren atención»)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 1 | Es una pantalla de carrera creíble, pero de **otra prueba**: «ESBK 2026 · Ronda 6 · Jerez» (l.302), «Circuito de Jerez – Ángel Nieto · del 9 al 11 de octubre de 2026» (l.335) y «Ahora · 10:42» (l.353). Tiene 24 participantes en 3 categorías (l.394-397), con verificaciones administrativa, técnica y de transpondedor (l.427-429) en lugar de moto y equipo. No usa ni un dato del brief. Le faltan el box, «Importar Excel RFME» e «Imprimir PDF» (pone «Exportar lista», l.338), el panel de detalle y las filas del Excel. |
| 2 | Jerarquía (Operate) | 3 | Es la que mejor piensa en la operación: plazo con barra de tiempo (l.343-356), «Requieren atención» ordenado por primera salida a pista (l.732-807) y cabecera por categoría con «9 inscritos · 4 listos · Libres 1 a las 16:40» (l.421). Pero la pregunta «¿en qué box está?» no tiene respuesta (no hay box en ninguna parte), la vista por categoría cubre 3 de las 9 y las filas miden unos 57 px. |
| 3 | Tells de IA | 2 | Tres tells (ver lista). |
| 4 | Tipografía | 4 | Archivo con eje de anchura: 75 % en dorsales y cifras (l.111, l.159) y 87,5 % en títulos (l.83, l.126). Dorsal en «placa» con borde, como un número de carrera (l.159), `tabular-nums` donde hace falta y ninguna mayúscula. A cambio, once tamaños (12/12,5/13/14/15/16/18/22/27/34/38) y secundarios a 12,5-13 px. |
| 5 | Color | 4 | Neutros cálidos (#F4F3EF, #E4E2DC, l.12-19), tinta como acción y cuatro estados con función. Todo pasa AA: muted 6,20:1 sobre blanco y 5,58:1 sobre el fondo, placeholder 4,94:1, estados entre 5,41 y 6,62:1. Pegas: el punto ámbar se queda en 2,95:1 como elemento no textual (l.148), y el rojo de marca y pestaña activa (#C4161C, l.21) casi coincide con el de incidencia (#B42318, l.25). |
| 6 | Estados y craft | 2 | El vacío está cableado, con «Quitar filtros» que devuelve el foco al buscador (l.721-726, l.871-879). «Avisar al equipo» pasa a «Aviso enviado» con `aria-disabled` y región `role=status` (l.891-899). Tiene enlace de salto y foco de 3 px (l.39). **No hay skeleton ni error inline**, que el brief exige, ni `:active`. Chips y `btn--sm` miden 32 px (l.90, l.143) y `rowbtn` 36 px (l.178). |
| 7 | Responsive | 4 | 390 px sin scroll. La tabla pasa a tarjetas con `grid-template-areas` (l.229), la navegación a un menú con `aria-expanded` (l.244-249, l.881-888) y las categorías a siglas SBK/SSP (l.265-268). Pero la página mide 7.812 px y «Requieren atención», lo más accionable, queda detrás de las 24 filas. |
| 8 | Movimiento | 2 | No hay ninguna transición: hover y selección cambian de golpe. La única animación es un latido infinito de 2,4 s sobre `box-shadow` en el punto «Verificaciones abiertas» (l.55-56), decorativo y sobre una propiedad que no compone. Respeta `reduce` (l.57). |

**Total: 22 / 40**

**Tells encontrados (3):**
1. Hero-metric genérico: cuatro KPI en tarjeta con cifra de 38 px, etiqueta, barra y pie, uno de ellos en negro como «hero» (l.108-121, l.358-384).
2. Borde lateral de color > 1 px: `.deadline{… border-left:4px solid var(--ink)}` (l.94).
3. Puntos medios encadenados: l.302, l.335, l.353, l.355, l.370-382, l.390, l.421, l.533, l.633, l.660, l.744-780, l.815 y l.897.

No contados: el `border-left:3px` de la navegación móvil (l.248) es indicador de página actual. `Roboto` solo aparece como respaldo (l.32).

**Fortalezas**
1. El mejor razonamiento de operación del conjunto: cuenta atrás hasta el cierre de la verificación, incidencias con el motivo exacto y la hora a la que rueda cada piloto («rueda a las 15:10») y una acción por incidencia.
2. Accesibilidad cuidada: textos `.vh` que dan el estado completo de cada verificación al lector de pantalla (l.427), `caption`, `aria-live` en el recuento y foco gestionado al limpiar filtros.

**Problemas prioritarios**
1. Ignora el brief: otra prueba, otra fecha, otro modelo de verificación y 24 participantes en vez de 129. El organizador de Navarra I no puede usarla.
2. Faltan piezas obligatorias: box, panel de detalle (con cascos y país), filas del Excel, «Importar Excel RFME», «Imprimir PDF», skeleton y error de importación.
3. No hay transiciones y sí una animación infinita sobre `box-shadow`. En móvil, el bloque de incidencias aparece al final de una página de 7.800 px.

---

## M: `M.html` (Saira Condensed + Atkinson Hyperlegible, asfalto + naranja + violeta)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 4 | Todos los datos del brief son fieles: las 8 filas con horas, boxes y licencias, «Yamaha R7 Cup (Rookie)», los avisos separados en «para oficina» y «nota», «Entraron 129 de las 132 filas» y las 3 filas con su motivo. La copy es del producto: «Faltan 25 por verificar» (l.304), «Para oficina» (l.373) y «Ver a Iker Valdemoro» en la fila duplicada (l.334). Pega: **inventa los recuentos** de los chips, «Moto pendiente 11», «Equipo pendiente 17» y «Para oficina 8» (l.371-373), y una regla que el brief no da: «Pegatina: se pone al verificar el equipo» (l.520, l.649). |
| 2 | Jerarquía (Operate) | 5 | Las tres preguntas se responden en el primer pantallazo de 1440. La 3 con barras de unidades por categoría en escala común y «faltan 6 de 29» (l.308-316). La 1 y la 2 con filtros de un clic, «Moto pendiente», «Equipo pendiente» y «Para oficina», y la columna Box en negrita (l.134). Las filas del Excel quedan arriba a la derecha y el detalle es fijo. Pulsar una categoría filtra la lista (l.680-685). |
| 3 | Tells de IA | 5 | Ninguno: ni mayúsculas, ni puntos medios, ni sombras, ni bordes laterales. |
| 4 | Tipografía | 4 | Pareja deliberada: Saira Condensed para dorsales y títulos (l.25, l.135, l.154) y Atkinson Hyperlegible para leer en el paddock (l.26). `tabular-nums` dirigido (l.42), `text-wrap: balance/pretty` (l.40-41), cuerpo de 16 px y tabla de 15. Pega: el cero con barra de Atkinson se ve en «Superstock 1ØØØ», «2Ø26» y «Ø8:15» (captura de 1440), y la escala tiene pasos muy próximos (14/15/16). |
| 5 | Color | 4 | Cada color tiene una función: naranja = pendiente, violeta = oficina, asfalto = acción y selección, rojo solo para error. Pasa AA en todo: grafito 6,28:1 sobre blanco y 5,45:1 sobre hormigón, «Pendiente» 4,75:1, violeta 7,27:1, error 5,69:1. Pega: en la tira, la unidad gris y la naranja tienen la misma luminancia (1,11:1 entre sí, l.88-89) y solo se distinguen por el tono, aunque el texto «faltan N de M» lo compensa. Los neutros (#EDEFF1, #59616A) están apenas entonados. |
| 6 | Estados y craft | 4 | Está cableado de verdad: búsqueda por dorsal exacto o nombre, filtro, orden con `aria-sort` (l.628-635), selección que repinta el detalle (l.641-662), vacío con texto dinámico y recuperación (l.624), estilo `:disabled` (l.68, l.122), `:active` (l.64), hover solo con puntero fino (l.189-197) y controles de 42-44 px. Pegas: las filas de categoría miden 28 px en escritorio (l.81); skeleton y error solo están en la vitrina (l.537-573), sin cablear a «Importar Excel RFME»; y «Mostrar los 120 restantes» no tiene manejador (l.492). |
| 7 | Responsive | 5 | 390 px sin scroll. La cabecera se reordena: buscador, botón principal a todo el ancho e «Importar»/«Imprimir PDF» a medias (l.237-242). Las filas pasan a rejilla con etiquetas (l.216, l.231), el detalle va después de la lista con «Volver a la lista» y desplazamiento automático (l.661), y los controles miden 44 px (l.243). |
| 8 | Movimiento | 5 | Transiciones acotadas a 100-150 ms y sin `all` (l.63, l.111). El `:active` usa `scale` con curva de salida (l.27, l.64). El brillo del skeleton va por `transform` (l.176); con `reduce` se convierte en un pulso de opacidad y se quita la escala (l.199-203). El `scrollIntoView` consulta `prefers-reduced-motion` (l.599-600). |

**Total: 36 / 40**

**Tells encontrados:** ninguno de los listados.
Casos límite, no contados: chips con radio de píldora de 21 px (l.111); barra interior de selección de 3-4 px (l.82, l.129).

**Fortalezas**
1. La que mejor convierte las tres preguntas en controles: «Moto pendiente», «Equipo pendiente» y «Para oficina» son filtros de un clic. Las categorías son botones que filtran, y la fila duplicada del Excel lleva al participante y le da el foco (l.687-693).
2. Craft completo y sin ruido: hit-areas de 42-44 px, hover condicionado a `(hover:hover)`, `disabled` definido, `prefers-reduced-motion` respetado también en JavaScript, y estilos de impresión pensados para «Imprimir PDF» (l.257-262).

**Problemas prioritarios**
1. Recuentos inventados en los chips (11/17/8): el brief no los da y en una herramienta de carrera una cifra falsa destruye la confianza.
2. El error de importación y el skeleton solo existen en la vitrina, y «Importar Excel RFME» y «Mostrar los 120 restantes» no hacen nada.
3. El cero con barra de Atkinson se cuela en nombres de categoría y horas («Superstock 1ØØØ», «Ø8:15»). La tira gris y naranja tiene la misma luminancia, y las filas de categoría miden 28 px.

---

## Q: `Q.html` (Chivo + Hanken + JetBrains Mono, rojo + azul + arcoíris de categorías)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 1 | Toma del brief la prueba, 129/104/81 %, las categorías y las filas del Excel, pero **altera las 8 filas de ejemplo**. Equipos: «Ferrandis Motorsport» (l.555), «Arranz Talent Team» (l.639), «French Tech Racing» (l.723), «Olmedilla Competición» (l.764), y el equipo de Hugo es «Carpas Yamaha R7» con box «Carpa #4» (l.598-599). Horas: 07:50, 08:10, 08:00, 08:30, 08:45, 08:50 (l.522-774). Avisos inventados: «Citado comisarios 10:00» (l.528), «Aut. paterna OK» (l.655). Recuentos inventados: 14/18/5 (l.399-401). El reloj marca la hora real del sistema y no las 09:40 (l.1304-1311). Usa decimales con punto («80.6%», l.231), un «PASS» en inglés y un «Peso 168.2 kg (Límite: 168 kg)» marcado como conforme (l.937). |
| 2 | Jerarquía (Operate) | 2 | La tabla tiene columnas de Box, Moto y Equipo, pero con 10 columnas de 10-11 px y badges de seis colores. A 1440 las píldoras de categoría salen cortadas en «SUPERSTO…» (l.250, medidas). Las filas del Excel están plegadas tras «Ver detalles» (l.341). El filtro «Pendiente Moto» coge cualquier «PENDIENTE» y «Pendiente Equipación» no está implementado (l.1287-1289). No hay orden por dorsal. El reloj GPS, la temperatura de pista y los nombres de comisarios compiten por la atención. |
| 3 | Tells de IA | 0 | Seis tells (ver lista). |
| 4 | Tipografía | 1 | Tres familias, mucho texto a 9-11 px (`label-caps` de 10 px, l.114; `text-[9px]`, l.168 y l.259), 49 elementos en mayúsculas, motos en monoespaciada (l.466) y `tabular-nums` solo en algunos sitios. |
| 5 | Color | 1 | Paleta tipo Material con rojo primario, azul secundario y nueve tonos de categoría (l.256-304), más badges esmeralda, ámbar, rojo, cielo y violeta. Placeholder a 1,40:1 (l.392), «Pendiente Boxes» a 3,19:1 con 11 px (l.232), paginación a 1,40:1 (l.859-861) y bordes de input a 1,23:1. |
| 6 | Estados y craft | 1 | Skeleton (`animate-pulse`) y error con «Reintentar» existen, pero tras un conmutador en la cabecera (l.172-182). El vacío es genérico. **No hay ningún `aria-label`**: los botones de icono solo tienen `title` (l.193-198) y el buscador no tiene etiqueta (l.392). `outline-none` en input y selects. Áreas de 22-32 px. El detalle deja fija la ficha «2 / 2 SELLADAS · AUTORIZADO» aunque elijas a un piloto pendiente (l.887-963). |
| 7 | Responsive | 0 | **Desborda: `scrollWidth` 1106 a 390 px.** La cabecera no se adapta, la tabla de 10 columnas tampoco, y el pie se parte palabra a palabra. A 1440 el texto de marca se corta por arriba y las categorías quedan ocultas. |
| 8 | Movimiento | 0 | `transition-all` en 15 elementos (l.185, l.235, l.251-303, l.312, l.392). `duration-500` en la barra (l.235). `animate-pulse` infinito sobre un badge «PENDIENTE» (l.514), `animate-ping` sobre «AUTORIZADO» (l.888) y un punto latiendo (l.166). Ninguna regla para `prefers-reduced-motion`. |

**Total: 6 / 40**

**Tells encontrados (6):**
1. Mayúsculas con tracking: l.148, l.149, l.168, l.173-180, l.230, l.244, l.251-303 (píldoras), l.433 (`th`), l.895, l.900, l.908, l.913, l.924 y l.968.
2. Emojis como iconos: banderas 🇪🇸/🇫🇷 en cada fila y en el detalle (l.456, l.500, l.544, l.588, l.629, l.671, l.713, l.754, l.878).
3. Puntos medios encadenados: l.6, l.148, l.157, l.345, l.358, l.371, l.1009, l.1017, más «•» en l.223, l.855 y l.1018.
4. Sombra gris uniforme: `shadow-sm` en cabecera, secciones, tabla y aside (l.139, l.208, l.386, l.866) y en botones (l.185, l.450).
5. Borde lateral de color > 1 px: banner de error `border-l-4 border-error` (l.806).
6. Tarjetas idénticas anidadas: cuatro mini-tarjetas en el detalle dentro del aside (l.894-919), tres tarjetas del Excel dentro del banner (l.342-380) y pasos de la checklist en recuadro dentro de recuadro (l.932-963).

**Fortalezas**
1. Pone el box en una columna propia junto a las dos verificaciones, lo que en principio responde a «quién falta y dónde está».
2. Usa vocabulario del paddock (comisarios, báscula, transpondedor, sellado) y ofrece acciones concretas para cada fila del Excel («Reasignar a Supersport», «Eliminar fila 131»).

**Problemas prioritarios**
1. Datos del brief alterados en casi todas las filas, y una ficha de detalle que no cambia al seleccionar (siempre «AUTORIZADO»). Muestra a pilotos pendientes como sellados.
2. Inservible en móvil (1106 px a 390) y escasa en escritorio: categorías cortadas, Excel plegado, texto de 9-11 px y contrastes de 1,2-3,2:1.
3. Accesibilidad y movimiento sin tratar: cero `aria-label`, buscador sin etiqueta, `transition-all`, animaciones infinitas sobre estados y nada para `reduce`. Carga Tailwind y Material Symbols por CDN, que el brief no permite, y deja comentarios internos en el HTML (l.7, l.11, l.14, l.16).

---

## R: `R.html` (Saira Condensed + Atkinson Hyperlegible, asfalto + naranja + violeta, más aire)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 5 | Datos del brief fieles y sin cifras inventadas: los chips no llevan recuentos (l.353-356). Copy instructiva en el Excel: «Elige la categoría actual y añádelo a mano», «Pídela al piloto», «No hay que hacer nada» (l.307, l.315, l.323). La leyenda de la tira cabe en una frase: «Cada marca es un participante: en gris, verificado; en naranja, pendiente» (l.285). El participante añadido (#11, l.402-411) cabe en el «al menos 8». |
| 2 | Jerarquía (Operate) | 4 | La misma estructura que responde a las tres preguntas, pero a 1440 el bloque de categorías y el del Excel ocupan el primer pantallazo. La lista empieza hacia los 1.130 px, «Orden» salta a una segunda línea (l.359-364) y la cifra «faltan N de M» queda lejos de su barra (columna de 116 px tras un `1fr`, l.76). Sin recuentos en los chips, para saber cuántas motos faltan hay que pulsar. |
| 3 | Tells de IA | 4 | Un tell: borde lateral de 4 px en el error (l.167). |
| 4 | Tipografía | 4 | La misma pareja y el mismo tratamiento que M (l.23-24, l.38-40), con el cero con barra en «Superstock 1ØØØ» y «2Ø26». |
| 5 | Color | 4 | Los mismos tokens y ratios que M: grafito 6,28 y 5,45:1, «Pendiente» 4,75:1, violeta 7,27:1. La misma pega en la tira gris y naranja (1,11:1). |
| 6 | Estados y craft | 4 | Búsqueda, filtros, orden, selección y la fila duplicada están cableados (l.591-677). Las filas de categoría (l.76) y los enlaces del Excel (l.92) suben a 40 px, `:active` y hover van con puntero fino (l.62, l.173-181). Pegas: no hay estilo `disabled` en ningún sitio, skeleton y error solo están en la vitrina, y «Importar Excel RFME» y «Mostrar los 120 restantes» no hacen nada (l.481). |
| 7 | Responsive | 5 | 390 px sin scroll. «Importar» e «Imprimir PDF» pasan a botones de icono de 44 px con `aria-label` (l.226-227, l.275-276), las filas a rejilla etiquetada (l.200, l.215), y el detalle lleva «Volver a la lista» y desplazamiento automático que respeta `reduce` (l.645). |
| 8 | Movimiento | 5 | Igual que M: 100-150 ms sin `all` (l.61, l.103), escala con curva de salida (l.25, l.62), brillo por `transform` (l.161), `reduce` con pulso de opacidad (l.183-187) y `scrollIntoView` condicionado (l.587-588). |

**Total: 35 / 40**

**Tells encontrados (1):**
1. Borde lateral de color > 1 px: `.error{… border-left:4px solid var(--rojo); border-radius:0 6px 6px 0}` (l.167).

**Fortalezas**
1. La copy más útil para la oficina: cada fila rechazada dice qué hacer, y la tira se explica en la propia frase de estado.
2. Cumple el brief sin inventar cifras y con todo lo que se toca a 40-44 px, también en escritorio.

**Problemas prioritarios**
1. En escritorio el primer pantallazo se lo comen el resumen y el Excel, y la lista empieza por debajo del pliegue.
2. Sin estilo `disabled`, y con los estados de carga y error solo como vitrina; ni la importación ni «Mostrar los 120 restantes» están cableadas.
3. El cero con barra en categorías y horas, y la tira gris y naranja sin diferencia de luminancia.

---

## T: `T.html` (Saira Condensed + Atkinson Hyperlegible, misma familia, sin transiciones)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 5 | Exactamente las 8 filas del brief, «8 de 129» (l.313) y «Mostrar los 121 restantes» (l.451), coherentes entre sí. No inventa cifras y usa la misma copy instructiva del Excel que R (l.287, l.295, l.303). |
| 2 | Jerarquía (Operate) | 4 | La misma estructura y los mismos reparos que R: lista por debajo del pliegue a 1440, «Orden» en otra línea (l.339-344) y cifras separadas de su barra (l.70), sin recuentos en los chips. |
| 3 | Tells de IA | 4 | Un tell: borde lateral de 4 px en el error, aquí con radio en las cuatro esquinas, de modo que el borde se curva (l.162). |
| 4 | Tipografía | 4 | La misma pareja, con `tabular-nums` global en `body` (l.29). Mismo cero con barra. |
| 5 | Color | 4 | Los mismos tokens y ratios que M y R. Misma pega en la tira (1,11:1). |
| 6 | Estados y craft | 3 | Filtros, orden, selección y la fila duplicada cableados (l.558-641). Pero no hay `:active` ni `disabled`, el hover no está condicionado al puntero (l.56, l.71, l.110) y se queda pegado en táctil, y las filas de categoría y los enlaces del Excel miden 36 px (l.70, l.87). Estados solo en vitrina; importación y «Mostrar los 121 restantes» sin manejador. |
| 7 | Responsive | 5 | 390 px sin scroll. Botones de icono de 44 px con `aria-label` (l.206-207, l.255-256), filas en rejilla etiquetada (l.183, l.197) y «Volver a la lista» (l.177). |
| 8 | Movimiento | 3 | No hay ninguna transición: hover y selección saltan. El brillo del skeleton anima `background-position` en bucle de 1,4 s lineal (l.157, l.161). A favor: `reduce` lo apaga (l.168-170) y el desplazamiento automático lo respeta (l.554-555). |

**Total: 32 / 40**

**Tells encontrados (1):**
1. Borde lateral de color > 1 px: `.error{… border-left:4px solid var(--rojo); border-radius:6px}` (l.162).

**Fortalezas**
1. La más fiel al brief de todas: ni un dato inventado, con el recuento de restantes cuadrado.
2. Conserva la estructura que mejor responde a las tres preguntas, con una lista funcional y una conversión a móvil limpia.

**Problemas prioritarios**
1. Acabado de interacción pobre: sin transiciones, sin `:active`, sin `disabled` y con hover pegajoso en táctil.
2. Objetivos de 36 px en las filas de categoría y en los enlaces del Excel, justo los que se pulsan en el paddock.
3. La lista queda por debajo del pliegue en escritorio, y los estados de carga y error no se pueden provocar.

---

## W: `W.html` (Barlow Condensed + Atkinson Next + Saira, asfalto + naranja + violeta, cuadrícula de puntos)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 1 | Toma del brief las categorías, el 81 % y las filas del Excel, pero **altera las filas de ejemplo**. Equipos: «Team Ferrandis» (l.479), «Arranz Motorsport» (l.509), «French Junior Team» (l.537); Hugo con equipo «Carpas Yamaha R7» y box «Carpas Paddock» (l.493-495). Horas: 09:10, 08:45, 07:55/08:05, 08:30, 09:00, 08:50 (l.472-557). Motos: «Beon PreMoto3» (l.524), «Yamaha YZF-R7 (689 cc)» (l.596). Licencia inventada (l.608) y «Tutor OK» (l.515). Pierde los avisos de Bruno y del dorsal 21. Hora «11:42 CEST» (l.172), IP, MyLaps y «14 comisarios» (l.727-732). Anglicismos: «Pendiente Scrutineering» (l.245), «Import Aborted» (l.689). |
| 2 | Jerarquía (Operate) | 3 | La tabla más densa (filas de 32 px) y la cuadrícula de puntos por categoría (l.250-352) responden bien a las preguntas 1 y 3, con «Moto pendiente» y «Equip. pendiente» en naranja junto al box. Pero los avisos de oficina se mezclan como badges violeta en las columnas de verificación, falta la columna de licencia, filtros y orden no hacen nada («Orden: Registro oficial RFME», l.563) y a 1440 el texto de la prueba se monta sobre el `h1` (captura). |
| 3 | Tells de IA | 1 | Cuatro tells (ver lista). |
| 4 | Tipografía | 2 | Cuatro familias (l.10, l.94-103), `h1` en mayúsculas (l.235), mucho texto a 10-11 px (l.369, l.376, l.591-608, l.620) y cabeceras de tabla en minúscula («dorsal», «piloto», l.439-446). |
| 5 | Color | 3 | Paleta coherente: asfalto, hormigón, naranja = pendiente, violeta = oficina, rojo = error. Pasa AA en lo principal: grafito 6,28 y 5,45:1, badge naranja 4,75:1, violeta 7,27:1. Pero el naranja como texto se queda en 3,33:1 con 11 px («29 (6 pend.)», l.255-345), el violeta marca también información que no es de oficina («Menor (14 años) - Tutor OK», l.515) y los grises de interfaz son puros (#eeeeee, #e2e2e2, l.46, l.39). |
| 6 | Estados y craft | 1 | Vacío, skeleton (`animate-pulse`) y error con reintento solo se ven desde un conmutador con corchetes en la cabecera («[Vista Principal (Cargada)]», l.186-194). Ni la búsqueda, ni los filtros, ni la selección tienen JavaScript. Las casillas miden 14 px y llevan `focus:ring-0` (l.419, l.423), así que no tienen foco visible. El buscador lleva `outline-none` (l.201), no tiene etiqueta y desaparece por debajo de `lg`. Cero `aria-label`, y áreas de 22-30 px. |
| 7 | Responsive | 0 | **Desborda: `scrollWidth` 795 a 390 px**, con `overflow-x-hidden` en `body` (l.159): Imprimir, Importar y Añadir quedan recortados e inalcanzables. La tabla no se reconvierte (scroll interno que esconde box y verificaciones), y no hay buscador. A 1440 también desborda (1511): «Añadir participante» sale cortado. |
| 8 | Movimiento | 2 | `transition-none` en todo (l.186, l.204, l.211…), así que no hay movimiento decorativo, pero tampoco transición alguna. Skeleton con `animate-pulse` de opacidad (l.707-715), sin regla para `prefers-reduced-motion`. |

**Total: 13 / 40**

**Tells encontrados (4):**
1. Mayúsculas con tracking: l.167, l.168, l.235, l.575, l.581, l.613, l.633 y l.689.
2. Puntos medios encadenados: l.6, l.172, l.236, l.376, l.383, l.563, l.577, l.717, l.727-728 y l.732.
3. Borde lateral de color > 1 px: `border-l-2` en las nueve celdas de categoría (l.252-342) y `border-l-4 border-l-rfme-orange` en los estados de verificación del detalle (l.615, l.623).
4. Tarjetas idénticas anidadas: filas del Excel enmarcadas dentro de una tarjeta enmarcada (l.364-384), y recuadros dentro del aside (l.589, l.615, l.623, l.641).

**Fortalezas**
1. La lista más densa y escaneable en escritorio: filas de 32 px, box en monoespaciada y un único naranja para «pendiente».
2. La cuadrícula de puntos por categoría, un punto por participante, se lee de un vistazo y compara categorías en escala común.

**Problemas prioritarios**
1. Datos del brief cambiados (equipos, horas, motos, box de Hugo), sin columna de licencia y con hora y metadatos inventados.
2. Móvil roto: acciones recortadas por `overflow-x: hidden`, sin buscador y con la tabla sin adaptar. Además desborda a 1440 y la cabecera se solapa con el título.
3. Es una maqueta: filtros, búsqueda y selección no funcionan, el foco de las casillas es invisible y no hay `aria-label`. Carga Tailwind y Material Symbols por CDN, que el brief no permite, y deja comentarios internos en el HTML (l.7, l.161, l.175, l.184).

---

## Z: `Z.html` (IBM Plex Sans + Plex Mono + Barlow Condensed, papel cálido + ámbar + violeta)

| # | Criterio | Nota | Justificación |
|---|---|---|---|
| 1 | Especificidad | 4 | Datos fieles: las 8 filas con «8 may 08:15» y los boxes. Porcentajes por categoría bien calculados (23/29 = 79 %, l.413-421) y «Sin verificar 25» (l.442). Copy del producto: «Aún no ha pasado. Está en Carpas Paddock» (l.620), «Un participante cuenta como verificado cuando ha pasado la verificación de moto y la de equipo» (l.409), «El Excel de la RFME no trae equipo para este piloto» (l.658). Pero el armazón es de panel genérico: KPI gigante del 81 %, tres cifras, rejilla 3×3 de tarjetas y antetítulos. |
| 2 | Jerarquía (Operate) | 4 | Responde a las tres preguntas: categorías con insignia «N pendientes», columnas agrupadas bajo «Verificación técnica» con el box al lado (l.487) y una columna «Oficina» con chips por tipo. El detalle abre con chips de resumen (l.601-604). Pero el bloque del 81 % ocupa sitio, los chips de oficina se parten en 3-4 líneas, «Provisional» se rompe en «Provision/al» por la columna del 9 % (l.154, l.530) y el Excel queda debajo de la lista. |
| 3 | Tells de IA | 2 | Tres tells (ver lista). |
| 4 | Tipografía | 3 | Trío deliberado: Plex Sans para leer, Plex Mono para box y códigos de país, Barlow Condensed para placas y cifras (l.38-40), con `tabular-nums` global (l.45). Pero los antetítulos y los `h3` van en mayúsculas con tracking (l.72, l.96, l.236), el cuerpo es de 14 px con secundarios a 11-12,5, hay más de doce tamaños y una palabra partida en la tabla. |
| 5 | Color | 4 | Neutros cálidos (#F4F3EF, #E3E1DA) y un tono por función: ámbar = pendiente, violeta = oficina, verde = verificado, rojo = error, azul = foco y selección. Pasa AA en todos los textos: muted entre 5,42 y 6,02:1, pendiente 6,28:1, oficina 7,38:1, ok 5,66:1, error 6,57:1. Pegas: los bordes de buscador, selects y chips (#C8C5BC) se quedan en 1,73:1, por debajo del 3:1 no textual (l.81, l.141, l.151), y en la barra el verde y el ámbar están a 1,49:1 (lo salva el separador blanco, l.107). |
| 6 | Estados y craft | 2 | **No hay `<script>`.** Filtros, orden, enlaces de categoría, navegación del detalle y «Mostrar 20 más» son inertes (l.439-470, l.588-591, l.580). A favor, los estados de vitrina mejor escritos: el vacío muestra los filtros aplicados y ofrece dos salidas (l.713-725), y el error dice «No se ha cambiado nada» y «La lista sigue con los 129 participantes» (l.748, l.755). También foco de 3 px y enlace de salto. Pero no hay `:active` ni `disabled`, y chips, selects y botones pequeños miden 32 px en escritorio (l.89, l.92, l.141, l.151). |
| 7 | Responsive | 4 | 390 px sin scroll. Imprimir y Añadir pasan a iconos de 44 px con `aria-label` (l.289-290, l.390-391), la tabla a rejilla etiquetada (l.300-315) y los selects a dos columnas de 40 px (l.298-299). Pero las nueve tarjetas de categoría se apilan de una en una, la página mide 7.341 px y el detalle no tiene vuelta a la lista. |
| 8 | Movimiento | 2 | Ninguna transición (los hover saltan). La única animación es el brillo del skeleton por `background-position`, en bucle de 1,4 s lineal (l.248, l.253), y `reduce` solo lo apaga (l.262). |

**Total: 25 / 40**

**Tells encontrados (3):**
1. Antetítulos en mayúsculas con tracking: `.eyebrow` (l.72, usado en l.376 y l.587), `.h3` (l.96, usado en l.612, l.626, l.639 y l.650) y `.state-cap` (l.236).
2. Hero-metric genérico: «81 %» a 64 px con «verificados» y tres cifras de 28 px debajo (l.104, l.111, l.402-408).
3. Puntos medios encadenados: l.6, l.376, l.381, l.413-421, l.598, l.677, l.685 y l.693.

No contados: `border-right:2px solid #fff` de la barra (l.107, falso positivo del detector) y el `linear-gradient` suave de la cabecera del detalle (l.191), que no es morado ni azul.

**Fortalezas**
1. La lectura de estado más clara por fila: columnas agrupadas «Verificación técnica: Moto / Equipo», una columna «Oficina» con chips que distinguen «resolver» de «información», y un detalle que dice dónde encontrar al piloto.
2. Los estados mejor redactados: el vacío enseña qué filtros causan el cero y el error explica qué no ha cambiado.

**Problemas prioritarios**
1. Es una maqueta estática: sin JavaScript no se puede buscar, filtrar, ordenar ni seleccionar, en una pantalla cuyo valor es precisamente ese.
2. El armazón de panel genérico (KPI gigante, tarjetas, antetítulos en mayúsculas) suma tres tells y le quita sitio a la lista.
3. Controles de 32 px y con bordes de 1,73:1 en escritorio, palabra partida en la columna de licencia y chips de oficina que alargan las filas.

---

## Contraste WCAG calculado (pares que importan)

| Variante | Par | Ratio | Veredicto |
|---|---|---|---|
| K | muted #5B6170 / blanco · / fondo #F4F3EF | 6,20 · 5,58 | AA |
| K | placeholder #6B7080 / blanco | 4,94 | AA |
| K | ámbar #8A5A00 / #FFF4D6 · error #B42318 / #FDECEA | 5,41 · 5,75 | AA |
| K | etiqueta #B3B8C2 / tinta #15171C | 9,01 | AA |
| K | punto ámbar #C98A00 / blanco (no texto) | 2,95 | < 3:1 |
| M/R/T | grafito #59616A / blanco · / hormigón #EDEFF1 | 6,28 · 5,45 | AA |
| M/R/T | «Pendiente» #1E2329 / naranja #F25C05 | 4,75 | AA |
| M/R/T | violeta #5B3CC4 / blanco · / hormigón | 7,27 · 6,31 | AA |
| M/R/T | borde de control #7D868E / blanco (no texto) | 3,70 | ≥ 3:1 |
| M/R/T | unidad gris #7D868E / unidad naranja #F25C05 | 1,11 | solo tono |
| Q | placeholder #d2d9f4 / blanco | 1,40 | falla |
| Q | ámbar-600 #d97706 / blanco (11 px) | 3,19 | falla |
| Q | borde de input #e2e7ff / blanco (no texto) | 1,23 | falla |
| Q | badges (ámbar-900, esmeralda-800, error) | 8,15 · 6,78 · 5,91 | AA |
| W | grafito / blanco · / hormigón | 6,28 · 5,45 | AA |
| W | naranja #F25C05 como texto / blanco (11 px) | 3,33 | falla |
| W | blanco / violeta · asfalto / naranja | 7,27 · 4,75 | AA |
| Z | muted #5D6371 / blanco · / fondo #F4F3EF | 6,02 · 5,42 | AA |
| Z | pendiente #874A00 / #FFF2D4 · oficina #5A32A8 / #F1ECFB | 6,28 · 7,38 | AA |
| Z | borde de input #C8C5BC / blanco (no texto) | 1,73 | falla |
| Z | barra verde #2E7D4F / ámbar #C27C0E | 1,49 | solo tono (con separador) |

---

## Ranking final

| Puesto | Variante | Total | Veredicto |
|---|---|---|---|
| 1 | **M** | 36 / 40 | La más completa: responde a las tres preguntas con filtros de un clic, sin tells y con el mejor acabado; lastran los recuentos inventados y los estados de vitrina. |
| 2 | **R** | 35 / 40 | M sin cifras inventadas y con objetivos de 40 px, pero con la lista por debajo del pliegue, sin `disabled` y con un borde lateral en el error. |
| 3 | **T** | 32 / 40 | La más fiel a los datos; pierde en acabado: sin transiciones, `:active` ni `disabled`, y con objetivos de 36 px. |
| 4 | **Z** | 25 / 40 | La mejor lectura por fila y los estados mejor escritos, en una maqueta sin JavaScript y con armazón de panel genérico. |
| 5 | **K** | 22 / 40 | Excelente pensamiento de operación y buena construcción, pero para otra prueba: no usa ni un dato del brief y le faltan box, detalle, Excel, carga y error. |
| 6 | **W** | 13 / 40 | Tabla densa y cuadrícula de puntos con idea, pero datos alterados, maqueta sin lógica y móvil y escritorio desbordados. |
| 7 | **Q** | 6 / 40 | Datos alterados, seis tells, contraste roto, `transition-all` y 1106 px a 390: no se puede usar. |

**Qué separa a las de arriba.** M, R y T comparten estructura y tokens, y son las únicas que cumplen a la vez los datos del brief, los 390 px sin scroll y la lógica de búsqueda, filtro y orden. Entre ellas decide el acabado: transiciones, `disabled`, tamaño de objetivo y un tell. Z y K son buenas ideas incompletas: Z no tiene interacción y K no hizo el brief. W y Q fallan en lo básico: alteran los datos de ejemplo, que en una herramienta de carrera equivale a mostrar pilotos verificados que no lo están, y desbordan en móvil.

## Patrones comunes

1. **Ninguna cablea el error de importación al botón «Importar Excel RFME»**, y ninguna muestra el skeleton en el sitio real de la lista. M, R, T y Z lo ponen en una vitrina al pie; Q y W tras un conmutador en la cabecera; K no lo tiene.
2. **«¿En qué box?» se responde solo con una columna.** Nadie agrupa ni filtra por zona (boxes frente a carpas), que es como se recorre el paddock. Q tiene un filtro de ubicación, pero no funciona.
3. **Licencias deducidas.** El brief no da el tipo de licencia salvo para Pau y Théo. M, R y T ponen «Nacional» y Z pone «RFME»; es razonable, pero es un dato supuesto.
4. **Tiras de progreso que separan verificado y pendiente solo por tono**: 1,11:1 de luminancia entre gris y naranja en M, R y T (y en W, que usa la misma paleta), y 1,49:1 en Z. Lo compensa el texto con la cifra.
5. **Objetivos por debajo de 40 px** en K (32-36), T (36), Z (32), Q y W (22-30). Solo M y R llegan a 40-44 px en todo.
