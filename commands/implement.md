# /implement (Global)

Autopilot de implementacion: lee un plan, crea rama, ejecuta todas las fases, genera diseños si aplica, valida con QA, commitea y crea PR.

## Uso

```
/implement [plan]
```

**Origenes soportados:**
- `nombre_del_plan` → Busca `doc/plans/{nombre}_plan.md`
- `doc/plans/mi_plan.md` → Path directo al archivo del plan
- Sin argumento → Lista planes disponibles en `doc/plans/` y pregunta cual ejecutar

---

## Paso 0: Cargar y Validar Plan

### 0.1 Localizar el plan

```
¿Que recibi?
├── nombre_del_plan → Buscar doc/plans/{nombre}_plan.md
├── path directo → Leer directamente
└── sin argumento → Listar doc/plans/*.md y preguntar
```

```bash
# Listar planes disponibles
ls doc/plans/*_plan.md 2>/dev/null
```

**Si no hay planes** → Informar: "No hay planes en doc/plans/. Ejecuta /plan primero."

### 0.2 Parsear el plan

Leer el archivo del plan completo y extraer:

| Campo | Donde encontrarlo | Obligatorio |
|-------|-------------------|:-----------:|
| Titulo | `# Plan: [titulo]` (primera linea H1) | Si |
| Resumen | Seccion `## Resumen` | Si |
| Fases | Secciones `### Fase N:` | Si |
| Componentes UI | Seccion `## Analisis UI` o `## Componentes UI` | No |
| Widgets a crear | Subseccion `### Widgets a Crear` | No |
| Archivos a crear/modificar | Seccion `## Archivos a Crear/Modificar` | No |
| Agentes involucrados | Referencias a AG-XX en las fases | No |
| Comandos finales | Seccion `## Comandos Finales` | No |
| Diseños Stitch | Referencias a `doc/design/` o pantallas Stitch | No |

### 0.3 Detectar si requiere diseño

**Regla de decision:**

```
¿El plan tiene diseños Stitch?
├── SI: Referencia a doc/design/{feature}/*.html
│   ├── ¿Existen los HTML? → Ir a Paso 4 (design-to-code)
│   └── ¿No existen? → Generar con Stitch (Paso 3)
├── SI: Seccion "Diseños Stitch" con pantallas listadas
│   └── Mismo flujo: verificar existencia → generar si faltan
└── NO: No hay referencias a diseño
    └── Saltar directamente a Paso 5 (implementacion)
```

### 0.4 Detectar stack tecnologico

```bash
# Detectar stack del proyecto actual
cat pubspec.yaml 2>/dev/null | grep -E "flutter:|dependencies:"  # Flutter
cat package.json 2>/dev/null | grep -E "react|next"              # React/Node
cat pyproject.toml 2>/dev/null | grep -E "fastapi|django"        # Python
ls .clasp.json appsscript.json 2>/dev/null                       # Google Apps Script
```

### 0.5 Validacion pre-vuelo

Antes de ejecutar, verificar:

- [ ] El plan tiene al menos una fase con tareas
- [ ] El stack del proyecto es detectable
- [ ] No hay cambios sin commitear (`git status --porcelain`)
- [ ] La rama main/master esta actualizada

```bash
# Verificar working tree limpio
git status --porcelain

# Verificar rama actual
git branch --show-current

# Actualizar main
git fetch origin
```

**Si hay cambios sin commitear** → Advertir al usuario y preguntar si continuar (puede perder contexto).

**Si no esta en main** → Advertir y preguntar si crear la rama desde la rama actual o desde main.

---

## Paso 1: Crear Rama de Feature

### 1.1 Derivar nombre de rama

Del titulo del plan, generar nombre de rama:

```
Plan: "Gestion de Propiedades"  → feature/gestion-de-propiedades
Plan: "Auth con Google OAuth"   → feature/auth-con-google-oauth
Plan: "Refactor DataSources"    → feature/refactor-datasources
```

**Reglas de naming:**
- Prefijo: `feature/` (siempre)
- Titulo en kebab-case (minusculas, guiones)
- Sin caracteres especiales ni acentos
- Max 50 caracteres despues del prefijo

