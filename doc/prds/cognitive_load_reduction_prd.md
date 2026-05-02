# PRD — Cognitive Load Reduction & Multi-Project Autonomy

**Versión:** 1.0 (draft)
**Fecha:** 2026-05-02
**Autor:** Jesús Pérez (con Claude)
**Engine target:** v5.29.0 → v5.31.0 (entrega por fases)
**Estado:** Pendiente de aprobación de fases

---

## 1. Problema

SpecBox Engine ha crecido orgánicamente desde v5.0 hasta v5.28. Cada release añadió nuevos gates, validaciones y confirmaciones — todos individualmente justificados. El resultado agregado es que el pipeline `/prd → /visual-setup → /plan → /implement` interrumpe al usuario en **17 puntos mayores** por feature, con concentración crítica en `/implement` (7 interrupciones, 4 bloqueantes).

Cuando el usuario lleva un único proyecto en paralelo, esto es manejable. Cuando lleva 3-5 proyectos simultáneamente, la matemática se vuelve hostil:

```
3 proyectos × 5 features activas × 4 UCs por feature ≈ 60+ interrupciones
                                                       compitiendo por
                                                       atención simultánea
```

### Síntomas observables

1. **Repreguntas implícitas**: cada `/prd` repregunta audiencia, JTBD, tono de marca y prioridades visuales que el usuario ya respondió en features anteriores del mismo proyecto.
2. **Confirmaciones operativas en bucle**: VEG preview, token confirmation, image cost warning, Stitch design check por pantalla — todas obligatorias, todas síncronas y bloqueantes.
3. **Fricción exponencial con escala**: añadir un cuarto proyecto no añade 25% más carga, añade un múltiplo de la fricción individual porque las interrupciones no se pueden batchear.
4. **Conocimiento del proyecto disperso**: brand_kit aquí, VEG por feature allá, settings.json en otro lado, decisiones en Engram, audiencia en N PRDs distintos. No hay un documento canónico que el engine lea PRIMERO.

### Causa raíz

El engine fue diseñado con un modelo mental **síncrono y bloqueante**: cada gate pregunta cuando lo necesita, sin cooperar con los otros gates ni respetar un presupuesto agregado de interrupciones por feature/proyecto/día. No existe el concepto de "perfil de autonomía del proyecto" ni una **fuente de verdad persistente a nivel de aplicación**.

---

## 2. Audiencia y JTBD

### Target

Desarrolladores que usan SpecBox Engine para llevar **2 o más proyectos en paralelo** con altos estándares de calidad y trazabilidad. Perfil técnico senior, ya familiarizado con el flujo `/prd → /plan → /implement`.

### JTBDs

**Racional:**
- Reducir el tiempo de respuesta promedio del usuario de N preguntas/feature a M preguntas/feature, donde M ≤ 30% de N.
- Permitir que el engine avance en lo que SÍ puede hacer mientras espera decisiones no críticas.
- Eliminar la repetición de preguntas cuya respuesta ya está implícita en el proyecto.

**Emocional:**
- Sentir que SpecBox es un colaborador que **respeta tu atención**, no un asistente ansioso que necesita validación constante.
- Confianza en que las decisiones que tomaste una vez quedan capturadas y no se desvanecen entre features.
- Tranquilidad para llevar 5 proyectos sin sentir que ninguno está completamente bajo control.

---

## 3. Solución propuesta

Cuatro capas independientes, entregables por fases. Cada capa aporta valor por sí sola — no es necesario implementar las cuatro para ver beneficio.

### Capa 1 — Documentos canónicos `app_prd.md` + `app_spec.md`

**Objetivo:** Crear una fuente de verdad por proyecto que el engine lea PRIMERO antes de preguntar nada.

**Artefactos:**

```
doc/app/
├── app_prd.md       ← Producto: visión, ICPs, JTBDs, perímetro v1-v∞, métricas
└── app_spec.md      ← Técnico: stack, backend, brand+VEG arquetipo, convenciones
```

**Comando nuevo:** `/app-init`
- Skill `direct` que entrevista al usuario UNA VEZ y genera ambos documentos.
- Si ya existen, ofrece modo "actualizar/ampliar" en lugar de sobrescribir.
- Captura todo el contexto de proyecto que hoy se repregunta feature a feature.

