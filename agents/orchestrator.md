# Orquestador de Agentes (Orchestrator)

> JPS Dev Engine v3.0.0
> Template generico -- personalizar por proyecto en `.claude/orchestrator.md`

## Proposito

Coordinar la ejecucion de subagentes especializados (AG-01 a AG-06) para implementar features completas. Decide el orden de ejecucion, resuelve dependencias entre agentes y valida que cada fase se complete antes de avanzar.

---

## Roles de Agentes

| ID | Rol | Archivo |
|----|-----|---------|
| AG-01 | Feature Generator | `agents/feature-generator.md` |
| AG-02 | UI/UX Designer | `agents/uiux-designer.md` |
| AG-03 | DB Specialist | `agents/db-specialist.md` |
| AG-04 | QA & Validation | `agents/qa-validation.md` |
| AG-05 | n8n Specialist | `agents/n8n-specialist.md` |
| AG-06 | Design Specialist | `agents/design-specialist.md` |

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

1. **AG-06** -- Generar disenos en Stitch (si hay pantallas nuevas)
2. **AG-03** -- Preparar base de datos (tablas, RLS, migraciones)
3. **AG-02** -- Crear/adaptar componentes UI
4. **AG-01** -- Generar estructura de la feature completa
5. **AG-05** -- Configurar workflows si aplica
6. **AG-04** -- Tests y validacion final

### Feature solo backend (API / DB)

1. **AG-03** -- Base de datos
2. **AG-01** -- Logica de negocio y repositorios
3. **AG-05** -- Workflows si aplica
4. **AG-04** -- Tests

### Feature solo UI (sin DB nueva)

1. **AG-06** -- Disenos Stitch
2. **AG-02** -- Componentes UI
3. **AG-01** -- Estructura de la feature
4. **AG-04** -- Tests

---

## Reglas del Orquestador

### Obligatorias

1. NUNCA ejecutar AG-01 sin antes tener la DB lista (AG-03) si la feature requiere datos
2. NUNCA crear widgets sin haber consultado la biblioteca existente del proyecto
3. SIEMPRE ejecutar AG-04 como ultima fase
4. SIEMPRE verificar compilacion/lint entre fases
5. Si un agente falla, detener la ejecucion y reportar el error

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

### Comunicacion entre agentes

- Cada agente recibe contexto del PRD y del plan
- AG-01 recibe output de AG-03 (nombres de tablas, modelos)
- AG-02 recibe output de AG-06 (HTMLs de diseno)
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

- Engine: `jps_dev_engine/`
- Skills: `jps_dev_engine/.claude/skills/`
- Arquitectura por stack: `jps_dev_engine/architecture/{stack}/`
- Infraestructura: `jps_dev_engine/infra/{servicio}/`
- Diseño Stitch: `jps_dev_engine/design/stitch/`