### 1.2 Crear y cambiar a la rama

```bash
# Crear rama desde main (o rama base)
git checkout -b feature/{nombre-del-plan} main

# Verificar
git branch --show-current
```

**Si la rama ya existe** → Preguntar al usuario: ¿Continuar en la rama existente o crear nueva con sufijo?

---

## Paso 2: Orquestacion por Sub-Agentes (Aislamiento Estricto)

> **REGLA**: El orquestador NUNCA implementa codigo. Solo planifica, delega y consolida.
> Ver `rules/GLOBAL_RULES.md` seccion "Aislamiento Estricto del Orquestador".

### 2.1 Mapeo de fases a sub-agentes

Cada fase del plan se ejecuta en un **sub-agente (Task) con contexto limpio e independiente**.
El orquestador le pasa SOLO el contexto minimo necesario.

| Fase del plan | Sub-agente | Contexto que recibe |
|---------------|------------|---------------------|
| Preparacion DB | AG-03 DB Specialist | Schema del plan + patrones infra/{db}/ |
| Diseño UI | AG-06 Design Specialist | Pantallas del plan + config Stitch |
| Design-to-code | AG-02 UI/UX Designer | HTMLs generados + patrones del stack |
| Feature Structure | AG-01 Feature Generator | Seccion de la fase + arquitectura del stack |
| Apps Script | AG-07 Apps Script | Seccion de la fase + patrones GAS |
| n8n / Workflows | AG-05 n8n Specialist | Seccion de la fase + patrones n8n |
| QA / Tests | AG-04 QA Validation | Archivos creados en fases previas (paths) |
| Quality Audit | AG-08 Quality Auditor | Evidence + baseline |
| Acceptance Tests | AG-09a Acceptance Tester | PRD con AC-XX + codigo implementado |
| Acceptance Gate | AG-09b Acceptance Validator | Evidence de AG-09a + audit de AG-08 |

### 2.2 Orden de ejecucion (secuencial)

```
Orquestador: Parsea plan → Extrae fases → Persiste plan en Engram
  |
  ├─ Task(AG-03): DB/Infra → reporte → mem_save → checkpoint
  ├─ Task(AG-06): Diseño Stitch (si aplica) → reporte → checkpoint
  ├─ Task(AG-02): Design-to-code (si aplica) → reporte → checkpoint
  ├─ Task(AG-01): Feature → reporte → mem_save → checkpoint
  ├─ Task(AG-07): Apps Script (si aplica) → reporte → checkpoint
  ├─ Task(AG-05): n8n (si aplica) → reporte → checkpoint
  ├─ Task(Orq.): Integracion (DI, routing) → commit
  ├─ Task(AG-04): QA → reporte → checkpoint
  ├─ Task(AG-08): Quality Audit → veredicto GO/NO-GO
  ├─ Task(AG-09a): Acceptance Tests → evidencia
  ├─ Task(AG-09b): Acceptance Gate → veredicto ACCEPTED/REJECTED
  |
  └─ Orquestador: Consolida → Push → PR → mem_session_summary
```

### 2.3 Protocolo de delegacion por fase

Para cada fase, el orquestador ejecuta este protocolo:

```
1. PREPARAR contexto (max ~8,700 tokens):
   - Extraer SOLO la seccion de la fase del plan (no el plan completo)
   - Cargar overview de arquitectura del stack (~500 words max)
   - Listar archivos que la fase va a modificar (paths, no contenido)
   - Incluir checkpoint de la fase anterior (si existe)

2. LANZAR sub-agente:
   - Usar Task tool con el prompt estructurado (ver Phase Task Template)
   - El sub-agente tiene acceso completo a Read/Write/Edit/Bash
   - El sub-agente ejecuta lint, build, tests dentro de su contexto

3. RECIBIR reporte del sub-agente (formato fijo):
   - files_created: [paths]
   - files_modified: [paths]
   - lint_result: pass|fail
   - phase_status: complete|failed|needs_healing
   - errors: [max 3 lineas]

4. CONSOLIDAR (orquestador):
   - Guardar resumen en Engram: mem_save con tags "phase,{N},{feature}"
   - Guardar checkpoint: .quality/evidence/{feature}/checkpoint.json
   - Si phase_status == "failed" → activar Self-Healing Protocol
   - Si phase_status == "complete" → commit parcial y siguiente fase
   - DESCARTAR todo el contexto del sub-agente excepto el resumen
```