**Modificaciones a skills existentes:**

| Skill | Cambio |
|-------|--------|
| `/prd` | Lee `app_prd.md` antes del Paso 2 (capturar problema). Si la audiencia, JTBD y tono ya están en app_prd → reutiliza, no repregunta. Solo captura **deltas específicos de la feature**. |
| `/plan` | Lee `app_spec.md` para VEG arquetipo, stack, convenciones. Solo confirma desviaciones puntuales. |
| `/visual-setup` | Si `app_spec.md` define brand kit + VEG arquetipo, salta directamente a generación de tokens sin preguntar dirección estética. |

**Estimación:** 8-12h. Riesgo bajo. Compatible 100% con proyectos existentes (degrada graceful — sin app_prd.md/app_spec.md, comportamiento actual intacto).

**ROI esperado:** Eliminación del 30-40% del ruido (las preguntas categoría B y parte de A).

---

### Capa 2 — Perfil de autopilot configurable

**Objetivo:** Que el usuario fije UNA VEZ qué nivel de autonomía quiere para cada proyecto, y los 17 puntos de fricción respeten ese nivel.

**Configuración en `.claude/settings.local.json` del proyecto:**

```json
{
  "specbox": {
    "autopilot": {
      "level": "medium",
      "image_budget_eur_per_feature": 5,
      "auto_confirm": [
        "veg_preview",
        "tokens",
        "image_cost_under_budget",
        "stitch_design_per_screen"
      ],
      "always_ask": [
        "destructive_actions",
        "scope_ambiguity",
        "ac_definition_failure",
        "budget_exceeded"
      ]
    }
  }
}
```

**Tres presets:**

| Nivel | Comportamiento |
|-------|----------------|
| `low` (actual, default backwards-compat) | Pregunta todo. 17 interrupciones por feature. |
| `medium` | Auto-confirma cosmético (tokens, VEG preview con score >0.8, stitch per screen). Pregunta arquitectura + costes >budget + ambigüedades reales. ~6-8 interrupciones. |
| `high` | Solo pregunta acciones destructivas + ambigüedad genuina + presupuesto excedido. ~3-4 interrupciones. |

**Modificaciones técnicas:**

- Helper compartido `lib/autopilot.mjs` (o equivalente Python en server) que cada hook/skill consulta antes de bloquear.
- Cada uno de los 17 puntos de fricción identificados en el mapeo se etiqueta con un `decision_key` (ej. `veg_preview`, `tokens`, `image_cost`, `stitch_design`, etc.).
- Si `decision_key ∈ auto_confirm` y no hay condición de escalación → el engine procede con el default razonable y registra la auto-decisión en evidencia.
- Si `decision_key ∈ always_ask` o el contexto detecta riesgo → escala al usuario igual que hoy.

**Trazabilidad:** Cada auto-decisión se registra en `.quality/autopilot_decisions.jsonl` con timestamp, decision_key, valor elegido, razón. Esto permite auditar en cualquier momento qué decidió el engine sin preguntar.

**Estimación:** 15-20h. Riesgo medio (toca 17 puntos en 5+ skills). Compatible 100% — sin config, comportamiento `low` (idéntico al actual).

**ROI esperado:** Eliminación del 30-50% adicional sobre Capa 1.

---

### Capa 3 — Cola de decisiones diferidas

**Objetivo:** Cambiar el modelo mental del engine de "síncrono bloqueante" a "asíncrono cooperativo". Cuando llega a un gate no crítico, **acumula la pregunta y sigue trabajando** en lo que SÍ puede.

**Artefacto:**

```
doc/app/decisions_queue.md
```

Markdown vivo con formato:

```markdown
## Pendientes

### [feature: signup-flow] VEG preview confirmation
- **Generado:** 2026-05-02 14:30
- **Bloquea:** generación de imágenes hero
- **Default propuesto:** Modo Per-ICP con arquetipo Startup
- **Acción del usuario:** confirmar / ajustar / responder en thread

### [feature: dashboard] Image budget excede presupuesto
- **Generado:** 2026-05-02 15:10
- **Bloquea:** generación de 8 imágenes (€12 total, presupuesto €5)
- **Default propuesto:** generar solo 3 críticas
- **Acción del usuario:** aprobar / reducir / cancelar
```

