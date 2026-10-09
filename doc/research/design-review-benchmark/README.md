# Prueba comparativa: qué capas de diseño merecen construirse (UC-9001)

> Fecha: 2026-10-09 · Engine v6.23.0 «Poda» · US-90 (EP-16 «El engine diseña con criterio»)
> Pregunta: de las cuatro capas que propone `/design-review` (brief, dirección, pulido y verificación),
> ¿cuáles mejoran de verdad una pantalla diseñada por un agente?

## Decisión (AC-04)

**Regla:** una capa se construye si sube la puntuación media al menos 3 puntos sobre 40 frente a la
variante sin ella. Δ es la media de 2 pantallas × 2 revisores ciegos.

| Capa | Comparación | P1 rev. A | P1 rev. B | P2 rev. A | P2 rev. B | **Δ medio** | **Decisión** |
|---|---|---|---|---|---|---|---|
| Brief | V1 − V0 | +3 | +4 | +8 | +8 | **+5,75** | **Construir** |
| Dirección | V2 − V1 | +7 | +6 | −3 | −1 | **+2,25** | **Aplazar** |
| Pulido | V3 − V2 | +3 | +1 | +1 | +2 | **+1,75** | **Aplazar** ¹ |
| Verificación | V4 − V3 | +1 | +2 | +13 | +7 | **+5,75** | **Construir** ¹ |
| Dirección en Stitch (solo P1) | S2 − S1 | +7 | +6 | — | — | +6,5 | Informativo ² |

¹ **Decisión «poco fiable».** En P2-V3 los dos revisores difieren 5 puntos (25 frente a 30), por encima
del umbral de 4. La conclusión no cambia con ninguno de los dos: el pulido queda entre +1 y +2 en P2 y
la verificación entre +7 y +13.

² Stitch mejora mucho con el paso de dirección, pero sus dos candidatos quedan muy por debajo del
resto (5,5 y 12 sobre 40). Ver más abajo.

**Lectura en una frase:** lo que más mejora una pantalla son dos capas, darle al agente el brief
(usuario, preguntas y datos reales) y obligarle a mirar el resultado con un revisor que no es él. La
dirección y el pulido aportan, pero menos de 3 puntos de media. La dirección se reparte de forma
desigual: +6,5 en la pantalla de app y −2 en la página comercial.

## Método

### Pantallas

| | Superficie | Brief |
|---|---|---|
| **P1** | Operate: «Participantes de la prueba» de PaddockManager (ESBK 2026 · Navarra I) | [`briefs/P1-BRIEF.md`](briefs/P1-BRIEF.md) |
| **P2** | Persuade: landing de «Propuestas» (propuestas.embed.build) | [`briefs/P2-BRIEF.md`](briefs/P2-BRIEF.md) |

- Las dos pantallas son nuevas y se diseñaron sin sistema de diseño.
- Los datos de P1 salen del dominio real de PaddockManager: Excel de la RFME, verificación de moto y
  equipo, categorías del ESBK 2026. Los nombres de pilotos y equipos son inventados.
- P2 es un **escenario de prueba**: Propuestas es una herramienta interna de embed.build y no se ofrece a
  terceros. La landing es un supuesto para medir una superficie comercial.

### Variantes

Cada variante la hace un agente aislado que solo puede leer los ficheros que se le dan, sin navegador
ni web.

| Variante | Qué recibe | Cómo se genera |
|---|---|---|
| V0 | Un encargo de una línea y las restricciones técnicas, sin brief | Independiente |
| V1 | El brief | Independiente |
| V2 | El brief y `frontend-design` (Anthropic, Apache-2.0) | Independiente |
| V3 | V2 más una pasada de pulido con `make-interfaces-feel-better` (Jakub Krehel, MIT) y `emil-design-eng` (Emil Kowalski, MIT) | Mismo diseñador, sobre una copia de V2 |
| V4 | V3 más una ronda de verificación: capturas reales a 1440 y 390 px, mediciones, detector de tells y crítica de un revisor aislado; después, una sola ronda de corrección | Mismo diseñador, sobre una copia de V3 |

V3 y V4 se hacen en cadena sobre el mismo diseño. Así, V3 − V2 y V4 − V3 miden solo la capa añadida,
sin el ruido de generar otro diseño. V0, V1 y V2 son generaciones independientes, porque la capa que
miden cambia cómo se diseña.

**Stitch (P1, AC-02):**
- **S1**: el prompt base de `/plan` (Paso 6.2).
- **S2**: el mismo prompt precedido del bloque «Visual Direction», que sale del paso de dirección del
  diseñador de V2.

Cada candidato se genera en un proyecto nuevo, con `GEMINI_3_8_FLASH` y `DESKTOP`. Los prompts y las
incidencias de la generación están en [`briefs/P1-stitch-prompts.md`](briefs/P1-stitch-prompts.md).

