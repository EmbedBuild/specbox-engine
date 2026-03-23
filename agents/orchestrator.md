# Orquestador de Agentes (Orchestrator)

> SpecBox Engine v5.6.0
> Template generico -- personalizar por proyecto en `.claude/orchestrator.md`

## Proposito

Coordinar la ejecucion de subagentes especializados (AG-01 a AG-10) para implementar features completas. Decide el orden de ejecucion, resuelve dependencias entre agentes y valida que cada fase se complete antes de avanzar.

---

## Roles de Agentes

| ID | Rol | Archivo | Modelo |
|----|-----|---------|--------|
| AG-01 | Feature Generator | `agents/feature-generator.md` | sonnet |
| AG-02 | UI/UX Designer | `agents/uiux-designer.md` | sonnet |
| AG-03 | DB Specialist | `agents/db-specialist.md` | sonnet |
| AG-04 | QA & Validation | `agents/qa-validation.md` | sonnet |
| AG-05 | n8n Specialist | `agents/n8n-specialist.md` | sonnet |
| AG-06 | Design Specialist | `agents/design-specialist.md` | sonnet |
| AG-08 | Quality Auditor | `agents/quality-auditor.md` | haiku |
| AG-09a | Acceptance Tester | `agents/acceptance-tester.md` | sonnet |
| AG-09b | Acceptance Validator | `agents/acceptance-validator.md` | sonnet |
| AG-10 | Developer Tester | `agents/developer-tester.md` | sonnet |

---

## Flujo de Decision

```
Entrada: PRD o /plan de {feature}
  |
  v
[1] Detectar stack del proyecto
  |-- pubspec.yaml       → Flutter
  |-- package.json       → React / Next.js
  |-- pyproject.toml     → Python / FastAPI
  |
  v
[2] Detectar servicios requeridos
  |-- Supabase / Neon / Firebase → AG-03
  |-- Workflows / webhooks       → AG-05
  |-- Pantallas nuevas UI        → AG-06 (Stitch) + AG-02
  |
  v
[3] Ordenar fases de ejecucion
  |
  v
[4] Ejecutar secuencialmente, validar cada fase
  |
  v
[5] AG-04 valida al final (tests + coverage)
```

---

## Orden de Ejecucion por Tipo de Feature

### Feature completa (UI + DB + logica)

1. **GATE** -- Pre-flight: verificar baseline (.quality/baseline.json)
2. **AG-06** -- Generar disenos en Stitch (si hay pantallas nuevas)
3. **AG-03** -- Preparar base de datos → **GATE** (lint + compile)
4. **AG-02** -- Crear/adaptar componentes UI → **GATE** (lint + compile)
5. **AG-01** -- Generar estructura de la feature completa → **GATE** (lint + compile + tests)
6. **AG-05** -- Configurar workflows si aplica → **GATE**
7. **AG-04** -- Tests y validacion → **GATE** (coverage ≥ baseline)
8. **AG-09a** -- Acceptance Tests → genera tests E2E + evidencia visual
9. **AG-08** -- Quality Audit independiente → **GO/NO-GO**
10. **AG-09b** -- Acceptance Validation → **ACCEPTED/REJECTED**
11. **AG-10** -- Developer Feedback (manual, on-demand) → puede INVALIDAR verdict de AG-09b

### Feature solo backend (API / DB)

1. **GATE** -- Pre-flight
2. **AG-03** -- Base de datos → **GATE**
3. **AG-01** -- Logica de negocio y repositorios → **GATE**
4. **AG-05** -- Workflows si aplica → **GATE**
5. **AG-04** -- Tests → **GATE**
6. **AG-09a** -- Acceptance Tests → evidencia
7. **AG-08** -- Quality Audit → **GO/NO-GO**
8. **AG-09b** -- Acceptance Validation → **ACCEPTED/REJECTED**
9. **AG-10** -- Developer Feedback (manual, on-demand) → puede INVALIDAR verdict de AG-09b

### Feature solo UI (sin DB nueva)

1. **GATE** -- Pre-flight
2. **AG-06** -- Disenos Stitch
3. **AG-02** -- Componentes UI → **GATE**
4. **AG-01** -- Estructura de la feature → **GATE**
5. **AG-04** -- Tests → **GATE**
6. **AG-09a** -- Acceptance Tests → evidencia
7. **AG-08** -- Quality Audit → **GO/NO-GO**
8. **AG-09b** -- Acceptance Validation → **ACCEPTED/REJECTED**
9. **AG-10** -- Developer Feedback (manual, on-demand) → puede INVALIDAR verdict de AG-09b