**Cuándo aplica:**

- Decisiones **no destructivas** (no afectan main, no gastan dinero >budget, no rompen el contrato).
- Decisiones cuyo default es **suficientemente bueno** para que el engine pueda seguir trabajando en otras tareas mientras espera.

**Cuándo NO aplica:**

- Acciones destructivas → siempre síncronas.
- Definition Quality Gate fallido → síncrono (porque sin AC no hay siguiente paso).
- Presupuesto excedido sin alternativa razonable → síncrono.

**Comando nuevo:** `/queue review`
- Lista todas las decisiones pendientes en todos los proyectos del usuario.
- Permite resolverlas en batch (ej. "aprobar todos los VEG preview con score >0.85").
- Tras resolución, los workers/skills que estaban esperando reanudan automáticamente.

**Estimación:** 25-35h. Riesgo alto (cambio arquitectónico en `/implement`, requiere mecanismo de reanudación). Recomendado solo después de validar Capas 1 y 2 en producción.

**ROI esperado:** El cambio de mayor impacto para multi-proyecto. Pasa de "interrumpido N veces al día" a "1 sesión de batch por mañana".

---

### Capa 4 — Decisiones canónicas con memoria Engram

**Objetivo:** Cuando el usuario confirma algo no trivial (ej. "siempre Playwright para Web", "siempre Modo VEG Per-ICP en este proyecto"), el engine lo guarda como decisión canónica y NUNCA vuelve a preguntar lo mismo.

**Mecanismo:**

- Aprovecha Engram MCP que ya está integrado.
- Tipo nuevo de observación: `decision_canonical` con `topic_key` único por proyecto + decision_key.
- Cada skill, antes de preguntar, hace `mem_search(topic_key="autopilot/{project}/{decision_key}")` y reutiliza si existe.
- Si la decisión canónica entra en conflicto con un cambio del proyecto, el engine pregunta una vez más para revalidar.

**Cuándo aplica:** Decisiones que el usuario explícitamente marca como "siempre así" o que se infieren tras 3+ confirmaciones idénticas consecutivas.

**Estimación:** 10-15h. Riesgo bajo. Depende de Capa 2 (necesita decision_keys).

**ROI esperado:** Marginal sobre Capas 1+2+3, pero cierra el círculo. La decisión "ya respondí esto" deja de existir como friction class.

---

## 4. Acceptance criteria

### AC-01 — `/app-init` genera documentos canónicos
- **Given** un proyecto SpecBox sin `doc/app/`
- **When** el usuario ejecuta `/app-init`
- **Then** existen `doc/app/app_prd.md` y `doc/app/app_spec.md` con secciones obligatorias rellenas, y `/prd` siguiente reutiliza la audiencia sin repreguntarla.

### AC-02 — Autopilot level reduce interrupciones medibles
- **Given** un proyecto con `autopilot.level: "medium"`
- **When** el usuario ejecuta el flujo completo `/prd → /plan → /implement` para una feature
- **Then** el contador de interrupciones registradas en `.quality/autopilot_decisions.jsonl` muestra ≤8 (vs ≥17 baseline), y todas las auto-decisiones quedan auditadas.

### AC-03 — Backwards compatibility total
- **Given** un proyecto SpecBox **sin** `doc/app/` y **sin** sección `autopilot` en settings
- **When** el usuario ejecuta cualquier skill del flujo
- **Then** el comportamiento es idéntico a v5.28 (17 interrupciones, todas síncronas, ningún cambio observable).

### AC-04 — Decisions queue no bloquea pipeline
- **Given** un proyecto con `autopilot.level: "high"` y `decisions_queue` activa
- **When** el engine encuentra una decisión deferrable durante `/implement`
- **Then** la pregunta se acumula en `doc/app/decisions_queue.md`, el engine continúa con el resto del UC y reanuda al recibir respuesta vía `/queue review`.

### AC-05 — Decisiones canónicas se reutilizan
- **Given** un usuario que ha confirmado 3 veces "Modo VEG Per-ICP" en distintas features del mismo proyecto
- **When** ejecuta `/plan` para una nueva feature
- **Then** el engine no repregunta el modo VEG, lee la decisión canónica de Engram y avanza. La decisión queda anotada en evidencia.

