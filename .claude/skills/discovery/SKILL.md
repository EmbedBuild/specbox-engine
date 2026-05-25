---
name: discovery
description: >
  Product Discovery ligero (15-30 min) antes de /prd. Guía conversacional
  en 3 fases (ICP identification, JTBD extraction, validation gate) que
  produce doc/discovery/<feature>/icp_jtbd.md y, en modo bootstrap, también
  doc/app/app_market.md. Use when the user says "discovery", "framing",
  "antes de PRD", "definir ICP", "definir JTBD", o ejecuta /discovery
  <feature_name>. Skill v6.0.0 — "Discovery Foundations".
context: direct
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git:*), Bash(pwd), mcp__SpecBox-MCP__start_discovery, mcp__SpecBox-MCP__validate_discovery_completeness
---

# /discovery — Product Discovery ligero para feature

Genera el problem framing de una feature ANTES de invocar `/prd`. Produce un artefacto trazable (`doc/discovery/<feature>/icp_jtbd.md`) cuyos ICPs y JTBDs viajan con la feature hasta los ACs del PRD, las UCs del plan y los tests E2E.

> **Filosofía**: *"You don't ship the wrong thing perfectly."* Tres de cada cuatro features que se construyen sin discovery requieren ≥2 iteraciones post-shipping para encontrar fit. Las que pasan por aquí tienen base estable.

---

## Uso

```
/discovery <feature_name>          # Standard mode (con app_market.md ya rellenado)
/discovery <feature_name>          # Bootstrap mode (primer feature del proyecto)
/discovery <feature_name> --status # Mostrar verdict actual sin reiniciar
/discovery <feature_name> --explain # Modo pedagógico expandido (incluso feature 6+)
```

El comando requiere `feature_name` slug-friendly (letras, números, `_`, `-`). Sin argumento aborta (D-02 opción a: simplicidad). El feature_name será el nombre del directorio bajo `doc/discovery/` y debe coincidir con el que usarás después en `/prd <feature_name>` y `/plan <feature_name>`.

---

## Paso 0 — Boot detection (v6.0.1 content-passing)

> **Cambio v6.0.1**: las tools MCP de discovery ya no leen ni escriben el filesystem del cliente. La skill es responsable de leer los archivos locales y pasar el contenido como parámetro, y de escribir cualquier artefacto que la tool devuelva.

1. **Leer settings** (`.claude/settings.local.json`) con la tool `Read`:
   - `specbox.discovery.gate_mode` ∈ `{off, warn, block}` (default `off` en upgrade, `warn` en fresh-clone v6.0).
   - `specbox.discovery.pedagogical_mode` ∈ `{auto, on, off}` (default `auto` — verbose en primeras 5 features).
   - `specbox.engine_version_at_onboard` (v6.0+ presente).

2. **Preparar el content bundle** (lectura cliente):
   - `pwd` → confirmar que estás en la raíz del repo.
   - Leer `doc/app/app_market.md` con `Read` si existe; si la `Read` falla con archivo no encontrado, tratar el contenido como `null`.
   - Leer `doc/discovery/<feature_name>/icp_jtbd.md` con `Read` si existe; si no existe, tratar como `null`.

3. **Llamar `start_discovery`** con la API v6.0.1:

   ```
   start_discovery(
     feature_name="<slug>",
     app_market_content=<contenido o null>,
     existing_artifact_content=<contenido o null>,
     mode="auto",
   )
   ```

   - Devuelve `discovery_id`, `mode_used` (standard | bootstrap), `artifact_path`, `next_step` y — cuando `status="created"` — un campo `skeleton_content` con el contenido inicial del artefacto.
   - **Si `status="created"`**: usar `Write` para escribir `skeleton_content` en `artifact_path` (la skill, no la tool, hace la escritura).
   - **Si `status="resumable"`**: significa que ya pasaste contenido existente. La tool reporta `current_verdict` y `missing`. Ofrecer al usuario: resumir (continuar editando el archivo local) o reiniciar (borrar el archivo y volver a llamar `start_discovery` con `existing_artifact_content=null`).
   - Si `mode_used="bootstrap"`, antes de bajar al feature, el skill primero rellena `doc/app/app_market.md` (ver Paso 5).

