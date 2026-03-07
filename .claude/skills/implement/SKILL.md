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

1. Obtener board_id de `.claude/settings.local.json` → `trello.boardId`
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
  ├── find_next_uc → UC-001 (Ready)
  │   ├── start_uc(UC-001) → In Progress
  │   ├── Implementar (Pasos 1-7.7)
  │   ├── complete_uc(UC-001) → Done
  │   ├── Merge secuencial (Paso 8.5)
  │   └── Pull main
  ├── find_next_uc → UC-002 (Ready)
  │   ├── start_uc(UC-002) → In Progress
  │   ├── ... (mismo ciclo)
  │   └── Pull main
  └── No mas UCs en Ready → Finalizar
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
1. PREPARAR contexto (max ~8,700 tokens):
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

### 4.3 Commit parcial de diseños

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
| Phase description | ~500 tokens | Del plan, solo la sección de la fase |
| Architecture rules | ~2,000 tokens | Solo el overview del stack, no todos los docs |
| Relevant source files | ~5,000 tokens | Solo archivos que la fase modifica |
| Stack patterns | ~1,000 tokens | Patterns relevantes (ej: solo BLoC si es state mgmt) |
| Checkpoint state | ~200 tokens | JSON minimal del checkpoint anterior |
| **Total per task** | **~8,700 tokens** | **< 5% de la ventana de contexto** |

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
- Save checkpoint: .claude/hooks/implement-checkpoint.sh {feature} {N} {phase_name}
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

```
¿phase_status?
├── complete → Commit parcial + mem_save resumen + siguiente fase
├── needs_healing → Lanzar nuevo Task de healing (ver Self-Healing Protocol)
└── failed → Guardar checkpoint failed + escalar a humano
```

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

## Paso 7.5: Acceptance Tests (AG-09a)

> Generar y ejecutar tests que validen acceptance criteria del PRD.
> Si no hay PRD disponible, saltar este paso con WARNING.

### 7.5.1 Localizar PRD

```
¿Cómo encontrar el PRD?
├── Plan referencia work item (PROYECTO-XX)
│   └── plane:retrieve_work_item_by_identifier → extraer PRD del description
├── Existe doc/prd/{feature}.md
│   └── Leer directamente
└── No se encuentra PRD
    └── WARNING: "No PRD found. Skipping acceptance tests."
    └── Saltar a Paso 7.6
```

### 7.5.2 Extraer Acceptance Criteria

Parsear sección "Criterios de Aceptación > Funcionales":
- Extraer cada AC-XX con su descripción
- Ignorar sección "Técnicos"
- Si no hay criterios AC-XX en el PRD → WARNING y saltar

### 7.5.3 Generar Acceptance Tests

Delegar a AG-09a (ver `agents/acceptance-tester.md`). Para cada AC-XX:

**Flutter (Patrol):**
- Archivo: `test/acceptance/ac_{NN}_{description_snake}_test.dart`
- Framework: `patrol` + `alchemist` (si golden aplica)
- Screenshot: `$.takeScreenshot('AC-{NN}_{description}')`
- Evidencia en: `.quality/evidence/{feature}/acceptance/`

**React (Playwright):**
- Archivo: `tests/acceptance/ac-{NN}-{description-kebab}.spec.ts`
- Framework: `@playwright/test`
- Screenshot: `page.screenshot({path: '.quality/evidence/{feature}/acceptance/AC-{NN}.png'})`
- Traces: `context.tracing.start()` / `stop()`

**Python (pytest):**
- Archivo: `tests/acceptance/test_ac_{NN}_{description_snake}.py`
- Framework: `pytest` + `httpx.AsyncClient`
- Evidence: request/response log a `.quality/evidence/{feature}/acceptance/AC-{NN}.json`

### 7.5.4 Ejecutar Acceptance Tests

```bash
# Flutter
flutter test test/acceptance/ --reporter expanded

# React
npx playwright test tests/acceptance/

# Python
pytest tests/acceptance/ -v
```

### 7.5.5 Generar Evidencia

Guardar en `.quality/evidence/{feature}/acceptance/`:
- Screenshots por criterio (AC-01.png, AC-02.png...)
- Traces (solo Playwright)
- `results.json` con resumen de ejecución

### 7.5.6 Commit

```bash
git add test/acceptance/ tests/acceptance/ .quality/evidence/{feature}/acceptance/
git commit -m "test({feature}): add acceptance tests for {N} criteria"
```

**NOTA**: Si los acceptance tests fallan, NO bloquear aquí. Reportar fallos y dejar que AG-09b decida el veredicto en Paso 7.7.

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
> Si no hay PRD disponible (Paso 7.5 fue saltado), saltar este paso.

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
.claude/hooks/implement-healing.sh {feature} acceptance {level} "{action}" "{result}"
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
🤖 Implementado con [SDD-JPS Engine](https://github.com/jesusperezdeveloper/jps_dev_engine) `/implement`
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

### 8.5.1 Verificar condiciones de auto-merge

Auto-merge SOLO si se cumplen TODAS estas condiciones:
- AG-08 verdict = **GO** o **CONDITIONAL GO**
- AG-09b verdict = **ACCEPTED** (no INVALIDATED)
- Todos los acceptance tests pasan
- El usuario ha confirmado modo autopilot
- **No hay feedback abierto con severity critical o major** (verificar feedback-summary.json)

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

#### Si origen es Trello:
1. Llamar `complete_uc(board_id, uc_id, evidence)` — mueve UC a Done + actualiza checklist US
2. Si `us_all_done == true` (todos los UCs de la US completados):
   - Llamar `move_us(board_id, us_id, "done")` — mover US a Done
   - Adjuntar delivery report: `attach_evidence(board_id, us_id, "us", "delivery", report_md)`
3. Reportar acceptance tests a Trello: `mark_ac_batch(board_id, uc_id, results)`

#### Si origen es Plane:
- Actualizar estado a "Finalizado"

### 8.5.5 Siguiente UC/card

#### Si origen es Trello (US-XX mode):
```
→ Llamar find_next_uc(board_id) para obtener siguiente UC en Ready
→ Si hay UC disponible:
  → start_uc(board_id, uc_id) — mueve a In Progress
  → Volver a Paso 0.1a con el nuevo UC
  → El nuevo feature branch parte del main actualizado (post-merge)
  → CERO conflictos garantizados
→ Si no hay mas UCs en Ready:
  → Verificar si todos los UCs de la US estan en Done
  → Si todos Done → move_us a Done + delivery report
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
