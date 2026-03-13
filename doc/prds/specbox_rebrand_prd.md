# PRD: Rebrand SDD-JPS Engine → SpecBox Engine by JPS

## Resumen Ejecutivo

El término "SDD" (Spec-Driven Development) se ha convertido en un estándar de industria con más de 30 frameworks compitiendo en el mismo espacio (GitHub Spec Kit, Amazon Kiro, Tessl, BMAD, GSD, Ralph Loop, etc.). El nombre actual "SDD-JPS Engine" diluye la identidad del producto al posicionarlo como "otra herramienta SDD más", cuando en realidad este engine va significativamente más allá del SDD genérico: orquestación multi-agente, self-healing, quality gates con Gherkin/BDD, gestión de proyectos integrada, y ciclo de vida completo.

El nuevo nombre **SpecBox Engine by JPS** conecta la identidad del creador (Verificador Técnico de MotoGP/WorldSBK + Software Developer) con la naturaleza del producto. "SpecBox" fusiona "Spec" (especificación — compartido entre software y motorsport) con "Box" (pit box — centro de operaciones táctico donde se coordina el equipo). "by JPS" firma como constructor, con el easter egg de John Player Special para quienes vienen del mundo racing.

Este refactor es exclusivamente cosmético (display text). No se modifican paths del filesystem, nombres de directorios internos, ni la API MCP. Se replica el patrón exitoso de v3.8.1 que ya ejecutó un rebrand similar.

## Alcance

### Incluye
- Actualización de `ENGINE_VERSION.yaml` campos `brand` y `brand_full`
- Rename de display text en todos los archivos del repositorio del engine
- Actualización de templates de onboarding (`CLAUDE.md.template`, `settings.json.template`, etc.)
- Actualización de README.md, CHANGELOG.md, GLOBAL_RULES.md
- Actualización del dashboard Sala de Máquinas (título, footer, metadata)
- Actualización de instrucciones del servidor MCP (`server.py` instructions)
- Actualización de Skills y Agent prompts que referencien el nombre
- Actualización de `install.sh` y scripts que muestren el nombre
- Rename del repositorio en GitHub: `sdd-jps-engine` → `specbox-engine`
- Backward compatibility: symlink `~/sdd-jps-engine` → `~/specbox-engine`
- Nuevo codename para la versión: `v4.3.0 "SpecBox"`
- Actualización del baseline registrado en el state registry

### No incluye
- Rename de paths internos del filesystem (se mantiene la estructura de directorios)
- Rename de los 21 proyectos onboarded (se actualizan en el próximo `upgrade_all_projects`)
- Modificación de la API MCP (tool names, endpoints)
- Cambios en la lógica de ningún skill, hook o agente
- Actualización de la campaña de LinkedIn (se hará como tarea separada)
- Rediseño del brand visual (colores, tipografía — se mantiene el JPS Developer theme)
- Cambios en Canva brand kit

---

## Objetivos

1. **Diferenciación** — Separar el producto del ecosistema SDD genérico con un nombre propio memorable
2. **Identidad** — Conectar la marca con la identidad dual del creador (motorsport + software)
3. **Continuidad** — Ejecutar el cambio sin romper ningún proyecto existente ni la API MCP
4. **Trazabilidad** — Mantener el historial de versiones y la referencia al nombre anterior

---

## Estado Actual vs Propuesto

### ACTUAL:
```
brand: "SDD-JPS Engine"
brand_full: "Spec-Driven Development Engine by JPS"
repo: github.com/jesusperezdeveloper/sdd-jps-engine
codename: "Stitch Design Gate" (v4.2.0)
baseline: "sdd-jps-engine"
```

### PROPUESTO:
```
brand: "SpecBox Engine"
brand_full: "SpecBox Engine by JPS"
repo: github.com/jesusperezdeveloper/specbox-engine
codename: "SpecBox" (v4.3.0)
baseline: "specbox-engine"
```

---

## User Stories y Use Cases

### US-01: Rebrand del Engine

> Como creador del engine, quiero que el nombre refleje la identidad diferenciada del producto, para que no se confunda con las 30+ herramientas SDD genéricas del mercado.