4. **Determinar verbosity pedagógico**:
   - Contar features previas: `ls doc/discovery/ | wc -l`. Si <5 → modo expanded (con justificaciones, ejemplos, anti-patterns).
   - Si flag `--explain` presente, modo expanded forzado.
   - Si >5 features ya, modo conciso (sin micro-justificaciones inline).

---

## Paso 1 — Fase 1: ICP identification

### 1.1 Mostrar ICPs canónicos del proyecto

Lee `doc/app/app_market.md` zona `icps_primary` y presenta los ICPs canónicos al usuario:

```
📋 ICPs canónicos del producto (heredados de doc/app/app_market.md):

  [1] ICP-1: <nombre>
      <atributos diferenciadores>

  [2] ICP-2: ...

[N] Añadir un ICP nuevo (warning de drift)

¿Qué ICPs están involucrados en esta feature? (1-3 seleccionables, separados por coma)
> _
```

Si `mode_used="bootstrap"`, los ICPs canónicos vienen del flujo que ya se ejecutó en Paso 5 (bootstrap), no de un app_market.md preexistente.

### 1.2 Micro-justificación pedagógica (modo expanded)

```
ℹ️  Por qué este paso importa:
   Cada feature la usa alguien. Si no sabes quién, vas a tomar mil decisiones
   (¿móvil o desktop? ¿simple o potente?) sin un norte claro y vas a producir
   algo técnicamente correcto pero que no encaja con nadie. Vamos a identificar
   1-3 ICPs concretos primero.

📚 Ejemplo (PaddockManager):
   ICP-1 = "racing managers de equipos privadores en motorsport amateur/semi-pro"
   — concreto, identificable (puedes encontrar 10 en LinkedIn), prioriza features
   muy diferentes a "todos los amantes del motor sport".

⚠️  Anti-pattern:
   "Developers que quieren más productividad" — demasiado vago, no permite
   priorizar features ni encontrar 3 personas concretas.
```

### 1.3 Para cada ICP NUEVO (no presente en app_market.md)

```
⚠️  ICP nuevo detectado: <nombre>

Sanity check: ¿conoces a 3 personas concretas que encajan en este ICP?
   [y] Sí, los puedo nombrar / encontrar en LinkedIn
   [n] No, es una hipótesis
   [t] Tentativo, conozco 1-2 pero no 3
> _
```

Registra la respuesta en el artefacto. Si `n` o `t`, el ICP queda marcado como `tentative` y se considerará drift al validar.

---

## Paso 2 — Fase 2: JTBD extraction (rational + emotional)

### 2.1 Por cada ICP seleccionado

Genera **drafts iniciales** con LLM (D-01 opción a) basándose en `feature_name` + descripción del problema (preguntar si no la tienes):

```
🎯 Generando drafts para ICP-1: <nombre>

JTBDs racionales draft:
  JR-F<feat>.1 [ICP-1]: Cuando <situación>, quiero <motivación>, para <resultado>.
  JR-F<feat>.2 [ICP-1]: Cuando ...
  JR-F<feat>.3 [ICP-1]: Cuando ...

JTBDs emocionales draft:
  JE-F<feat>.1 [ICP-1]: <sensación>
  JE-F<feat>.2 [ICP-1]: <sensación>

✏️  Edita libremente: [a]ccept all  [e]dit  [d]elete one  [+]add one  [n]ext ICP
> _
```

**Formato canónico enforced**: "Cuando [situación], quiero [motivación], para [resultado]". Si el usuario escribe algo que no encaja, ofrece reformatear.

### 2.2 Micro-justificación pedagógica (modo expanded)