### 2.4 Presupuesto de tokens del orquestador

El orquestador debe mantenerse **por debajo del 15%** de la ventana de contexto:

| Lo que retiene | Tokens estimados |
|----------------|-----------------|
| Plan parseado (titulos de fases) | ~300 |
| Resumen por fase (5 lineas x N fases) | ~150 x N |
| Checkpoints acumulados | ~200 x N |
| Estado actual (feature, branch, stack) | ~100 |
| **Total para 7 fases** | **~2,750 tokens** |

Todo lo demas (contenido de archivos, output de lint, code diffs) vive en sub-agentes o en Engram.

---

## Paso 3: Generar Diseños en Stitch (si faltan)

> Solo ejecutar si el plan referencia diseños que NO existen aun.

### 3.1 Verificar HTMLs existentes

```bash
# Buscar HTMLs de diseño referenciados en el plan
ls doc/design/{feature}/*.html 2>/dev/null
```

### 3.2 Detectar configuracion Stitch

1. Buscar `stitch.projectId` en `.claude/settings.local.json`
2. Si no existe, buscar en `~/.claude/settings.local.json`
3. Si no se encuentra → Preguntar al usuario o usar `mcp__stitch__list_projects`

### 3.3 Generar pantallas faltantes

Para cada pantalla referenciada en el plan que no tenga HTML:

1. Construir prompt siguiendo la plantilla del engine (ver `design/stitch/prompt-template.md`)
2. **SIEMPRE Light Mode** en los prompts
3. Ejecutar generacion:

```
mcp__stitch__generate_screen_from_text(
  projectId: "[stitch.projectId]",
  prompt: "[prompt construido]",
  deviceType: "[stitch.deviceType]",
  modelId: "[stitch.modelId]"
)
```

4. Obtener HTML con `mcp__stitch__get_screen`
5. Guardar en `doc/design/{feature}/{screen_name}.html`
6. Registrar prompts en `doc/design/{feature}/{feature}_stitch_prompts.md`

**Reglas:**
- Una pantalla a la vez (la API tarda minutos)
- NO preguntar entre pantallas (modo autopilot) — generar todas las que falten
- Si falla una pantalla, registrar el error y continuar con las demas
- Reintentar una vez si hay timeout

---

## Paso 4: Design-to-Code (si hay diseños)

> Convertir los HTML de Stitch a codigo del stack del proyecto.

### 4.1 Listar HTMLs disponibles

```bash
ls doc/design/{feature}/*.html
```

### 4.2 Conversion por stack

Para cada HTML de diseño:

#### Flutter
1. Leer HTML y extraer: layout, componentes, colores, espaciado, tipografia
2. Crear widgets en la estructura del feature:
   - `lib/presentation/features/{feature}/widgets/` para widgets especificos
   - `lib/core/widgets/` para widgets reutilizables (si se identifican)
3. Respetar:
   - `AppColors` y `AppSpacing` (nunca hardcodear)
   - Responsividad: mobile/tablet/desktop layouts
   - Clases separadas (NUNCA metodos `_buildX()`)

#### React
1. Leer HTML y extraer: estructura JSX, clases CSS, componentes
2. Crear componentes en:
   - `src/components/features/{feature}/` para componentes especificos
   - `src/components/ui/` para primitivos reutilizables
3. Respetar:
   - Server Components por defecto, `'use client'` solo si necesita interactividad
   - Tailwind CSS para estilos
   - TypeScript obligatorio

#### Google Apps Script
1. Leer HTML y extraer: estructura, estilos, interacciones
2. Crear templates en:
   - `src/html/` o `html/` para templates HtmlService
3. Respetar:
   - `google.script.run` para comunicacion con backend
   - CSS inline o `<style>` en el template
   - `<?!= include('css') ?>` para estilos compartidos

