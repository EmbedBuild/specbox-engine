# VEG Tooling Decisions — Consolidacion Fase 0

> Fecha: 2026-03-07
> Contexto: Decisiones finales de Fase 0 para el feature VEG
> Estado: APROBADO — Input para Fases 1-6

---

## 1. Provider de imagenes

| Rol | Provider | MCP | Transporte |
|-----|----------|-----|------------|
| **Primario** | Freepik (Mystic + Stock) | freepik-company/freepik-mcp | Remote HTTP |
| **Fallback** | OpenAI GPT-Image-1 + Gemini Imagen 4 | lansespirit/image-gen-mcp | stdio/SSE/HTTP |
| **Prototipado** | Hugging Face | huggingface.co/mcp | Remote HTTP |

**Estrategia:** Stock-first (buscar antes de generar) + generacion AI cuando no hay match + fallback multi-provider.

**Abstraccion del Engine:** El skill `/implement` NO referencia providers concretos. Usa un concepto abstracto de "MCP de imagenes configurado" que se resuelve en runtime segun la config del proyecto en `.claude/settings.local.json`.

---

## 2. Estrategia de animaciones por stack

| Stack | Herramienta principal | Version | Complemento |
|-------|----------------------|---------|-------------|
| **Flutter** | `flutter_animate` | ^4.5.2 | Hero (built-in) + Lottie (assets pre-hechos) |
| **React** | `motion` (ex Framer Motion) | ^12.35.0 | CSS para hovers triviales |

**Filosofia:** API declarativa, composable, definible como catalogo de constantes. Claude genera codigo correcto con ambas.

**Dependencias por stack:**

Flutter (`pubspec.yaml`):
```yaml
dependencies:
  flutter_animate: ^4.5.2
  # Opcional para confetti/checkmark:
  lottie: ^3.3.1
```

React (`package.json`):
```json
{
  "dependencies": {
    "motion": "^12.35.0"
  }
}
```

---

## 3. Configuracion VEG en settings

```json
{
  "veg": {
    "enabled": true,
    "image_provider": {
      "primary": "freepik",
      "fallback": "lansespirit",
      "maxImagesPerScreen": 5,
      "defaultAspectRatio": "16:9",
      "stockSearchFirst": true
    },
    "motion": {
      "enabled": true,
      "flutter": {
        "package": "flutter_animate",
        "version": "^4.5.2"
      },
      "react": {
        "library": "motion",
        "version": "^12.35.0"
      }
    },
    "defaults": {
      "fallback_mode": "uniform",
      "fallback_motion_level": "moderate"
    }
  }
}
```

---

## 4. Riesgos identificados y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| MCP de imagenes no disponible | Media | Bajo | Degradacion graceful: documentar prompts, continuar sin imagenes |
| Freepik API rate limits | Baja | Medio | Fallback a lansespirit automatico |
| flutter_animate deprecated | Muy baja | Alto | Built-in Flutter como fallback (mas verboso) |
| motion (React) breaking changes | Baja | Medio | Variants son objetos JS puros, migran facilmente |
| Hover en mobile | Cierta | Bajo | Sub-agente AG-02 usa whileTap en mobile |
| Stagger con listas largas | Media | Bajo | Limitar a 10-15 items visibles |
| Shared-element complejo | Media | Medio | Solo activar en motion level "expressive" |

---

## 5. Decision de versionado

- Esta feature se libera como **v3.9.0 "Visual Experience Generation"**
- Backward compatible: sin targets en PRD → VEG se salta
- No requiere migracion de proyectos existentes

---

## 6. Archivos a crear/modificar (resumen)

### Crear:
- `doc/templates/veg-template.md` — Template del artefacto VEG
- `doc/templates/veg-archetypes.md` — Reglas de derivacion por arquetipo

### Modificar:
- `.claude/skills/prd/SKILL.md` — Seccion Audiencia + validacion
- `.claude/skills/plan/SKILL.md` — Paso 2.5b VEG Generation
- `.claude/skills/implement/SKILL.md` — Pasos 0, 3, 3.5, 4, 6
- `agents/design-specialist.md` — VEG awareness
- `agents/uiux-designer.md` — Motion catalog
- `agents/orchestrator.md` — Decision de modo VEG
- `agent-teams/prompts/lead-agent.md` — Orquestacion VEG
- `agent-teams/prompts/design-specialist.md` — VEG en Stitch
- `templates/settings.json.template` — Seccion veg
- `templates/CLAUDE.md.template` — Seccion VEG en flujo
- `ENGINE_VERSION.yaml` — v3.9.0
- `CLAUDE.md` — Documentar VEG
