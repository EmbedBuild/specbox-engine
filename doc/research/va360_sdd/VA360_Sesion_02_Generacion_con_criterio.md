# VA360 · Sesión 2 de 5 — Claude Code: generación de código con criterio

> **Spec-Driven Development para equipos técnicos**
> VALEN · VA360 LABS
> *Bloque 1 · Sesión 2 de 5 · 42 slides*

**Fuente original:** [VA360_Sesion_02_Generacion_con_criterio _ Pegasus - Google Slides.pdf](VA360_Sesion_02_Generacion_con_criterio%20_%20Pegasus%20-%20Google%20Slides.pdf)

---

## Agenda de la sesión

> *Slide 02 / 42*

Lo que vamos a ver hoy:

1. Repaso de la sesión 1
2. Por qué el "vibe coding" se rompe a partir de cierto tamaño
3. Qué es Spec-Driven Development y por qué es la metodología de referencia en 2026
4. Las 4 fases del flujo SDD · Specify → Plan → Tasks → Implement
5. SDD "a mano" en Claude Code con slash commands propios
6. SDD con tooling · GitHub Spec Kit, Kiro, otras opciones
7. Mantener la spec viva · spec drift, regeneración, validación cruzada
8. Cierre, deberes y preguntas

---

# MÓDULO 01 · Repaso: qué hicimos, qué tocaba hacer

> *Slide 03 / 42*

## 1 · Recordatorio Sesión 1 — Tres ideas que cerraron la sesión 1

> *Slide 04 / 42*

1. **Memoria explícita en archivos.** `CLAUDE.md` + auto-memoria en `~/.claude/projects/`. Lo que está en Git, es del equipo.
2. **Empieza minimalista.** `CLAUDE.md` + `settings.json` + 1–2 commands. Ya tienes el 80% del valor.
3. **Explore → Plan → Code → Commit.** Plan Mode (`Shift+Tab×2`) y editar el plan con `Ctrl+G`: las dos teclas más usadas.

## 2 · Deberes que tocaban — Lo que teníais que traer hecho

> *Slide 05 / 42*

1. Crear la estructura `.claude/` en un proyecto vuestro.
2. Escribir un `CLAUDE.md` con las 5 secciones (Stack, Comandos, Convenciones, Decisiones, Anti-patrones).
3. Crear vuestro primer slash command propio.
4. Hacer al menos un ciclo completo Explore → Plan → Code → Commit en una tarea real.
5. Traer dos preguntas concretas sobre algo que no funcionó.

## Conexión con la sesión de hoy

> *Slide 06 / 42*

**Explore → Plan → Code → Commit era la versión simple.**

Hoy lo formalizamos: SDD versiona el "Plan" en artefactos y convierte la spec en la fuente de verdad. **No el código.**

---

# MÓDULO 02 · El problema: por qué el vibe coding se rompe

> *Slide 07 / 42*

## Definición operativa — Qué es "vibe coding"

> *Slide 08 / 42*

Pedirle a un agente código por intuición, en lenguaje natural, sin estructura previa. Iterar hasta que "funciona".

> Funciona genial para prototipos. Se cae en producción.

**El término:** lo popularizó Andrej Karpathy a principios de 2025. Llevamos más de un año largo viendo dónde se cae.

## Los datos de 2026 — Lo que dicen los benchmarks y el trabajo de campo

> *Slide 09 / 42*

| Métrica | Cifra | Fuente |
|---|---|---|
| Tasa de código vulnerable generado por LLMs | **9.8 – 42.1 %** | Yan et al., 2025 |
| Issues introducidos por IA viviendo en repos productivos | **110 000+** | arXiv, feb 2026 |
| Menos "regenerar desde cero" con flujo SDD vs ad-hoc | **10×** | GitHub, 2025-2026 |
| Features documentadas con spec-first (Kiro) | **40h → 8h** | AWS Kiro, 2026 |

## El patrón que vais a reconocer — Vibe coding vs SDD

> *Slide 10 / 42*

| ❌ Vibe coding | ✅ Spec-Driven Development |
|---|---|
| Pasan los unit tests | La spec define el contrato |
| Viola un patrón arquitectónico | El plan define la arquitectura |
| Rompe un contrato de API que nadie escribió | Las tareas definen el orden |
| Mete un anti-patrón de seguridad que aflora en producción | El código es solo el output, regenerable |