#### UC-001: Actualizar identidad del engine
- **Actor**: Developer (Jesús)
- **Horas estimadas**: 2h
- **Pantallas**: N/A (backend/config)

**Acceptance Criteria:**
- [ ] **AC-01**: `ENGINE_VERSION.yaml` muestra `brand: "SpecBox Engine"` y `brand_full: "SpecBox Engine by JPS"` con `version: "4.3.0"` y `codename: "SpecBox"`
- [ ] **AC-02**: `README.md` título principal dice "SpecBox Engine by JPS" y no contiene "SDD-JPS Engine" en ningún lugar excepto en la sección de changelog/historial
- [ ] **AC-03**: `CHANGELOG.md` incluye entrada v4.3.0 con los cambios de rebrand, manteniendo intacto el historial de versiones anteriores
- [ ] **AC-04**: `GLOBAL_RULES.md` referencia "SpecBox Engine" en todas las menciones al engine excepto citas históricas
- [ ] **AC-05**: El comando `get_engine_version` via MCP retorna `brand: "SpecBox Engine"` y `brand_full: "SpecBox Engine by JPS"`
- [ ] **AC-06**: El comando `get_engine_status` via MCP retorna `engine_version: "4.3.0"`

#### UC-002: Actualizar templates de onboarding
- **Actor**: Developer (Jesús)
- **Horas estimadas**: 1h
- **Pantallas**: N/A

**Acceptance Criteria:**
- [ ] **AC-07**: `CLAUDE.md.template` referencia "SpecBox Engine" en el header y en todas las menciones al engine
- [ ] **AC-08**: `settings.json.template` no contiene "sdd-jps" en display text (paths internos se mantienen)
- [ ] **AC-09**: `team-config.json.template` referencia "SpecBox Engine" si aparece el nombre del engine
- [ ] **AC-10**: `quality-baseline.json.template` no contiene "sdd-jps" en display text
- [ ] **AC-11**: Ejecutar `onboard_project` con un nombre de test genera archivos que dicen "SpecBox Engine"

#### UC-003: Actualizar Skills y Agent Prompts
- **Actor**: Developer (Jesús)
- **Horas estimadas**: 1.5h
- **Pantallas**: N/A

**Acceptance Criteria:**
- [ ] **AC-12**: Todos los archivos `SKILL.md` en `skills/` que mencionan "SDD-JPS Engine" ahora dicen "SpecBox Engine"
- [ ] **AC-13**: Todos los agent prompts en `agents/prompts/` que mencionan "SDD-JPS" ahora dicen "SpecBox Engine"
- [ ] **AC-14**: El skill `/prd` no contiene "SDD-JPS" en su contenido visible
- [ ] **AC-15**: El skill `/implement` no contiene "SDD-JPS" en su contenido visible
- [ ] **AC-16**: El skill `/plan` no contiene "SDD-JPS" en su contenido visible

#### UC-004: Actualizar servidor MCP e instrucciones
- **Actor**: Developer (Jesús)
- **Horas estimadas**: 1h
- **Pantallas**: N/A

**Acceptance Criteria:**
- [ ] **AC-17**: `server.py` instructions string referencia "SpecBox Engine by JPS" en lugar de "SDD-JPS Engine"
- [ ] **AC-18**: Cualquier docstring o metadata del servidor MCP que mencione el nombre del engine está actualizada
- [ ] **AC-19**: El Dockerfile y `docker-compose.yml` no contienen "sdd-jps" en labels o nombres de servicio visibles al usuario (paths internos se mantienen)
- [ ] **AC-20**: Los endpoints MCP siguen funcionando sin cambios (no se renombra ningún tool)

#### UC-005: Actualizar Dashboard / Sala de Máquinas
- **Actor**: Developer (Jesús)
- **Horas estimadas**: 0.5h
- **Pantallas**: Dashboard principal

**Acceptance Criteria:**
- [ ] **AC-21**: El título del dashboard muestra "SpecBox Engine" o "Sala de Máquinas — SpecBox Engine"
- [ ] **AC-22**: El footer del dashboard muestra "SpecBox Engine by JPS" y la versión correcta
- [ ] **AC-23**: Cualquier referencia visual a "SDD-JPS" en el frontend React está reemplazada

