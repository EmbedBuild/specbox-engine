# Lo que se rehúsa salvo que el brief lo pida

Estos son los defaults de la UI generada por modelos en 2026: aparecen sea cual sea el producto. No
están prohibidos. Si el brief, la marca o el sistema de diseño piden uno, se respeta. Lo que no vale es
llegar a uno porque el eje estaba libre: eso es no decidir.

Al revisar una dirección o una pantalla, cada coincidencia se **cambia** o se **justifica por
escrito**.

Fuentes: frontend-design (Anthropic), craft-floor de Impeccable (Paul Bakaus) y taste-skill
(Leonxlnx), calibradas con lo que se observó en la prueba UC-9001. Detalle en
[../THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Paletas

- Fondo crema (cerca de `#F4F1EA`) con titular serif y acento terracota o arcilla (cerca de `#D97757`).
- Fondo casi negro con un único acento verde ácido o bermellón.
- Beige con latón, ocre o burdeos como paleta «artesana» por defecto (`#b08947`, `#b6553a`,
  `#9a2436`…).
- Índigo o violeta con degradado de «SaaS calmado» (por ejemplo `#4F46E5` con `#8B5CF6`), y degradados
  morado-azul como decoración.
- Gris con un solo acento azul en una herramienta de trabajo: es la categoría sin su acabado.
- Papel con rotulador amarillo como voz de cualquier landing (visto dos veces en UC-9001).

## Tipografía

- Inter, Roboto, Arial o Space Grotesk como única voz «porque sí».
- Fraunces o Instrument Serif como display por defecto (las dos serifas favoritas de los modelos).
- Etiquetas en mayúsculas con espaciado (eyebrows) sobre cada título.
- Una palabra del titular en cursiva, negrita u otro color como acento.
- Monoespaciada como disfraz de «técnico», en lugar de reservarla para código, datos y medidas.

## Estructura

- Tarjetas idénticas (icono, título y texto) como estructura de la página, y tarjetas dentro de
  tarjetas.
- La plantilla de métrica héroe: número grande, etiqueta pequeña, cifras de apoyo y acento.
- Numeración 01 / 02 / 03 cuando el contenido no es una secuencia.
- Un modal para una tarea que no necesita interrumpir.
- Un mismo radio y una misma sombra gris suave en todo, sin jerarquía.

## Superficies

- Texto con degradado.
- Vidrio y desenfoque como decoración.
- Borde lateral de color de más de 1 px en tarjetas, filas, avisos o callouts.
- Sombra dura desplazada (`4px 4px 0`) fuera de un mundo neobrutalista elegido.
- Sparklines, anillos de progreso o rectángulos con sombra que sustituyen al contenido.
- Emojis o caracteres Unicode en lugar de un juego de iconos.

## Texto

- «Acme», «John Doe», `99,99 %`, lorem ipsum y cualquier cifra, testimonio o logo inventado.
- `→` añadido al final de enlaces y botones.
- Metadatos encadenados con puntos medios (`A · B · C`) y etiquetas «PALABRA — fragmento».
- La raya (`—`) como recurso de estilo en titulares, etiquetas y botones.
- Botones que no dicen qué pasa («Enviar», «Continuar») en lugar de la acción («Guardar cambios»).

## Movimiento

- La misma entrada de fundido y subida en cada sección al cargar.
- `transition: all`, animaciones de más de 300 ms en la interfaz y `ease-in` en respuestas al usuario.
- Animar desde `scale(0)`. Se empieza desde `0.95` o más, con opacidad.
- Animación en interacciones de alta frecuencia (atajos de teclado, filas de una tabla que se usa
  cien veces al día).
- Bucles infinitos (brillos, pulsos) que no respetan `prefers-reduced-motion`.

## Cómo se aplica

1. En la **dirección**: la pasada 2 de [direction.md](direction.md) recorre esta lista contra el plan.
2. En la **verificación**: el criterio 3 de [rubric.md](rubric.md) cuenta los que aparecen, con su
   línea, y descuenta según cuántos haya.
3. Un detector por patrones ayuda, pero **no decide**: el texto del propio brief («ESBK 2026 ·
   Navarra I») no es un tell aunque lleve puntos medios. Cada hallazgo se comprueba en el código.