> "El test pasa, pero algo está mal y nadie sabe qué."
> vs
> "La spec es la fuente de verdad. El código es desechable."

## La frase que lo resume

> *Slide 11 / 42*

> **"The spec is the prompt."**
>
> La spec, escrita con suficiente detalle, **es** el prompt. Los agentes son cada vez más capaces; lo que sigue siendo escaso es la claridad.

---

# MÓDULO 03 · Qué es Spec-Driven Development

> *Slide 12 / 42*

## Definición operativa — SDD en una frase

> *Slide 13 / 42*

**La idea clave:**

> Una metodología en la que una **especificación ejecutable y versionada en control de código** es la única fuente de verdad. El equipo (o un agente) escribe primero una spec detallada, deriva un plan, lo trocea en tareas atómicas, y solo entonces genera código. Si los requisitos cambian, se edita la spec y se regenera lo que toca.

Referencia: <https://es.wikipedia.org/wiki/Desarrollo_dirigido_por_especificaciones>

## El giro mental — Antes · con SDD

> *Slide 14 / 42*

| Antes | Con SDD |
|---|---|
| Código = fuente de verdad. La doc se queda obsoleta. | Spec = fuente de verdad. El código es output regenerable. |
| Cambias el código, intentas actualizar la doc. | Cambias la spec, regeneras el código afectado. |
| Conocimiento en cabezas y wikis dispersas. | Conocimiento en specs versionadas que el agente lee. |
| Implementación = lo caro. | Implementación = barata. Lo escaso es la claridad. |

## Cómo llegamos aquí — Línea temporal corta

> *Slide 15 / 42*

| Fecha | Hito |
|---|---|
| **2025 · Q1** | Karpathy populariza "vibe coding". Funciona para prototipos. |
| **2025 · Q2-Q3** | Primeros experimentos formales: equipos escriben spec antes de prompt. |
| **2025 · Sep** | GitHub abre Spec Kit. AWS lanza Kiro. |
| **2026 · Ene** | Paper fundacional arXiv: *"Spec-Driven Development: From Code to Contract"*. |
| **2026 · Q1-Q2** | Spec Kit pasa de 70k stars. DeepLearning.AI lanza curso oficial. SDD es mainstream. |

## Encaje con prácticas existentes — SDD vs TDD vs BDD vs PRD vs DDD

> *Slide 16 / 42*

| Práctica | Qué define | Relación con SDD |
|---|---|---|
| **TDD** (Test-Driven Development) | Cómo se comporta a nivel de unidad | Complementaria · las tareas SDD pueden exigir TDD dentro |
| **BDD** (Behavior-Driven Development) | Escenarios de usuario observables | SDD da los invariantes estructurales que BDD asume |
| **PRD** (Product Requirements Document) | Documento para humanos | SDD es el equivalente ejecutable y vivo |
| **DDD** (Domain-Driven Design) | Modelado del dominio | SDD puede materializar la *ubiquitous language* en spec |

---

# MÓDULO 04 · Las cuatro fases — Specify → Plan → Tasks → Implement

> *Slide 17 / 42*

## El workflow oficial de SDD — Cuatro fases

> *Slide 18 / 42*

> Cada fase produce un artefacto que alimenta a la siguiente.
> **No se pasa de fase sin validar la anterior.**

| Fase | Nombre | Qué hace |
|---|---|---|
| **01** | **Specify** | Qué se construye y por qué. User journeys, criterios de éxito. *Sin stack técnico.* |
| **02** | **Plan** | Stack, arquitectura, decisiones técnicas. Por fases: Foundation, Core, Polish. |
| **03** | **Tasks** | Trocear el plan en tareas atómicas con dependencias y archivos. |
| **04** | **Implement** | El agente ejecuta tareas. El humano revisa cambios pequeños y enfocados. |

## Fase 01 · Specify — Qué se construye, por qué — sin stack

> *Slide 19 / 42*

**Produce: `spec.md`**