```
ℹ️  Diferencia racional vs emocional:
   - **Racional**: lo que el usuario PUEDE HACER y MEDIR. Se valida con tests
     E2E automatizados.
   - **Emocional**: cómo el usuario quiere SENTIRSE. Se valida con qualitative
     gate (preguntas reflexivas + screenshot review) en /implement.

📚 Ejemplo (McProfit):
   JR racional: "Cuando cierro el mes, quiero consolidar P&L de 5 franquicias
                en <1 día, para que no me roben el fin de semana."
   JE emocional: "Reducir la ansiedad de cierre de mes — no sentir que algo
                 se me va a escapar."

⚠️  Anti-pattern JTBD racional: "Quiero que sea rápido" — no es un JTBD, es
   un atributo. Mejor: "Cuando despliego a producción, quiero feedback de
   errores en <30s para hacer rollback antes de que afecte a más usuarios."

⚠️  Anti-pattern JTBD emocional: "Quiero que se sienta moderno" — vago. Mejor:
   "Quiero sentir control sobre el proceso, no dependencia ciega del LLM."
```

---

## Paso 3 — Fase 3a: Drift detection

Compara los ICPs y JTBDs declarados contra `doc/app/app_market.md`:

```
🔍 Análisis de drift vs app_market.md:

ICPs nuevos introducidos por esta feature: [list o "ninguno"]
JTBDs nuevos introducidos por esta feature: [list o "ninguno"]

Para cada elemento nuevo:
  📌 ICP nuevo: <nombre>
     ¿Cómo lo manejamos?
       [a] feature_creep_rejected — descarto este ICP, no pertenece a esta feature
       [b] app_market_updated — añadir este ICP al app_market.md como ICP del producto
       [c] documented_exception — excepción puntual solo para esta feature (requiere justificación)
     > _

  📌 JTBD nuevo: <texto>
     ¿Cómo lo manejamos? [a/b/c]
     > _
```

Acciones:
- **(a) feature_creep_rejected**: si la feature solo tiene drift rejected → marcar feature como **cancelada**, NO generar artefacto válido para `/prd`. Mostrar mensaje al usuario.
- **(b) app_market_updated**: ofrecer editar `doc/app/app_market.md` ahí mismo. Eliminar `status="template-pristine"` de la zona modificada.
- **(c) documented_exception**: pedir justificación obligatoria y registrar en sección "Drift from app_market" del `icp_jtbd.md` con `Resolución: documented_exception` + texto de justificación.
- **(d) no_drift**: cuando la feature NO introduce ICPs/JTBDs nuevos (hereda todo de `app_market.md`). Registrar en la sección "Drift from app_market" del `icp_jtbd.md` con `Resolución: no_drift`. `validate_discovery_completeness` lo trata como `drift.resolved=true` con `drift.kind="no_drift"`.

Las 4 resoluciones canónicas son: `feature_creep_rejected`, `app_market_updated`, `documented_exception`, `no_drift`. Cualquiera satisface el gate. El alias legacy `no drift detected` (con espacios) sigue aceptado por compatibilidad pero se normaliza a `no_drift` en la respuesta.

---

## Paso 4 — Fase 3b: Validation evidence

Resumen consolidado de lo capturado + pregunta de evidence:

```
📊 Resumen del Discovery de <feature_name>:
   ICPs: <list>
   JTBDs racionales: <count>
   JTBDs emocionales: <count>
   Drift: <count nuevos elementos> resueltos

🔎 Validation evidence:
   ¿Hay alguna conversación reciente, datapoint de mercado o evidence externa
   que respalde estos JTBDs?

   [c] Sí, conversación con usuarios — describir
   [d] Sí, datapoint o señal de mercado — describir
   [w] No, waiver explícito — confiar en intuición fundada (registrar razón)
   > _
```

Registra la respuesta en la sección "Validation evidence" del artefacto. Si waiver, requiere texto que documente por qué es razonable no tener evidence externa todavía (ej. "feature interna del engine, no requiere validación con usuarios externos").

---

## Paso 5 — Bootstrap mode (primer /discovery del proyecto)

Si `mode_used="bootstrap"`, antes de bajar al flujo de la feature concreta, el skill primero rellena `doc/app/app_market.md`:

