# VEG Tooling Decisions — Consolidacion Fase 0

> Fecha: 2026-03-07
> Contexto: Decisiones finales de Fase 0 para el feature VEG
> Estado: APROBADO — Input para Fases 1-6

---

## 1. Provider de imagenes

| Rol | Provider | MCP | Transporte | Coste |
|-----|----------|-----|------------|-------|
| **Primario** | Canva (Design Model + Magic Media) | MCP oficial Canva | Remote HTTP | **€0** (con Pro/Premium) |
| **Fallback** | OpenAI GPT-Image-1 + Gemini Imagen 4 | lansespirit/image-gen-mcp | stdio/SSE/HTTP | $0.02-0.19/img |
| **Alternativo** | Freepik (Mystic + Stock) | freepik-company/freepik-mcp | Remote HTTP | Plan de pago |

**Estrategia:** Canva-first (generate-design → export PNG) + fallback a lansespirit para fotorrealismo hiperrealista o si Canva no esta disponible.

**Cambio vs decision original (2026-03-07):** Se reemplazo Freepik como primary por Canva MCP. Razon: el usuario tiene suscripcion Canva Premium activa — €0 adicional vs Freepik que requiere plan de pago independiente (€5-143/mes). Freepik se mantiene como alternativo para proyectos que lo prefieran.

**Abstraccion del Engine:** El skill `/implement` soporta multiples providers via config. El provider se resuelve en runtime segun `veg.image_provider.primary` en `.claude/settings.local.json`.

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

## 4. Costes de Image Generation

| Provider | Coste/imagen | Auth | Como obtener |
|----------|-------------|------|-------------|
| **Canva (PRIMARY)** | **€0** (con suscripcion) | OAuth (browser) | https://www.canva.com — Pro €12/mes o Premium (ya contratado) |
| Freepik (alternativo) | Segun plan | `FREEPIK_API_KEY` | https://www.freepik.com/api — Essential €5/mes a Pro €143/mes |
| OpenAI GPT-Image-1 | $0.02-0.19 | `OPENAI_API_KEY` | https://platform.openai.com — Billing activo requerido |
| Gemini Imagen 4 | $0.02-0.06 | `GOOGLE_API_KEY` | https://aistudio.google.com — Billing activo requerido |

**Estimacion por proyecto tipico (5 pantallas × 3 imagenes = 15 imagenes):**
- Con Canva (primary): **€0** — incluido en suscripcion
- Con OpenAI (fallback): $0.30-$2.85
- Con Gemini (fallback): $0.30-$0.90

**Ventaja clave:** Al usar Canva como primary, el 90%+ de las imagenes se generan sin coste adicional. Solo se recurre al fallback de pago para fotorrealismo hiperrealista que Canva no logra.

## 5. Riesgos identificados y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| MCP de imagenes no instalado | Alta (proyecto nuevo) | Bajo | Health check (Paso 3.5.1) + PENDING_IMAGES.md + instrucciones de setup |
| MCP instalado pero sin API key/saldo | Media | Bajo | Health check detecta 401/403, informa al usuario con link de setup |
| Usuario no sabe que cuesta dinero | Alta (primera vez) | Medio | Advertencia obligatoria con estimacion (Paso 3.5.0) |
| Freepik API rate limits | Baja | Medio | Fallback a lansespirit automatico |
| VEG derivado incorrecto para el target | Media | Alto | Preview obligatorio con confirmacion (Paso 2.5b.3) |
| Motion deps no instaladas | Media | Medio | Auto-install en Paso 4.0 antes de design-to-code |
| flutter_animate deprecated | Muy baja | Alto | Built-in Flutter como fallback (mas verboso) |
| motion (React) breaking changes | Baja | Medio | Variants son objetos JS puros, migran facilmente |
| Hover en mobile no funciona | Cierta | Medio | Enforcement hover→tap en Paso 4.2 (Flutter: GestureDetector, React: whileTap + @media(hover:hover)) |
| Stagger con listas largas | Media | Bajo | Limitar a 10-15 items visibles |
| Shared-element complejo | Media | Medio | Solo activar en motion level "expressive" |

---

## 6. Decision de versionado

- Esta feature se libera como **v3.9.0 "Visual Experience Generation"**
- Backward compatible: sin targets en PRD → VEG se salta
- No requiere migracion de proyectos existentes

---

## 7. Archivos a crear/modificar (resumen)

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