- ✓ User stories y journeys
- ✓ Requisitos funcionales
- ✓ Criterios de éxito medibles
- ✓ Casos frontera identificados

**No contiene:**

- ✗ Tecnologías concretas
- ✗ Estructura de carpetas
- ✗ Diseño de base de datos

**Ejemplo de prompt:**

> Construye una aplicación que me ayude a organizar mis fotos en álbumes separados. Los álbumes se agrupan por fecha y se pueden reorganizar arrastrando en la página principal. Los álbumes nunca están anidados. Dentro de cada álbum, las fotos se previsualizan en mosaico.

## Fase 02 · Plan — Cómo se construye — stack y arquitectura

> *Slide 20 / 42*

**Produce: `plan.md`**

- Stack técnico (frameworks, lenguajes, librerías)
- Arquitectura y patrones
- Modelo de datos
- Fases: Foundation → Core → Polish
- Check contra "constitution" del proyecto

**Constitution — principios no negociables del proyecto.** Spec Kit la introduce como archivo. Aplica en cada fase. Ejemplos:

- "TDD obligatorio"
- "CLI-first en toda librería"
- "Sin SQL crudo, todo vía ORM"
- "Tipos estrictos, prohibido `any`"

## Fase 03 · Tasks — El desglose atómico

> *Slide 21 / 42*

**Produce: `tasks.md`**

- Tareas atómicas (minutos, no días)
- Dependencias entre tareas
- Marcador `[P]` si paraleliza
- Rutas de archivo concretas
- Tests primero si aplica TDD

**Una tarea queda así:**

```markdown
## Task 2.3 [P] · POST /albums

**Archivos:**
src/api/albums/create-album.controller.ts
src/api/albums/dto/create-album.dto.ts

**Depende de:** Task 2.1 (modelo)
                Task 2.2 (service)

**Test primero:**
create-album.controller.spec.ts

**Criterios:**
· valida con Zod
· 201 con Location header
· 409 si nombre duplicado
```

## Fase 04 · Implement — El código, por fin

> *Slide 22 / 42*

**Una tarea cada vez.** Diffs pequeños, enfocados. No dumps de mil líneas. El humano revisa cambios pequeños y aprueba.

**Por fases. Validar antes de avanzar.** Implementación monolítica = contexto saturado = errores.

---

# MÓDULO 05 · SDD a mano — cuatro slash commands y nada más

> *Slide 23 / 42*

## Estructura mínima — Lo que necesitáis en el repo

> *Slide 24 / 42*

Cuatro slash commands y una carpeta `specs/`. **Cero dependencias externas.**

```
mi-proyecto/
├── CLAUDE.md
├── specs/
│   ├── 001-album-organizer/
│   │   ├── spec.md
│   │   ├── plan.md
│   │   └── tasks.md
│   └── 002-photo-upload/
│       └── ...
└── .claude/
    └── commands/
        ├── spec-new.md
        ├── spec-plan.md
        ├── spec-tasks.md
        └── spec-implement.md
```

## Slash command 1 de 4 · `/spec-new` — empezar una feature

> *Slide 25 / 42*

Archivo: `.claude/commands/spec-new.md`

```markdown
---
description: Crea spec.md inicial para una feature nueva
argument-hint: <nombre-feature>
---

Estoy iniciando una feature nueva: $ARGUMENTS

Crea la carpeta `specs/<NNN>-$ARGUMENTS/` donde NNN es el
siguiente número correlativo (mira las carpetas que ya existen).

Dentro, crea spec.md con: Contexto, User stories, Requisitos
funcionales, Criterios de éxito, Casos frontera, Fuera de alcance.

Hazme las preguntas necesarias para rellenarlo.
NO incluyas stack técnico ni decisiones de implementación.
```

## Slash command 2 de 4 · `/spec-plan` — del qué al cómo

> *Slide 26 / 42*

Archivo: `.claude/commands/spec-plan.md`

```markdown
---
description: Genera plan.md técnico para la spec actual
argument-hint: <numero-feature>
---

Lee `specs/$ARGUMENTS-*/spec.md` y CLAUDE.md (stack y convenciones).

Genera plan.md con:
## Stack técnico (versiones concretas)
## Arquitectura (patrón a aplicar, justificación)
## Modelo de datos (tablas, migraciones)
## Fases (Foundation → Core → Polish)
## Riesgos técnicos
## Check contra CLAUDE.md (¿viola algún anti-patrón?)

NO escribas código. Espera mi aprobación del plan.
```

