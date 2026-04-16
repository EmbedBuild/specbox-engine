---
name: autopilot-implement
description: >
  Autonomous implementation from a plan file. Creates feature branch,
  implements all phases, generates Stitch designs if needed, converts
  designs to code, runs QA validation, and creates GitHub PR.
  Use when the user says "implement plan", "execute plan", "autopilot",
  or references implementing a previously created plan.
disable-model-invocation: true
---

## Checkpoint System

Before starting, check for existing checkpoint:
- Read .quality/evidence/${feature}/checkpoint.json if exists
- If checkpoint found AND branch exists:
  - Report: "Found checkpoint at Phase {N}. Resume or restart?"
  - If resume: git checkout the branch, skip to Phase N+1
- After each successful phase, save checkpoint:
  ```bash
  mkdir -p .quality/evidence/${feature}
  echo '{"phase": N, "phase_name": "...", "branch": "...", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'", "status": "complete"}' > .quality/evidence/${feature}/checkpoint.json
  ```
- On error: save checkpoint with status "failed" and phase details

# /implement (Global)

Autopilot de implementacion: lee un plan, crea rama, ejecuta todas las fases, genera diseños si aplica, valida con QA, commitea y crea PR.

## Uso

```
/implement [plan]
```

**Origenes soportados:**
- `US-XX` → User Story de Trello (ejecuta todos los UCs en secuencia)
- `UC-XXX` → Use Case individual de Trello
- `nombre_del_plan` → Busca `doc/plans/{nombre}_plan.md`
- `doc/plans/mi_plan.md` → Path directo al archivo del plan
- Sin argumento → Lista planes disponibles en `doc/plans/` y pregunta cual ejecutar

---

## Paso 0: Cargar y Validar Plan

### 0.1 Localizar el plan

```
Que recibi?
├── US-XX → Modo Trello: ejecutar bloque de UCs de la US
├── UC-XXX → Modo Trello: ejecutar un UC individual
├── nombre_del_plan → Buscar doc/plans/{nombre}_plan.md
├── path directo → Leer directamente
└── sin argumento → Listar doc/plans/*.md y preguntar
```

### 0.1a Si es US-XX o UC-XXX (Trello spec-driven):

1. Obtener board_id (buscar en orden de prioridad):
   - `.claude/project-config.json` → `trello.boardId` (PREFERIDO — Claude Code rechaza campos custom en settings.local.json)
   - `.claude/settings.local.json` → `trello.boardId` (fallback legacy)
   - Si no existe en ninguno → ERROR: "Configura trello.boardId en .claude/project-config.json"
2. Si US-XX:
   - Llamar `get_us(board_id, us_id)` → datos de la US
   - Llamar `list_uc(board_id, us_id)` → listar UCs hijos
   - Llamar `find_next_uc(board_id)` → determinar primer UC a ejecutar
   - Buscar plan adjunto: `get_evidence(board_id, us_id, "us", "plan")`
   - Si hay plan en `doc/plans/` → cargar plan local
   - Si no hay plan → ERROR: "Ejecuta /plan US-XX primero"
3. Si UC-XXX:
   - Llamar `get_uc(board_id, uc_id)` → datos completos del UC
   - Derivar us_id del UC → buscar plan de la US padre
4. Parsear plan y filtrar solo las fases relevantes para el UC actual
5. Llamar `start_uc(board_id, uc_id)` → mover a In Progress + timestamp

**Flujo de ejecucion por US (bloque de UCs):**
```
US-XX recibida
  ├── Cargar plan de la US
  ├── find_next_uc → UC-001 (Backlog)
  │   ├── start_uc(UC-001) → In Progress
  │   ├── Implementar (Pasos 1-7.7)
  │   ├── move_uc(UC-001, "review") → Review (humano aprueba Done)
  │   ├── Merge secuencial (Paso 8.5)
  │   └── Pull main
  ├── find_next_uc → UC-002 (Backlog)
  │   ├── start_uc(UC-002) → In Progress
  │   ├── ... (mismo ciclo)
  │   └── Pull main
  └── No mas UCs en Backlog → Finalizar
```

### 0.1b Si es plan local:

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
| VEGs | `doc/veg/{feature}/*.md` — artefactos Visual Experience Generation | No |
| Modo VEG | Seccion "Visual Experience Generation" del plan | No |
| Trello US/UC | Origen US-XX o UC-XXX + board_id | No |

### 0.3 Detectar si requiere diseño y VEG

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

¿El plan tiene seccion "Visual Experience Generation"?
├── SI: Cargar VEGs de doc/veg/{feature}/*.md
│   ├── Leer modo VEG (1/2/3) y archivos generados
│   ├── Activar pasos VEG: enriquecer Stitch (3), generar imagenes (3.5), inyectar motion (4)
│   └── Preparar resumen VEG compacto (~400 tokens) para sub-agentes
└── NO: Pipeline legacy (sin cambios)
```

### 0.4 Detectar stack tecnologico

```bash
# Detectar stack del proyecto actual
cat pubspec.yaml 2>/dev/null | grep -E "flutter:|dependencies:"  # Flutter
cat package.json 2>/dev/null | grep -E "react|next"              # React/Node
cat pyproject.toml 2>/dev/null | grep -E "fastapi|django"        # Python
ls .clasp.json appsscript.json 2>/dev/null                       # Google Apps Script
```

### 0.4a Inicializar Pipeline State (v5.19.0)

Despues de detectar el stack y parsear el plan, inicializar `pipeline_state.json`
para que `pipeline-phase-guard.mjs` pueda validar el orden de fases:

```bash
mkdir -p .quality/evidence/${feature}
```

Determinar qué fases aplican al proyecto:

```
has_db = plan incluye fase DB/Infra (AG-03)
has_ui = plan incluye fase Diseño/Design-to-code (AG-02/AG-06)

# Pre-marcar fases no aplicables como completadas
completed_phases = []
if NOT has_db:  completed_phases.append("db_infra")
if NOT has_ui:  completed_phases.append("stitch_designs", "design_to_code")
```

Escribir el estado inicial:

```json
// .quality/evidence/${feature}/pipeline_state.json
{
  "feature": "${feature}",
  "has_ui": true|false,
  "has_db": true|false,
  "completed_phases": ["...fases no aplicables pre-marcadas..."],
  "current_phase": "init",
  "last_updated": "ISO8601"
}
```

**IMPORTANTE**: Este archivo es OBLIGATORIO. Sin el, `pipeline-phase-guard.mjs` permite todo
(modo permisivo). Con el, enforce mecánico del orden de fases.

### 0.5 Validacion pre-vuelo (HARD BLOCKS)

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

### 0.5b Guardia anti-implementacion-en-main (BLOQUEANTE)

> **REGLA INNEGOCIABLE**: Nunca se puede implementar directamente en main/master.

Esta validacion se ejecuta ANTES del Paso 1 y se RE-VERIFICA antes de cada Paso 5 (implementacion de fases).

```
current_branch = git branch --show-current

¿current_branch es main o master?
├── SI (estamos en Paso 0): OK — el Paso 1 creara la rama feature/
├── SI (estamos en Paso 5+): ❌ ERROR FATAL
│   → "BLOQUEADO: Se esta intentando implementar directamente en main.
│      Esto viola el protocolo de ramas del engine.
│      El Paso 1 debio crear una rama feature/ antes de llegar aqui.
│      ACCION: Parar inmediatamente. NO escribir codigo en main."
│   → PARAR el pipeline. No continuar bajo ninguna circunstancia.
└── NO: OK — continuar normalmente
```

**Por que este bloqueo es necesario:**
- Sin rama feature/, no hay PR posible
- Sin PR, no hay acceptance evidence ni review
- Sin review, el merge secuencial no puede funcionar
- Implementar en main directamente rompe TODO el pipeline de calidad

### 0.5c.vs Visual Identity Gate (si UC tiene pantallas) (BLOQUEANTE)

> **REGLA**: No se puede implementar UI sin identidad visual configurada.
> Este gate impide generar diseños genéricos que no representan la marca del producto.
> Se ejecuta ANTES del Design Gate (0.5d) porque sin brand kit los diseños carecen de sentido.

```
¿El UC/plan tiene pantallas listadas?
├── No tiene pantallas → SKIP (gate no aplica, UC sin UI)
└── Tiene pantallas → Verificar identidad visual:
    │
    ¿Existe doc/brand/brand_kit/SKILL.md?
    ├── SI → OK — brand kit configurado, continuar
    └── NO → Verificar mas:
        │
        ¿Existe stitch.designSystemAssetId en .claude/settings.local.json?
        ├── SI → OK — Design System configurado (brand kit parcial aceptable)
        └── NO → Verificar si el proyecto usa Stitch:
            │
            ¿Existe stitch.projectId en .claude/settings.local.json
             O existen doc/design/**/*.html?
            ├── NO → SKIP (proyecto no usa Stitch, gate no aplica)
            └── SI → ❌ BLOCKED
                "❌ BLOCKED: Visual identity not configured.
                 This project uses Stitch but has no brand kit or Design System.
                 Without visual identity, designs are generic and inconsistent.

                 Run /visual-setup first to configure:
                 - Brand Kit (colors, typography, CSS tokens)
                 - Design System in Stitch (applied automatically to every screen)
                 - VEG base (visual directives for sub-agents)
                 - Prompt template (reusable structure for Stitch generation)

                 /visual-setup takes ~5 minutes and only needs to run once per project."
                → PARAR. No continuar bajo ninguna circunstancia.