#### Python (FastAPI)
1. Si hay frontend (Jinja2/NiceGUI):
   - Convertir HTML a templates Jinja2 o componentes NiceGUI
2. Si es API-only: saltar design-to-code

### 4.3 Commit parcial de diseños

```bash
git add doc/design/{feature}/
git commit -m "design: add Stitch designs for {feature}"
```

---

## Paso 4.5: Pre-flight Quality Gate

> OBLIGATORIO antes de implementar. Establece el punto de partida medible.

### 4.5.1 Verificar baseline existente

```bash
cat .quality/baseline.json 2>/dev/null
```

**Si no existe** → Ejecutar quality gate audit internamente:
1. Ejecutar lint del stack (DEBE ser 0/0/0 para continuar)
2. Ejecutar tests, medir coverage
3. Generar `.quality/baseline.json`

**Si existe** → Cargar y usar como referencia.

### 4.5.2 Registrar pre-gate

Guardar estado previo en `.quality/evidence/{feature}/pre-gate.json`:

```json
{
  "phase": "pre",
  "timestamp": "[ISO]",
  "lint": {"errors": 0, "warnings": 0, "infos": 0},
  "coverage": {"value": 72.3},
  "tests": {"total": 148, "passing": 148, "failing": 0}
}
```

---

## Paso 5: Ejecutar Fases de Implementacion (Delegacion a Sub-Agentes)

> Cada fase se delega a un sub-agente limpio. El orquestador NO ejecuta codigo.
> Ver Paso 2.3 para el protocolo de delegacion.

### 5.1 Para cada fase del plan

El orquestador lanza un Task por fase con el Phase Task Template:

```
Execute Phase {N}: {phase_name}

CONTEXT:
- Plan: {SOLO la seccion de esta fase, no el plan completo}
- Stack: {stack_name}
- Architecture: {overview del stack, max 500 words}
- Files to modify: {list paths}
- Ownership: Only modify files in {ownership_paths}
- Previous checkpoint: {checkpoint JSON de fase N-1}

RULES:
- Run lint after implementation: {stack_lint_command}
- Quality gate between phases: lint 0/0/0 (BLOQUEANTE), compile (BLOQUEANTE), tests pass (BLOQUEANTE)
- Save checkpoint: .claude/hooks/implement-checkpoint.sh {feature} {N} {phase_name}
- If lint fails, apply self-healing (Level 1 first, then Level 2)

RETURN FORMAT (OBLIGATORIO):
- files_created: [list of paths]
- files_modified: [list of paths]
- lint_result: pass|fail (N errors, N warnings)
- gate_result: {lint, compile, tests} each pass|fail
- errors: [brief description if any, max 3 lines]
- phase_status: complete|failed|needs_healing
```

### 5.1.1 Post-Task (orquestador)

Cuando el sub-agente devuelve su reporte:

```
¿phase_status?
├── complete → Commit parcial + mem_save resumen + siguiente fase
├── needs_healing → Lanzar nuevo Task de healing (ver Self-Healing Protocol)
└── failed → Guardar checkpoint failed + escalar a humano
```

Guardar `.quality/evidence/{feature}/phase-N-gate.json` con los datos del reporte.

### 5.2 Reglas por stack durante implementacion

#### Flutter
```bash
# Despues de cada modificacion .dart
dart fix --apply && dart analyze

# Despues de build_runner (Freezed, etc.)
dart run build_runner build --delete-conflicting-outputs && dart fix --apply
```

#### React
```bash
# Despues de cambios
npx eslint . --fix && npx tsc --noEmit
```

#### Python
```bash
# Despues de cambios
ruff check . --fix && ruff format . && mypy .
```

#### Google Apps Script
```bash
# Despues de cambios
npm run lint && npm run build
```

### 5.3 Commits parciales por fase

Cada fase completada genera un commit:

```bash
# Formato: tipo(scope): descripcion
git add [archivos-de-la-fase]
git commit -m "feat({feature}): {descripcion de la fase}"
```

**Tipos de commit:**
- `feat`: Nueva funcionalidad
- `fix`: Correccion
- `refactor`: Reestructuracion
- `chore`: Configuracion, dependencias
- `test`: Tests
- `design`: Diseños UI

