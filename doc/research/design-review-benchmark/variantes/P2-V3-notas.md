# P2 V3: pasada de pulido sobre V2

Alcance: el `index.html` completo (CSS propio, JS mínimo, sin frameworks). La dirección visual no cambia:
misma paleta, tipografía, layout y textos. Revisadas tipografía, superficies, animaciones, iconos y
rendimiento. 17 cambios.

## Cambios

| # | Antes | Después | Por qué |
| --- | --- | --- | --- |
| 1 | `-webkit-font-smoothing` en `body` | En `html`, junto con `-moz-osx-font-smoothing: grayscale` | El suavizado va en la raíz para que todo el texto se pinte igual en macOS |
| 2 | `text-wrap: balance` solo en `h1-h3`; `pretty` solo en `p` | `balance` también en los títulos que son `<p>` (hoja, panel, móvil, éxito); `pretty` en `li`, `figcaption` y `dd` | Evita viudas en títulos de maqueta, pies de figura y listas |
| 3 | Horas de las aperturas alineadas a la izquierda («8:14» bajo «19:06») | Alineadas a la derecha con cifras tabulares | Los dos puntos quedan en columna y la tabla se lee de un vistazo |
| 4 | Mesa de 24 px con panel y formulario de 14 px a 16 px del borde (móvil) | Hasta 752 px, interior de 8 px y mesa = 8 px + margen (24 a 32 px); en escritorio el margen pasa de 24 px y se queda igual | Radios concéntricos: con un margen pequeño, los radios desiguales hacen que la esquina interior se vea pellizcada |
| 5 | Marcos de estados con radio exterior de 12 px y bloque interior de 14 px (el de dentro más redondo que el de fuera) | Marco de 20 px, relleno de 12 px y bloques interiores de 8 px; campos de 7,2 a 8 px | Exterior = interior + relleno |
| 6 | Panel, formulario, marcos de estados y acciones del panel con borde `1px #D3D9E8` para separarse del fondo | Anillo de sombra translúcido (`0 0 0 1px` tinta al 16 %) más sombra leve | Los bordes que solo dan profundidad funcionan mejor como sombra: se adaptan a la mesa y al blanco. Los bordes de campos, estados y separadores se mantienen |
| 7 | Botón pequeño y conmutador de 40 px; enlace «Ver cómo funciona» y logotipo de unos 20 a 24 px de alto | 44 px con puntero táctil (`pointer: coarse`); enlace y logotipo con 44 px de alto mínimo | Áreas de toque de 44 × 44 en móvil, que es la mitad de las visitas |
| 8 | Ninguna respuesta al pulsar; transición `background-color, border-color` con `ease` | `scale(.96)` al pulsar en botones, conmutador y opciones (no en los desactivados), 150 ms, `ease-out` propia `cubic-bezier(.23,1,.32,1)`; propiedades listadas una a una | La pulsación confirma que la interfaz responde; nunca `transition: all` |
| 9 | `:hover` sin condiciones; el conmutador no tenía hover | Hover solo con `(hover: hover) and (pointer: fine)`; hover suave en la opción no pulsada del conmutador | En táctil el hover se queda pegado tras el toque |
| 10 | Sello de «Aceptada» con keyframes de 450 ms desde `scale(1.12)`, giro y rebote | Transición de 200 ms (opacidad y `scale` de .96 a 1) con `@starting-style`, sin rebote | Por debajo de 300 ms, interrumpible si se cambia rápido y nunca desde una escala exagerada |
| 11 | El cambio de estado se animaba igual con ratón o teclado | Sin animación en la carga (`data-tocado`) ni al activar con teclado (`data-teclado`, `detail === 0`); al volver a «Pendiente» también hay transición | No animar en la carga ni en acciones de teclado |
| 12 | Rotulador de 900 ms tras 600 ms; comentario de 500 ms con `ease` a los 1,45 s | Rotulador de 700 ms tras 400 ms con `ease-in-out` fuerte; comentario de 400 ms con `ease-out` y desenfoque de 4 px, 100 ms después de terminar el trazo | El mensaje clave aparece a 1,6 s en vez de a 1,95 s. Lo que entra usa `ease-out`; lo que se mueve en pantalla, `ease-in-out` |
| 13 | El éxito del formulario y el error de envío aparecían de golpe | Entrada con `@starting-style`: opacidad, 8 px hacia arriba y desenfoque de 4 px a 0 en 300 ms; el check pasa de `scale(.25)` a 1 con desenfoque, 80 ms después. Con movimiento reducido, solo opacidad | Un estado poco frecuente puede tener una entrada; el movimiento reducido conserva el fundido |
| 14 | Iconos con trazo de 1,6 o 2 junto a texto regular, y de 2,2 junto a semibold | 1,5 junto a texto regular (dispositivos, reloj, candado, error de campo) y 2 junto a semibold (checks, alerta del aviso) | El grosor del icono acompaña el peso del texto de al lado |
| 15 | Punto del icono de alerta dibujado como trazo de 0,01 | Círculo relleno de radio 1,15 | Con el trazo nuevo, más fino, el punto casi desaparecía a 16 px |
| 16 | Icono de aceptación de 1,2 rem (1,28 em) con 0,05 rem de ajuste | 1,125 rem (1,2 em) y 1 px de ajuste óptico | Tamaño entre 1 y 1,25 em del texto y centrado con la primera línea |
| 17 | El «Reintentar» de la demostración se estrechaba al pasar a «Enviando…» | `min-width: 7rem` | El cambio de texto ya no mueve el contenido |

## Considerado y descartado

- **Entrada escalonada del hero (título, entradilla y CTA):** retrasaría la lectura del CTA y rompería el
  único momento orquestado que ya tiene la página.
- **`will-change` en el rotulador:** `clip-path` no se compone de forma fiable en todos los navegadores y
  no hay ningún tirón comprobado que lo justifique.
- **Sombras en negro puro:** la regla del negro es para contornos de imagen, y aquí no hay imágenes. El
  tono de tinta forma parte de la paleta.
- **Radio concéntrico en la hoja de papel (3 px):** el papel no tiene esquinas redondas. Es una decisión
  de material, no una superficie de interfaz.
- **Animar los errores de cada campo:** se actualizan mientras se escribe, es decir, en acciones de teclado
  muy frecuentes, así que van sin animación.
- **Animar las barras de lectura al entrar en pantalla:** sería decorativo y retrasaría el dato.
- **Cambiar por sombra el borde del botón claro:** ese borde de 2 px es la forma del botón sobre el fondo
  de error, así que es estructura.
- **Cifras tabulares en precios y numerales de los pasos:** no cambian de valor; se quedan con cifras de
  caja alta.

## Verificación

Hecho: equilibrio de etiquetas, ids sin duplicar, sintaxis de JS y llaves de CSS, y ausencia de texto
prohibido. **Sin verificar:** no hay navegador ni capturas en esta pasada, así que el movimiento a cámara
lenta, los estados de hover y pulsación y el aspecto a 390 y 1440 px no están vistos. `@starting-style`
necesita Chrome 117, Safari 17.5 o Firefox 129; en navegadores anteriores los estados aparecen sin
animación.
