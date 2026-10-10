# Rúbrica de revisión de una pantalla

La usan quienes revisan un diseño: la crítica de candidatos de Stitch o Claude Design en `/plan` y la
verificación de pantallas implementadas en `/implement`.

El revisor tiene que ser **un subagente aislado**, que no vea el razonamiento de quien diseñó.
Recibe:
- el brief;
- la pantalla (HTML o captura);
- las capturas reales a 1440 y 390 px;
- las mediciones.

Es la misma rúbrica de 8 criterios de la prueba UC-9001. El pulido medible (make-interfaces-feel-better
y emil-design-eng) está dentro del criterio 6 y del 8: no hay una pasada de pulido aparte. Fuentes en
[../THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Mediciones antes de opinar

Lo que más puntos movió en la prueba fue una medición, no una opinión. Antes de puntuar:

- **Desbordamiento:** `scrollWidth` del documento a 390 px y a 1440 px, y los elementos que
  sobresalen. Un `scrollWidth` mayor que el ancho es scroll horizontal, salvo que lo que sobra esté
  recortado y oculto.
- **Capturas de página completa** a los dos anchos. Si la pantalla va en un iframe, la ventana tiene
  que ser más alta que el iframe, porque Chrome no pinta lo que queda fuera.
- **Contraste WCAG** de los pares reales: cuerpo, secundario, placeholder, chips, botones y texto
  sobre fondos de estado.
- **Tells:** se recorre [defaults.md](defaults.md) en el código y se cita la línea de cada uno.

## Los 8 criterios (0-5; un 5 solo si no hay nada que reprochar)

1. **Especificidad.** ¿Está pensada para este producto, este usuario y estos datos, o serviría para
   cualquiera? ¿La copy es del producto? **Una cifra, fila o función que no sale del brief ni del PRD
   es un defecto de este criterio.**
2. **Jerarquía.** ¿Responde en segundos a las tres preguntas del brief? (En Persuade: en menos de un
   minuto.) ¿La densidad es la adecuada para la superficie?
3. **Tells.** Cuántos de [defaults.md](defaults.md) aparecen sin que el brief los justifique: 5 si no
   hay ninguno, 0 si hay cinco o más.
4. **Tipografía.** Elección deliberada, escala clara, medida de línea, `tabular-nums` en cifras y sin
   mayúsculas innecesarias.
5. **Color.** Paleta comprometida y coherente, un color por significado, neutros entonados y contraste
   AA en cuerpo y placeholders.
6. **Estados y acabado.**
   - Estados: vacío que enseña qué hacer, skeleton (no spinner) y error inline con recuperación, **en
     su sitio real** y no solo en una vitrina.
   - Controles: `hover`, `focus-visible`, `:active` y `disabled` definidos, y acciones conectadas.
   - Pulido medible: áreas de pulsación de al menos 44 px en táctil y 40 px en escritorio; radios
     concéntricos (exterior = interior + padding); sombras con desplazamiento y desenfoque.
7. **Responsive.** A 390 px, sin scroll horizontal (medido). La tabla se reconvierte con sentido y la
   navegación es usable. En Operate, la lista antes que un resumen largo.
8. **Movimiento.**
   - Solo `transform` y `opacity`, nunca `transition: all`.
   - Menos de 300 ms, con `ease-out` en las respuestas al usuario y nunca `ease-in`.
   - Sin animación en la carga ni en interacciones de alta frecuencia; nada desde `scale(0)`.
   - `prefers-reduced-motion` respetado, también en los bucles.

## Veredicto

- **Block:** algo roto, ilegible, que desborda o que incumple el brief.
- **Needs changes:** se entrega con arreglos concretos.
- **Approve:** no hay defectos de severidad alta ni media.

## Formato de la revisión

```markdown
| # | Criterio | Nota | Justificación (con línea o zona de la captura) |
Total: N/40 · Veredicto: Block | Needs changes | Approve

## Defectos (máximo 8, por severidad)
| Severidad | Dónde | Qué está mal | Qué hacer |
```

Cada defecto se puede arreglar en una sola ronda: concreto, con su ubicación y sin proponer un
rediseño.

## La ronda de corrección

- **Una sola ronda.** Después se vuelve a medir y capturar.
- **No se inventan datos para cumplir un defecto.** Si arreglarlo exige un dato que el brief o el PRD
  no dan, la pantalla lo muestra como pendiente (`[DATO REAL: …]`) y se avisa. En la prueba, el
  diseñador inventó un participante y unos recuentos de filtro para satisfacer la crítica, y los
  revisores lo penalizaron.
- Si quien corrige no está de acuerdo con un defecto, puede no aplicarlo, pero tiene que dejar escrito
  por qué.
- La verificación siguiente señala como defecto cualquier cifra o elemento nuevo sin fuente.