---

## Paso 6: Integracion

> Tareas transversales post-implementacion.

### 6.1 Registrar en DI / Routing / Config

Segun el stack:

| Stack | Accion |
|-------|--------|
| Flutter | Registrar en GetIt/Injectable, anadir GoRoutes |
| React | Actualizar App Router, registrar stores |
| Python | Registrar routers en main.py, actualizar DI |
| Apps Script | Exportar funciones en index.ts, actualizar appsscript.json scopes |

### 6.2 Build final

```bash
# Flutter
dart run build_runner build --delete-conflicting-outputs
dart fix --apply && dart analyze

# React
npm run build

# Python
ruff check . --fix && mypy .

# Apps Script
npm run build
```

### 6.3 Commit de integracion

```bash
git add .
git commit -m "chore({feature}): integration and wiring"
```

---

## Paso 7: QA y Validacion

### 7.1 Ejecutar tests

```bash
# Flutter
flutter test --coverage
lcov -l coverage/lcov.info | tail -1  # Verificar >= 85%

# React
npx jest --coverage --passWithNoTests

# Python
pytest --cov --cov-report=term-missing

# Apps Script
npm run test
```

### 7.2 Verificar coverage minimo

**Cobertura minima**: 85%

Si la cobertura es menor:
1. Identificar archivos sin cobertura
2. Generar tests adicionales
3. Re-ejecutar hasta alcanzar 85%

### 7.3 Lint final

```bash
# Flutter
dart analyze

# React
npx eslint . && npx tsc --noEmit

# Python
ruff check . && mypy .

# Apps Script
npm run lint
```

### 7.4 Commit de tests

```bash
git add .
git commit -m "test({feature}): add tests with 85%+ coverage"
```

---

## Paso 7.5: Quality Audit (AG-08)

> OBLIGATORIO después de QA. El auditor independiente verifica que todo es real.

### 7.5.1 Ejecutar AG-08

El Quality Auditor (AG-08) ejecuta su checklist completo:
1. **Test Quality**: ¿Los tests son reales? ¿Tienen assertions significativas?
2. **Coverage Legitimacy**: ¿El coverage es legítimo? ¿No hay exclusiones tramposas?
3. **Architecture Compliance**: ¿Las capas se respetan?
4. **Convention Compliance**: ¿Se siguen las convenciones del stack?
5. **Dead Code**: ¿No se introdujo código muerto?

### 7.5.2 Generar evidence

Guardar en `.quality/evidence/{feature}/`:
- `final-gate.json` — Métricas finales
- `audit.json` — Resultado del audit de AG-08
- `report.md` — Report legible con veredicto

### 7.5.3 Evaluar veredicto

| Veredicto | Acción |
|-----------|--------|
| ✅ GO | Continuar a crear PR |
| ⚠️ CONDITIONAL GO | Crear PR con notas de mejora |
| 🛑 NO-GO | PARAR. Reportar hallazgos. Intentar fix. Re-auditar (max 2 intentos) |

### 7.5.4 Commit de evidencia

```bash
git add .quality/evidence/{feature}/
git commit -m "quality({feature}): audit evidence and report"
```

---

## Paso 8: Crear Pull Request

### 8.1 Push de la rama

```bash
git push -u origin feature/{nombre-del-plan}
```

### 8.2 Generar resumen de PR

Analizar todos los commits de la rama para generar el body:

```bash
# Ver commits de la rama
git log main..HEAD --oneline

# Ver archivos cambiados
git diff main..HEAD --stat
```

### 8.3 Crear PR