### Puntuación

- **Dos revisores ciegos por pantalla.** Las variantes se renombran al azar (los mapas están en
  `revisiones/mapa-ciego-P*.txt`) y cada revisor las recorre en un orden distinto. Usan la rúbrica de 8
  criterios sobre 40 ([`RUBRICA.md`](RUBRICA.md)) y una revisión anterior como calibración.
- **Mediciones que no dependen del modelo:**
  - capturas a página completa con Playwright y Chrome a 1440 y 390 px reales;
  - `scrollWidth` y elementos que sobresalen;
  - un detector de tells por patrones, con su línea.

## Resultados

### Puntuación por variante (sobre 40)

**P1, Operate**

| Variante | Rev. A | Rev. B | Media | Veredicto de los revisores (resumido) |
|---|---|---|---|---|
| V0 | 22 | 22 | 22,0 | Bien construida, pero de otra prueba: no usa los datos del brief y le faltan el detalle, el Excel y dos estados |
| V1 | 25 | 26 | 25,5 | La mejor copy de producto, sobre una maqueta estática con eyebrows y cifra héroe |
| V2 | 32 | 32 | 32,0 | La más fiel a los datos; le falta acabado (sin `disabled`, `:active` ni transiciones) |
| V3 | 35 | 33 | 34,0 | V2 con capa de interacción y movimiento; inventa un participante para arreglar un filtro |
| V4 | 36 | 35 | 35,5 | La más completa y mejor acabada; inventa recuentos en los filtros |
| S1 | 6 | 5 | 5,5 | Datos alterados, seis tells, contraste roto y 1106 px de ancho a 390 |
| S2 | 13 | 11 | 12,0 | Buena idea (matriz por categoría), pero datos cambiados, desborda en los dos anchos y texto de 9-11 px |

**P2, Persuade**

| Variante | Rev. A | Rev. B | Media | Veredicto de los revisores (resumido) |
|---|---|---|---|---|
| V0 | 19 | 21 | 20,0 | La copy más persuasiva, pero de otro producto: inventa precios, funciones y un cliente |
| V1 | 27 | 29 | 28,0 | La más persuasiva y mejor cableada, hundida por el repertorio de plantilla (6 tells, nota 0 en el criterio 3) |
| V2 | 24 | 28 | 26,0 | Idea limpia sin tells de plantilla, pero desborda 9 px a 390 y el CSS tiene regresiones |
| V3 | 25 | 30 | 27,5 | El pulido mejora el tacto, pero mantiene el desbordamiento |
| V4 | 38 | 37 | 37,5 | La única sin fallos técnicos ni tells; corrige todo lo que la crítica señaló |

**Acuerdo entre revisores:** la diferencia media es de 1,8 puntos por variante y la máxima de 5 (P2-V3).

### Mediciones

| Variante | scrollWidth a 1440 | scrollWidth a 390 | Sobresalen a 390 | Tells del detector ³ |
|---|---|---|---|---|
| P1-V0 | 1440 | 390 | 3 | 14 |
| P1-V1 | 1440 | 390 | 0 | 5 |
| P1-V2 | 1440 | 390 | 0 | 1 |
| P1-V3 | 1440 | 390 | 0 | 1 |
| P1-V4 | 1440 | 390 | 0 | 0 |
| P1-S1 | 1440 | **1106** | 8 | 0 |
| P1-S2 | **1511** | **795** | 8 | 3 |
| P2-V0 | 1440 | 390 | 0 | 9 |
| P2-V1 | 1440 | 390 | 0 | 9 |
| P2-V2 | 1440 | **399** | 8 | 2 |
| P2-V3 | 1440 | **399** | 8 | 2 |
| P2-V4 | 1440 | 390 | 0 | 0 |

³ El detector es orientativo. Cuenta como tell, por ejemplo, el texto del propio brief con puntos medios
(«ESBK 2026 · Navarra I»). Los revisores lo comprobaron en el código antes de contarlo.

## Lectura por capa

**Brief (+5,75): construir.** Sin brief, los dos agentes diseñaron otra cosa:
- en P1, otra prueba, otro circuito y otros datos;
- en P2, un producto con precios y funciones que no existen.

Los revisores lo resumen igual: «una pantalla bien hecha puntúa poco si no es la pantalla pedida». El
brief además reduce los tells (P1: de 14 a 5).

**Dirección (+2,25): aplazar.** Ayuda mucho en la pantalla de app: V2 es la más fiel a los datos, con un
color por significado y una pieza propia, la parrilla por categoría. En la landing resta un poco: V1
ya era la página más persuasiva, aunque cargada de tells, y V2 la limpia pero rompe el móvil.