## Slash command 3 de 4 · `/spec-tasks` — trocear el plan

> *Slide 27 / 42*

Archivo: `.claude/commands/spec-tasks.md`

```markdown
---
description: Trocea el plan en tareas atómicas
argument-hint: <numero-feature>
---

Lee spec.md y plan.md de `specs/$ARGUMENTS-*/`.

Genera tasks.md con tareas atómicas:
· Cada tarea con un ID (Task 1.1, 1.2, 2.1, ...)
· Archivos exactos que toca
· Dependencias con otras tareas
· Marcador [P] si paraleliza con otras de su fase
· Test primero si aplica TDD

Una tarea = < 30 min de un humano. Si es más, trocéala.
```

## Slash command 4 de 4 · `/spec-implement` — ejecutar tarea

> *Slide 28 / 42*

Archivo: `.claude/commands/spec-implement.md`

```markdown
---
description: Ejecuta una tarea de la spec actual
argument-hint: <numero-feature> <id-tarea>
---

Lee tasks.md y localiza la tarea $2.

Antes de tocar nada:
1. Comprueba que las dependencias estén [x] hechas.
2. Lee los archivos relacionados en el repo.
3. Si la tarea exige test primero, escríbelo y verifica
   que falla.

Implementa SOLO lo que la tarea pide.
NO toques archivos fuera de los listados.
Al terminar, marca la tarea como [x] en tasks.md.
```

**Por qué a mano antes que tooling:** hacerlo a mano una vez os enseña qué hace cada fase y por qué. Después podéis pasar a Spec Kit u otra herramienta sabiendo lo que automatiza.

---

# MÓDULO 06 · SDD con tooling — panorama 2026

> *Slide 29 / 42*

## La referencia · Open Source — GitHub Spec Kit

> *Slide 30 / 42*

| Campo | Valor |
|---|---|
| **Origen** | GitHub · open source (sept 2025) |
| **Estrellas** | ~70k+ (mayo 2026) |
| **Comando CLI** | `specify init <proyecto>` |
| **Agentes** | 20+ (Claude Code, Copilot, Cursor, Gemini, …) |
| **Diferencial** | `constitution.md` — principios inviolables |

**Slash commands:**

| Comando | Función |
|---|---|
| `/speckit.constitution` | principios del proyecto |
| `/speckit.specify` | qué se construye |
| `/speckit.clarify` | resuelve ambigüedades |
| `/speckit.plan` | cómo se construye |
| `/speckit.tasks` | troceado atómico |
| `/speckit.analyze` | gaps cross-artefacto |
| `/speckit.implement` | ejecución |

## El resto del panorama — Otras opciones con tracción

> *Slide 31 / 42*

| Herramienta | Descripción |
|---|---|
| **AWS Kiro** | IDE completo con SDD nativo. AWS documenta features 40h → 8h. UI y steering persistente. |
| **Tessl** | Specs como contratos verificables. Más cercano a TLA+ en filosofía. |
| **OpenSpec** | Spec-first agnóstico, formato YAML/Markdown estandarizado. |
| **BMAD** | Agentes especializados por rol (Analyst, PM, Architect) que colaboran. |
| **Google Antigravity** | Versión de Google del enfoque spec-first integrada con sus herramientas. |
| **cc-sdd** | Plantillas estilo Kiro pero corriendo sobre Claude Code o Gemini CLI. |

## Decisión práctica — Cuál elegir según equipo

> *Slide 32 / 42*

| Contexto | Recomendación | Razón |
|---|---|---|
| **Equipos pequeños · un proyecto** | **SDD a mano** | Cuatro slash commands en Claude Code. Cero dependencias, todo en el repo, vosotros controláis el formato. |
| **Equipos medianos · varios proyectos** | **GitHub Spec Kit** | El estándar de facto. Agnóstico de agente, comunidad grande, ecosistema de extensiones. |
| **Equipos grandes · compliance** | **Spec Kit + constitution** | Constitution fuerte y extensiones de auditoría. O Kiro si el equipo va all-in en su IDE. |
| **Muchas regeneraciones** | **Tessl o BMAD** | Cuanto más sofisticada la spec, más leverage da regenerar con cada modelo nuevo. |

