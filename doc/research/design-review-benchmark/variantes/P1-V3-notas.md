# P1 «Participantes de la prueba»: segunda pasada (V3, pulido)

Alcance: todo `index.html` (tipografía, superficies, movimiento, iconos y rendimiento) más el fallo de
Supersport. La dirección visual no cambia: misma paleta, tipos, layout y parrilla. Sin navegador ni
capturas: lo comprobado es la sintaxis del script (`node --check`) y una revisión del CSS por
especificidad y orden de cascada.

## Cambios

| # | Antes | Después | Por qué |
|---|---|---|---|
| 1 | Filtrar por Supersport dejaba la lista vacía aunque el estado decía 9; el recuento con filtro decía «N coinciden» sin relación con los totales | Fila de ejemplo de Supersport (dorsal 11, verificada, sin avisos). Con solo categoría: «1 de 9 en Supersport» y «Mostrar los 8 restantes de Supersport», con totales leídos de `data-total` de la parrilla | Ninguna categoría da ya una lista vacía falsa, y la lista y la parrilla cuentan lo mismo |
| 2 | Texto con el suavizado por defecto | `-webkit-font-smoothing: antialiased` y `-moz-osx-font-smoothing: grayscale` en `html` | En macOS el texto se veía más grueso de lo previsto, sobre todo la condensada en negrita |
| 3 | Títulos y párrafos con corte por defecto | `text-wrap: balance` en h1-h3 y títulos de estado; `pretty` en p, li, dd y figcaption | Evita palabras sueltas en la última línea («…restantes», motivos del Excel) |
| 4 | `tabular-nums` en todo el `body`, incluido el dorsal grande de la ficha | Solo en tabla, recuentos, parrilla, ficha y hora de cabecera; el dorsal de la placa vuelve a cifras proporcionales | Cifras de ancho fijo donde hay columnas o números que cambian; el número grande es de exhibición y se ve mejor proporcional |
| 5 | Línea bajo la cabecera fija de la tabla con `border-bottom` en `border-collapse` | `box-shadow: inset 0 -2px 0` y padding uniforme | Con bordes colapsados el borde no acompaña a la celda fija y la línea desaparecía al hacer scroll |
| 6 | Barra de acento (categoría pulsada y error de importación) sobre una caja con las cuatro esquinas redondeadas | Radio solo en el lado derecho (`0 4px 4px 0`, `0 6px 6px 0`) | La barra se curvaba en las esquinas y parecía una cuña, no una línea recta |
| 7 | Botones con icono y texto con 14 px a ambos lados | 12 px en el lado del icono y 14 px en el del texto (`.con-icono`) | El icono pesa visualmente más que el aire; con el mismo padding el botón parecía desplazado |
| 8 | Grosores de icono mezclados: check 2,4 (≈2,25 px), más 2,2, resto 2 | Todo el juego a ≈1,6 px renderizados: check 1,75, lupa 1,8, error 1,6, botones 2 | Un único grosor por juego, a medio camino entre el texto regular de las celdas y el negrita de los botones |
| 9 | El icono de imprimir llevaba `fill="#fff"` fijo en la hoja | Redibujado solo con trazo y `currentColor`; el cuerpo deja hueco por donde sale la hoja | Al pasar el ratón el botón se vuelve gris y aparecía un rectángulo blanco dentro del icono |
| 10 | Sin respuesta al pulsar | `scale: .96` en `:active` para botones y filtros, 150 ms con curva de salida propia (`--salida`); se desactiva con reduced motion | Confirma la pulsación al instante, también en el móvil del paddock |
| 11 | Cambios de color en hover instantáneos y bruscos | `background-color` / `color` a 100 ms `ease` en botones, filtros, categorías, enlaces y filas | Interacción frecuente: transición mínima de color, nunca movimiento |
| 12 | Hover aplicado en cualquier dispositivo | Hover dentro de `@media (hover: hover) and (pointer: fine)`; la fila seleccionada gana siempre al hover | En táctil el hover se quedaba pegado tras tocar una fila y tapaba el estado de selección |
| 13 | Áreas de pulsación de 36 px (enlaces del Excel, filas de categoría) y 42 px en móvil | 40 px en escritorio; 44 px en móvil para botones, filtros, selects, buscador, enlaces y «Volver a la lista» | Tamaño mínimo cómodo con ratón y con el dedo, sin solapes |
| 14 | Esqueleto animando `background-position` y sin animación con reduced motion | Brillo en un pseudoelemento con `transform: translateX`; con reduced motion, pulso suave de opacidad | `transform` va en la GPU y no repinta; reducir movimiento no significa quitar la señal de que está cargando |
| 15 | Destello gris del navegador al tocar en móvil | `-webkit-tap-highlight-color: transparent` solo donde hay respuesta propia (botones, filtros, categorías, filas) | El destello se sumaba a la selección y a la escala de pulsación |
| 16 | Saltar a la lista o a la ficha la dejaba pegada al borde | `scroll-margin-top: 16px` en `#lista` y `#detalle` | Deja aire al llegar desde el enlace de salto o al elegir fila en el móvil |

Total: 16 cambios.

## Considerado y descartado

- **Sustituir los bordes de los botones secundarios y de la placa del dorsal por sombras en capas**:
  ese borde de tinta no está para dar profundidad, es el dibujo del botón y de la placa. Una sombra al
  6-8 % quedaría por debajo de 3:1 sobre el hormigón.
- **Animar el cambio de ficha al elegir una fila (fundido o desenfoque)**: se hace decenas de veces
  al día; el contenido tiene que cambiar al instante.
- **Animar la entrada y la salida de filas al filtrar**: lo dispara el teclado al buscar; las acciones
  de teclado no se animan.
- **Entrada escalonada de la parrilla al cargar la página**: la herramienta se abre muchas veces al
  día y cada repetición costaría atención.
- **Escala al pulsar en filas de la tabla y de categorías**: son elementos anchos; un 4 % de 800 px
  son 32 px de movimiento. Ya responden con la selección y el estado pulsado.
- **Radios concéntricos para los botones dentro del estado vacío y del error**: el botón no está en
  la esquina y el padding es de 16-24 px; son superficies independientes.
- **Chevron del select con `currentColor` mediante máscara**: el select no tiene estados de color.
- **`will-change` en el esqueleto**: sin indicios de tirones en el primer fotograma; `transform` ya
  se compone en la GPU.
- **Sombra en la cabecera fija de la tabla al quedarse pegada**: exige JS de scroll; la línea de 2 px
  ya separa.
