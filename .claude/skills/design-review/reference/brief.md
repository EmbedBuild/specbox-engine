# Brief de pantalla

El brief es lo que más mejora una pantalla diseñada por un agente. En la prueba UC-9001, quitarlo
bajó la puntuación 5,75 puntos sobre 40 de media, y en una de las dos pantallas el agente diseñó
otra prueba de otro campeonato con otros datos. Un brief corto y concreto vale más que una guía de
estilo larga.

## De dónde sale cada campo (y qué no se pregunta)

| Campo | Fuente, en este orden | Se pregunta solo si… |
|---|---|---|
| Producto y contexto | `doc/app/app_prd.md` (visión) → PRD de la feature | no hay ninguno de los dos |
| Quién la usa | Audiencia del PRD → `app_prd.md` (audiencia) → `app_market.md` (ICP) | la pantalla es para alguien que no aparece en ninguno |
| Cuándo y dónde la usa | Audiencia del PRD (contexto de uso) → AC de la UC | no se puede deducir (frecuencia, dispositivo, prisa) |
| Las tres preguntas | JTBD del PRD y de `app_market.md` → AC de la UC | casi siempre: confírmalas con quien pide la pantalla |
| Contenido de la pantalla | «Interacciones UI» del PRD → AC de la UC → pantallas de la UC | falta una pieza que los AC exigen |
| Datos reales | Ejemplos del PRD y de los AC → fixtures, seeds, documentación del dominio | no hay ninguna fuente: pide 6-10 filas de ejemplo |
| Superficie | [surfaces.md](surfaces.md) | la pantalla mezcla dos superficies |
| Marca y sistema | `app_spec.md` (Brand & Visual) → tokens → `doc/design/DESIGN.md` | nunca: si no hay, se dice «sin sistema» |
| Restricciones técnicas | `app_spec.md` (stack) → plan de la feature | nunca |

Usa `get_inheritable_values_tool(app_prd_content, app_spec_content)` para no repreguntar lo que el
canon ya responde. Si el MCP es remoto, pásale el contenido de los ficheros, no sus rutas.

## Reglas de los datos

- **Reales o marcados.** Un dato que no sale de una fuente del proyecto va como `[DATO REAL: qué
  falta]`, visible en la pantalla. Nunca se inventa para que la pantalla «quede completa».
- **Personas ficticias, dominio real.** Si los datos reales tienen nombres de personas, usa nombres
  inventados verosímiles en el idioma del producto y conserva todo lo demás: categorías, importes,
  estados, fechas, volúmenes.
- **Volumen real.** Indica cuántos elementos hay de verdad (129 participantes, 8 propuestas) aunque
  se muestren menos. El diseño de una lista de 8 no es el de una de 129.
- **Cifras que cuadran.** Los totales del resumen tienen que salir de las filas de ejemplo.
- **Fechas y formatos del idioma del producto**, y la fecha de «hoy» fijada en el brief.

## Plantilla

```markdown
# Brief: {pantalla} ({superficie})

## Producto y contexto
{2-4 frases: qué es el producto, qué parte es esta pantalla y qué NO hace el sistema
(lo que vive en otro sitio).}

## Quién la usa y para qué
{Rol, frecuencia, dispositivo y situación (por ejemplo: oficina de carrera, portátil, varias veces al día).}

Tiene que responder en segundos a:
1. {pregunta 1}
2. {pregunta 2}
3. {pregunta 3}

## Pantalla a construir
1. {pieza}: {qué muestra y qué acciones tiene}
2. …
N. Estados: vacío ({cuándo}), carga ({dónde}) y error ({cuál}), **en su sitio real**, no solo en
   una vitrina.

## Datos reales de ejemplo
{Tabla o lista con los datos. Hoy es {fecha}. Lo que falta, como [DATO REAL: …].}

## Marca y sistema
{Sistema de diseño y tokens, o «sin sistema: la dirección decide».}

## Restricciones técnicas
- Stack: {…}
- Modo: {claro/oscuro}. Idioma y formatos: {…}.
- Anchos: 1440 y 390 px sin scroll horizontal.
- Accesibilidad: contraste AA, foco visible, áreas de pulsación de 44 px en táctil y 40 px en escritorio.
- Sin datos inventados, sin lorem ni marcas tipo «Acme».
```

## Ejemplo resumido (de la prueba UC-9001)

> **Participantes de la prueba (Operate).** La usa el director técnico durante el fin de semana de
> carrera, en un portátil de la oficina y a veces en el móvil del paddock. Responde a:
> 1. ¿Quién falta por verificar moto o equipo, y en qué box está?
> 2. ¿Quién tiene algo que resolver en oficina antes de salir a pista?
> 3. ¿Cómo va cada categoría?
>
> Datos: 129 participantes, 104 verificados y 8 filas reales con dorsal, categoría, box y estado de
> verificación. Se deja claro qué NO hace el sistema: las inscripciones y los pagos son de la
> federación, no de esta pantalla.

Esa última frase deja fuera de la pantalla lo que el producto no hace; sin ella, un diseño de
«inscripciones» tiende a inventar estados de pago.
