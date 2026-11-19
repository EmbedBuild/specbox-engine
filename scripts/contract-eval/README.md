# ¿Detectan más fallos las pruebas con contrato? (US-128 · UC-12801 AC-04)

Una medición con fallos sembrados para decidir si AG-09a escribe el contrato de cada criterio por
defecto (AC-05). Método tomado de `doc/plans/fable5_evaluation_plan.md` del orquestador: misma tarea,
misma base, dos pasadas, revisión humana y un informe.

## La regla, fijada antes de empezar

El contrato gana si, sumando las 5 UC y las dos pasadas, el brazo **B** (contrato primero) detecta
**más mutantes** que el brazo **A** (desde los criterios) **sin más falsos positivos** (pruebas que
fallan sobre el código bueno). Si gana, AG-09a lo escribe siempre y la medida `contract_first` nace
en «warn»; si no, el contrato queda como opción y la medida nace en «off» (plan, §3.5).

## Las 5 UC

| UC | Módulo | Qué decide |
|---|---|---|
| UC-12604 | `server/plan_contract.py` | El contrato del plan: criterios y ficheros por fase |
| UC-12603 | `server/closed_files.py` | Los ficheros de una UC cerrada y qué UC tocaron unas rutas |
| UC-12502 | `server/approval.py` | La huella de los criterios aprobados y su estado |
| UC-12305 | `server/coordination/enforcement.py` (marcas «por decidir») | Qué marcas detienen una UC |
| UC-12606 | `server/impact_radius.py` | El radio de impacto de un cambio |

## Los pasos

1. **Mutantes** (`mutants/<UC>/mutants.json`): por UC, un agente aislado escribe 8 a 10 cambios de
   comportamiento a partir de los criterios (límites, ramas que faltan, orden, casos ignorados). Se
   registran **antes** de generar ninguna prueba (commit propio).
2. **Revisión de equivalentes**: `python scripts/contract-eval/run.py --check-mutants` aplica cada
   mutante en una copia, comprueba que el módulo importa y si lo detectan las pruebas que ya existían.
   Los que no detectan se revisan a mano; un mutante que no cambia ningún resultado se marca
   `"equivalent": true` con su motivo y no cuenta.
3. **Dos brazos × dos pasadas × 5 UC**: subagentes aislados que no ven los mutantes, las pruebas del
   módulo ni lo que generan los demás. Mismo encargo y mismo modelo; solo cambia el paso del contrato:
   - **A**: genera las pruebas de aceptación desde los criterios de la UC (como hoy).
   - **B**: escribe antes `contract.json` (pre, post y undefined por criterio) y genera las pruebas
     desde él, citando `pre` y `post` en cada una.
   Cada pasada deja `test_generated.py`, `meta.json` (tokens y segundos) y, en B, `contract.json`
   en `.quality/evidence/UC-12801/contract-eval/generated/<UC>/<A|B>-p<N>/`.
4. **Medición**: `python scripts/contract-eval/run.py` ejecuta cada fichero sobre el código bueno
   (falsos positivos) y con cada mutante no equivalente (detectado si falla alguna prueba que pasaba).
   Escribe `results.jsonl` y `report.md` en `.quality/evidence/UC-12801/contract-eval/`, que se
   adjuntan como evidencia `ag09` de la UC.

## El resultado (2026-11-19)

| Brazo | Mutantes detectados | Falsos positivos | Pruebas por pasada | Tokens por pasada | Segundos por pasada |
|---|---|---|---|---|---|
| A, desde los criterios | 91/100 | 0 | 41,9 | 185 666 | 109,9 |
| B, contrato primero | 94/100 | 0 | 58,4 | 202 268 | 196,6 |

**El contrato gana** según la regla: B detecta 3 mutantes más sin más falsos positivos. El margen es
pequeño, y B escribe más pruebas (58 frente a 42 por pasada), que explica parte de la diferencia. Por
UC, sumando las dos pasadas: B gana en UC-12305 (20 frente a 19), UC-12502 (20 frente a 18) y
UC-12603 (20 frente a 19); empata en UC-12606 (18 y 18: los dos brazos dejan pasar M06, el orden entre
«documentación» y «contrato»), y pierde por uno en UC-12604 (16 frente a 17: B se deja M03 y M05 en
las dos pasadas). El detalle está en
`.quality/evidence/UC-12801/contract-eval/report.md` y `results.jsonl`.

## Límites

- Los subagentes trabajan en la copia del repositorio: el aislamiento (no leer `tests/` ni
  `scripts/contract-eval/`) es una instrucción, no una barrera. Cada pasada lo declaró en su informe al
  orquestador; esos informes no se guardan en la evidencia.
- Los mutantes son de un agente, no de una herramienta de mutación (`mutmut` metería una dependencia
  y cambios sintácticos que no prueban los criterios); su sesgo se compensa con la revisión de
  equivalentes y con que los dos brazos se miden contra los mismos.
- Cinco UC del propio engine, todas de lógica pura en Python: el resultado dice algo de este tipo de
  código, no de una interfaz.
- Una pasada del brazo A (UC-12305, pasada 2) leyó el PRD del orquestador antes de que respondiera el
  MCP: trae los mismos criterios que `get_uc`, no pruebas ni mutantes.
- Los subagentes recibieron el `CLAUDE.md` del engine, que describe en prosa varias de estas UC; lo
  recibieron los dos brazos por igual.
