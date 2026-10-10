---
name: design-review
description: >
  Design criteria for each screen before it is drawn or coded: a brief grounded in the
  project's real users, questions and data, a visual direction checked against the
  generic defaults of AI-made UI, and a verification of the result with real screenshots,
  deterministic rules and an isolated reviewer. Use when the user says "design review", "brief
  de pantalla", "dirección visual", "verifica la pantalla", "diseña con criterio", "anti AI
  slop", or before generating a screen with Stitch, Claude Design or code.
context: direct
---

# /design-review

Criterio de diseño por pantalla. SpecBox ya genera diseño (Stitch, Claude Design, tokens,
DESIGN.md); esta skill decide **para quién y con qué datos** se diseña y **qué dirección** se
toma, antes de dibujar o escribir código, y **comprueba el resultado** con capturas y mediciones.

Por qué existe, con datos (prueba comparativa UC-9001, `doc/research/design-review-benchmark/`):
- el **brief** sube la pantalla +5,75/40: sin él, el agente diseña otra pantalla con otros datos;
- la **verificación** sube +5,75/40: lo que más puntos movió fue una medición, no una opinión;
- la **dirección** sube +6,5/40 en pantallas de app cuando va seguida de verificación.

## Regla de oro: sin brief no hay diseño

Antes de escribir una dirección, un prompt de Stitch o Claude Design, o el código de una
pantalla, tiene que existir su brief en `doc/design/{feature}/{pantalla}.brief.md`.
Si no existe, esta skill lo construye primero (`brief`) o lo pide. Nunca se diseña «a ver qué
sale» ni se rellena con datos inventados.

## Subcomandos

| Subcomando | Qué hace | Escribe | Referencia |
|---|---|---|---|
| `brief <pantalla>` | Usuario, las tres preguntas que la pantalla responde, datos reales y superficie | `doc/design/{feature}/{pantalla}.brief.md` | [reference/brief.md](reference/brief.md) |
| `direction <pantalla>` | Dirección visual revisada contra lo que saldría por defecto | `doc/design/{feature}/{pantalla}.direction.md` | [reference/direction.md](reference/direction.md) |
| `verify <pantalla>` | Capturas a 1440 y 390, reglas deterministas y revisor aislado | `doc/design/{feature}/{pantalla}.verify.md` | [reference/verify.md](reference/verify.md) |

Referencias compartidas, que se cargan solo cuando hacen falta:
- [reference/surfaces.md](reference/surfaces.md): reglas por superficie (Operate, Persuade, Read).
- [reference/defaults.md](reference/defaults.md): lo que se rehúsa salvo que el brief lo pida.
- [reference/rubric.md](reference/rubric.md): la rúbrica de 8 criterios y el formato de veredicto.
  La usan la crítica de candidatos de `/plan` y la verificación de pantallas de `/implement`.

## `/design-review brief <pantalla>`

1. Identifica la feature y la pantalla: el argumento, la UC activa o la sección de pantallas del
   PRD. Si hay varias candidatas, pregunta cuál.
2. Lee lo que el proyecto ya sabe y **no lo vuelvas a preguntar**:
   - `doc/app/app_prd.md` y `doc/app/app_spec.md` con `get_inheritable_values_tool` (audiencia,
     stack, marca);
   - `doc/app/app_market.md` (ICP y JTBD), si existe;
   - el PRD de la feature (sección «Audiencia» e «Interacciones UI») y las UC con sus AC.
3. Rellena la plantilla de [reference/brief.md](reference/brief.md). Pregunta solo lo que falte
   de verdad: normalmente las tres preguntas de la pantalla y de dónde salen los datos reales.
4. Datos: usa los reales del dominio (PRD, AC, fixtures, seeds, documentación del producto). Si
   falta uno, déjalo como marcador visible (`[DATO REAL: …]`). Nada de «Acme», «John Doe» ni lorem.