El mismo patrón que vio la primera prueba ciega aparece aquí: cuanto más ambiciosa es la dirección, más
se nota no mirar el resultado. Con verificación detrás, la dirección queda en la variante ganadora de
las dos pantallas.

**Pulido (+1,75): aplazar.** Como pasada separada mejora el tacto (estados, áreas de pulsación,
movimiento con `reduce`), pero no lo que más puntúa. Sobre todo, no arregla lo que no se ve: el
desbordamiento de P2 sobrevive al pulido.

**Verificación (+5,75): construir.**
- **En P2 sube 10 puntos.** La crítica aislada bloqueó por el desbordamiento a 390 px, que nadie había
  visto, y la corrección dejó la página sin fallos técnicos ni tells.
- **En P1 sube 1,5.** V3 ya estaba limpia, y la corrección añadió cifras inventadas para cumplir un
  defecto de la crítica, que los revisores penalizan.

**Stitch y dirección (+6,5): informativo.** El paso de dirección le sirve a Stitch: S2 aplica la paleta,
las tipografías y la parrilla por categoría. Pero los dos candidatos quedan en el fondo de la tabla:
- solo escritorio (1106 y 795 px a 390);
- datos del brief alterados;
- texto de 9-11 px y tells.

Confirma D18 (Stitch y Claude Design generan candidatos, nunca producción) y el valor de criticar cada
candidato antes de guardarlo (UC-9004).

## Hallazgos que cambian el diseño de `/design-review`

1. **Prohibir inventar datos para arreglar un defecto.** En P1, el diseñador inventó un participante
   (V3) y recuentos de filtro (V4) para cumplir lo que pedían su propio fallo y la crítica. La crítica y
   la corrección tienen que decir «si falta el dato, márcalo; no lo inventes».
2. **La verificación tiene que medir, no solo opinar.** Lo que más puntos movió (el desbordamiento de
   P2) lo encontró una medición, `scrollWidth` a 390, no el juicio del diseñador ni el pulido.
3. **El pulido puede ir dentro de la verificación.** Sus reglas medibles (áreas de pulsación,
   `disabled`, `:active`, `reduce`, `tabular-nums`) caben en la rúbrica de la crítica. Una pasada
   aparte cuesta unos 90.000-100.000 tokens por pantalla y aporta menos de 2 puntos.
4. **Patrones que ninguna variante resolvió:**
   - el skeleton y el error solo aparecen en una vitrina al pie, nunca en su sitio real;
   - las acciones del panel no están conectadas;
   - en móvil, el resumen ocupa 700-1.000 px antes de la primera fila.

   La rúbrica de UC-9003 debería pedirlos explícitamente.

## Coste

| Pieza | Tokens aprox. |
|---|---|
| Dominio real de PaddockManager (exploración previa) | 0,15 M |
| Generación V0, V1 y V2 (6 agentes) | 1,0 M |
| Pulido V3 (2 pasadas) | 0,19 M |
| Verificación V4: 2 críticas aisladas y 2 correcciones | 0,38 M |
| Revisión ciega (4 revisores) | 1,49 M |
| **Total** | **≈ 3,2 M** |

La estimación del plan era de 2,3 M. La diferencia sale casi entera de los revisores, que leen todas las
variantes con sus capturas.

Coste por pantalla de cada capa, en una implantación real:
- dirección: unos 15.000 tokens;
- pulido: unos 95.000;
- verificación (crítica más corrección): 160.000-220.000.

## Límites

- **Muestra pequeña:** dos pantallas, una generación por variante y dos revisores. El ruido de generación
  de V0, V1 y V2 no está medido.
- **Revisores modelo:** los revisores también son modelos. Su acuerdo es alto (1,8 puntos de media),
  pero no sustituye a una revisión humana.
- **Sin sistema de diseño:** las pantallas se hicieron sin sistema de diseño. Con uno (tokens y
  componentes), la dirección tiene menos margen. Un dato previo: un lienzo de Claude Design con sistema
  de diseño sacó 34/40.
- **Solo Stitch para la dirección en P1:** los candidatos de Stitch se midieron solo en P1.

## Material

- `briefs/`: los dos briefs y los prompts de Stitch.
- `RUBRICA.md`: la rúbrica de 8 criterios.
- `variantes/`: el HTML de cada variante y las notas de sus diseñadores (`P1-V0.html`,
  `P1-V2-notas.md`…).
- `capturas/`: las capturas en JPG a 1440 px (reducidas a 960 de ancho) y a 390 px, más las medidas y la
  salida del detector de cada variante.
- `revisiones/`:
  - las cuatro revisiones ciegas (`P1-revisor-A.md`…);
  - las críticas aisladas de la verificación (`P*-V4-critica.md`);
  - los mapas ciegos.
