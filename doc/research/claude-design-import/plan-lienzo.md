# /plan crea el lienzo de una feature (UC-9201)

> Fecha: 2026-10-10 · Claude Code 2.1.288 · tipo Design (release `1791586906-56be`)
> Prueba real con una feature de prueba de dos pantallas del panel: una cola de aceptación de UC y el
> detalle de una UC para aceptarla. Los datos son del board de EmbedBuild/specbox-manager. El sistema es
> el de la prueba de UC-9204: tokens de Tinta y dos componentes compilados, `Button` y `StatusBadge`.

## Lo que hizo /plan (Paso 6.0b)

1. **Precondiciones:**
   - la herramienta `Artifact` en la sesión;
   - el tipo Design en el listado de tipos;
   - la sesión de claude.ai (la creación no falló);
   - el sistema publicado (`veg.claude_design.designSystem`).
2. **Briefs** de `/design-review` para las dos pantallas. Cada uno lleva el usuario, las tres preguntas
   y datos reales del board: 1 UC pendiente y 7 aceptadas hoy, comprobadas una a una con `get_uc`.
3. **Un lienzo**, creado con el tipo Design y sin ficheros.
4. **`canvas.mjs scaffold`:**
   - 4 artboards: `Main.dc.html` y `cola-390.dc.html` para la cola; `detalle.dc.html` y
     `detalle-390.dc.html` para el detalle;
   - a 1440 y 390, 80 px entre columnas y una fila por pantalla;
   - un título por fila y una nota con las tres preguntas de cada brief;
   - el registro del sistema y sus cuatro ficheros, que copió el servidor (`tokens.json`, `tokens.css`,
     `components/bundle.css` y `components/bundle.js`);
   - `claude-design.json`, con qué pantalla es cada artboard.
5. **Artboards**:
   - pintan con `var(--token)` y las clases de los estilos de texto del sistema;
   - **ningún artboard declara variables ni `:root`**;
   - los botones y las etiquetas de estado son los componentes reales del sistema, montados con
     `<x-import>`. En las vistas congeladas: 1 botón y 1 etiqueta en la cola y 4 y 4 en el detalle,
     todos `tp-btn`/`tp-badge` y ningún `<button>` suelto;
   - los artboards de 390 montan la página fluida de 1440 con `<dc-import>`.
6. **Anotación en el plan:**

   | Pantalla | Artboard 1440 | Artboard 390 | Brief |
   |---|---|---|---|
   | cola | `Main.dc.html` | `cola-390.dc.html` | `doc/design/cola-aceptacion/cola.brief.md` |
   | detalle | `detalle.dc.html` | `detalle-390.dc.html` | `doc/design/cola-aceptacion/detalle.brief.md` |

## La crítica (Paso 6.4b) sobre la copia congelada

El lienzo no se abre ni se captura. `/design-review import --out <scratch>/critica` lo congela, `verify`
lo mide a 1440 y 390, y un revisor aislado por pantalla lo puntúa con la rúbrica.

| Pantalla | Primera revisión | Tras una ronda | Lo que cambió |
|---|---|---|---|
| Cola | 28/40 · Block | **32/40 · Needs changes** | Estados visibles, la misma estructura en todas las filas, «criterios cumplidos» con su evidencia y datos comprobados en el board |
| Detalle | 29/40 · Block | **29/40 · Needs changes** | Sin datos ajenos al brief, evidencia enlazada a su informe, áreas de pulsación de 44 px, foco visible, acciones también al final, estado de carga |

`verify` no encontró desbordamiento en ningún caso. Los avisos que quedan, `estados-controles`, son del
`Button` del sistema de prueba, que no tiene estilos de pulsado ni desactivado. Los dos revisores lo
atribuyen al sistema, no a la pantalla.

### Hallazgo: los estados no se veían

En la primera ronda los dos revisores bloquearon por los estados (vacío, carga, error, aceptada), y los
estados estaban: el artboard los tiene como una opción (`estado`) en su `data-props`. Pero la copia
congelada solo pinta el valor por defecto.

Se arregló en el proceso, no en la pantalla:
- `canvas.mjs import --states estado=vacía,cargando,error` congela cada valor como vista aparte
  (`Main@vacia.html`…);
- usa un artboard auxiliar que monta el original con `<dc-import>` y se borra al terminar;
- la crítica de 6.4b pasa esas vistas al revisor, y el design-to-code también las recibe.

En la segunda ronda los dos revisores juzgaron los estados y encontraron defectos reales en ellos: un
«0» falso en carga y en error, y el aviso de error lejos del botón pulsado. Antes eran invisibles.

### Lo que no se hizo

- Una segunda ronda de corrección: la regla es una sola ronda, y los defectos que quedan son para la
  aceptación humana del lienzo o para `/implement`.
- Arreglar el `Button` del sistema de prueba: no es de un proyecto real.