---

# MÓDULO 07 · Spec drift: mantener la spec viva

> *Slide 33 / 42*

## El error más común en SDD — Los tres tipos de drift

> *Slide 34 / 42*

> No es escribir mal la spec inicial. Es no actualizarla cuando el código se desvía.

1. **Drift de implementación**
   *El código diverge de la spec en silencio durante el implement.*
   **Mitigación:** Hook `PostToolUse` que avisa si un diff toca código sin referencia a una tarea.

2. **Drift por cambio de requisitos**
   *El producto cambia, se actualiza el código, no la spec.*
   **Mitigación:** PR rule: si el código cambia comportamiento, la spec debe cambiar en el mismo PR.

3. **Drift cruzado**
   *Dos specs se contradicen tras meses de evolución.*
   **Mitigación:** `/speckit.analyze` periódico o slash command propio equivalente.

## La regla de oro

> *Slide 35 / 42*

> Si el código que vas a escribir no se desprende lógicamente de algo escrito en la spec, **no es código: es deuda técnica con disfraz.**
>
> Actualiza la spec antes.

## Validación cruzada — Checklist antes de cerrar la feature

> *Slide 36 / 42*

- [ ] ¿Cada requisito de la spec está cubierto por al menos una tarea?
- [ ] ¿Cada tarea está `[x]` cerrada o reescalada?
- [ ] ¿Los tests cubren criterios de éxito de la spec, no solo detalles de implementación?
- [ ] ¿Los anti-patrones del `CLAUDE.md` siguen respetados?
- [ ] ¿La spec sigue siendo legible en 6 meses por alguien que se incorpora hoy?

## Lo que dice la industria

> *Slide 37 / 42*

> **"El moat no son las specs. Es el leverage de regeneración que las specs maduras te dan con cada nueva generación de modelos."**

Los equipos que empezaron a construir su biblioteca de specs en 2025 o 2026 pueden regenerar contra Claude 6, GPT-6 o lo que venga.

Los que se retrasaron, no.

---

# TRAMO FINAL · Cierre — lo que importa · deberes · preguntas

> *Slide 38 / 42*

## Lo que importa — Tres ideas para la próxima sesión

> *Slide 39 / 42*

1. **La spec es la fuente de verdad, no el código.**
   Es el cambio mental de SDD. El código se regenera; la spec se conserva y se versiona como cualquier artefacto crítico.

2. **Cuatro fases, cuatro artefactos.**
   Specify → Plan → Tasks → Implement. Cada uno produce un `.md` que alimenta al siguiente. No se salta uno.

3. **Empieza a mano, adopta tooling cuando duela.**
   Cuatro slash commands propios os llevan al 80%. Spec Kit u otras herramientas son el siguiente paso, no el primero.

## Trabajo entre sesiones — Deberes para la sesión 3

> *Slide 40 / 42*

1. Crear `specs/` en vuestro repo y los 4 slash commands (`spec-new`, `spec-plan`, `spec-tasks`, `spec-implement`).
2. Escribir una spec completa para una feature pequeña real (1-2 días, no un toy example).
3. Llegar hasta `tasks.md` aprobado **sin escribir código todavía**.
4. Implementar al menos 3 tareas con `/spec-implement` y observar diffs.
5. Instalar GitHub Spec Kit en una rama experimental, comparar con vuestra versión "a mano".
6. Traer una pieza de código generado vía SDD que no os convenza del todo.

## Lo que viene — Sesión 3: Revisión de código y refactorización

> *Slide 41 / 42*

Pasamos del *"generar bien"* al *"revisar bien lo que ya hay"*: code review asistido, detección de code smells, refactor con criterio, generación de tests sobre código legacy, y cómo extraer specs retrospectivamente.

---

## Preguntas y debate

> *Slide 42 / 42*

**VALEN · VA360 LABS**

---

*VA360 LABS · CLAUDE CODE · SESIÓN 02 · 42 / 42*