5. Elige la superficie (Operate, Persuade o Read) con [reference/surfaces.md](reference/surfaces.md).
6. Guarda el brief y enséñalo en una pantalla: usuario, preguntas, datos y superficie.

## `/design-review direction <pantalla>`

1. **Comprueba que existe el brief.** Si no existe, ejecuta antes `brief` o pídelo.
2. Lee el sistema del proyecto, si lo hay: `design-system.tokens.json`, `doc/design/DESIGN.md`,
   el brand kit. **Con tokens del sistema, la dirección no inventa valores**: decide composición,
   jerarquía, densidad y una pieza propia, y toma colores, tipos y radios de los tokens.
3. Haz el plan con [reference/direction.md](reference/direction.md): paleta con función (sin
   tokens), tipografías con su papel, concepto de composición con wireframe ASCII, una pieza
   propia y principios.
4. **Revisa el plan contra [reference/defaults.md](reference/defaults.md).** Para cada coincidencia,
   cámbiala o explica por qué el brief la justifica. Deja escrito qué cambiaste y por qué.
5. Guarda `{pantalla}.direction.md` con una sección «Lo que se rehúsa».
6. Si la pantalla va a Stitch o a Claude Design, traduce la dirección a un bloque «Visual
   Direction» que va antes del prompt (ver [reference/direction.md](reference/direction.md)).
7. **La dirección no se da por buena sin verificación.** Cuando haya resultado (candidato o
   código), se pasa por `verify`.

## `/design-review verify <pantalla>`

1. **Comprueba que existe el brief.** Sin brief, el revisor no sabe qué tenía que resolver.
2. Mide desde la raíz del proyecto con `scripts/verify.mjs` (destino: la URL con el servidor de
   desarrollo levantado o el HTML del candidato). Usa el Playwright del proyecto y no instala nada;
   si no lo hay, sale con código 2 y se sigue sin capturas, diciéndolo.
3. Pasa brief, rúbrica, capturas, JSON y código a un **subagente aislado** con el encargo de
   [reference/verify.md](reference/verify.md). Quien diseñó no se revisa.
4. Escribe `{pantalla}.verify.md`: veredicto (Block, Needs changes o Approve), tres problemas
   prioritarios, notas, mediciones y hallazgos con su ubicación.
5. Como mucho una ronda de corrección. Después, otra medición con `--previous` y `--sources`:
   una cifra nueva sin fuente es un defecto.

## Cómo encaja en el resto del flujo

Esta skill es la base de EP-16. Otras piezas, en construcción, la consumen:
- `/plan` (UC-9004): crítica de cada candidato de Stitch o Claude Design con
  [reference/rubric.md](reference/rubric.md), en un subagente aislado y con una sola ronda de
  corrección. Mientras tanto, antes de generar una pantalla, ejecuta aquí `brief` y `direction` y
  construye el prompt con los dos ficheros.
- `/implement` (UC-9102): `verify` de cada pantalla implementada después del design-to-code.
  Mientras tanto, ejecútalo aquí antes de cerrar una UC con pantallas.
- `/visual-setup` (UC-9002): proceso de dirección y lista de lo que se rehúsa, a nivel de proyecto.

## Lo que esta skill no hace

- No genera pantallas ni código: prepara el criterio con el que otros los generan y comprueba
  lo que sale.
- No sustituye al sistema de diseño: con tokens, manda el sistema.
- No inventa datos para que una pantalla «quede completa»: marca lo que falta.
- No instala skills de terceros: su contenido está incorporado aquí, con atribución.

## Fuentes y licencias

El proceso y las listas condensan trabajo de terceros, con licencia MIT y Apache-2.0:
frontend-design (Anthropic), Impeccable (Paul Bakaus), make-interfaces-feel-better
(Jakub Krehel), emil-design-eng (Emil Kowalski) y taste-skill (Leonxlnx). Autor, origen,
versión, licencia y qué se tomó de cada una: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