#### UC-006: Actualizar scripts e instalación
- **Actor**: Developer (Jesús)
- **Horas estimadas**: 0.5h
- **Pantallas**: N/A

**Acceptance Criteria:**
- [ ] **AC-24**: `install.sh` muestra "SpecBox Engine" en sus mensajes de output al usuario
- [ ] **AC-25**: Todos los hooks que imprimen el nombre del engine en logs usan "SpecBox Engine"
- [ ] **AC-26**: `analyze-sessions.sh` y `update-baseline.sh` usan el nombre actualizado en output

#### UC-007: Rename repositorio GitHub y backward compatibility
- **Actor**: Developer (Jesús)
- **Horas estimadas**: 0.5h
- **Pantallas**: N/A

**Acceptance Criteria:**
- [ ] **AC-27**: El repositorio en GitHub se llama `specbox-engine` (rename via GitHub settings)
- [ ] **AC-28**: El symlink `~/sdd-jps-engine` → `~/specbox-engine` existe para backward compatibility
- [ ] **AC-29**: Los remotes de git en proyectos existentes siguen funcionando (GitHub redirige automáticamente)
- [ ] **AC-30**: `.git/config` del repo tiene el remote actualizado a `specbox-engine`

#### UC-008: Actualizar state registry y baseline
- **Actor**: Developer (Jesús)
- **Horas estimadas**: 0.5h
- **Pantallas**: N/A

**Acceptance Criteria:**
- [ ] **AC-31**: El baseline registrado en el state registry dice `specbox-engine` en lugar de `sdd-jps-engine`
- [ ] **AC-32**: `get_sala_de_maquinas` no muestra "sdd-jps" en ningún campo visible
- [ ] **AC-33**: Los 21 proyectos existentes siguen apareciendo correctamente en la Sala de Máquinas

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medición |
|-----|----------|----------|
| Zero downtime | Ningún proyecto existente deja de funcionar durante o después del rebrand | Test manual: ejecutar `get_board_status` en mcprofit-web |
| Backward compat | Symlink `~/sdd-jps-engine` → `~/specbox-engine` permite que CLAUDE.md existentes sigan funcionando | Test: `ls -la ~/sdd-jps-engine` apunta a specbox-engine |
| API stability | Ningún tool name MCP cambia | Test: `get_engine_status`, `list_skills` retornan mismos tools |
| Completeness | `grep -ri "sdd-jps" .` en el repo no devuelve resultados fuera de CHANGELOG.md y referencias históricas | Grep exhaustivo post-implementación |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| CLAUDE.md de proyectos existentes referencian "sdd-jps-engine" en paths | Alta | Bajo | Symlink de backward compat + `upgrade_all_projects` posterior |
| GitHub rename rompe clones existentes | Baja | Bajo | GitHub redirige automáticamente repos renombrados |
| Campaña LinkedIn ya publicada con nombre anterior | Media | Bajo | Los posts hablan del concepto, no del nombre técnico del repo |
| Algún archivo se escapa del rename | Media | Bajo | Grep exhaustivo como quality gate final (AC-NFR4) |

---

## Plan de Implementación (alto nivel)

### Fase 1: Core Identity (ENGINE_VERSION + README + CHANGELOG + GLOBAL_RULES)
- Actualizar ENGINE_VERSION.yaml
- Actualizar README.md
- Añadir entrada v4.3.0 en CHANGELOG.md
- Actualizar GLOBAL_RULES.md

### Fase 2: Templates y Onboarding
- Actualizar CLAUDE.md.template
- Actualizar settings.json.template
- Actualizar team-config.json.template
- Actualizar quality-baseline.json.template

### Fase 3: Skills y Agent Prompts
- Scan y replace en todos los SKILL.md
- Scan y replace en todos los agent prompts
- Verificar que ningún skill tiene "SDD-JPS" residual

### Fase 4: MCP Server y Dashboard
- Actualizar server.py instructions
- Actualizar frontend React (Sala de Máquinas)
- Actualizar Dockerfile labels

