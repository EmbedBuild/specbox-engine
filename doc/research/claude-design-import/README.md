# Traer las pantallas de un lienzo de Claude Design al proyecto (UC-9202)

> Fecha: 2026-10-10 · Claude Code 2.1.288 · Chrome del sistema con el Playwright de un proyecto
> Lienzo de prueba: «Seguimiento de propuestas», privado, versión `1791625997-6470`. Lo creó `/design`
> el 2026-10-09 con el sistema de diseño de embed.build: un artboard a 1440 px y otro a 390 px.

## El problema

`/design` crea lienzos, pero no importa: siempre crea uno nuevo. La exportación oficial (Compartir ›
Exportar › HTML) es un paquete que se desempaqueta con JavaScript y lleva el motor del lienzo, y
además es un paso manual. Un design-to-code que parta de ahí arrastra el motor o tiene que adivinar.

## Lo que se comprobó

| Pregunta | Resultado |
|---|---|
| ¿Qué sirve un lienzo? | `project/canvas.json` (índice v3), un `project/<artboard>.dc.html` por artboard, la copia del sistema en `project/ds/<carpeta>/` y, del tipo Design, `artifact-type/dc-runtime.js` (188 KB: React 18 y el motor) |
| ¿Se pinta fuera de claude.ai? | Sí. Se sirve la carpeta en local con el motor del lienzo en lugar de `support.js` y se abre con Playwright |
| ¿Se puede congelar? | Sí. Se serializa el DOM ya pintado sin scripts, sin la hoja que el motor usa para editar, sin las marcas de plantilla y sin el `<span>` de cada hueco |
| ¿La vista congelada es igual? | **0 píxeles distintos.** A 1440 da 1440×1647 y a 390 da 390×3010 frente a la versión viva. Se abrió desde el disco, sin red y sin JavaScript (y a 390, con la emulación de móvil que usa `verify`) |
| ¿Las tipografías sin conexión? | Las hojas de Google Fonts se bajan una vez al importar, solo `latin` y `latin-ext`, que cubren el español, «» y €. Las fuentes van en data: dentro de `fonts/<huella>.css`. Chrome no carga fuentes de `file://` a `file://`, pero sí hojas, y estas llevan las fuentes dentro |

Hubo dos trampas:
- **El ancho de 390.** La fuente del lienzo no trae `<meta viewport>`. Con la emulación de móvil,
  Chrome maquetaba el artboard de 390 a 980 px. El lienzo lo pinta en un iframe de su ancho, así que el
  congelado pinta sin emulación y la vista añade `viewport`.
- **El charset.** El motor mete su hoja antes que la cabecera de la fuente. Con el banner de origen
  delante, `<meta charset>` quedaba pasado el primer KB. La vista lo pone el primero (byte 510).

## Lo que deja `/design-review import`

```
doc/design/propuestas/
├── canvas/Main.dc.html, canvas/Movil.dc.html   fuentes, tal cual
├── Main.html (60 KB), Movil.html (49 KB)        vistas congeladas, sin motor
├── fonts/8da9037d995c.css                       Instrument Sans y JetBrains Mono, sin conexión
├── canvas.html                                  vista del lienzo con dirección, versión y fecha
└── claude-design.json                           manifiesto
```

La importación de los dos artboards tarda 3,9 s.

## Idempotencia (AC-03)

| Paso | Estados | Escrito |
|---|---|---|
| Primera importación | Main `nuevo`, Movil `nuevo` | 6 ficheros + tipografías |
| Segunda, mismo lienzo | `igual`, `igual` (`sin_cambios`) | nada: mismos mtime y tamaño de todos los ficheros |
| Lienzo con un texto de Movil cambiado | Main `igual`, Movil `cambiado` | `canvas/Movil.dc.html`, `Movil.html`, `canvas.html`, `claude-design.json` |

Main conserva la versión de la que salió (`version=1791625997-6470` en su primera línea) y Movil lleva
la nueva. La huella de cada artboard junta:
- su fuente;
- su marco en el lienzo;
- la copia del sistema de diseño.

Por eso un cambio en el sistema también se detecta.

## Design-to-code desde la vista congelada (AC-04)

Un subagente hizo el design-to-code de `Movil.html` en un sitio estático (HTML, CSS con las variables de
los tokens de embed.build y un JS propio para filtros y selección). Siguió las reglas del Paso 4 de
`/implement`: la disposición sale de la vista y los valores, de los tokens. Resultado:

| Comprobación | Resultado |
|---|---|
| Piezas del motor en el código (`support.js`, `<x-dc>`, `DCLogic`, `<sc-*>`, `<dc-import>`, `<x-import>`, `/_blob/`, `data-dc-*`) | ninguna |
| Peticiones al abrir la página | sus ficheros y Google Fonts; **ninguna** a claude.ai ni al motor |
| Errores en consola y selección de una propuesta | ninguno; el detalle cambia |
| Puerta de diseño con la entrada real de Claude Code | `exit 0` |
| `verify` a 1440 y 390 | `scrollWidth` 1440 y 390, sin hallazgos de las reglas, 3,2 s |

El subagente encontró tres defectos del lienzo y los corrigió en el código:
- la selección de «Hoy toca llamar» no se ve;
- el logo está por debajo del mínimo del sistema;
- el chip neutro desaparece en la fila seleccionada.

Coinciden con lo que vio el revisor aislado del 2026-10-09: la vista congelada sirve también para
revisar.

## Lo que el motor no es

`dc-runtime.js` es de Anthropic y viene en cada lienzo. La importación lo lee del lienzo en su versión y
lo usa solo para pintar en local:
- no se copia al proyecto;
- no se versiona en el engine;
- la prueba de congelado real lo toma de `SPECBOX_DC_RUNTIME` y se salta sin él.