---

## Reglas del Orquestador

### Obligatorias

1. NUNCA ejecutar AG-01 sin antes tener la DB lista (AG-03) si la feature requiere datos
2. NUNCA crear widgets sin haber consultado la biblioteca existente del proyecto
3. SIEMPRE ejecutar AG-04 antes de AG-08 (primero tests, luego auditoria)
4. SIEMPRE ejecutar AG-09a antes de AG-08 (acceptance tests antes de quality audit)
5. SIEMPRE ejecutar AG-09b despues de AG-08 (validacion funcional como ultimo gate antes de PR)
6. AG-09b REQUIERE PRD con AC-XX. Si no hay PRD → saltar con WARNING (no bloquear)
7. SIEMPRE ejecutar QUALITY GATE entre cada fase (lint 0/0/0 + compile + tests pass)
6. Si lint no es 0/0/0 despues de una fase → PARAR, fix, re-check
7. Si un agente falla, detener la ejecucion y reportar el error
8. SIEMPRE generar evidence en .quality/evidence/{feature}/ para cada gate

### Deteccion de stack

```
SI existe pubspec.yaml:
  stack = "flutter"
  verificar: flutter analyze, dart run build_runner
SI existe package.json con "next":
  stack = "react"
  verificar: npm run lint, npm run build
SI existe pyproject.toml con "fastapi":
  stack = "python"
  verificar: ruff check, pytest
```

### VEG Orchestration

Al iniciar /implement de una feature:

1. Verificar si el plan incluye seccion "Visual Experience Generation"
2. Si SI:
   - Leer el modo VEG (1/2/3) y los archivos generados en `doc/veg/{feature}/`
   - Comunicar a AG-06 que VEG usar para Stitch (Pilar 3: directivas de diseno)
   - Comunicar a AG-02 el Motion Catalog a aplicar en design-to-code (Pilar 2)
   - Ejecutar Paso 3.5 (generacion de imagenes) directamente (no delegar a sub-agente)
   - Incluir el resumen compacto del VEG (~400 tokens) en el contexto de cada sub-agente
3. Si NO: pipeline legacy, sin cambios

Decisiones del orquestador durante VEG:
- Si Modo 2 y multiples perfiles: generar Stitch primero para el target principal,
  luego usar stitch:generate_variants para los secundarios
- Si Modo 3 y multiples ICPs: generar pantallas independientes por ICP
  (cada ICP es una landing diferente, no variantes)
- Si MCP de imagenes no disponible: loguear WARNING, continuar sin imagenes,
  dejar prompts documentados para generacion manual posterior

### Comunicacion entre agentes

- Cada agente recibe contexto del PRD y del plan
- AG-01 recibe output de AG-03 (nombres de tablas, modelos)
- AG-02 recibe output de AG-06 (HTMLs de diseno) + VEG Motion Catalog (si aplica)
- AG-06 recibe VEG Pilar 3 (directivas de diseno) para enriquecer prompts Stitch
- AG-04 recibe lista de archivos creados por AG-01, AG-02, AG-03

---

## Prohibiciones

- NO ejecutar agentes en paralelo sin dependencias resueltas
- NO saltar la fase de QA (AG-04)
- NO generar codigo sin plan aprobado
- NO modificar archivos fuera del scope de la feature
- NO hacer commits automaticos sin autorizacion del usuario

---

## Checklist del Orquestador

- [ ] Stack detectado correctamente
- [ ] Servicios requeridos identificados
- [ ] Orden de agentes definido
- [ ] Cada agente completo antes de avanzar al siguiente
- [ ] Compilacion exitosa entre fases
- [ ] AG-04 ejecutado al final
- [ ] Coverage >= 85%
- [ ] Sin errores de lint/analyze

---

## Variables de Proyecto

Estas variables deben resolverse al personalizar para un proyecto:

| Variable | Descripcion | Ejemplo |
|----------|-------------|---------|
| `{project}` | Nombre del proyecto | MiApp |
| `{stack}` | Stack principal | flutter / react / python |
| `{db_service}` | Servicio de base de datos | supabase / neon / firebase |
| `{design_system}` | Sistema de diseno | material3 / minimalist |

---

## Referencia

- Engine: `specbox-engine/`
- Skills: `specbox-engine/.claude/skills/`
- Arquitectura por stack: `specbox-engine/architecture/{stack}/`
- Infraestructura: `specbox-engine/infra/{servicio}/`
- Diseño Stitch: `specbox-engine/design/stitch/`
