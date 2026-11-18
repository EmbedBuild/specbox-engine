# El CLAUDE.md de un proyecto

El CLAUDE.md se carga en cada sesión, así que solo lleva lo que el agente necesita siempre: las
reglas innegociables (Quality Contract, la comprobación de la memoria persistente y el recorrido de
la UC) y lo propio del proyecto. Desde la 6.38.0 (UC-12209) la plantilla genera 200 líneas o menos;
el resto vive en las skills y en las guías del engine, y la tabla de abajo dice dónde.

## Zonas de la plantilla y secciones del proyecto

La plantilla (`templates/CLAUDE.md.template`) marca lo suyo:

```
<!-- @specbox:claude-md start id="memoria" -->
...
<!-- @specbox:claude-md end -->
```

| Zona | Qué lleva |
|------|-----------|
| `version` | La versión del engine con la que se generó o actualizó por última vez |
| `memoria` | La comprobación de Engram y qué hacer tras una compactación |
| `calidad` | El Quality Contract (las cinco reglas) y la referencia a `rules/GLOBAL_RULES.md` |
| `recorrido` | El recorrido de una UC, los comandos y la CI a mano |
| `agentes` | La tabla de agentes del engine |
| `pruebas` | Aceptación, E2E y VEG, en una línea cada uno, con su referencia |
| `permisos` | Permisos de Claude Code y dónde se explica cada hook |

Lo que queda **fuera** de los marcadores es del proyecto: Stack, Arquitectura, Reglas del Proyecto,
Sistema de Diseño, Servicios Externos y cualquier sección que añadáis. Nadie lo reescribe.

## Qué hace `upgrade_project` con el CLAUDE.md

`upgrade_project` recibe el CLAUDE.md actual en `claude_md_content` (el cliente lo lee; el servidor
no toca vuestro disco) y responde en `claude_md.status`:

| status | Cuándo | Qué se escribe |
|--------|--------|----------------|
| `merged` | El CLAUDE.md tiene marcadores | Solo el cuerpo de cada zona; las zonas nuevas se añaden tras la anterior en el orden de la plantilla y las retiradas se quitan (`replaced`, `added`, `removed`) |
| `unchanged` | Las zonas ya están al día | Nada |
| `proposal` | El CLAUDE.md no tiene marcadores (plantilla de antes de la 6.38.0) | Nada: devuelve `sections_leaving` (qué sale y adónde va), `sections_kept` y `proposed_content` |
| `applied` | Lo mismo, con `confirm_claude_md=true` | La propuesta |
| `created` | `claude_md_content` vacío: el proyecto no tiene CLAUDE.md | La plantilla |
| `content_required` | No se pasó `claude_md_content` | Nada: el CLAUDE.md ya no se regenera a ciegas |
| `malformed` | Un marcador abierto sin cerrar o repetido | Nada |

Antes de la 6.38.0, `upgrade_project` devolvía un CLAUDE.md regenerado entero y quien lo copiaba
perdía sus secciones propias. Ahora un CLAUDE.md que ya existía solo cambia con `upgrade_project`,
y uno sin marcadores solo cuando la persona ha visto qué sale y lo confirma.

En la propuesta, el título del proyecto se queda, las zonas `version`, `memoria` y `calidad` van
primero (es lo que el agente lee antes), después las secciones del proyecto en su orden, luego las
demás zonas.

## Adónde fue cada sección de la plantilla anterior

| Sección de la plantilla anterior | Adónde va |
|----------------------------------|-----------|
| Memoria Persistente (Engram) — REQUERIDO | Zona `memoria` (comprobación y compactación); la instalación por sistema, la persistencia y las tools, a [memoria-engram.md](memoria-engram.md) |
| Quality Contract — Calidad sobre velocidad | Zona `calidad`; la tabla de antipatrones, a `rules/GLOBAL_RULES.md` (Antipatrones prohibidos) |
| Agentes del Proyecto | Zona `agentes`; Agent Teams, a `docs/agent-teams.md` |
| Comandos Disponibles | Zona `recorrido` |
| Flujo de Desarrollo | Zona `recorrido` (recorrido de la UC y CI a mano) |
| Trello — Fuente de Verdad (Spec-Driven) | Zona `recorrido` (el tablero, sea cual sea el backend); lo propio de Trello, en [Trello](#trello) |
| Acceptance Testing — Gherkin BDD | Zona `pruebas`; el formato `.feature` y el paquete por stack, a `.claude/skills/implement/SKILL.md` (Paso 7.5) y `rules/GLOBAL_RULES.md` (Acceptance Testing) |
| Visual Experience Generation — VEG (v3.9) | Zona `pruebas`; los tres pilares y la configuración, a `.claude/skills/visual-setup/SKILL.md` y `.claude/skills/plan/SKILL.md` (Paso 2.5b) |
| E2E Testing | Zona `pruebas`; los patrones por stack, a `architecture/{stack}/e2e-testing.md` |
| Permisos de Claude Code | Zona `permisos`; el detalle, a [permisos.md](permisos.md) |
| Hooks | Zona `permisos`; cada hook, a [hooks.md](hooks.md) |

La misma tabla está en `server/claude_md.py` (`RELOCATIONS`), que es la que usa `upgrade_project`
para la propuesta; `tests/test_claude_md_template.py` comprueba que cada destino existe.

## Trello

Con `trello.boardId` en `.claude/settings.local.json`, el tablero es Trello:

| Concepto | En Trello | Identificador |
|----------|-----------|---------------|
| User Story | Tarjeta con la etiqueta «US» | US-XX |
| Use Case | Tarjeta con la etiqueta «UC» | UC-XXX |
| Acceptance Criteria | Elementos del checklist de la tarjeta UC | AC-XX |

`/prd` lee o crea las US y UC y adjunta el PRD en PDF; `/plan` adjunta el plan; `/implement` recorre
`find_next_uc` → `start_uc` → fases → `complete_uc`. Las tools son las mismas que con los otros
backends (`setup_board`, `get_us`, `list_us`, `get_uc`, `list_uc`, `start_uc`, `complete_uc`,
`find_next_uc`, `mark_ac_batch`, `attach_evidence`, `import_spec`).