### Fase 5: Scripts y Hooks
- Actualizar install.sh
- Actualizar hooks con output visible
- Actualizar scripts de análisis

### Fase 6: GitHub Repo y Backward Compat
- Rename repo en GitHub settings
- Crear symlink backward compat
- Actualizar git remote
- Actualizar state registry / baseline

### Fase 7: Verificación Final
- `grep -ri "sdd-jps" .` → solo CHANGELOG.md y referencias históricas
- Test MCP: `get_engine_version`, `get_engine_status`, `list_skills`
- Test onboarding: `onboard_project` genera archivos correctos
- Test dashboard: Sala de Máquinas muestra nombre correcto

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)
- [ ] **AC-01**: ENGINE_VERSION.yaml muestra brand "SpecBox Engine" y brand_full "SpecBox Engine by JPS" con version 4.3.0 y codename "SpecBox"
- [ ] **AC-02**: README.md título dice "SpecBox Engine by JPS", sin "SDD-JPS Engine" fuera de changelog
- [ ] **AC-03**: CHANGELOG.md incluye v4.3.0 con cambios de rebrand, historial intacto
- [ ] **AC-04**: GLOBAL_RULES.md usa "SpecBox Engine" en todas las menciones no históricas
- [ ] **AC-05**: get_engine_version retorna brand "SpecBox Engine"
- [ ] **AC-06**: get_engine_status retorna engine_version "4.3.0"
- [ ] **AC-07**: CLAUDE.md.template referencia "SpecBox Engine"
- [ ] **AC-08**: settings.json.template sin "sdd-jps" en display text
- [ ] **AC-09**: team-config.json.template referencia "SpecBox Engine"
- [ ] **AC-10**: quality-baseline.json.template sin "sdd-jps" en display text
- [ ] **AC-11**: onboard_project genera archivos con "SpecBox Engine"
- [ ] **AC-12**: Todos los SKILL.md dicen "SpecBox Engine" en lugar de "SDD-JPS Engine"
- [ ] **AC-13**: Todos los agent prompts actualizados
- [ ] **AC-14**: Skill /prd sin "SDD-JPS"
- [ ] **AC-15**: Skill /implement sin "SDD-JPS"
- [ ] **AC-16**: Skill /plan sin "SDD-JPS"
- [ ] **AC-17**: server.py instructions dice "SpecBox Engine by JPS"
- [ ] **AC-18**: Docstrings/metadata del servidor MCP actualizados
- [ ] **AC-19**: Dockerfile sin "sdd-jps" en labels visibles
- [ ] **AC-20**: Endpoints MCP sin cambios (API stable)
- [ ] **AC-21**: Dashboard título muestra "SpecBox Engine"
- [ ] **AC-22**: Dashboard footer muestra "SpecBox Engine by JPS" y versión
- [ ] **AC-23**: Frontend React sin "SDD-JPS" visual
- [ ] **AC-24**: install.sh muestra "SpecBox Engine"
- [ ] **AC-25**: Hooks usan "SpecBox Engine" en logs
- [ ] **AC-26**: Scripts de análisis usan nombre actualizado
- [ ] **AC-27**: Repo GitHub se llama specbox-engine
- [ ] **AC-28**: Symlink ~/sdd-jps-engine → ~/specbox-engine existe
- [ ] **AC-29**: Remotes de proyectos existentes siguen funcionando
- [ ] **AC-30**: .git/config remote actualizado
- [ ] **AC-31**: Baseline en state registry dice specbox-engine
- [ ] **AC-32**: get_sala_de_maquinas sin "sdd-jps" visible
- [ ] **AC-33**: 21 proyectos existentes aparecen correctamente

### Técnicos (no validados por AG-09)
- [ ] Proyecto compila sin errores (Python server + React dashboard)
- [ ] Tests existentes pasan
- [ ] Docker build exitoso
- [ ] `grep -ri "sdd-jps" .` solo en CHANGELOG.md y contexto histórico

---

**Prioridad**: high
**Complejidad**: Media
**Horas estimadas**: 7.5h (total US-01)

*Generado: 2026-03-13*
*Engine: SDD-JPS Engine v4.2.0 → SpecBox Engine v4.3.0*