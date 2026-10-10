# P2 V4: corrección a partir de la verificación externa de V3

Partí de una copia de V3. V2 y V3 no se han tocado. Corregí los 8 defectos, en orden de severidad. Del
defecto 5 dejé fuera una parte, la del formulario (ver al final). Las líneas son las de `V4/index.html`.

| Defecto | Qué hice | Línea |
| --- | --- | --- |
| 1. Alta: scroll horizontal a 390 px (`div.dos-col__texto@399`) | `.dos-col` declara `grid-template-columns:minmax(0,1fr)` en la regla base y sus hijos llevan `min-width:0`. La pista ya no crece hasta el min-content de la fila de pestañas del móvil, que tiene `nowrap`. Apliqué la misma regla a `.hero__rejilla`, que tiene el mismo patrón (una rejilla sin columnas declaradas que contiene una escena) | 152-153, 81 |
| 2. Alta: los dos móviles se apilan a 1440 px (les faltaban 1,3 px) | Desde 60rem, `.moviles` pasa a `flex-wrap:nowrap` con `gap:1rem`, y cada `.movil` a `flex:0 1 16.5rem; min-width:0`. A 1440 px caben a tamaño completo (544 px de 550,7). Entre 960 y 1400 px se estrechan en lugar de bajar a otra fila, así que la sección no vuelve a quedarse con 900 px vacíos | 216-220 |
| 3. Media: el espaciado de `.texto` no se aplicaba (`:where()` perdía frente a `p{margin:0}`) | La regla pasa a `.texto > * + *` (1,1rem) y se añade `.texto > .titulo-seccion + *` (1,25rem). El conmutador conserva sus 2rem porque su regla va después | 141-142 |
| 4. Media: animación de carga larga y con retraso (`clip-path` 0,7 s, `blur`, 1,2 s de espera) | El fluorescente se anima con `scale` (de 0 a 1 en X, origen a la izquierda) en 300 ms con `ease-out` y 100 ms de retraso. El comentario aparece con opacidad y `translate` en 250 ms con 150 ms de retraso, así que está visible a los 0,4 s en lugar de a los 1,6 s. He quitado `filter` de los keyframes, de `.aparece` y del check del éxito | 107, 119-124, 126-127, 130-133 |
| 5. Media: tarjeta dentro de tarjeta en «Así responde el formulario» | `.estado` pierde el fondo, el anillo, la sombra, el radio y el relleno. El nombre del estado queda como rótulo encima de su caja (éxito, campo con error o aviso), que es la única caja | 292-293 |
| 6. Baja: cabecera con glass y borde lateral de 2 px | He borrado el bloque `@supports (backdrop-filter…)` y la cabecera se queda con `rgba(255,255,255,.96)`. En móvil, el `border-left` de `.comentario` pasa a ser la misma raya guía horizontal de 1,5 px que se usa en escritorio. En escritorio solo se recoloca esa raya (`left:auto; right:…`) | 58, 112-118 |
| 7. Baja: botones falsos en la maqueta del panel | «Ampliar validez», «Generar PIN nuevo» y «Revocar acceso» ya no tienen anillo, sombra, fondo ni relleno: son texto seminegrita en la barra de acciones, separados por 1,5rem, y ya no parecen pulsables. Revocar sigue en rojo | 202-203 |
| 8. Baja: casilla vacía del PIN casi invisible (1,4:1) | El borde de `.pin__caja` pasa a `var(--borde-campo)` (#7d85a6, 3,6:1) | 230 |

## No aplicado

- **Defecto 5, parte del formulario (`.formulario-zona` > `.formulario`):** no lo he cambiado. La mesa
  (`--mesa`) no es una tarjeta, sino la superficie sobre la que se apoya cada objeto de la página: la hoja,
  el panel, los móviles y el formulario. Quitarla solo aquí rompería la regla que siguen las otras tres
  escenas. El problema real era la repetición de marco dentro de marco en los tres estados, y eso sí está
  corregido.

## Sin verificar

No había navegador en esta ronda, así que estas medidas no están repetidas:

- `scrollWidth = clientWidth` a 390 px;
- los dos móviles en una sola fila a 1440 px;
- el estrechamiento de los móviles entre 960 y 1400 px.

Las cifras salen del cálculo con las medidas de la verificación. Sí comprobé la sintaxis de JS y CSS y que
no hay texto prohibido. Los únicos cambios en el HTML de V4 son de CSS.