```

```bash
# Verificacion rapida
ls doc/brand/brand_kit/SKILL.md 2>/dev/null
cat .claude/settings.local.json 2>/dev/null | grep -c "designSystemAssetId"
```

**Por que este bloqueo es necesario:**
- Sin brand kit, Stitch genera con paleta y tipografia por defecto
- Los diseños resultantes no representan la marca del producto
- design-to-code hereda el estilo generico, creando deuda visual
- Cada pantalla generada sin brand kit es una pantalla que hay que rehacer
- `/visual-setup` solo se ejecuta UNA VEZ por proyecto (~5 min) y resuelve el problema permanentemente

### 0.5d Stitch Design Gate (si UC tiene pantallas) (BLOQUEANTE)

> **REGLA**: No se puede generar codigo de presentacion sin diseños Stitch previos.
> Este gate impide que el agente en modo autopilot salte el paso de diseño.

```
¿El UC/plan tiene pantallas listadas?
  pantallas = extraer campo "screens" o "pantallas" del UC/plan
  ├── pantallas vacías o no definidas → SKIP (gate no aplica, UC sin UI)
  └── pantallas definidas → Verificar diseños:
      │
      Para cada pantalla listada:
        ¿Existe doc/design/{feature}/*.html con HTML correspondiente?
        ├── SI → OK
        └── NO → Acumular en lista missing_designs[]
      │
      ¿missing_designs está vacío?
      ├── SI → OK — todos los diseños existen, continuar
      └── NO → Verificar campo stitch_designs del plan:
          │
          ¿stitch_designs == "PENDING"?
          ├── SI → ❌ BLOCKED
          │   "❌ BLOCKED: Stitch designs pending for UC-XXX.
          │    The plan has stitch_designs: PENDING — designs were not generated.
          │    Run /plan first to generate Stitch designs, or create them manually
          │    in doc/design/{feature}/ before running /implement."
          │   → PARAR. No continuar bajo ninguna circunstancia.
          └── NO (campo no existe o no es PENDING) → ❌ BLOCKED
              "❌ BLOCKED: No Stitch designs found for UC-XXX.
               Missing designs for screens: {missing_designs[]}
               Expected location: doc/design/{feature}/
               Run /plan first or generate designs manually."
              → PARAR. No continuar bajo ninguna circunstancia.
```

**Verificacion concreta:**
```bash
# Contar HTMLs de diseño existentes para el feature
ls doc/design/${feature}/*.html 2>/dev/null | wc -l

# Si es 0 y el UC tiene pantallas → BLOCKED
```

**Por que este bloqueo es necesario:**
- Sin diseños previos, el design-to-code genera UI sin referencia visual
- El agente en autopilot inventa layouts que no fueron aprobados por el usuario
- Se pierde la trazabilidad diseño → codigo que AG-08 verifica
- El resultado es UI generica en lugar de UI intencional derivada de VEG/Stitch

### 0.5d.1 Retrofit: Enforcement progresivo para proyectos legacy

> Para proyectos con codigo UI pre-v4.2.0, el Design Gate aplica enforcement
> progresivo basado en el nivel de compliance del proyecto.

```
¿Existe baseline de design compliance?
  .quality/scripts/design-baseline.sh . → leer enforcementLevel
  │
  ├── L0 (compliance < 30%): Proyecto legacy, mucho codigo sin Stitch
  │   → Paso 0.5d se comporta como WARNING, no BLOCK
  │   → Mensaje: "⚠️ Design compliance L0: {rate}%. UC-XXX no tiene diseños.
  │     Recomendacion: ejecutar /plan para generar diseños antes de implementar.
  │     Este proyecto esta en modo retrofit — el gate no bloquea aun."
  │   → Continuar implementacion (el codigo se genera sin diseño)
  │   → AG-08 Check 6 reporta como INFO, no CRITICAL
  │   → /check-designs muestra deuda de diseño acumulada
  │
  ├── L1 (compliance 30-79%): Proyecto en transicion
  │   → Paso 0.5d BLOQUEA solo si el plan es nuevo (post-v4.2.0)
  │   → Planes legacy (sin campo stitch_designs) → WARNING + continuar
  │   → Planes nuevos (con campo stitch_designs) → BLOCK si PENDING/missing
  │   → AG-08 Check 6: CRITICAL solo en archivos nuevos del diff
  │   → Archivos existentes modificados: WARNING (no CRITICAL)
  │   → complianceRate solo puede subir (ratchet)
  │
  └── L2 (compliance >= 80%): Proyecto alineado
      → Paso 0.5d BLOQUEA siempre (comportamiento estandar)
      → AG-08 Check 6: CRITICAL en todo archivo de presentation/pages/
      → Sin excepciones — el proyecto ya esta alineado
```

**Como migrar de L0 a L2 progresivamente:**

1. **Fase 1 (L0 → L1)**: Ejecutar `/check-designs` para ver deuda. Al implementar
   features nuevas, usar `/plan` con Stitch. Cada feature alineada sube el rate.
   Al alcanzar 30% → upgrade automatico a L1.

2. **Fase 2 (L1 → L2)**: Aprovechar cada modificacion de features existentes para
   generar diseños Stitch retroactivos. Usar `/plan feature:nombre_existente` para
   generar diseños de features legacy que se estan tocando. Al alcanzar 80% → L2.

3. **Fase 3 (L2 estable)**: Todo nuevo codigo pasa por Stitch. La deuda legacy
   restante se resuelve en sprints dedicados o cuando se toca el codigo.

### 0.5c Validacion de Trello state (si spec-driven) (BLOQUEANTE)

> Solo aplica si el origen es US-XX o UC-XXX (Trello spec-driven).

```
¿Se llamo start_uc(board_id, uc_id) en Paso 0.1a?
├── SI: Verificar con get_uc(board_id, uc_id) que status == "in_progress"
│   ├── Confirmado: OK — continuar
│   └── No confirmado: ⚠️ WARNING — start_uc pudo haber fallado silenciosamente
│       → Reintentar start_uc una vez
│       → Si falla de nuevo: continuar con WARNING en el log
└── NO (start_uc no fue llamado): ❌ ERROR FATAL
    → "BLOQUEADO: No se llamo start_uc antes de implementar.
       El estado del UC en Trello no refleja que esta en progreso.
       Esto causara inconsistencia en el board."
    → Llamar start_uc ahora como recovery
    → Si falla: PARAR y notificar al usuario
```

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

Para cada fase, el orquestador ejecuta:

```
1. PREPARAR contexto (max ~20,000 tokens — v5.24.0 expandido para Opus 4.7):
   - Extraer SOLO la seccion de la fase del plan
   - Cargar overview de arquitectura del stack (~500 words max)
   - Listar archivos que la fase va a modificar (paths, no contenido)
   - Incluir checkpoint de la fase anterior

2. LANZAR sub-agente (Task tool):
   - Contexto limpio e independiente
   - Acceso completo a Read/Write/Edit/Bash
   - Ejecuta lint, build, tests dentro de su contexto

3. RECIBIR reporte estructurado:
   - files_created, files_modified, lint_result, phase_status, errors

4. CONSOLIDAR:
   - mem_save con tags "phase,{N},{feature}"
   - checkpoint.json
   - Si failed → Self-Healing
   - Si complete → commit + siguiente fase
   - DESCARTAR contexto del sub-agente excepto resumen
```

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

**Si hay VEG activo**: Enriquecer cada prompt Stitch con las directivas del Pilar 3 (Diseno):

```
Visual Direction (from VEG - {target_name}):
- Density: {density}, Whitespace: {whitespace}
- Visual hierarchy: {style}, CTA prominence: {prominence}
- Typography: headings {weight}, body {spacing}, hero {scale}
- Section separation: {separation_style}
- Mood: {mood} — this should FEEL {JTBD emocional}
- Data presentation: {data_style}

Image Placeholders (generate with placeholder boxes):
- Hero: [{type}] {description from VEG Pilar 1}
- (mark each with [IMAGE: {id}] for later replacement)
```

**Reglas:**
- Una pantalla a la vez (la API tarda minutos)
- NO preguntar entre pantallas (modo autopilot) — generar todas las que falten
- Si falla una pantalla, registrar el error y continuar con las demas
- Reintentar una vez si hay timeout

---

## Paso 3.5: Generar Imagenes con MCP (si hay VEG activo)

> Prerequisito: VEG activo con prompts de imagen definidos (Pilar 1).
> Si el MCP de imagenes no esta configurado → registrar prompts pendientes y continuar.

### 3.5.0 Advertencia de costes

**OBLIGATORIO**: Antes de generar imagenes, informar al usuario:

```
📷 VEG Image Generation — {N} imagenes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Provider configurado: {primary} ({fallback} como fallback)

Coste estimado:
  • Canva (Pro/Premium): €0 adicional (incluido en suscripcion)
  • Freepik (Mystic): Segun plan contratado
  • OpenAI GPT-Image-1: ~$0.02-0.19/imagen → total ~${min}-${max}
  • Gemini Imagen 4: ~$0.02-0.06/imagen → total ~${min}-${max}

¿Continuar con la generacion de imagenes? (s/n/skip)
  s = generar imagenes con MCP
  n = cancelar VEG imagenes completamente
  skip = documentar prompts para generacion manual posterior
```

Si el provider es `canva` y el usuario tiene suscripcion activa, el coste es €0 — mencionar explicitamente.
Si el usuario elige `skip` o `n` → saltar a Paso 3.5.4 (registrar prompts pendientes).

### 3.5.1 Verificar MCP de imagenes (Health Check)

**No basta con leer la config — hay que probar que el MCP responde.**

1. Leer `veg.image_provider` de `.claude/settings.local.json`
2. Determinar el provider a usar:
   - Si `primary: "canva"` → intentar Canva MCP
   - Si `primary: "freepik"` → intentar Freepik MCP
   - Si `primary: "lansespirit"` → intentar lansespirit MCP
3. **Health check obligatorio** — intentar una operacion trivial:
   - Canva: llamar `mcp__canva__search-designs` con query trivial (ej: "test")
   - Freepik: llamar `mcp__freepik__check_status` o `mcp__freepik__search_resources` con query trivial
   - lansespirit: llamar `mcp__image-gen__generate_image` con un prompt de test minimo
   - Si la llamada retorna "tool not found" o error de conexion → MCP no instalado
4. **Decision:**
   ```
   Health check OK?
   ├── SI → Continuar con generacion
   ├── NO (tool not found) → MCP no instalado
   │   ├── Informar: "El MCP '{provider}' no esta configurado en este entorno.
   │   │   Para configurarlo, anadir a .vscode/mcp.json o .claude/settings.json:"
   │   │   {mostrar bloque JSON de configuracion del provider}
   │   │
   │   │   Canva: Solo necesita suscripcion Pro/Premium. Auth via OAuth (browser popup).
   │   │   Freepik: Necesita FREEPIK_API_KEY con plan activo.
   │   │   lansespirit: Necesita OPENAI_API_KEY y/o GOOGLE_API_KEY con billing activo.
   │   └── Saltar a Paso 3.5.4 (registrar prompts pendientes)
   ├── NO (auth error / 401 / 403) → Sesion expirada o suscripcion inactiva
   │   ├── Canva: "La sesion OAuth de Canva expiro. Reconectar en el navegador."
   │   ├── Otros: "Verificar que la API key es valida y tiene creditos."
   │   └── Saltar a Paso 3.5.4
   └── NO (timeout / 500) → intentar fallback
       ├── Si hay fallback configurado → repetir health check con fallback
       └── Si no hay fallback → Paso 3.5.4
   ```

### 3.5.2 Generar imagenes

El flujo depende del provider configurado.

#### Si provider = "canva" (RECOMENDADO — €0 con suscripcion)

Para cada `[IMAGE: {id}]` identificado en los disenos Stitch:

1. Leer el prompt base del VEG para ese tipo de seccion (hero, features, etc.)
2. Contextualizar con el contenido especifico de la pantalla
3. Construir prompt para Canva `generate-design`:
   ```
   Create a {width}x{height} design: {prompt del VEG}.
   Style: {mood from Pilar 1}. Palette: {palette}. Type: {photography/illustration}.
   This is a standalone visual asset, not a presentation.
   ```
4. Llamar `mcp__canva__generate-design` con el prompt
5. Llamar `mcp__canva__export-design` para exportar como PNG
6. Guardar en: `doc/veg/{feature}/assets/{image_id}.png`
7. Registrar en: `doc/veg/{feature}/image_prompts.md`

**Dimensiones por tipo de asset:**
| Tipo | Dimensiones | Uso |
|------|------------|-----|
| Hero | 1920x1080 | Banner principal, above the fold |
| Feature illustration | 800x800 | Secciones de features |
| Background | 1920x1080 | Fondos de seccion |
| Icon/badge | 512x512 | Iconos decorativos |
| Social proof | 1200x630 | Testimonios, logos |

#### Si provider = "freepik"

Para cada `[IMAGE: {id}]`:
1. **Si stockSearchFirst = true**: buscar en stock con `search_resources`
   - Si hay match profesional → `download_resource` → usar
   - Si no → generar con `generate_image` (Mystic AI)
2. Guardar y registrar igual que arriba

#### Si provider = "lansespirit" (fallback de pago)

Para cada `[IMAGE: {id}]`:
1. Generar con `generate_image` (OpenAI GPT-Image-1 o Gemini Imagen 4)
   - Imagenes con texto legible → preferir OpenAI
   - Fotorrealismo puro → preferir Gemini Imagen 4 (mas barato)
2. Guardar y registrar igual que arriba

### 3.5.3 Reglas

- Maximo de imagenes por pantalla: `veg.image_provider.maxImagesPerScreen` (default 5)
- Prioridad: hero > feature illustrations > social proof > backgrounds > decorativas
- Si el MCP falla mid-generation: registrar prompt + continuar (imagen pendiente)
- Retry: 1 intento. Si falla 2 veces → skip con log
- Budget de contexto: Los prompts de imagen NO se incluyen en el contexto de los sub-agentes. Solo el orquestador ejecuta este paso.
- Canva genera diseños con layers — el export como PNG aplana automaticamente. El resultado es una imagen usable directamente.

### 3.5.4 Registrar imagenes pendientes (fallback manual)

Si el MCP no estaba disponible, fallo, o el usuario eligio `skip`:

1. Crear `doc/veg/{feature}/PENDING_IMAGES.md`:

```markdown
# Imagenes Pendientes — {feature}

> Generadas por VEG pero no producidas por MCP.
> Usar estos prompts para generar manualmente en Canva, Midjourney, DALL-E, Freepik, etc.

| ID | Tipo | Prompt | Aspect Ratio | Prioridad |
|----|------|--------|-------------|-----------|
| hero | photography | "{prompt completo}" | 16:9 | Alta |
| feature-1 | illustration | "{prompt completo}" | 1:1 | Media |

## Como completar

1. Generar cada imagen con el provider de tu preferencia
2. Guardar en `doc/veg/{feature}/assets/{id}.{ext}`
3. Ejecutar `/implement` de nuevo — detectara las imagenes y las integrara (Paso 6.1b)

## Coste estimado si se usa API

| Provider | Coste/imagen | Total ({N} imagenes) |
|----------|-------------|---------------------|
| Canva (Pro/Premium) | €0 | €0 |
| Freepik Mystic | Segun plan | Segun plan |
| OpenAI GPT-Image-1 | $0.02-0.19 | ${min}-${max} |
| Gemini Imagen 4 | $0.02-0.06 | ${min}-${max} |
```

2. Mantener placeholders `[IMAGE: {id}]` en los diseños — el Paso 6.1b los reemplazara cuando las imagenes existan.
3. Log en consola: `⚠️ {N} imagenes pendientes. Ver doc/veg/{feature}/PENDING_IMAGES.md`
4. **NUEVO: Activar flag de calidad visual degradada:**
   ```
   veg_images_pending = true
   ```
   Este flag tiene consecuencias en pasos posteriores:
   - **Paso 7.6 (AG-08 Quality Audit)**: Si `veg_images_pending == true`:
     - AG-08 verdict = **CONDITIONAL GO** como maximo (nunca GO pleno)
     - Razon: "VEG Pilar 1 no completado — {N} imagenes usan placeholders CSS"
     - AG-08 DEBE listar las imagenes pendientes en su report
   - **Paso 8 (PR body)**: Anadir banner visible:
     ```
     > ⚠️ **VEG Pilar 1 incompleto**: Este PR usa {N} imagenes placeholder.
     > Las imagenes profesionales deben generarse antes del deploy a produccion.
     > Ver `doc/veg/{feature}/PENDING_IMAGES.md` para prompts listos.
     ```
   - **Paso 8.5 (Auto-merge)**: Auto-merge BLOQUEADO si `veg_images_pending == true`
     - Razon: "No se puede auto-merge con imagenes placeholder — calidad visual degradada"
     - El usuario puede aprobar manualmente si acepta el estado visual actual

### 3.5.5 Prohibicion de placeholders CSS como sustituto de imagenes VEG

> **REGLA**: Cuando el VEG especifica imagenes (Pilar 1), los sub-agentes NO pueden
> sustituirlas por gradientes CSS, iconos SVG inline, o iniciales de texto como "solucion".
> Estas tecnicas son aceptables SOLO si el VEG no existe o no especifica imagenes.

```
¿El proyecto tiene VEG con Pilar 1 (Imagenes)?
├── SI: Las secciones que requieren imagenes DEBEN usar:
│   ├── Imagenes reales de doc/veg/{feature}/assets/ (si existen)
│   ├── Placeholders <img> con src apuntando a PENDING_IMAGES paths (si no existen)
│   └── NUNCA: gradientes CSS, divs con colores, iconos como sustituto de fotos
└── NO: Libre de usar cualquier tecnica visual
```

---

## Paso 4: Design-to-Code (si hay disenos)

> Convertir los HTML de Stitch a codigo del stack del proyecto.

### 4.0 Instalar dependencias VEG Motion (si hay VEG activo)

**OBLIGATORIO antes de escribir codigo con animaciones.** Verificar e instalar:

```
¿El VEG tiene motion habilitado (motion_level != none)?
├── SI → Verificar e instalar dependencias:
│   ├── Flutter:
│   │   ├── Leer pubspec.yaml → ¿tiene flutter_animate?
│   │   ├── NO → ejecutar: flutter pub add flutter_animate
│   │   └── SI → verificar version compatible (^4.5.2)
│   ├── React:
│   │   ├── Leer package.json → ¿tiene motion?
│   │   ├── NO → ejecutar: npm install motion
│   │   └── SI → verificar version compatible (^12.35.0)
│   └── Python / Apps Script → N/A (sin motion library)
└── NO → Saltar (no hay animaciones que implementar)
```

Si la instalacion falla → WARNING, continuar design-to-code SIN animaciones.
Registrar en log: `⚠️ No se pudo instalar {package}. Design-to-code sin VEG Motion.`

### 4.1 Listar HTMLs disponibles

```bash
ls doc/design/{feature}/*.html
```

### 4.2 Conversion por stack

**Si hay VEG activo**, incluir el Motion Catalog (Pilar 2) en el contexto del sub-agente AG-02:

```
VEG Motion Catalog:
  page_enter: {animation} {duration}ms {easing}
  scroll_reveal: {animation} stagger {delay}ms
  hover_buttons: {animation} {duration}ms
  loading: {style}
  transitions_pages: {type} {duration}ms
  feedback_success: {animation}
  feedback_error: {animation}
  motion_level: {subtle / moderate / expressive}

Motion level rules:
  - subtle: ONLY page_enter + loading. Skip scroll, hover, feedback.
  - moderate: All except feedback animations.
  - expressive: Full catalog.
```

Para cada HTML de diseno:

#### Flutter
1. Leer HTML y extraer: layout, componentes, colores, espaciado, tipografia
2. Crear widgets en la estructura del feature:
   - `lib/presentation/features/{feature}/widgets/` para widgets especificos
   - `lib/core/widgets/` para widgets reutilizables (si se identifican)
3. Respetar:
   - `AppColors` y `AppSpacing` (nunca hardcodear)
   - Responsividad: mobile/tablet/desktop layouts
   - Clases separadas (NUNCA metodos `_buildX()`)
4. **Si hay VEG Motion**: Aplicar animaciones usando `flutter_animate`:
   - Importar `package:flutter_animate/flutter_animate.dart`
   - Usar `.animate()` chainable para cada tipo de animacion del catalogo
   - Loading states: usar el estilo VEG (skeleton = shimmer + Container, shimmer = `.shimmer()`)
   - NO anadir animaciones que no esten en el catalogo VEG
   - **Mobile hover enforcement**: Si el proyecto es mobile-first o el VEG target es mobile:
     - NO usar MouseRegion para hover effects
     - Reemplazar hover → GestureDetector con onTapDown/onTapUp para feedback tactil
     - Si se necesita hover en desktop: usar LayoutBuilder para detectar plataforma

#### React
1. Leer HTML y extraer: estructura JSX, clases CSS, componentes
2. Crear componentes en:
   - `src/components/features/{feature}/` para componentes especificos
   - `src/components/ui/` para primitivos reutilizables
3. Respetar:
   - Server Components por defecto, `'use client'` solo si necesita interactividad
   - Tailwind CSS para estilos
   - TypeScript obligatorio
4. **Si hay VEG Motion**: Aplicar animaciones usando `motion` (ex Framer Motion):
   - Importar `{ motion, AnimatePresence }` de `"motion/react"`
   - Definir variants como constantes reutilizables
   - `whileInView` para scroll_reveal, `whileHover` para hover effects
   - `AnimatePresence` para page transitions y exit animations
   - NO anadir animaciones que no esten en el catalogo VEG
   - **Mobile hover enforcement**: Si el proyecto es mobile-first o el VEG target es mobile:
     - Reemplazar `whileHover` → `whileTap` en todos los componentes interactivos
     - Si se necesita hover en desktop: usar media query `@media (hover: hover)` para aplicar condicionalmente
     - NUNCA dejar `whileHover` sin alternativa `whileTap` en un proyecto responsive

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

### 4.3 Traceability comment (OBLIGATORIO)

Cada archivo de pagina/pantalla generado por design-to-code DEBE incluir un comentario de trazabilidad en las primeras lineas:

```dart
// Generated from: doc/design/{feature}/{screen}.html
```

```tsx
// Generated from: doc/design/{feature}/{screen}.html
```

```python
# Generated from: doc/design/{feature}/{screen}.html
```

**Regla**: Si el archivo no tiene este comentario, AG-08 lo reportara como violacion de trazabilidad en el Check 6 (Design Traceability).

### 4.4 Commit parcial de diseños

```bash
git add doc/design/{feature}/
git commit -m "design: add Stitch designs for {feature}"
```

---

## Execution Strategy: Task Isolation with Context Budget

CRITICAL: Each phase MUST be executed in an isolated Task to prevent context saturation.

### Context Budget per Phase

Each spawned Task has a context budget. The main agent MUST control what goes into each task.

| Concepto | Budget máximo | Notas |
|----------|--------------|-------|
| Phase description | ~1,500 tokens | Del plan, sección completa de la fase (v5.24.0: ampliado para incluir edge cases) |
| Architecture rules | ~4,500 tokens | Overview del stack + patrones relevantes para la fase |
| Relevant source files | ~11,000 tokens | Archivos que la fase modifica + dependencias cercanas (v5.24.0: permite contexto más rico) |
| Stack patterns | ~2,500 tokens | Patterns relevantes (ej: BLoC + repository + testing si es state mgmt) |
| Checkpoint state | ~500 tokens | JSON del checkpoint anterior + resumen de fases completadas |
| **Total per task** | **~20,000 tokens** | **~2% de ventana de Opus 4.7 (1M context)** — v5.24.0: expandido de ~8,700 |

### Context Loading Rules

**INCLUIR en el Task:**
- Descripción de la fase (copiada literalmente del plan)
- File ownership del agente asignado a esta fase
- Archivos existentes que la fase va a MODIFICAR (contenido actual)
- Reglas de arquitectura del stack detectado (solo el overview, no todos los docs)
- Checkpoint de la fase anterior (si existe)

**EXCLUIR del Task (nunca cargar):**
- Código de fases anteriores ya completadas
- Archivos que la fase no va a tocar
- Logs, evidence, baselines, healing history
- Otros planes, PRDs, o documentación no relacionada
- Código generado (.g.dart, .freezed.dart, node_modules, build/)
- README, CHANGELOG, o documentación del engine

**EXCLUIR de la respuesta del Task (poda de retorno):**
- Contenido completo de archivos creados (solo devolver paths)
- Stack traces completos (solo primeras 10 líneas si hay error)
- Output completo de lint (solo resumen: N errors, N warnings)

### Phase Task Template

Para cada fase, el main agent spawnea un Task con exactamente este formato:

```
Execute Phase {N}: {phase_name}

CONTEXT:
- Plan: {paste ONLY the phase section, not the full plan}
- Stack: {stack_name}
- Architecture: {paste overview paragraph, max 500 words}
- Files to modify: {list paths}
- Ownership: Only modify files in {ownership_paths}

RULES:
- Run lint after implementation: {stack_lint_command}
- Save checkpoint: node .claude/hooks/implement-checkpoint.mjs {feature} {N} {phase_name}
- If lint fails, apply self-healing (Level 1 first, then Level 2)

RETURN FORMAT:
- files_created: [list of paths]
- files_modified: [list of paths]
- lint_result: pass|fail (N errors, N warnings)
- errors: [brief description if any, max 3 lines]
- phase_status: complete|failed|needs_healing
```

### Context Saturation Prevention

The main agent monitors its own context growth:
1. After each phase completes, the main agent retains ONLY:
   - Updated checkpoint JSON
   - Phase summary (files changed, status) — max 5 lines per phase
   - Cumulative error count
2. Full phase details are persisted in checkpoint files, NOT in agent memory
3. If a phase returns more than 20 lines of output, summarize to 5 lines before storing

### Budget Verification (optional, pre-flight)

Before spawning a Task, the main agent can estimate the context load:
```bash
.quality/scripts/context-budget.sh lib/features/{feature_name}/
```
If the result exceeds 30% of context window → split the phase into sub-phases.

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
- Quality gate: lint 0/0/0 (BLOQUEANTE), compile (BLOQUEANTE), tests pass (BLOQUEANTE)
- Save checkpoint: node .claude/hooks/implement-checkpoint.mjs {feature} {N} {phase_name}
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

```
¿phase_status?
├── complete → Commit parcial + mem_save resumen + siguiente fase
├── needs_healing → Lanzar nuevo Task de healing (ver Self-Healing Protocol)
└── failed → Guardar checkpoint failed + escalar a humano
```

### 5.1.1a Pipeline State Update (Post-Phase) — v5.19.0 Mechanical Enforcement

Despues de guardar el checkpoint, **SIEMPRE** actualizar `pipeline_state.json` para que
`pipeline-phase-guard.mjs` pueda validar la secuencia de fases mecanicamente:

```bash
# Leer estado actual o crear nuevo
PIPELINE_STATE=".quality/evidence/${feature}/pipeline_state.json"
mkdir -p ".quality/evidence/${feature}"
```

El orquestador mantiene y actualiza este archivo despues de CADA fase completada:

```json
{
  "feature": "${feature}",
  "has_ui": true,
  "has_db": true,
  "completed_phases": ["db_infra", "stitch_designs", "design_to_code", "feature_code"],
  "current_phase": "integration",
  "last_updated": "2026-04-05T18:00:00Z"
}
```

**Mapeo de fases del plan a IDs de pipeline_state:**

| Fase del plan | ID en completed_phases | Condicion |
|---------------|----------------------|-----------|
| DB/Infra (AG-03) | `db_infra` | Solo si el plan tiene fase DB |
| Stitch Designs (AG-06) | `stitch_designs` | Solo si proyecto tiene UI |
| Design-to-Code (AG-02) | `design_to_code` | Solo si proyecto tiene UI |
| Feature Code (AG-01) | `feature_code` | Siempre |
| Apps Script (AG-07) | `appscript` | Solo si aplica |
| n8n (AG-05) | `n8n` | Solo si aplica |
| Integration/DI | `integration` | Siempre (si hay fase) |
| QA/Tests (AG-04) | `tests` | Siempre |

**IMPORTANTE**: Si una fase no aplica al proyecto (ej: no hay DB), marcarla como completada
al inicio para que el guard no bloquee las fases dependientes:

```javascript
// Ejemplo: proyecto sin DB ni UI
{
  "completed_phases": ["db_infra", "stitch_designs", "design_to_code"],
  "has_ui": false,
  "has_db": false
}
```

Esto permite que `pipeline-phase-guard.mjs` valide el orden sin falsos positivos.

### 5.1.1b Implementation Delta (Post-Phase) — v5.0 Spec-Code Sync

Despues de guardar el checkpoint, generar el delta block para tracking spec-code:

1. Recopilar del reporte de fase: `files_created`, `files_modified`, `phase_status`, `decisions`
2. Leer archivos esperados del plan (si disponible en `doc/plans/`)
3. Verificar si hubo self-healing (leer `.quality/evidence/${feature}/healing.jsonl`, ultima linea)
4. Generar bloque delta con `generate_phase_delta()` (max 500 tokens):
   - Si implementacion conforme al plan → "Sin deltas — implementacion conforme al plan"
   - Si fase fallo → "Fase fallida — pendiente de resolucion" + error resumido
   - Si self-healing → linea adicional con tipo y resultado
5. Acumular en variable del orquestador: `implementation_deltas.append(delta_block)`

El orquestador mantiene en memoria durante toda la sesion:
```
implementation_deltas: list[str] = []  # uno por fase completada
```

**IMPORTANTE:** Este paso es informativo (nunca bloquea). Si falla la generacion del delta, continuar normalmente.

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

### 6.1b Registrar assets VEG (si hay imagenes generadas)

Si el Paso 3.5 genero imagenes en `doc/veg/{feature}/assets/`:

| Stack | Accion |
|-------|--------|
| Flutter | Copiar a `assets/images/veg/` + registrar en `pubspec.yaml` assets |
| React | Copiar a `public/images/veg/` o `src/assets/veg/` + importar en componentes |
| Python | Copiar a `static/images/veg/` (si tiene frontend) |
| Apps Script | Subir a Google Drive o embeber como base64 en HTML |

Referenciar las imagenes en los widgets/componentes generados en Paso 4, reemplazando los placeholders `[IMAGE: {id}]` con las rutas reales.

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

## Paso 7.5: Acceptance Tests con Gherkin BDD (AG-09a)

> Generar y ejecutar tests BDD en formato Gherkin que validen acceptance criteria del PRD.
> PRD es OBLIGATORIO. Sin PRD no hay AC-XX → no hay acceptance tests → pipeline PARA.

### 7.5.1 Localizar PRD

```
¿Cómo encontrar el PRD?
├── Spec-Driven (Trello/Plane/FreeForm)
│   └── get_evidence(board_id, us_id, "us", "prd") → extraer PRD adjunto
├── Existe doc/prd/{feature}.md o doc/prd/PRD_{feature}.md
│   └── Leer directamente
├── Existe en attachment de la US card/item
│   └── Descargar y leer
└── No se encuentra PRD en NINGUNA ubicacion
    └── ERROR FATAL: "No PRD found. Cannot validate acceptance criteria."
    └── PARAR PIPELINE — no continuar sin PRD
    └── Reportar al usuario: "PRD requerido. Ejecutar /prd primero."
```

Extraer sección "Criterios de Aceptación > Funcionales":
- Extraer cada AC-XX con su descripción
- Ignorar sección "Técnicos"
- Si no hay criterios AC-XX en el PRD → ERROR FATAL, PARAR pipeline

### 7.5.2 Generar archivos .feature

Delegar a AG-09a (ver `agents/acceptance-tester.md`).

Generar un archivo `.feature` por cada UC del plan actual, con un `Escenario` por cada AC-XX:

```gherkin
# language: es
@US-XX @UC-XXX
Característica: {Título del UC-XXX}

  @AC-01
  Escenario: {Descripción del AC-01}
    Dado ...
    Cuando ...
    Entonces ...

  @AC-02
  Escenario: {Descripción del AC-02}
    Dado ...
    Cuando ...
    Entonces ...
```

**Reglas:**
- Tags obligatorios: `@US-XX`, `@UC-XXX`, `@AC-XX` en cada escenario
- Idioma obligatorio: `# language: es`
- Un `.feature` por UC, un `Escenario` por AC-XX

**Ubicación por stack:**

| Stack | Directorio |
|-------|-----------|
| Flutter | `test/acceptance/features/` |
| React | `tests/acceptance/features/` |
| Python | `tests/acceptance/features/` |
| GAS | `tests/acceptance/features/` |

### 7.5.3 Generar step definitions

Generar step definitions usando el framework BDD nativo del stack:

**Flutter (Playwright E2E contra CanvasKit web build):**
- Step file: `e2e/acceptance/steps/UC-XXX_steps.ts`
- Framework: `playwright-bdd` + `@playwright/test`
- Reutilizar `e2e/acceptance/steps/common_steps.ts` si existe
- Screenshot: via `evidenceStep()` en cada paso (PASS y FAIL)
- Traces: `retain-on-failure`
- Reporter: `html` + `json` (OBLIGATORIO ambos)
- Pre-requisito: `flutter build web --web-renderer canvaskit --release`
- Selectores: `getByRole()` semánticos (CanvasKit no genera DOM)

**React (Playwright E2E real):**
- Step file: `tests/acceptance/steps/UC-XXX_steps.ts`
- Framework: `playwright-bdd` + `@playwright/test`
- Reutilizar `tests/acceptance/steps/common_steps.ts` si existe
- Screenshot: via `evidenceStep()` en cada paso (PASS y FAIL)
- Traces: `retain-on-failure`
- Reporter: `html` + `json` (OBLIGATORIO ambos)

**Python (pytest-bdd):**
- Step file: `tests/acceptance/steps/UC_XXX_steps.py`
- Framework: `pytest-bdd`
- Reutilizar `tests/acceptance/steps/common_steps.py` si existe
- Evidence: request/response log por escenario

**GAS (jest-cucumber):**
- Step file: `tests/acceptance/steps/UC-XXX_steps.ts`
- Framework: `jest-cucumber`
- Reutilizar `tests/acceptance/steps/common_steps.ts` si existe

### 7.5.4 Instalar dependencias BDD (si no están)

Verificar que las dependencias BDD están instaladas. Si no, instalarlas:

```bash
# Flutter
flutter pub add --dev bdd_widget_test

# React
npm install -D playwright-bdd

# Python
pip install pytest-bdd

# GAS
npm install -D jest-cucumber
```

### 7.5.5 Ejecutar tests

```bash
# Flutter
flutter test test/acceptance/ --reporter json > reports/cucumber-report.json

# React
npx bddgen && npx playwright test tests/acceptance/ --reporter=json

# Python
pytest tests/acceptance/ --cucumberjson=reports/cucumber-report.json

# GAS
npx jest tests/acceptance/ --json --outputFile=reports/cucumber-report.json
```

### 7.5.6 Recopilar evidencia

Guardar en `.quality/evidence/{feature}/acceptance/`:
- Screenshots automáticos en cada Escenario (AC-01.png, AC-02.png...)
- JSON report en formato Cucumber estándar (`cucumber-report.json`)
- Traces (solo Playwright)

### 7.5.7 Generar HTML Evidence Report (Flutter y React OBLIGATORIO)

> Para Flutter y React, generar informe HTML self-contained con screenshots base64.
> El humano abre este archivo en su browser para validar calidad visual del E2E.

1. Leer `results.json` de `.quality/evidence/{feature}/acceptance/`
2. Para cada AC-XX con screenshot → leer PNG, convertir a base64
3. Generar HTML usando el template definido en `agents/acceptance-tester.md` seccion 8
4. Guardar en `.quality/evidence/{feature}/acceptance/e2e-evidence-report.html`

**El informe DEBE incluir:**
- Pass rate (%) con color verde/amarillo/rojo
- Card por cada AC-XX con: status badge, screenshot embebido, steps, duration
- Error details con stack trace para los FAIL
- Resumen de viewports testeados

### 7.5.8 Generar PDF de evidencia

Generar PDF con estructura:
- **Titulo**: Acceptance Tests — {feature} / UC-XXX
- **Resumen**: Total escenarios, pasados, fallidos, pass rate
- **Tabla AC**: AC-XX | Descripcion | Resultado (PASS/FAIL)
- **Detalle por escenario**: Steps ejecutados, screenshot path, logs
- **Footer**: Timestamp, branch, commit SHA

Guardar en `.quality/evidence/{feature}/acceptance/acceptance-report.pdf`

### 7.5.9 Adjuntar evidencia (si spec-driven)

Si el flujo es spec-driven (tiene board_id y UC card):
```
attach_evidence(board_id, uc_card_id, "uc", "acceptance", pdf_path)
```
Agregar comentario estructurado en la card del UC:
```
Acceptance Tests — UC-XXX
{N} passed / {M} failed | Pass rate: XX%
Evidencia adjunta: acceptance-report.pdf
HTML report: .quality/evidence/{feature}/acceptance/e2e-evidence-report.html
```

### 7.5.10 Commit

```bash
git add test/acceptance/ tests/acceptance/ e2e/acceptance/ .quality/evidence/{feature}/acceptance/
git commit -m "test(acceptance): E2E acceptance tests + evidence report for UC-XXX"
```

**NOTA**: Si los acceptance tests fallan, NO bloquear aqui. Reportar fallos y dejar que AG-09b decida el veredicto en Paso 7.7.

---

## Paso 7.6: Quality Audit (AG-08)

> Ejecutar AG-08 Quality Auditor para verificar calidad de código.
> Ver `agents/quality-auditor.md` para checks completos.

Ejecutar audit completo:
1. Test Quality Audit (tests reales, no triviales)
2. Coverage Legitimacy Audit (sin exclusiones tramposas)
3. Architecture Compliance Audit (capas respetadas)
4. Convention Compliance Audit (patrones del stack)
5. Dead Code Detection (no aumentó)

Generar `.quality/evidence/{feature}/audit.json` y `.quality/evidence/{feature}/report.md`.

Emitir veredicto: **GO / CONDITIONAL GO / NO-GO**

Si **NO-GO** → Aplicar self-healing (ver Self-Healing Protocol) y re-auditar. Máximo 2 intentos.

---

## Paso 7.7: Acceptance Gate (AG-09b)

> Validación independiente de que la feature cumple los acceptance criteria.
> PRD es obligatorio (Paso 7.5 ya lo verifico). Si llegamos aqui, el PRD existe.

### 7.7.1 Ejecutar AG-09b Acceptance Validator

Delegar a AG-09b (ver `agents/acceptance-validator.md`). El validador recibe:
- PRD con AC-XX (misma fuente que 7.5.1)
- `git diff main..HEAD` (código implementado)
- Resultados de tests unitarios (AG-04, Paso 7)
- Resultados de acceptance tests (AG-09a, Paso 7.5)
- Screenshots/evidencia generada
- audit.json de AG-08 (Paso 7.6)

### 7.7.2 Evaluar veredicto

```
ACCEPTED    → Continuar a Paso 8 (crear PR)
CONDITIONAL → Healing (ver 7.7.3), luego re-validar
REJECTED    → Healing (ver 7.7.3), luego re-validar
```

### 7.7.3 Healing de Acceptance

Si CONDITIONAL o REJECTED:
1. Leer `acceptance-report.json` → identificar criterios FAIL
2. Para cada criterio FAIL:
   - Falta código → implementar lo faltante
   - Falta test → AG-09a regenera solo los fallidos
   - Test falla → corregir implementación o test
3. Re-ejecutar acceptance tests (solo los fallidos)
4. Re-ejecutar validaciones: lint + compile + AG-09b
5. **Máximo 2 intentos** de healing de acceptance
6. Si tras 2 intentos sigue REJECTED → reportar al humano con `acceptance-report.md`

### 7.7.4 Registrar healing

```bash
node .claude/hooks/implement-healing.mjs {feature} acceptance {level} "{action}" "{result}"
```

### 7.7a Implementation Status — modo freeform (v5.0 Spec-Code Sync)

Si el pipeline NO es spec-driven (no hay board_id ni Trello/Plane configurado):

1. Verificar que `implementation_deltas[]` tiene al menos 1 entrada
2. Derivar `uc_id` del nombre del plan (e.g. `uc_001_plan.md` → `UC-001`) o usar `"FREEFORM"`
3. Obtener branch name actual: `git rev-parse --abbrev-ref HEAD`
4. Buscar PRD en `doc/prds/` usando `find_prd_path(project_path, feature=feature_name)`
5. Si PRD encontrado: ejecutar `append_implementation_status(prd_path, uc_id, branch, implementation_deltas)`
6. Commit del PRD actualizado:
   ```bash
   git add doc/prds/{prd_file}
   git commit -m "docs({feature}): add Implementation Status for {uc_id}"
   ```
7. Si no se encuentra PRD → WARNING en output, no bloquear

**IMPORTANTE:** En modo spec-driven, este paso se ejecuta en 8.5.3a en su lugar.

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

## Acceptance Evidence

{Generar tabla desde acceptance-report.json de AG-09b. Si no hay PRD/AC-XX, omitir sección.}

| Criterio | Status | Evidencia |
|----------|--------|-----------|
| AC-01: {descripción} | ✅ PASS | [screenshot](evidence/AC-01.png) |
| AC-02: {descripción} | ✅ PASS | [screenshot](evidence/AC-02.png) |
| AC-XX: {descripción} | ⚠️ CONDITIONAL | [trace](evidence/AC-XX_trace.zip) |

**AG-09 Verdict**: {ACCEPTED / CONDITIONAL / REJECTED}
**AG-08 Verdict**: {GO / CONDITIONAL GO / NO-GO}

## Test Plan

- [ ] Tests unitarios pasan con 85%+ coverage
- [ ] Lint sin errores
- [ ] Build exitoso
- [ ] Acceptance tests pasan
- [ ] {Criterios adicionales del plan}

## Developer Feedback

{Si existe .quality/evidence/${feature}/feedback-summary.json con open > 0:}

| ID | Severity | AC-XX | Status | GitHub |
|----|----------|-------|--------|--------|
{Fila por cada FB-NNN open}

{Si no hay feedback o todos resueltos: "No developer feedback reported."}

## Plan Reference

`{path al plan}`

---
🤖 Implementado con [SpecBox Engine](https://github.com/jesusperezdeveloper/specbox-engine) `/implement`
EOF
)"
```

### 8.4 Vincular con work item (si aplica)

Si el plan referencia un work item de Plane/Trello:
- Anadir link a la PR en un comentario del work item
- Actualizar estado a "En Pruebas"

---

## Paso 8.5: Merge Secuencial (Post-PR)

> Si estamos en modo autopilot (ejecutando múltiples cards en secuencia),
> merge antes de iniciar la siguiente card. Esto evita conflictos entre PRs.

### 8.5.0 Validacion pre-merge (BLOQUEANTES)

> Estas validaciones se ejecutan ANTES de verificar condiciones de auto-merge.
> Son HARD BLOCKS — si fallan, el merge NO puede proceder bajo ninguna circunstancia.

```
VALIDACION 1: ¿Estamos en una rama feature/?
  branch = git branch --show-current
  ¿branch empieza con "feature/"?
  ├── SI: OK
  └── NO: ❌ ERROR FATAL
      → "BLOQUEADO: No se puede hacer merge desde '{branch}'.
         El protocolo requiere una rama feature/ con PR asociada.
         Algo salto el Paso 1 (Crear Rama de Feature)."
      → PARAR INMEDIATAMENTE.

VALIDACION 2: ¿Existe PR abierta para esta rama?
  gh pr view --json state,url 2>/dev/null
  ¿Existe PR con state == "OPEN"?
  ├── SI: OK — guardar URL para referencia
  └── NO: ❌ ERROR FATAL
      → "BLOQUEADO: No hay PR abierta para la rama actual.
         El Paso 8 debio crear una PR antes de llegar aqui.
         Sin PR no hay acceptance evidence ni review."
      → PARAR. Ofrecer ejecutar Paso 8 como recovery.

VALIDACION 3 (solo Trello spec-driven): ¿El UC esta en estado correcto?
  uc_data = get_uc(board_id, uc_id)
  ¿uc_data.status == "in_progress"?
  ├── SI: OK — el UC fue iniciado correctamente con start_uc
  └── NO: ⚠️ WARNING
      → "El UC {uc_id} esta en estado '{uc_data.status}' en lugar de 'in_progress'.
         Esto indica que start_uc no fue llamado o fallo."
      → Intentar start_uc como recovery
      → Continuar con WARNING en el log

VALIDACION 4: ¿El flag veg_images_pending esta activo?
  ¿veg_images_pending == true?
  ├── SI: Auto-merge BLOQUEADO
  │   → "⚠️ Auto-merge bloqueado: VEG Pilar 1 incompleto ({N} imagenes placeholder).
  │      Opciones:
  │      a) Generar imagenes con /implement --images-only
  │      b) Aprobar merge manualmente aceptando calidad visual degradada
  │      c) Crear PENDING_IMAGES.md y resolver post-merge"
  │   → Esperar decision del usuario
  └── NO: OK
```

### 8.5.1 Verificar condiciones de auto-merge

Auto-merge SOLO si se cumplen TODAS estas condiciones:
- AG-08 verdict = **GO** o **CONDITIONAL GO**
- AG-09b verdict = **ACCEPTED** (no INVALIDATED)
- Todos los acceptance tests pasan
- El usuario ha confirmado modo autopilot
- **No hay feedback abierto con severity critical o major** (verificar feedback-summary.json)
- **No hay VEG images pendientes** (`veg_images_pending == false`) — NUEVO v4.0.1

### 8.5.1a Verificar feedback abierto

Si existe `.quality/evidence/${feature}/feedback-summary.json`:
- Leer campo `blocking`
- Si `blocking == true` → merge bloqueado por feedback

```
¿Todas las condiciones se cumplen?
├── SÍ → Paso 8.5.2 (auto-merge)
└── NO → Pausar, notificar al usuario, esperar aprobación manual
         → Si el bloqueo es por feedback:
           "⚠️ Merge bloqueado: {N} feedback tickets abiertos ({blocking_ids})"
           "Resolver con /feedback resolve FB-NNN o aprobar manualmente"
         → Si el bloqueo es por AG-09b INVALIDATED:
           "⚠️ AG-09b verdict fue INVALIDATED por feedback {FB-NNN}."
           "Re-ejecutar /implement para re-validar o resolver feedback primero."
         → Cuando el usuario apruebe: continuar con 8.5.2
```

### 8.5.1a Escribir Implementation Status en PRD (v5.0 Spec-Code Sync)

Antes del merge, escribir el Implementation Status en el PRD:

1. Localizar PRD del feature/US actual:
   - Si spec-driven: buscar en `doc/prds/` por us_id o feature name
   - Si freeform: ya se hizo en Paso 7.7a (saltar este paso)
2. Compilar `implementation_deltas[]` en seccion Markdown con `compile_uc_status(uc_id, branch, deltas)`
3. Append al PRD con `append_implementation_status(prd_path, uc_id, branch, implementation_deltas)`
4. Commit del PRD actualizado:
   ```bash
   git add doc/prds/{prd_file}
   git commit -m "docs({feature}): add Implementation Status for {uc_id}"
   git push origin {branch}
   ```
5. Si no se encuentra PRD → WARNING, no bloquear el merge

**Tambien disponible como MCP tool:** `write_implementation_status(project_path, uc_id, branch, phase_deltas)`
**Consulta posterior:** `get_implementation_status(project_path, item_id)` — devuelve JSON con deltas y overall_status

### 8.5.2 Merge

```bash
gh pr merge --squash --delete-branch
```

### 8.5.3 Actualizar main

```bash
git checkout main
git pull origin main
```

### 8.5.4 Actualizar work item

#### Todos los backends (Trello/Plane/FreeForm):
1. Llamar `move_uc(board_id, uc_id, "review")` — mueve UC a **Review** (NO a Done)
2. Adjuntar evidencia: `attach_evidence(board_id, uc_id, "uc", "acceptance", evidence_md)`
3. Reportar acceptance tests: `mark_ac_batch(board_id, uc_id, results)`

> **IMPORTANTE**: El agente NUNCA mueve a Done. Solo a Review.
> El humano revisa la PR, ejecuta flujos manuales, verifica E2E,
> y SOLO ENTONCES mueve a Done (manualmente o via complete_uc).
> Si todos los UCs de la US estan en Review/Done, la US se queda
> en su estado actual — el humano decide cuando mover la US a Done.

### 8.5.5 Siguiente UC/card

#### Si origen es Trello (US-XX mode):
```
→ Llamar find_next_uc(board_id) para obtener siguiente UC en Backlog
→ Si hay UC disponible:
  → start_uc(board_id, uc_id) — mueve a In Progress
  → Volver a Paso 0.1a con el nuevo UC
  → El nuevo feature branch parte del main actualizado (post-merge)
  → CERO conflictos garantizados
→ Si no hay mas UCs en Backlog:
  → Verificar si todos los UCs de la US estan en Review o Done
  → NO mover US a Done — el humano decide tras revisar todas las PRs
  → Finalizar pipeline con resumen global
```

#### Si origen es plan local:
```
→ Volver a Paso 0 con la siguiente card
→ El nuevo feature branch parte del main actualizado (post-merge)
→ CERO conflictos garantizados
```

Si no hay mas cards → finalizar pipeline con resumen global.

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

## Self-Healing Protocol

Cuando una fase falla, el sistema intenta auto-recuperarse antes de pedir intervención humana.

### Nivel 1: Auto-Fix (automático, sin preguntar)

Para errores de lint/format:
1. Ejecutar auto-fix del stack:
   - Flutter: `dart fix --apply && dart format .`
   - React: `npx eslint --fix . && npx prettier --write .`
   - Python: `ruff check --fix . && ruff format .`
   - GAS: `npx eslint --fix .`
2. Re-ejecutar validación
3. Si pasa → continuar. Si falla → escalar a Nivel 2

### Nivel 2: Diagnóstico + Fix (automático, 1 intento)

Para errores de compilación o imports:
1. Leer el error completo (primeras 50 líneas)
2. Identificar la causa raíz:
   - Import faltante → añadir import
   - Tipo incorrecto → corregir tipo
   - Archivo referenciado no existe → crear stub o corregir path
   - Dependencia faltante → añadir a pubspec/package.json/requirements
3. Aplicar fix
4. Re-ejecutar validación
5. Si pasa → continuar. Si falla → escalar a Nivel 3

### Nivel 3: Rollback parcial (automático, último recurso)

Si el error persiste tras Nivel 2:
1. Guardar checkpoint con status "failed" y error details
2. `git stash` los cambios de la fase actual
3. Registrar en `.quality/evidence/${feature}/healing.jsonl`:
   ```jsonl
   {"phase": N, "error": "...", "level": 3, "action": "rollback", "timestamp": "..."}
   ```
4. Intentar la fase una vez más desde cero (fresh attempt)
5. Si falla de nuevo → escalar a Nivel 4

### Nivel 4: Intervención humana (reportar y pausar)

Si nada funciona:
1. Guardar checkpoint con status "needs_human" y full error context
2. Generar `.quality/evidence/${feature}/error_report.md` con:
   - Fase que falló y número de intentos
   - Error completo
   - Fixes intentados
   - Archivos modificados en la fase
   - Sugerencia de resolución
3. Reportar al usuario: "Phase {N} failed after 2 attempts. See error report at .quality/evidence/{feature}/error_report.md"
4. Preguntar: "¿Quieres que intente un approach diferente, o prefieres intervenir manualmente?"

### Retry Budget

- Máximo 2 intentos completos por fase (original + 1 retry)
- Máximo 3 auto-fixes de lint por fase
- Si 2 fases consecutivas fallan → detener pipeline y generar report completo
- Total de auto-heals por implementación: máximo 8

### Logging

TODOS los intentos de self-healing se registran en `.quality/evidence/${feature}/healing.jsonl`:
```jsonl
{"phase": 1, "error": "dart analyze: 3 errors", "level": 1, "action": "dart fix --apply", "result": "resolved", "timestamp": "..."}
{"phase": 3, "error": "build failed: missing import", "level": 2, "action": "added import to user_bloc.dart", "result": "resolved", "timestamp": "..."}
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
- [ ] Stitch Design Gate pasado (Paso 0.5d — si UC tiene pantallas)
- [ ] VEGs cargados del plan (si aplica)
- [ ] Disenos Stitch generados con directivas VEG (si aplica)
- [ ] Usuario informado de costes antes de generar (Paso 3.5.0 — €0 con Canva)
- [ ] MCP health check ejecutado antes de generar imagenes (Paso 3.5.1)
- [ ] Imagenes generadas con MCP o PENDING_IMAGES.md creado (Paso 3.5.4)
- [ ] Motion dependencies instaladas antes de design-to-code (Paso 4.0)
- [ ] Design-to-code ejecutado con Motion Catalog (si VEG activo)
- [ ] Mobile hover→tap enforcement aplicado (si proyecto responsive/mobile)
- [ ] Assets VEG registrados en el proyecto (Paso 6.1b, si aplica)
- [ ] Todas las fases del plan implementadas
- [ ] Commits parciales por fase
- [ ] Integracion completada (DI, routing, config)
- [ ] Build sin errores
- [ ] Tests con 85%+ coverage
- [ ] Lint sin errores
- [ ] PRD con acceptance criteria (AC-XX) localizado
- [ ] Acceptance tests generados (1 por criterio funcional)
- [ ] Evidencia visual capturada (screenshots/traces)
- [ ] AG-08 veredicto GO o CONDITIONAL GO
- [ ] AG-09 veredicto ACCEPTED
- [ ] PR creada con sección Acceptance Evidence
- [ ] Work item actualizado (si aplica)
- [ ] Self-healing log limpio (0 level 3+ events)
- [ ] Healing budget no excedido (≤8 auto-heals total)

---

## Referencia Rapida

| Concepto | Valor |
|----------|-------|
| Planes | `doc/plans/{nombre}_plan.md` |
| Diseños | `doc/design/{feature}/` |
| Branch naming | `feature/{nombre-plan-kebab-case}` |
| Coverage minimo | 85% |
| Commits | Uno por fase + integracion + tests + acceptance |
| PR body | Summary + Changes + Stitch + Acceptance Evidence + Test Plan |
| Acceptance tests | `test/acceptance/` o `tests/acceptance/` |
| Evidencia acceptance | `.quality/evidence/{feature}/acceptance/` |
| AG-08 veredicto | GO / CONDITIONAL GO / NO-GO |
| AG-09 veredicto | ACCEPTED / CONDITIONAL / REJECTED |
| Merge secuencial | Auto-merge si AG-08=GO + AG-09=ACCEPTED |

---

## Referencia MCP Trello (dev-engine-trello)

| Tool | Uso en /implement |
|------|-------------------|
| `get_us(board_id, us_id)` | Paso 0: cargar datos de la US |
| `list_uc(board_id, us_id)` | Paso 0: listar UCs hijos |
| `get_uc(board_id, uc_id)` | Paso 0: detalle completo del UC (ACs, pantallas) |
| `find_next_uc(board_id)` | Paso 0/8.5: determinar siguiente UC a implementar |
| `start_uc(board_id, uc_id)` | Paso 0: mover UC a In Progress + timestamp |
| `complete_uc(board_id, uc_id, evidence)` | Paso 8.5: mover UC a Done + actualizar US checklist |
| `move_us(board_id, us_id, target)` | Paso 8.5: mover US cuando todos UCs Done |
| `mark_ac_batch(board_id, uc_id, results)` | Paso 8.5: reportar resultados de ACs a Trello |
| `attach_evidence(board_id, id, type, kind, md)` | Paso 8.5: adjuntar delivery report como PDF |
| `get_evidence(board_id, id, type)` | Paso 0: buscar plan/PRD adjunto |