### AC-06 — Métrica de carga cognitiva
- **Given** baseline pre-implementación (registrar manualmente sobre proyectos actuales)
- **When** se completa la entrega de Capas 1+2
- **Then** el conteo agregado de interrupciones por feature/proyecto/día es ≤50% del baseline, medido sobre 2 features post-release.

---

## 5. Roadmap por fases

| Fase | Capa | Versión target | Estimación | Riesgo | Dependencias |
|------|------|----------------|------------|--------|--------------|
| F1 | Capa 1 (`app_prd.md` + `app_spec.md` + `/app-init`) | v5.29.0 | 8-12h | Bajo | Ninguna |
| F2 | Capa 2 (autopilot level + 17 decision_keys) | v5.30.0 | 15-20h | Medio | F1 (recomendado) |
| F3 | Capa 4 (Engram canónicas) | v5.30.1 | 10-15h | Bajo | F2 |
| F4 | Capa 3 (cola diferida + `/queue review`) | v5.31.0 | 25-35h | Alto | F1 + F2 |

**Total:** 58-82h distribuidas en 3 releases. Cada release entregable independientemente.

---

## 6. Fuera de alcance v1

- Dashboard web de la cola de decisiones (Sala de Máquinas) → v5.32+ si la cola se valida.
- Notificaciones push al móvil cuando hay decisiones pendientes (vía OpenClaw Gateway) → v5.32+.
- Auto-aprendizaje: el engine sugiere subir el autopilot level cuando ve patrones consistentes → v6.0.
- Migración automática de proyectos existentes a `doc/app/` (los proyectos heredados llaman a `/app-init` cuando quieran).

---

## 7. Métricas de éxito

1. **Reducción de interrupciones por feature**: ≥50% medido sobre 2 features post-F2.
2. **Adopción de `app_prd.md`/`app_spec.md`**: ≥80% de proyectos onboarded en 30 días tras F1.
3. **Adopción de `autopilot.level >= "medium"`**: ≥60% en 60 días tras F2.
4. **Decisiones canónicas hit rate**: ≥40% de las preguntas evitadas en proyectos con F3 desplegado durante 30 días.
5. **Satisfacción cualitativa**: el usuario reporta que puede llevar **+1 proyecto adicional simultáneamente** sin aumentar carga cognitiva percibida.

---

## 8. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Auto-confirm toma decisiones que el usuario habría rechazado | Media | Alto | Trazabilidad obligatoria en `.quality/autopilot_decisions.jsonl` + comando `/queue review --recent` para revertir últimas N decisiones. |
| `app_prd.md`/`app_spec.md` quedan desactualizados respecto al código real | Alta | Medio | F2 incluye un drift detector que avisa cuando el spec real diverge. Idea similar al Spec-Code Sync existente. |
| Cola de decisiones se llena y el usuario nunca la procesa | Media | Alto | Auto-resolve después de N días con default propuesto, dejando log auditable. Threshold configurable. |
| Capa 3 introduce bugs de reanudación en `/implement` | Alta | Crítico | F4 detrás de feature flag. Beta interna en 1 proyecto antes de release público. |

---

## 9. Pregunta abierta para el usuario

**¿Qué orden de Capas y qué nivel de agresividad quieres para los presets?**

Opciones para presets (Capa 2):

- **Conservador**: `medium` solo auto-confirma tokens y stitch per screen. VEG preview e image cost siguen preguntando.
- **Equilibrado** (propuesto en este PRD): `medium` auto-confirma tokens, stitch, VEG preview (si score>0.8), image_cost (si <budget).
- **Agresivo**: `medium` auto-confirma todo lo anterior + Definition Quality Gate (si AC tiene score >0.7 — solo pregunta si es objetivamente malo).

Y orden de fases:

- **Opción A** (recomendada): F1 → F2 → F3 → F4. Riesgo creciente, valor incremental.
- **Opción B** (rápida): F1 + F2 paralelas en v5.29. Más riesgo pero entrega en 1 release el 70% del valor.
- **Opción C** (mínima viable): solo F1 en v5.29 y validar 30 días antes de decidir el resto.

---

**Próximo paso:** El usuario elige orden + agresividad de presets. Tras decisión, se genera el plan técnico (`/plan` style) con desglose UC por UC.
