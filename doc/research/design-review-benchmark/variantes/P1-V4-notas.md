# P1 «Participantes de la prueba»: tercera pasada (V4, corrección tras verificación)

Base: copia de V3. Corregidos los 8 defectos de la crítica en una ronda; el n.º 2 con una
limitación que explico abajo. Sin navegador: la altura del primer pantallazo es una estimación por
métricas (cabecera ≈162 px + bloque superior ≈345 px + cabecera de lista y 3 filas ≈375 px ≈ 880 px)
y está **sin verificar en captura**. El script pasa `node --check`.

## Defectos

| Defecto | Qué hice | Línea |
|---|---|---|
| 1 · Media · La lista queda fuera del primer pantallazo a 1440 | Cabecera más baja (padding 14/18). Estado: texto de ayuda en una línea junto al título y filas de categoría de 28 px sin hueco. Bloque del Excel compacto: «Fila N» a la derecha del nombre y la acción en línea al final del motivo, con el área de pulsación ampliada con `::after`. Lista: «Orden» sube a la barra del título junto al recuento, las etiquetas de los filtros pasan a ser solo para lector de pantalla (el select ya dice «Todas las categorías») y hay menos margen antes de la tabla | CSS 51, 71-73, 78-84, 93-98, 103, 124-125; HTML 303-306, 321-336, 342-349 |
| 2 · Media · Los filtros no dan cifra | Cifra en cada chip en `tabular-nums` y peso regular: Todos 129, Moto pendiente 11, Equipo pendiente 17, Para oficina 8. Al pulsar un chip, la lista dice «3 de 11» y «Mostrar los 8 restantes». Los chips pasan a llamarse «Moto/Equipo pendiente» para que quepan en una fila | HTML 369-373; CSS 118-120; JS 613-618 |
| 3 · Media · A 390, importar e imprimir solo con icono | Etiqueta visible: «Importar» (el nombre accesible sigue siendo «Importar Excel RFME») e «Imprimir PDF». A ese ancho bajan a una fila propia a medias, bajo «Añadir participante» | HTML 294-295; CSS 67, 238-242 |
| 4 · Baja · Borde lateral de color en el error | Quitado: borde completo de 1 px en `--rojo` y radio uniforme de 6 px | CSS 182 |
| 5 · Baja · La fecha del panel parte mal | Texto acortado a «Hoy, 8 de mayo, 09:12», sin «a las». Si aun así salta de línea, el check se alinea arriba | CSS 161-162; HTML 507; JS 638 |
| 6 · Baja · Sin estado deshabilitado | `.btn:disabled` y `.chip input:disabled + span`: texto grafito, borde `--linea`, `not-allowed` y sin escala. Ejemplo visible en el estado «Cargando» («Mostrar los 120 restantes» deshabilitado) | CSS 68, 121-122, 194; HTML 558 |
| 7 · Baja · Hover de fila casi invisible y hexadecimales sueltos | Tokens `--pasada` (#F1F3F5) y `--asfalto-2` (#3A434D) en `:root`, usados en filas, categorías y botón principal | CSS 23-24, 191-195 |
| 8 · Baja · Cifra de categoría lejos de su barra | La rejilla pasa a `150px auto 1fr` y `max-width: 720px`: la cifra queda pegada al final de cada barra | CSS 80-84 |

## Lo que no apliqué (o apliqué en parte)

- **N.º 2, que las cifras «se actualicen con la búsqueda y la categoría»:** el brief no da cuántos
  faltan por moto o por equipo, ni cuántos tienen algo en oficina, y menos por categoría. Las cifras
  de la prueba entera (11 y 17 con 3 en ambas, que suman los 25 pendientes del brief, y 8 de oficina)
  son de ejemplo y cuadran entre sí. Para actualizarlas por categoría tendría que inventar 27 cifras
  más, o contar sobre las 9 filas de muestra, que contradiría los 129. Al buscar o filtrar por
  categoría las cifras se ocultan en vez de mostrar un dato falso. Con datos reales bastaría un
  recuento por chip.
- **Reducir las filas de categoría a 28 px choca con el mínimo de 40 px en escritorio:** lo apliqué
  igual. Cada fila mide unos 720 px de ancho, así que es fácil de acertar con el ratón; en móvil
  siguen por encima de 44 px.
- **Notas de la crítica fuera de los 8 defectos:**
  - No toqué el latido del esqueleto con movimiento reducido: es solo opacidad y es la única señal
    visual de carga.
  - Mantuve las transiciones de color de 100 ms: la crítica no las marca como defecto y no mueven
    nada.