```
👋 ¡Es la primera vez que ejecutas /discovery en este proyecto!

Antes de definir esta feature, necesitamos definir para quién es el producto
entero. Esto solo se hace una vez por proyecto.

Tiempo estimado: 30-45 min (producto) + 15-30 min (feature) = ≤75 min total.

¿Comenzamos? [y/n]
```

Si `y`, ejecuta los 5 bloques esenciales de `app_market.md`:

1. **ICPs primarios** (1-3, con sanity check "3 personas concretas" por cada uno).
2. **No-ICPs** (anti-mercado): quién NO es target — protege contra feature creep.
3. **JTBDs racionales globales** (3-5, formato canónico).
4. **JTBDs emocionales globales** (2-3).
5. **North Star Metric**: 1 NSM + 2-3 input metrics.

Bloques opcionales (saltables con `[skip]`):
- Posicionamiento competitivo.
- Principios anti-feature.

Tras rellenar cada zona, **elimina el atributo `status="template-pristine"`** del marcador de zona en `app_market.md`. Esto activa el hook normal (el hook deja de tratar la zona como "pristine").

Auto-derivar zona auto `exportable_copy` con LLM: landing headline, LinkedIn post template, elevator pitch — derivados de los ICPs+JTBDs definidos.

Tras completar `app_market.md` con `Write`/`Edit`, llamar `record_app_docs_signature` para sellar la baseline, y bajar al flujo de la feature (vuelve al Paso 1 en modo standard).

> **Nota v6.0.1**: `record_app_docs_signature` sigue siendo state-tool (cat B) — no cambia firma. La firma se calcula a partir del contenido que el cliente ya escribió en disco vía la API de telemetría/state estándar.

---

## Paso 6 — Output generation (v6.0.1 content-passing)

1. **Reescribir `doc/discovery/<feature_name>/icp_jtbd.md`** con `Write` o `Edit` aplicando todo el contenido capturado (no solo el skeleton inicial). Las secciones que el skeleton dejó como `_(Pendiente...)_` se reemplazan con contenido real.

2. **Releer el artefacto** con `Read` para tener el contenido final en memoria.

3. **Llamar `validate_discovery_completeness`** con la API v6.0.1:

   ```
   validate_discovery_completeness(
     feature_name="<slug>",
     icp_jtbd_content=<contenido recién leído>,
   )
   ```

   - Devuelve `{verdict, missing, drift, artifact_path}`.
   - Si `verdict="READY_FOR_PRD"`: mostrar al usuario:
     ```
     ✅ Discovery completo para <feature_name>
        Artefacto: doc/discovery/<feature_name>/icp_jtbd.md
        Discovery ID: disc-...
        Verdict: READY_FOR_PRD

     Next step recomendado:
        /prd <feature_name>
     ```
   - Si `verdict="DISCOVERY_INCOMPLETE"`: mostrar las razones específicas:
     ```
     ⚠️  Discovery incompleto para <feature_name>
        Faltan: <list>
        Run /discovery <feature_name> de nuevo para resumir.
     ```

4. **Telemetría**: emitir evento `discovery_completed` al MCP via `report_session` con `{feature_name, verdict, duration_minutes, drift_detected_count, mode_used}`.

---

## Reglas inviolables

- **NO simular entrevistas con usuarios**. Si el usuario lo pide, recordar: el sanity check "3 personas concretas" no se puede automatizar; debe ser ejercicio humano.
- **NO sustituir validation evidence con suposiciones**. Si no hay evidence real, el waiver debe ser explícito y documentado.
- **NO sobrescribir** zonas `manual` de `app_market.md` sin pasar por el flujo de drift detection (Paso 3).
- **NO crear `icp_jtbd.md` directamente** sin pasar por `start_discovery` — pierde el UUID + idempotencia.

---

## Pedagogical layer — progressive onboarding

- **Feature 1-5**: modo `expanded` (micro-justificaciones, ejemplos, anti-patterns en cada paso).
- **Feature 6+**: modo `concise` (sin explicaciones inline; el usuario ya conoce los conceptos).
- **Override**: `--explain` fuerza modo expanded en cualquier feature.

