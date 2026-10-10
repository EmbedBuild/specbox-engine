# P1 «Participantes de la prueba»: notas de diseño (V2)

## Plan
Tema: la oficina de carrera durante el fin de semana. La pantalla tiene que responder tres preguntas
(quién falta por verificar y en qué box, qué hay que resolver en oficina, cómo va cada categoría).

**Paleta (6 + 1 funcional)**
- Papel `#FFFFFF`: superficie de trabajo (lista y estado).
- Hormigón `#EDEFF1`: columna lateral (Excel y ficha) y fila seleccionada.
- Asfalto `#1E2329`: texto, botón principal, foco.
- Grafito `#59616A`: texto secundario (AA sobre papel y hormigón).
- Naranja comisario `#F25C05`: solo «pendiente de verificar» (relleno con texto asfalto, 4,7:1).
- Tinta de sello `#5B3CC4`: solo lo que hay que resolver en oficina (papeleo).
- Rojo `#B3261E`: únicamente para el error de importación.

**Tipografía**
- Saira Condensed 600/700: dorsales, títulos y números de fila (recuerda a la placa del dorsal).
- Atkinson Hyperlegible 400/700: texto de interfaz, legible deprisa y en el móvil al sol del paddock.
- Escala clásica: 14 / 15-16 / 21 / 24 / 36 / 64.

**Layout (1440)**
```
cabecera: marca + hora | «Participantes» + prueba | buscar · Importar · Imprimir · Añadir
[ Faltan 25 por verificar: parrilla por categoría ] [ 3 filas del Excel no entraron ] (hormigón)
[ Lista: filtros + tabla 8 columnas               ] [ Ficha del participante, sticky ]
[ Otros estados: sin coincidencias | cargando | error al importar                      ]
```
Alineado a la izquierda. En 390 px, una columna (estado, lista en bloques, ficha, Excel, estados);
importar e imprimir pasan a botón de icono con etiqueta accesible.

**Principios**: el color solo aparece donde hay que actuar; lo hecho es gris. Una sola pieza con
carácter: la parrilla de unidades por categoría.

## Revisión del plan contra lo que haría por defecto
- Por defecto: tres tarjetas KPI (129 / 104 / 81 %) y barras de progreso. Cambiado por un titular
  que dice lo accionable («Faltan 25 por verificar») y una parrilla donde cada marca es un
  participante: gris verificado, naranja pendiente. Se cuenta y se compara el tamaño de categoría.
- Por defecto: Inter y botón azul. Cambiado por una condensada de placa de dorsal y una tipografía de
  alta legibilidad; el principal es asfalto, sin azul.
- Por defecto: semáforo verde/ámbar/rojo en chips. Quité el verde del todo (lo verificado no pide
  nada); naranja = falta verificar; violeta de sello = oficina. Dos columnas de color responden a
  las preguntas 1 y 2 de un vistazo.
- Por defecto: todo en tarjetas blancas con sombra. Cambiado por regiones de fondo (papel frente a
  hormigón), sin sombras; radios distintos según función (chips de filtro, botones, unidades).
- Por defecto: un único icono genérico de «aviso». Separé avisos de oficina (marca violeta, negrita)
  de notas informativas (gris): menor de edad, cambio de categoría o dorsal repetido válido.
- Por defecto: cabecera con meta unida por puntos medios y encabezados de tabla en mayúsculas.
  Cambiado por frases normales y encabezados en minúscula inicial.

## Decisiones clave
- «Equipo» significa equipo (team) y equipo del piloto; las columnas usan el vocabulario del brief
  («Moto verificada», «Equipo verificado») y el filtro dice «Falta verificar equipo».
- El box está justo antes de las verificaciones para leer «quién falta y dónde» en un barrido.
- Las filas rechazadas del Excel viven junto al estado, con qué hacer en cada una; la repetida dice
  que no hay nada que hacer y lleva a la fila original.
- Las acciones conservan el nombre en todo el flujo («Añadir participante», «Importar Excel RFME»).
- Ficha seleccionada por defecto: Mateo Rubial (una verificación hecha, otra pendiente, casco sin
  QR FIM). La licencia se muestra por tipo (Nacional, Provisional, FFM), sin inventar números.
- JS mínimo: búsqueda (dorsal exacto o texto sin tildes), filtros, orden, selección y estado vacío
  real. Autocrítica: quité el verde (accesorio sobrante) y reajusté anchos de columna a 1440.
