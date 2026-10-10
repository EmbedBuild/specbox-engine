# El sistema del proyecto dentro de un lienzo de Claude Design (UC-9204)

> Fecha: 2026-10-10 · Claude Code 2.1.288 · tipos Design (release `1791586906-56be`) y Design System
> (release `1791558544-c1cf`).
> La prueba se hizo con un sistema y un lienzo de prueba, privados, en la cuenta del owner. El sistema
> salió de los tokens de Tinta (`tests/fixtures/design_system/tinta.design-system.tokens.json`) y de
> dos componentes compilados con esbuild.

## Por qué hacía falta

En la prueba del 2026-10-09, el lienzo con el sistema de embed.build tuvo que declarar a mano, en cada
artboard, las 52 variables que usa la hoja del sistema. El `bundle.css` de embed.build dice que sus
valores salen de un `tokens.css` que el sistema no publica, y la página del tipo solo genera ese fichero
cuando alguien guarda una edición en ella. El sistema de SpecBox sí funciona tal cual, porque su
`bundle.css` (compilado con Tailwind) declara sus variables.

## Lo que publica `/visual-setup` ahora

`ds-artifact.mjs build` deja en `project/`:

| Fichero | Qué lleva |
|---|---|
| `tokens.json` | Los tokens validados contra la gramática del tipo. Con Tinta no se cae ninguno |
| `tokens.css` | Variables del primer tema en `:root, [data-theme="light"]`, las del oscuro en `[data-theme="dark"]`, los demás tokens en `:root` y una clase por estilo de texto. La primera línea, `/* <título> — generated from tokens.json */`, es la que la página reconoce para regenerarlo |
| `components/bundle.css` | `@import` de Google Fonts con los pesos que usan los estilos, y la hoja de los componentes |
| `components/bundle.js` | El script clásico de esbuild (`--format=iife --global-name=<Ns>`, React como global) con su cabecera `@ds-bundle` |
| `components/<Comp>/README.md` · `preview.html` | Las props de cada componente, leídas de su interfaz en los tipos, y una vista previa |
| `README.md` | Tablas que nombran tokens, «Lo que se rehúsa» del DESIGN.md y «Consuming this system» |
| `components/Cover/preview.html` · `design-system.json` | La portada y el índice |

El servidor acepta publicar `tokens.css`. Cuando la página del sistema se abre, vuelve a guardar el
índice (`design-system.json`, con las claves ordenadas), pero no toca `tokens.css`.

## AC-01: el lienzo pinta con los valores del sistema sin declarar variables

El lienzo instala el sistema como dice la guía del tipo Design:
- copias en el servidor de `tokens.json`, `tokens.css` y `components/bundle.css`;
- su registro en `designSystems`.

El artboard enlaza `ds/tintaprueba/tokens.css` y `components/bundle.css`, y su `<helmet>` solo lleva
`body{margin:0}`. Congelado con `/design-review import` y abierto sin red ni JavaScript, sus estilos
calculados son los de los tokens:

| Elemento | Calculado | Token |
|---|---|---|
| Fondo y texto | `#f7f6f4` / `#1a1b1e` | `paper-000` / `ink-900` |
| Título | 24/30 px, 600, IBM Plex Sans, −0,01em | clase `display-lg` |
| Tarjeta | `#ffffff`, radio 6 px | `paper-100`, `radius-md` |
| Chip «En revisión» | `#fbf0dc` / `#92400e` | `status-review-bg` / `status-review-text` |
| Botón | `#1a1b1e` / `#ffffff`, 13 px 500 | `accent` (alias de `ink-900`) / `on-accent`, clase `label` |
| Dato | IBM Plex Mono 12 px | clase `data-sm` |
| Tipografías cargadas | IBM Plex Sans 400/500/600 e IBM Plex Mono 400 | — |

Falta comprobar en el editor que el menú de tema enseña los colores y los estilos de texto del
sistema. Lo comprueba el owner abriendo el lienzo.

## AC-02: el lienzo monta los componentes compilados

Con `Button` y `StatusBadge` compilados con esbuild y publicados en el sistema, un segundo artboard
monta `<x-import component-from-global-scope="TintaPrueba.StatusBadge" status="review">` y
`TintaPrueba.Button`. Congelado, el DOM ya no tiene `<x-import>`, sino los componentes reales, con sus
clases y los colores de los tokens:
- `tp-badge--review` sale en `#fbf0dc` / `#92400e`;
- `tp-btn--primary` sale en `#1a1b1e` / `#ffffff`, con 44 px de alto;
- `tp-btn--secondary` lleva su borde de `line-300`.

## AC-03: ¿sirve el camino de `DesignSync`?

Pendiente: la prueba necesita que el owner arranque `/design-sync`. `DesignSync` solo se usa dentro de
esa skill.

Lo que ya se sabe:
- ningún proyecto local ancla hoy un proyecto de claude.ai/design (`veg.claude_design.projectId`);
- `Artifact list` con el tipo Design System enseña solo artifacts;
- la instalación en un lienzo pide una dirección `https://claude.ai/artifact/<id>`.
