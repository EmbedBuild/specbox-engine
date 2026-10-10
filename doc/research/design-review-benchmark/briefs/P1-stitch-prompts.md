# Prompts de Stitch para P1 (AC-02 de UC-9001)

- Modelo: `GEMINI_3_8_FLASH`. Dispositivo: `DESKTOP`.
- Cada candidato va en un proyecto nuevo para que el sistema de diseño automático de uno no contamine
  al otro:
  - S1: `9698277924063554485`
  - S2: `9275310487958538181`
- El prompt base sigue la plantilla de `/plan` (Paso 6.2), sin sistema de diseño.
- S2 es el mismo prompt base precedido del bloque «Visual Direction», que sale del paso de dirección
  del diseñador de V2 en P1.

## Prompt base (S1)

```
Design a race-weekend operations screen for PaddockManager, the platform the Spanish Motorcycling Federation (RFME) uses to run the Spanish Superbike Championship (ESBK).

Design System:
- Theme: Light Mode

Screen: Participantes de la prueba (ESBK 2026 · Navarra I · Circuito de Navarra, Los Arcos · 8 y 9 de mayo)

Used by the race director / organizer on a laptop in race control, several times a day during the race weekend, to answer in seconds: (1) who still has to pass the bike or equipment technical verification and in which box they are; (2) who has something to sort out at the office before going on track (provisional or foreign licence, bike without sticker, helmet without FIM QR, Excel rows that were not imported); (3) how each category is doing (verified vs pending). All UI copy in Spanish (Spain).

Content (real data):
- Header: event name, search by rider / number / team, actions "Importar Excel RFME", "Añadir participante", "Imprimir PDF".
- Verification by category: 129 participants, 104 verified (81 %). Yamaha R7 Cup 29 (6 pending), ESBK Talent 25 (4), PreTalent 14 (3), Supersport 300 14 (3), Sportbike 13 (3), Superstock 1000 11 (2), Superstock 600 10 (2), Supersport 9 (1), Superbike 4 (1).
- Participants table (129 rows; search, filter by category and by pending, sort by number). Rows to show: #7 Iker Valdemoro Sanz, Superbike, Honda CBR1000RR-R, Valdemoro Racing, box 12, bike verified 08:15, equipment verified 08:20 / #39 Bruno Lavín Ortuño, Superstock 1000, BMW M1000RR, Team Ortuño SBK, box 21, bike pending / #21 Pau Ferrandis Llobet, Sportbike, Kawasaki Ninja 400, box 14, provisional licence, equipment pending / #21 Hugo Cebrián Montaner, Yamaha R7 Cup (Rookie), Yamaha R7, Carpas Yamaha R7, bike without sticker, both pending / #15 Lucía Arranz Peñalver, ESBK Talent, Honda NSF250R, box 25, verified, minor (14) / #8 Mateo Rubial Gaspar, PreTalent, Beon, Carpas Paddock, no team, helmet without FIM QR, equipment pending / #67 Théo Marchandeau (FRA), Superstock 600, Yamaha R6, box 3, FFM licence, equipment pending / #44 Nerea Olmedilla Ruiz, Supersport 300, brand "SIN MARCA" in the Excel, box 18, bike pending.
- Detail panel for the selected rider: number, category, bike, team, box, licence, country, bike and equipment verification with time or pending, helmets (sticker, FIM QR), office warnings, actions "Editar participante" and "Asignar box".
- "Filas del Excel que no entraron" (3 of 132): row 46 Daniel Escartín Moreno (#52), category "Supersport NG" does not exist in the championship; row 88 Álvaro Cifuentes Rey (#33, Superstock 600), missing licence; row 131 Iker Valdemoro Sanz (#7), duplicated row.

States to show:
- Loaded state with the data above
- Empty state (no participant matches the search)
- Loading state (skeleton) and an inline error (Excel import failed)

Layout: Desktop (1440px wide)
Icons: Material Symbols
```

## Bloque de dirección antepuesto en S2

Sale del paso de dirección del diseñador de P1-V2 (sus notas: plan, revisión contra lo que haría por
defecto y decisiones), traducido al formato de prompt. Después de este bloque va el prompt base
completo, sin cambios.

```
Visual Direction (decided before designing; follow it instead of default dashboard patterns):
- Concept: the race-control office during the weekend. Colour appears only where someone has to act; what is already done stays grey. One signature piece: a grid per category where each mark is one participant (grey = verified, orange = pending), under a headline that states the action: "Faltan 25 por verificar".
- Palette: Paper #FFFFFF (work surface), Concrete #EDEFF1 (side column and selected row), Asphalt #1E2329 (text, primary button, focus), Graphite #59616A (secondary text), Marshal orange #F25C05 only for "pending verification" (with asphalt text on it), Stamp violet #5B3CC4 only for office issues (paperwork), Red #B3261E only for the import error. No green, no blue.
- Typography: Saira Condensed 600/700 for race numbers, titles and figures (like a number plate); Atkinson Hyperlegible 400/700 for all UI text.
- Layout: header (brand + local time | "Participantes" + event | search, Importar, Imprimir, Añadir). First row: the status grid by category next to "3 filas del Excel no entraron" on concrete. Second row: list with filters and an 8-column table, box right before the two verification columns, plus a sticky detail panel on concrete. Last row: the other states. Everything left-aligned.
- Refuse: three KPI cards with progress bars, Inter and a blue primary button, traffic-light green/amber/red chips, white cards with shadows everywhere, metadata joined with middle dots, uppercase table headers.
```

## Incidencias de la generación

- Las dos llamadas a `generate_screen_from_text` superaron el tiempo de espera del cliente. S1 apareció
  más tarde en su proyecto.
- En S2, la herramienta MCP `list_screens` devolvió vacío durante más de una hora, aunque el proyecto
  ya tenía sistema de diseño y miniatura. La API REST (`GET /v1/projects/{id}/screens`) sí mostraba las
  pantallas: dos terminadas y una en estado «Generating Screen…». Esa pantalla a medio generar parece
  vaciar el listado del MCP.
- Las dos pantallas terminadas de S2 salen de generadores distintos de Stitch: `figaro_agent`, que
  diseña a partir del prompt, y `HatterAgent`, que hace una «recreación». Para comparar en igualdad se
  usa la de `figaro_agent` (`69986d29e0634e4d847a0cab9e7d1653`), el mismo generador que produjo S1
  (`e5287e6813f345368af80c8b4437f900`).
