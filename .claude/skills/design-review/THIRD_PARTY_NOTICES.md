# Avisos de terceros

La skill `/design-review` incorpora contenido derivado de cinco proyectos de terceros, usado según
sus licencias originales.

**Ningún fichero de esos proyectos se copia tal cual.** Su contenido se ha traducido al español,
condensado, reordenado y combinado con criterio propio de SpecBox y con resultados de la prueba
UC-9001 (`doc/research/design-review-benchmark/`). Cada referencia de la skill dice al principio de
qué fuentes sale.

Versiones revisadas el 2026-10-09, a partir de copias locales de cada repositorio.

| Proyecto | Autor | Origen | Versión revisada | Licencia | Texto de la licencia |
|---|---|---|---|---|---|
| frontend-design | Anthropic | https://github.com/anthropics/skills (`skills/frontend-design`) | copia del 2026-10-09 | Apache-2.0 | [licenses/Apache-2.0.txt](licenses/Apache-2.0.txt) |
| Impeccable | Paul Bakaus (Copyright 2025 Paul Bakaus) | https://github.com/pbakaus/impeccable | 4.5.2 | Apache-2.0 | [licenses/Apache-2.0.txt](licenses/Apache-2.0.txt) |
| make-interfaces-feel-better | Jakub Krehel (Copyright (c) 2026 Jakub Krehel) | https://github.com/jakubkrehel/make-interfaces-feel-better | copia del 2026-10-09 | MIT | [licenses/MIT-make-interfaces-feel-better.txt](licenses/MIT-make-interfaces-feel-better.txt) |
| emil-design-eng (de emilkowalski/skills) | Emil Kowalski (Copyright (c) 2026 Emil Kowalski) | https://github.com/emilkowalski/skills | copia del 2026-10-09 | MIT | [licenses/MIT-emilkowalski-skills.txt](licenses/MIT-emilkowalski-skills.txt) |
| taste-skill (design-taste-frontend v2) | Leonxlnx (Copyright (c) 2026 Leonxlnx) | https://github.com/Leonxlnx/taste-skill | v2 | MIT | [licenses/MIT-taste-skill.txt](licenses/MIT-taste-skill.txt) |

## Qué se tomó de cada uno y dónde está

**frontend-design (Anthropic, Apache-2.0).** Modificado: traducido, condensado y combinado.
- El proceso en dos pasadas (plan; revisión contra el default; construcción) → `reference/direction.md`.
- La lista calibrada de rasgos de la UI generada (crema con terracota, negro con acento ácido, kit de
  tarjetas, eyebrows, puntos medios, `→`) → `reference/defaults.md`.
- Las pautas de copy (la acción da nombre al botón, los errores dicen qué pasó y cómo seguir) →
  `reference/defaults.md` y `reference/rubric.md`.

**Impeccable (Paul Bakaus, Apache-2.0).** Modificado: traducido, condensado y combinado.
- Los modos de superficie Operate, Persuade y Read, con sus límites y comprobaciones →
  `reference/surfaces.md`.
- La lista «Refuse» y las verificaciones del craft-floor → `reference/defaults.md` y
  `reference/rubric.md`.
- La idea de un contrato de dirección que se escribe antes de construir → `reference/direction.md`.
- El fichero NOTICE de Impeccable atribuye a terceros solo sus referencias de iOS y Android, que esta
  skill no usa.

**make-interfaces-feel-better (Jakub Krehel, MIT).** Los principios medibles de pulido (áreas de
pulsación de 44 y 40 px, radios concéntricos, `tabular-nums`, nada de `transition: all`) →
criterio 6 y criterio 8 de `reference/rubric.md`.

**emil-design-eng (Emil Kowalski, MIT).** Las reglas de movimiento (menos de 300 ms, `ease-out` en
las respuestas, nunca `ease-in`, nada desde `scale(0)`, sin animación en interacciones de alta
frecuencia, `prefers-reduced-motion`) → criterio 8 de `reference/rubric.md` y `reference/defaults.md`.

**taste-skill (Leonxlnx, MIT).** Las prohibiciones concretas de paleta y tipografía por defecto (beige
con latón u ocre, Fraunces e Instrument Serif como display, la raya como recurso de estilo) →
`reference/defaults.md`.

## Avisos de licencia

- **Apache-2.0** (frontend-design, Impeccable). Licensed under the Apache License, Version 2.0. El
  texto completo está en [licenses/Apache-2.0.txt](licenses/Apache-2.0.txt). El contenido derivado se
  ha modificado según lo descrito en «Qué se tomó de cada uno».
- **MIT** (make-interfaces-feel-better, emil-design-eng, taste-skill). Los avisos de copyright y de
  permiso se conservan en los ficheros `licenses/MIT-*.txt`.