```bash
gh pr create \
  --title "[Feature] {Titulo del plan}" \
  --body "$(cat <<'EOF'
## Summary

{Resumen del plan en 2-3 bullet points}

## Changes

{Lista de cambios principales agrupados por fase}

## Stitch Designs

{Si aplica: lista de pantallas generadas con links a HTMLs}

## Quality Report

| Métrica | Pre | Post | Delta | Gate |
|---------|-----|------|-------|------|
| Lint | 0/0/0 | 0/0/0 | = | ✅ |
| Coverage | {pre}% | {post}% | {delta} | ✅/🛑 |
| Tests | {pre} | {post} | +{N} | ✅ |
| Architecture | {N} violations | {N} violations | {delta} | ✅/🛑 |

**Veredicto AG-08**: {GO/CONDITIONAL GO/NO-GO}
**Evidence**: `.quality/evidence/{feature}/`

## Test Plan

- [ ] Tests unitarios pasan con coverage ≥ baseline
- [ ] Lint 0/0/0
- [ ] Build exitoso
- [ ] AG-08 Quality Audit: GO
- [ ] {Criterios adicionales del plan}

## Plan Reference

`{path al plan}`

---
🤖 Implementado con [JPS Dev Engine](https://github.com/jesusperezdeveloper/jps_dev_engine) `/implement` + Quality Gates
EOF
)"
```

### 8.4 Vincular con work item (si aplica)

Si el plan referencia un work item de Plane/Trello:
- Anadir link a la PR en un comentario del work item
- Actualizar estado a "En Desarrollo" o "En Pruebas"

---

## Output Final

```
## ✅ Implementacion Completada

**Plan**: `{path al plan}`
**Rama**: `feature/{nombre}`
**PR**: {url de la PR}

### Resumen de ejecucion:

| Fase | Estado | Commits |
|------|--------|---------|
| Diseño Stitch | ✅/⏭️ Saltado | {N} |
| Design-to-code | ✅/⏭️ Saltado | {N} |
| {Fase 1 del plan} | ✅ | {N} |
| {Fase 2 del plan} | ✅ | {N} |
| Integracion | ✅ | {N} |
| QA | ✅ | {N} |

### Metricas:

- **Archivos creados**: {N}
- **Archivos modificados**: {N}
- **Tests**: {N} pasando
- **Coverage**: {X}%
- **Commits**: {N} totales
- **Diseños Stitch**: {N} pantallas (si aplica)

### PR lista para review:
{url de la PR}
```

---

## Manejo de Errores

### Error en compilacion/lint durante una fase

```
1. Leer el error completo
2. Intentar fix automatico (dart fix, eslint --fix, ruff --fix)
3. Si persiste: analizar y corregir el codigo
4. Si no se puede resolver:
   - Commitear el progreso hasta ahora
   - Reportar al usuario con detalles del error
   - Sugerir solucion manual
   - NO continuar con fases siguientes
```

### Error en generacion Stitch

```
1. Registrar el error
2. Reintentar UNA vez
3. Si falla de nuevo:
   - Continuar con las demas pantallas
   - Reportar pantallas fallidas al final
   - La implementacion continua sin esos diseños
```

### Tests no alcanzan 85% coverage

```
1. Identificar archivos sin coverage
2. Generar tests adicionales (hasta 3 intentos)
3. Si no se alcanza:
   - Reportar coverage actual
   - Listar archivos que necesitan tests
   - Crear la PR de todas formas con nota sobre coverage
```

### Conflictos de merge

```
1. NO resolver automaticamente
2. Reportar los archivos en conflicto
3. Pedir al usuario que resuelva
4. Continuar despues de la resolucion
```

---

## Checklist de Calidad

- [ ] Plan leido y parseado correctamente
- [ ] Rama creada desde main
- [ ] Stack detectado
- [ ] Diseños Stitch generados (si aplica)
- [ ] Design-to-code ejecutado (si aplica)
- [ ] Todas las fases del plan implementadas
- [ ] Commits parciales por fase
- [ ] Integracion completada (DI, routing, config)
- [ ] Build sin errores
- [ ] Tests con 85%+ coverage
- [ ] Lint sin errores
- [ ] PR creada con resumen completo
- [ ] Work item actualizado (si aplica)

---

## Referencia Rapida

| Concepto | Valor |
|----------|-------|
| Planes | `doc/plans/{nombre}_plan.md` |
| Diseños | `doc/design/{feature}/` |
| Branch naming | `feature/{nombre-plan-kebab-case}` |
| Coverage minimo | 85% |
| Commits | Uno por fase + integracion + tests |
| PR body | Summary + Changes + Stitch + Test Plan |