Implementado via `record_skill_hint(project_path=".", skill_name="discovery")` y `get_skill_hint(project_path=".", skill_name="discovery")` (sistema existente). El contador se incrementa al final de cada `/discovery` exitoso.

---

## Pedagogical hooks — mensaje cuando bloquea `/prd`

Cuando el hook `pre-prd-discovery-check` (gate=block) impide ejecutar `/prd` porque discovery es incompleto:

```
⚠️ /prd bloqueado: discovery incompleto para <feature_name>

Razones:
- <missing[0]>
- <missing[1]>
- Drift sin resolver: <icps_nuevos[0]> no está en app_market.md

¿Por qué este bloqueo importa para tu feature?
Sin discovery, los AC del PRD nacen sin justificación trazable.
3 de cada 4 features que se construyen sin discovery requieren
≥2 iteraciones post-shipping para encontrar fit. Las que sí
pasan por discovery tienen base estable.

Atajo (15-30 min):
  /discovery <feature_name>

O salta este check (registrado para review post-shipping):
  /prd <feature_name> --skip-discovery --reason "..."
```

---

## Qualitative gate prompts (para JTBDs emocionales)

Este bloque se invoca desde `/implement`, no desde `/discovery` directamente. Cuando un AC del PRD lleva tag `[JE-X.Y]`, antes de marcarlo passed se ejecutan **3 preguntas fijas** (D-04 opción a):

```
🎭 Qualitative gate para AC-<id> [JE-<X>.<Y>]

JTBD emocional vinculado: <texto del JE-X.Y>

Antes de marcar este AC como passed, responde:

1. ¿Después de usar la feature, el usuario siente <sensación esperada>?
   [y] Sí, claramente
   [n] No, la implementación no transmite eso
   [m] Más o menos, ambiguo
   > _

2. ¿Hay algún screenshot del flujo que demuestre esa sensación?
   [adjuntar path a screenshot, o "no" para skip]
   > _

3. ¿La implementación entrega la sensación de forma observable, o requiere
   que el usuario sepa "qué se está intentando"?
   [o] Observable (cualquiera lo siente)
   [s] Solo si sabes
   [n] No observable
   > _
```

Solo se marca AC como passed si:
- Pregunta 1 = `y`, AND
- Pregunta 2 ≠ vacía (screenshot adjunto), AND
- Pregunta 3 ∈ {o, s} (no n).

Si falla cualquier criterio, AC queda en `qualitative_gate_failed` y el usuario decide: revisar implementación, o waiver explícito con justificación.

---

## Compatibilidad con el resto del engine

- **`/prd`** (UC-D003): si existe `doc/discovery/<feature>/icp_jtbd.md` con verdict READY_FOR_PRD, lo lee en Paso 0 y pre-rellena "Audience" + "Success Criteria" del PRD. Tagging `[JR-X.Y]` / `[JE-X.Y]` automático en cada AC.
- **`/plan`** (UC-D003): chequea cobertura JTBD por UC. Warning si JTBD definido en discovery no tiene UC.
- **`/implement`** (UC-D003): qualitative gate en ACs con tag JE (ver arriba). HTML Evidence Report sección "Discovery alignment".
- **`/app-init` / `/app-sync`**: respetan `app_market.md` (UC-D005). Plantilla pristine no produce drift.

---

## Telemetría

Eventos emitidos al MCP (`report_session`):

| Evento | Cuándo | Payload |
|--------|--------|---------|
| `discovery_started` | Inicio del flujo | `{feature_name, mode, timestamp}` |
| `discovery_completed` | Final con verdict READY_FOR_PRD o INCOMPLETE | `{feature_name, verdict, duration_minutes, drift_detected}` |
| `discovery_skipped` | Usuario ejecuta `/prd --skip-discovery` | `{feature_name, reason}` |
| `qualitative_gate_passed` | En `/implement`, AC JE marcada passed | `{feature_name, ac_id, jtbd_id}` |

Métricas agregadas en Sala de Máquinas: NSM (% features Done con discovery + AC taggeados), tiempo medio en /discovery, % features descartadas en discovery, distribución de drift resolutions.
