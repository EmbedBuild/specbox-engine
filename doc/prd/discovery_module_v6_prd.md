# PRD: Discovery Module v6.0 — SpecBox Engine

**Versión**: 6.0.0
**Codename**: "Discovery Foundations"
**Fecha**: 24 de mayo de 2026
**Estado**: PRD ready for `/plan`
**Autor**: Jesús Pérez (JPS Developer), con asistencia de Claude

---

## 0. Meta-context (dogfooding nivel meta)

Este PRD aplica el propio módulo Discovery sobre sí mismo: la sección 2 contiene el `app_market.md`-equivalent del módulo, y cada AC en las secciones 3.x está taggeado a un JTBD definido en 2.3 o 2.4. Esto sirve dos propósitos: (a) validar que el modelo conceptual es operacionalizable antes de implementarlo, y (b) producir un ejemplo de referencia que SpecBox Engine puede usar para enseñar el módulo a futuros users.

---

## 1. Resumen ejecutivo

SpecBox Engine v6.0 introduce un módulo de **Product Discovery permanente** integrado en el pipeline canónico. El módulo añade un paso `/discovery` antes de `/prd` que produce un artefacto `icp_jtbd.md` por feature, conteniendo los ICPs involucrados y sus JTBDs racionales y emocionales. Estos JTBDs se convierten en el **espinazo trazable** que viaja con la feature hasta los AC del PRD, las UC del plan y los tests E2E de la implementación.

A nivel producto entero, se introduce un tercer documento canónico `doc/app/app_market.md` (junto a los existentes `app_prd.md` y `app_spec.md`), que define los ICPs primarios, JTBDs globales, North Star Metric y posicionamiento competitivo del proyecto. Las features individuales heredan referenciando este documento.

Para sostener este módulo sin acumular deuda técnica, v6.0 también refactoriza el sistema interno de documentos canónicos (`app_docs`) de un modelo hardcoded a 2 docs a un **registro extensible de N documentos canónicos**. Esto convierte la introducción de futuros docs canónicos (v6.x+) en una operación trivial: una entrada en el registro + una plantilla. Sin refactor, sin if/else duplicados, sin bugs por casuística asimétrica.

La filosofía es audaz pero gobernada: **4 US (3 user-facing de Discovery + 1 de fundación arquitectural)**, backwards compatibility total con proyectos v5.x, opt-in en proyectos existentes (`discovery.enabled=false` por default), **versionado stable directo (`6.0.0`), no experimental**, porque la decisión arquitectural es definitiva. Discovery viene para quedarse.

El diferenciador estratégico frente a Spec Kit, Kiro, Cursor, Lovable y ChatPRD es que ninguno tiene una fase de problem framing previa al spec. SpecBox v6.0 ocupa ese espacio con enforcement arquitectural, no con docs externos.

---

## 2. Discovery del módulo (`app_market.md` aplicado al módulo Discovery)

### 2.1 ICPs primarios

**ICP-1 — Developer solo con productos en mercado.**
Software developer individual o equipo de 1-3 personas, con experiencia construyendo apps usando Claude Code, que mantiene productos digitales reales con clientes pagando. No tiene PM en el equipo. Ejemplo canónico: Jesús con PaddockManager (motor sport ops), McProfit (P&L hospitalería), Futbase (gestión clubes). Watering hole: comunidad SpecBox, LinkedIn dev/AI, Anthropic ecosystem.

**ICP-2 — Developer experto cruzando a producto.**
Software developer/integrador con dominio técnico fuerte (n8n, backend, automation) pero sin práctica formal de discovery o PM. Empieza a posicionar herramientas propias en mercado, no solo a entregar para clientes. Ejemplo canónico: Valentín Ayesa (n8n ambassador España, founder VA360). Watering hole: comunidades n8n, LinkedIn automation, eventos de no-code/low-code.

**ICP-3 — Profesional no-dev aprendiendo a construir con AI.**
Profesional de otra disciplina (finance, restauración, marketing) que empieza a construir aplicaciones aprovechando AI-assisted development, y adopta SpecBox como su primer entorno de desarrollo riguroso porque no quiere hacer "vibe coding" puro. Ejemplo canónico: Nani (finance profesional), Juan Valenzuela (hospitality finance). Watering hole: LinkedIn finance/business, comunidades de building in public.

### 2.2 No-ICPs (anti-mercado)

- **Product Managers profesionales** con experiencia en producto: ya tienen tools (Productboard, Linear, Notion) y procesos propios; el módulo les añadiría fricción.
- **Equipos enterprise** con departamentos dedicados de UX research: el módulo es deliberadamente ligero y no compite con esa estructura.
- **Vibe coders puros** que solo quieren shipping rápido sin proceso: filosóficamente incompatibles con SpecBox.
- **Researchers académicos** de UX: necesitan rigor metodológico que el módulo no pretende ofrecer.

Identificar a los no-ICPs es tan importante como identificar a los ICPs: protege contra feature creep ("habría que añadir competitive analysis", "necesitamos personas más elaboradas"). Si una petición de feature proviene de un no-ICP, se rechaza por diseño.

### 2.3 JTBDs racionales principales

**Para ICP-1 (Developer solo con productos en mercado):**

- **JR-1.1**: Cuando estoy a punto de construir una nueva feature, quiero validar rápidamente que resuelve un problema real para usuarios reales, para no gastar 1-2 semanas en algo que nadie usa.
- **JR-1.2**: Cuando defino la feature en el PRD, quiero que los criterios de aceptación respondan a necesidades concretas de un usuario específico, no a mi propia suposición.
- **JR-1.3**: Cuando reviso features ya shippeadas, quiero saber si mi discovery predijo bien o no, para calibrar mi intuición en futuras features.

**Para ICP-2 (Developer experto cruzando a producto):**

- **JR-2.1**: Quiero un método estructurado y rápido para definir el problema antes del PRD, sin convertirme en PM ni leer libros de producto.
- **JR-2.2**: Quiero exportar las definiciones de mercado (ICPs, JTBDs) a copy de landing y posts de LinkedIn sin reescribirlas desde cero.

**Para ICP-3 (Profesional no-dev aprendiendo):**

- **JR-3.1**: Quiero entender qué estoy haciendo cuando defino una feature, no solo seguir un checklist a ciegas.
- **JR-3.2**: Quiero que el sistema me enseñe los conceptos mientras los uso, no que me obligue a leer documentación antes de empezar.

**Para mantenedor del engine (ICP interno, US-D04):**

- **JR-M.1**: Cuando añado un doc canónico nuevo al engine, quiero que el cambio sea un único punto de modificación, para no olvidar actualizar 6 lugares duplicados.
- **JR-M.2**: Cuando un proyecto v5.x se upgradea a v6.0+, quiero que el sistema sepa qué docs canónicos esperaba a esa versión origen, para no warnear sobre docs no introducidos aún.

### 2.4 JTBDs emocionales principales

**Para ICP-1:**

- **JE-1.1**: Sentir control sobre el proceso de desarrollo, no dependencia ciega del LLM.
- **JE-1.2**: Reducir la ansiedad de "puede que esté construyendo lo equivocado".
- **JE-1.3**: Sentir orgullo profesional por hacer las cosas bien, no solo rápido.

**Para ICP-2:**

- **JE-2.1**: Sentir que el proceso es eficiente y no añade burocracia gratuita.
- **JE-2.2**: Sentirse legítimo como creador de producto, no solo "el técnico".

**Para ICP-3:**

- **JE-3.1**: Sentir confianza para hablar de su producto con otros profesionales sin sentirse impostor.
- **JE-3.2**: No sentirse perdido en la jerga del PM.
- **JE-3.3**: Sentir progreso visible y entendible en cada paso.

**Para mantenedor del engine (US-D04):**

- **JE-M.1**: Sentir que la arquitectura es honesta — no esconde deuda técnica detrás de un cap arbitrario.

### 2.5 North Star Metric del módulo

**NSM**: porcentaje de features completadas (estado Done) que pasaron por `/discovery` Y tienen ≥1 AC taggeado a JTBD, medido por proyecto activo, en una ventana móvil de 30 días.

Esta NSM captura tres dimensiones simultáneamente:
- **Adopción real** (no solo invocación esporádica del comando)
- **Integración efectiva** (no basta con ejecutar `/discovery`, debe traducirse al PRD vía tagging AC→JTBD)
- **Granularidad por proyecto** (detecta abandono parcial: un user puede usarlo en McProfit y no en Futbase)

**Input metrics** (leading indicators):
- Tiempo promedio invertido en `/discovery` por feature (target post-primera-feature: <30 min)
- Porcentaje de features con verdict `READY_FOR_PRD` (vs `DISCOVERY_INCOMPLETE`)
- Tasa de features descartadas durante `/discovery` (predictivo de valor: si nunca se descarta nada, el módulo no está siendo crítico)

### 2.6 Posicionamiento competitivo

Frente a GitHub Spec Kit, AWS Kiro, Cursor, Lovable, ChatPRD y skills community de Claude Code, SpecBox v6.0 es el **único framework SDD opinionated con enforcement arquitectural de problem framing previo al spec**. Los demás operan en espacio-solución desde el primer paso. La trazabilidad ICP/JTBD → AC → evidence E2E es estructuralmente imposible en ellos.

Mensaje canónico: *"You don't ship the wrong thing perfectly."*

### 2.7 Principios anti-feature (qué NO hace el módulo, aunque pudiera)

- **NO simula entrevistas con usuarios** (Claude no puede; sería self-deception).
- **NO genera surveys o cuestionarios** para distribuir externamente.
- **NO hace competitive analysis automatizado** (eso es discovery formal, no ligero).
- **NO calcula TAM/SAM/SOM** (no aplica a granularidad feature).
- **NO crea roadmap multi-feature** (es planning, no discovery; territorio de `/plan`).
- **NO sustituye a hablar con usuarios reales** (el sanity check de "3 personas concretas" lo recuerda explícitamente).

---

## 3. User Stories

### US-D01 — Discovery conversational flow per feature

> **Como** developer sin formación formal de PM,
> **quiero** ser guiado por un flujo conversacional corto (15-30 min) que me ayude a identificar los ICPs involucrados en una feature y sus JTBDs racionales y emocionales,
> **para** definir el camino de validación de la feature antes de invocar `/prd`.

**ICPs involucrados**: ICP-1, ICP-2, ICP-3
**JTBDs satisfechos**: JR-1.1, JR-2.1, JR-3.1, JR-3.2, JE-1.1, JE-2.1, JE-3.1, JE-3.3

#### UC-D001 — Ejecutar `/discovery [feature_name]` en modo estándar

**Descripción**: cuando el proyecto ya tiene `doc/app/app_market.md` completado, `/discovery [feature_name]` lanza un flujo conversacional de 3 fases (ICP identification, JTBD extraction, validation gate), genera `doc/discovery/<feature_name>/icp_jtbd.md` y termina con un verdict explícito.

**Acceptance Criteria**:

- **AC-D001-01** [JR-1.1, JR-3.1]: La invocación `/discovery user_export` en un proyecto con `app_market.md` completado lanza un flujo interactivo en ≤2 segundos desde el comando.
- **AC-D001-02** [JR-3.1, JE-3.2]: La Fase 1 (ICP identification) muestra los ICPs canónicos del `app_market.md` y pregunta cuáles están involucrados en esta feature. El usuario puede seleccionar 1-3 ICPs preexistentes o añadir uno nuevo con warning de drift.
- **AC-D001-03** [JR-1.1, JE-1.2]: Para cada ICP nuevo (no presente en `app_market.md`), el flujo aplica el sanity check "¿conoces a 3 personas concretas que encajen?" y registra la respuesta en el artefacto. Si la respuesta es no, marca el ICP como tentativo.
- **AC-D001-04** [JR-1.1, JR-1.2, JR-3.1]: La Fase 2 (JTBD extraction) genera, para cada ICP seleccionado, un draft de 2-3 JTBDs racionales y 1-2 JTBDs emocionales en formato canónico "Cuando [situación], quiero [motivación], para [resultado esperado]". El usuario edita/refina/elimina/añade libremente.
- **AC-D001-05** [JE-3.2, JR-3.2]: Cada concepto nuevo introducido en el flujo (ICP, JTBD racional, JTBD emocional) viene acompañado de: (a) una micro-justificación en lenguaje natural de por qué importa, (b) un ejemplo real del ecosistema embed.build (PaddockManager/McProfit/Futbase/SpecBox), (c) un anti-pattern explícito como contraejemplo.
- **AC-D001-06** [JR-1.1, JE-1.2]: La Fase 3 (validation gate) muestra resumen consolidado y pregunta: "¿hay alguna conversación reciente, datapoint de mercado o evidence externa que respalde estos JTBDs?" La respuesta (libre, o explícito waiver) se registra en `icp_jtbd.md`.
- **AC-D001-07** [JR-1.2, JR-2.1]: El artefacto final `doc/discovery/<feature_name>/icp_jtbd.md` se genera con la estructura canónica definida en la sección 4.1 y contiene `discovery_id` único trazable.
- **AC-D001-08** [JR-1.1]: El flujo completo se completa en ≤30 minutos para un user experimentado (después de su primera feature) y ≤60 minutos para la primera feature de un user nuevo (en modo bootstrap).
- **AC-D001-09** [JE-1.1, JE-2.1]: El flujo es interrumpible en cualquier fase. Una segunda invocación de `/discovery [feature_name]` detecta artefacto parcial y ofrece resumir o reiniciar.
- **AC-D001-10** [JR-3.1, JE-3.3]: El comando muestra al final un verdict explícito: `READY_FOR_PRD` o `DISCOVERY_INCOMPLETE` con lista específica de razones (ej: "falta JTBD racional para ICP-2").

#### UC-D002 — Ejecutar `/discovery` en modo bootstrap (primer uso en proyecto)

**Descripción**: cuando `doc/app/app_market.md` está vacío o ausente, `/discovery [feature_name]` detecta la situación y entra en modo bootstrap: primero completa el nivel producto (ICPs canónicos, JTBDs globales, NSM, posicionamiento), luego desciende al nivel feature.

**Acceptance Criteria**:

- **AC-D002-01** [JR-3.1, JE-3.2]: La detección de `app_market.md` vacío/ausente lanza modo bootstrap automáticamente sin requerir flag explícito.
- **AC-D002-02** [JE-3.2, JE-3.3]: El modo bootstrap muestra mensaje pedagógico inicial: "Antes de definir esta feature, necesitamos definir para quién es el producto entero. Esto solo se hace una vez por proyecto."
- **AC-D002-03** [JR-2.2, JR-3.1]: La fase producto completa los 5 bloques esenciales de `app_market.md`: ICPs primarios, no-ICPs, JTBDs racionales globales, JTBDs emocionales globales, NSM. Los bloques opcionales (posicionamiento, anti-features) se ofrecen pero pueden saltarse.
- **AC-D002-04** [JR-2.2]: El `app_market.md` generado incluye sección "Exportable copy" con extractos pre-formateados para landing, LinkedIn post y elevator pitch, derivados automáticamente de ICPs+JTBDs.
- **AC-D002-05** [JR-1.1]: Tras completar `app_market.md`, el flujo desciende automáticamente al modo estándar de UC-D001 para la feature solicitada.
- **AC-D002-06** [JE-1.1, JE-3.3]: El tiempo total de bootstrap (producto + primera feature) no supera 75 minutos.

---

### US-D02 — Inheritance and traceability from discovery to implementation

> **Como** SpecBox Engine,
> **quiero** que los ICPs y JTBDs definidos en `/discovery` se hereden automáticamente al PRD, se taggeen a los AC, se preserven en las UC del plan y se validen en los tests E2E de la implementación,
> **para** mantener trazabilidad estratégica completa desde el problem framing hasta la evidence de shipping.

**ICPs involucrados**: ICP-1, ICP-2
**JTBDs satisfechos**: JR-1.2, JR-1.3, JE-1.1, JE-1.3, JE-2.2

#### UC-D003 — Integración bidireccional Discovery ↔ PRD ↔ Plan ↔ Implement

**Descripción**: la herencia funciona como pipeline: `/prd` lee `icp_jtbd.md` y pre-rellena secciones, cada AC del PRD se taggea con ≥1 JTBD, `/plan` chequea cobertura JTBD en UCs, `/implement` valida AC racionales vía Playwright (existente) y añade qualitative gate para JTBDs emocionales.

**Acceptance Criteria**:

- **AC-D003-01** [JR-1.2]: La invocación de `/prd [feature_name]` detecta automáticamente `doc/discovery/<feature_name>/icp_jtbd.md` si existe, lo lee y pre-rellena las secciones "Audience" y "Success Criteria" del PRD.
- **AC-D003-02** [JR-1.2, JE-1.3]: El PRD generado contiene un bloque "Discovery traceability" con: `discovery_id`, hash del `icp_jtbd.md` referenciado, lista de ICPs y JTBDs heredados.
- **AC-D003-03** [JR-1.2]: Cada Acceptance Criterion del PRD lleva un tag `[JR-X.Y]` o `[JE-X.Y]` referenciando los JTBDs que satisface. Si un AC no tiene tag, el sistema emite warning ("AC-XX sin JTBD backing — ¿feature creep?").
- **AC-D003-04** [JR-1.3, JE-1.1]: La invocación de `/plan [feature_name]` lee el PRD taggeado, calcula la cobertura JTBD por UC y emite warning si algún JTBD definido en discovery no tiene UC que lo satisfaga.
- **AC-D003-05** [JR-1.3, JE-1.3]: Durante `/implement`, los tests E2E Playwright (mecanismo existente) validan AC racionales como ahora. Para AC taggeados a JTBDs emocionales (`[JE-X.Y]`), se añade un "qualitative gate": prompt al developer con preguntas reflexivas + screenshot review obligatorio antes de marcar AC como passed.
- **AC-D003-06** [JR-1.3]: El HTML Evidence Report final (mecanismo existente `evidenceStep()`) incluye nueva sección "Discovery alignment" mostrando: cobertura JTBD alcanzada, AC con qualitative gate passed, AC sin JTBD tag (si los hay).
- **AC-D003-07** [JR-2.2]: La sincronización es bidireccional via `apply_app_docs_sync` extendido: cambios en `icp_jtbd.md` post-PRD generan warning de drift; cambios en AC sin update de JTBDs generan warning inverso.

---

### US-D03 — Strategic drift detection across project lifetime

> **Como** SpecBox Engine,
> **quiero** detectar cuándo una feature nueva en discovery introduce ICPs o JTBDs no presentes en `doc/app/app_market.md`,
> **para** alertar al developer sobre posible feature creep estratégico o necesidad de actualizar la tesis del producto.

**ICPs involucrados**: ICP-1, ICP-2
**JTBDs satisfechos**: JR-1.2, JR-2.2, JE-1.2

#### UC-D004 — Drift detection ICP/JTBD entre feature y producto

**Descripción**: cada `/discovery` por feature compara los ICPs y JTBDs declarados contra `app_market.md`. Si introduce elementos no presentes a nivel producto, dispara warning estructurado que el user debe responder explícitamente.

**Acceptance Criteria**:

- **AC-D004-01** [JR-1.2, JE-1.2]: Al final de la Fase 2 (JTBD extraction) en UC-D001, el sistema compara cada ICP y JTBD declarado contra `app_market.md`. Elementos nuevos se listan explícitamente.
- **AC-D004-02** [JR-1.2, JE-1.2]: Para cada elemento nuevo, el sistema pregunta: "¿Es esto: (a) feature creep que debería rechazarse, (b) extensión legítima que debería actualizar `app_market.md`, o (c) excepción puntual aceptable solo para esta feature?". La respuesta se registra.
- **AC-D004-03** [JR-2.2]: Si la respuesta es (b), el sistema ofrece actualizar `app_market.md` ahí mismo. Si la respuesta es (c), registra "excepción documentada" en `icp_jtbd.md` con justificación obligatoria.
- **AC-D004-04** [JR-1.2]: Si la respuesta es (a), la feature se marca como cancelada en `/discovery` y no genera artefacto que permita pasar a `/prd`.
- **AC-D004-05** [JR-1.2, JE-1.2]: El hook `verify_app_market` (extensión de `verify_app_docs` existente) chequea sync entre `app_market.md` y los `icp_jtbd.md` de las últimas N features (default N=5). Si hay drift sistemático sin resolver, warning durante invocación de cualquier slash command.
- **AC-D004-06** [JR-1.2]: Comando opcional `/discovery --review` muestra dashboard de drift: ICPs nuevos introducidos por feature en últimas 30 días, JTBDs emergentes, excepciones documentadas pendientes de resolver.

---

### US-D04 — Multi-document canonical registry foundation

> **Como** mantenedor del SpecBox Engine,
> **quiero** que el sistema `app_docs` (sync, drift detection, hook enforcement, upgrade path) opere sobre un registro extensible de N documentos canónicos en lugar de hardcodear `app_prd` y `app_spec`,
> **para** poder añadir `app_market.md` en v6.0 y futuros documentos canónicos en v6.x+ sin duplicar código ni introducir bugs por casuística asimétrica.

**ICPs involucrados**: mantenedor del engine (ICP interno, no users finales del producto).
**JTBDs satisfechos**: JR-M.1, JR-M.2, JE-M.1

#### UC-D005 — Refactor `app_docs` a registro multi-doc

**Descripción**: extraer la lista de docs canónicos del código duplicado actual (`PRD_PATH`/`SPEC_PATH` en `server/app_docs/sync.py:38-39`, mismo patrón en `app-docs-sync-guard.mjs:34-35`, `EVENT_ZONE_MAP` en `sync.py:166-179`, etc.) a un registro único `server/app_docs/registry.py` + descriptor JSON consumible por el hook Node.js. Todo el resto del sistema itera sobre el registro.

**Acceptance Criteria**:

- **AC-D005-01** [JR-M.1]: Existe módulo `server/app_docs/registry.py` que expone `CANONICAL_DOCS: list[CanonicalDoc]`. Cada entrada tiene: `id`, `path`, `introduced_in` (semver), `template_path`, `required_zones: dict[str, ZoneKind]`, `event_zone_map: dict[event, list[zone_id]]`.
- **AC-D005-02** [JR-M.1]: `server/app_docs/sync.py` (`verify_app_docs_in_sync`, `record_sync_signature`, `EVENT_ZONE_MAP`) itera sobre `CANONICAL_DOCS` en lugar de tener 2 ramas hardcoded para PRD/SPEC. Las constantes `PRD_PATH`, `SPEC_PATH` se eliminan.
- **AC-D005-03** [JR-M.1]: `.claude/hooks/app-docs-sync-guard.mjs` lee `templates/canonical_docs.json` (descriptor generado desde el módulo Python como source-of-truth — ver D-10 resuelta como opción (b)) e itera sobre la lista. Sin hardcoded `checkDoc('app_prd', ...)` / `checkDoc('app_spec', ...)`.
- **AC-D005-04** [JR-M.2]: Cada `CanonicalDoc` lleva campo `introduced_in: str` (semver). El hook y `verify_app_docs_in_sync` ignoran un doc cuando: (a) no existe en disco, AND (b) `project_meta.engine_version_at_onboard < doc.introduced_in`. Esto evita warnings espurios en proyectos upgrade-from-v5.x.
- **AC-D005-05** [JR-M.2]: `meta.json` del proyecto incluye nuevo campo `engine_version_at_onboard` (capturado en `onboard_project` y preservado en `upgrade_project`). Para proyectos v5.x preexistentes que no tengan este campo en su `meta.json`, política conservadora: tratar como `"unknown"`, y el hook solo verifica docs con `introduced_in <= 5.29.0`. Esto resuelve D-11 como opción (b).
- **AC-D005-06** [JR-M.1]: Tests de regresión: matriz `{proyectos fixture en v5.29, v5.33, v5.35} × {operaciones: verify, repair, hook commit, /app-sync}` pasa sin cambio de comportamiento observable. Snapshot tests guardan output esperado.
- **AC-D005-07** [JR-M.1]: La extensión de `CANONICAL_DOCS` con `app_market.md` (UC-D006) requiere **una sola línea de código + una entrada en el registro + una plantilla**. Sin cambios en `sync.py`, hook, ni `/app-sync`.
- **AC-D005-08** [JR-M.2]: Tool MCP `read_app_docs_tool` recibe parámetro opcional `doc_ids: list[str] = None`. Si None, devuelve todos los docs canónicos del proyecto (incluyendo nuevos como `app_market`). Backwards compat: comportamiento previo = pasar `doc_ids=["app_prd", "app_spec"]` explícito.
- **AC-D005-09** [JE-M.1]: La PR del refactor incluye un documento `doc/decisions/multi_doc_registry.md` explicando: por qué se hizo, qué patrón se eligió (registry vs subclasses vs plugins), qué se descartó, cómo extender en futuras versiones.
- **AC-D005-10** [JR-M.1, JR-M.2]: `upgrade_project` se extiende para iterar sobre `CANONICAL_DOCS` y, para cada doc canónico con `introduced_in > project_meta.engine_version_at_onboard`:
  - Si el archivo NO existe en el proyecto destino → escribe plantilla vacía con marcadores de zona desde `template_path`.
  - Si el archivo SÍ existe → no toca nada (preserva contenido del usuario, incluso si las zonas están mal formadas — `/app-sync --review` es quien arregla eso).
  - Reporta en el return cuáles docs canónicos creó vs cuáles ya existían en campo nuevo `canonical_docs_created: list[dict]`.
- **AC-D005-11** [JE-M.1]: La invariante "`upgrade_project` nunca pisa contenido existente" se preserva. Lo que cambia es que ahora puede CREAR archivos nuevos, no MODIFICAR archivos existentes. Esa distinción se documenta explícitamente en el docstring de `upgrade_project` y en `doc/decisions/multi_doc_registry.md`.
- **AC-D005-12** [JR-M.2]: Test fixture específico: "proyecto v5.35 con `app_prd.md` modificado manualmente recibe upgrade a v6.0". Verifica:
  - `app_prd.md` queda exactamente igual (byte por byte).
  - `app_spec.md` queda exactamente igual.
  - `app_market.md` se crea desde plantilla vacía con marcador `status="template-pristine"`.
  - `engine_version_at_onboard` se preserva o se marca `"unknown"` si no existía.
- **AC-D005-13** [JR-M.1]: Plantillas de docs canónicos llevan marcador `status="template-pristine"` en zonas `manual`. El hook `app-docs-sync-guard.mjs` lo respeta — no warnea sobre docs presentes pero no inicializados. `/discovery` y `/app-init` eliminan el marcador automáticamente cuando rellenan la primera zona.

#### UC-D006 — Introducción de `app_market.md` vía el registro

**Descripción**: una vez existe el registro multi-doc (UC-D005), añadir `app_market.md` es trivial. Este UC valida que efectivamente lo es: la diff de la PR debe demostrar el cap (1 archivo nuevo + 1 línea modificada + 0 cambios en lógica).

**Acceptance Criteria**:

- **AC-D006-01** [JR-M.1]: Plantilla `templates/app_market.md.template` existe con las 8 zonas definidas en sección 4.1.1 (ICPs primarios, no-ICPs, JTBDs racionales, JTBDs emocionales, NSM, posicionamiento, anti-features, exportable copy). Todas las zonas manuales llevan marcador `status="template-pristine"`.
- **AC-D006-02** [JR-M.1]: Entry añadida en `CANONICAL_DOCS` con `id="app_market"`, `introduced_in="6.0.0"`, `template_path="templates/app_market.md.template"`, y los `event_zone_map` para eventos de Discovery (`app_market_icp_added`, `app_market_jtbd_added`, `nsm_updated`).
- **AC-D006-03** [JR-M.1]: Diff de la PR de UC-D006 muestra: 1 archivo nuevo (template), 1 entry nueva en `registry.py`, 0 cambios en `sync.py` / hook / skills. Validado por revisión visual del diff antes de merge.
- **AC-D006-04** [JR-M.2]: Hook `app-docs-sync-guard.mjs` corre verde en proyecto v5.35-upgraded-to-v6.0 sin `app_market.md` rellenado (solo con plantilla pristine). Verificado en test fixture.
- **AC-D006-05** [JR-M.1]: `/app-sync --check` reporta `app_market: template-pristine (introduced_in 6.0.0, project_version_at_onboard 5.33.0, awaiting first /discovery)` como info, no como drift.

---

## 4. Architecture spec

### 4.1 Nuevos artefactos

#### 4.1.1 `doc/app/app_market.md` (nivel producto, canónico)

Plantilla generada por `upgrade_project` (vacía, status template-pristine) y completada por modo bootstrap del primer `/discovery`. Estructura:

```markdown
# Mercado del producto

> Documento canónico nivel producto. Cambia raramente. Define para quién es la app entera y qué jobs aborda. Cada feature individual hereda de este documento.

<!-- @specbox:zone start kind="manual" id="icps_primary" status="template-pristine" -->
## ICPs primarios
[1-3 ICPs canónicos, cada uno con: rol, 3 atributos diferenciadores, watering hole]
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="anti_icps" status="template-pristine" -->
## No-ICPs (anti-mercado)
[Quién explícitamente NO es target — protege contra feature creep]
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="jtbds_rational" status="template-pristine" -->
## JTBDs racionales principales
[3-5 jobs funcionales globales, formato "Cuando X, quiero Y, para Z"]
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="jtbds_emotional" status="template-pristine" -->
## JTBDs emocionales principales
[2-3 sensaciones que el producto entrega o evita]
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="north_star_metric" status="template-pristine" -->
## North Star Metric
[1 NSM + 2-3 input metrics, con criterios Amplitude]
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="positioning" status="template-pristine" -->
## Posicionamiento competitivo (opcional)
[Frente a qué alternativas, en qué dimensión ganamos]
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="anti_features" status="template-pristine" -->
## Principios anti-feature (opcional)
[Cosas que el producto NUNCA hace, aunque pudiera]
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="auto" id="exportable_copy" auto_sync_on="app_market_icp_added,app_market_jtbd_added" -->
## Exportable copy (auto-derivado)
### Landing headline
### LinkedIn post template
### Elevator pitch (30 segundos)
<!-- @specbox:zone end -->

---
**Signature**: <hash>
**Last updated**: <ISO timestamp>
**Updated by**: <discovery_id que originó el cambio>
```

#### 4.1.2 `doc/discovery/<feature_name>/icp_jtbd.md` (nivel feature, efímero)

Generado por `/discovery [feature_name]`. Estructura:

```markdown
# Discovery: <feature_name>

**Discovery ID**: <uuid>
**Created**: <ISO timestamp>
**Status**: READY_FOR_PRD | DISCOVERY_INCOMPLETE
**Source of inheritance**: doc/app/app_market.md @ <signature>

## ICPs involucrados

### ICP-X: <name>
- **Inherited from app_market**: yes | no (new — see drift section)
- **Sanity check**: ¿conoces 3 personas concretas? [yes/no/tentative]
- **Specific to feature**: [atributos extra relevantes para esta feature]

## JTBDs racionales
- **JR-FX.1** [ICP-X]: Cuando [situación], quiero [motivación], para [resultado].
- **JR-FX.2** [ICP-Y]: ...

## JTBDs emocionales
- **JE-FX.1** [ICP-X]: [sensación a entregar o evitar]
- **JE-FX.2** [ICP-Y]: ...

## Validation evidence
- **Evidence type**: conversation | datapoint | market signal | explicit waiver
- **Description**: [registro libre o justificación de waiver]
- **Date**: <ISO timestamp>

## Drift from app_market
- **Nuevos ICPs introducidos**: [lista o ninguno]
- **Nuevos JTBDs introducidos**: [lista o ninguno]
- **Resolución**: feature_creep_rejected | app_market_updated | documented_exception
- **Justification** (si exception): [texto]

## Verdict
**READY_FOR_PRD** | **DISCOVERY_INCOMPLETE** because:
- [razón específica si incomplete]
```

#### 4.1.3 Estructura de directorios resultante

```
doc/
  app/
    app_market.md       (NUEVO en v6.0, canónico, nivel producto)
    app_prd.md          (existente desde v5.29)
    app_spec.md         (existente desde v5.29)
  discovery/            (NUEVO directorio)
    <feature_1>/
      icp_jtbd.md
    <feature_2>/
      icp_jtbd.md
    ...
```

#### 4.1.4 Canonical docs registry (NUEVO)

Source-of-truth única para qué documentos canónicos existen, en qué versión se introdujeron, qué zonas tienen, qué eventos los mutan. Vive en `server/app_docs/registry.py` y se serializa a `templates/canonical_docs.json` (descriptor consumible por el hook Node.js, regenerado automáticamente desde el módulo Python por un script de build).

```python
# server/app_docs/registry.py (NUEVO en v6.0)

@dataclass(frozen=True)
class CanonicalDoc:
    id: str                              # "app_prd", "app_spec", "app_market"
    path: str                            # "doc/app/app_prd.md"
    introduced_in: str                   # semver: "5.29.0", "6.0.0"
    template_path: str                   # "templates/app_prd.md.template"
    required_zones: dict[str, ZoneKind]  # {"vision": MANUAL, "roadmap": AUTO, ...}
    event_zone_map: dict[str, list[str]] # {"complete_uc": ["roadmap"], ...}

CANONICAL_DOCS: list[CanonicalDoc] = [
    CanonicalDoc(
        id="app_prd",
        path="doc/app/app_prd.md",
        introduced_in="5.29.0",
        template_path="templates/app_prd.md.template",
        required_zones={...},
        event_zone_map={...},
    ),
    CanonicalDoc(
        id="app_spec",
        path="doc/app/app_spec.md",
        introduced_in="5.29.0",
        template_path="templates/app_spec.md.template",
        required_zones={...},
        event_zone_map={...},
    ),
    CanonicalDoc(
        id="app_market",
        path="doc/app/app_market.md",
        introduced_in="6.0.0",
        template_path="templates/app_market.md.template",
        required_zones={...},
        event_zone_map={
            "app_market_icp_added": ["exportable_copy"],
            "app_market_jtbd_added": ["exportable_copy"],
            ...
        },
    ),
]
```

Todo el resto del sistema (`sync.py`, hook, skills, `upgrade_project`, `verify_app_docs`) consume este registro. Añadir un doc nuevo en futuras versiones se reduce a (a) plantilla + (b) entrada en `CANONICAL_DOCS` + (c) regenerar el JSON descriptor. Sin cambios en lógica.

### 4.2 Nuevos MCP tools (3) y refactor de tools existentes (5)

#### 4.2.1 `Specbox-engine:start_discovery` (NUEVO)

**Signature**:
```
start_discovery(
  feature_name: str,
  project_path: str,
  mode: "auto" | "standard" | "bootstrap" = "auto"
) -> { discovery_id: str, status: str, artifact_path: str, mode_used: str }
```

**Behavior**:
- En modo `auto`: detecta si `app_market.md` está vacío/ausente → bootstrap; si no → standard.
- Crea estructura `doc/discovery/<feature_name>/` si no existe.
- Inicializa `icp_jtbd.md` con UUID y timestamp.
- Idempotente: segunda invocación con mismo feature_name detecta artefacto existente y retorna `status: "resumable"`.
- Retorna estructurado: error en `result.error.code` (no excepciones).

#### 4.2.2 `Specbox-engine:validate_discovery_completeness` (NUEVO)

**Signature**:
```
validate_discovery_completeness(
  feature_name: str,
  project_path: str
) -> { verdict: "READY_FOR_PRD" | "DISCOVERY_INCOMPLETE", missing: list[str], drift: dict }
```

**Behavior**:
- Lee `doc/discovery/<feature_name>/icp_jtbd.md`.
- Chequea presencia y formato de: ≥1 ICP, ≥1 JTBD racional por ICP, ≥1 JTBD emocional por ICP, evidence o explicit waiver, drift section resuelta.
- Si falta cualquier elemento, retorna `DISCOVERY_INCOMPLETE` con lista específica en `missing`.
- Calcula drift vs `app_market.md` y lo retorna en `drift`.
- Llamado por: hook `pre-prd-discovery-check` y comando `/discovery --status`.

#### 4.2.3 `Specbox-engine:detect_v60_migration_case` (NUEVO)

**Signature**:
```
detect_v60_migration_case(
  project_path: str
) -> MigrationPlan { case_id: str, steps: list[MigrationStep], backup_required: bool, notes: list[str] }
```

**Behavior**:
- Análogo a `detect_v529_migration_case` existente (precedente directo en `server/app_docs/migration_v529.py`).
- Clasifica el proyecto en uno de los 8 casos hipotéticos descritos en §4.8 (upgrade path).
- Devuelve plan estructurado en dry-run; ejecutor con `apply=True` opt-in.

#### 4.2.4 Tools existentes refactorizadas (no nuevas, refactor in-place)

Las siguientes tools de v5.29 se refactorizan para iterar sobre `CANONICAL_DOCS` en lugar de hardcodear PRD/SPEC. La signatura externa se preserva (backwards compat):

- **`read_app_docs_tool`**: añade parámetro opcional `doc_ids: list[str] = None`. Si None, lee todos los docs canónicos del proyecto vía el registro. Default behaviour previo = explícito `doc_ids=["app_prd", "app_spec"]`.
- **`apply_app_docs_sync`**: itera sobre `CANONICAL_DOCS.event_zone_map` en lugar de tener `EVENT_ZONE_MAP` hardcoded.
- **`record_app_docs_signature`**: itera sobre todos los docs del registro presentes en el proyecto.
- **`detect_app_docs_drift`**: añade nuevo modo "strategic drift" para detectar ICPs/JTBDs entre `icp_jtbd.md` features y `app_market.md`. Modos previos (S1-S4) se preservan.
- **`verify_app_docs`**: extender para chequear coherencia N-documento (no solo tri-documento). Lee el registro.

#### 4.2.5 `evaluate_autopilot_decision`: nueva entry en el catálogo

Añadir `decision_key = "discovery_completeness_gate"` al catálogo de 19 → 20 decision_keys en `server/app_docs/autopilot.py`. Tiers default:
- `low`: `ask`
- `conservador`: `ask`
- `equilibrado`: `auto_if_discovery_ready` (nueva regla: auto-confirm si `validate_discovery_completeness` devuelve `READY_FOR_PRD`)
- `agresivo`: `auto_if_discovery_ready`

### 4.3 Hooks: 1 nuevo + 1 refactorizado

#### 4.3.1 `pre-prd-discovery-check.mjs` (NUEVO)

**Tipo**: WARNING por defecto en proyectos existentes (`gate_mode=off`), BLOCKING en proyectos nuevos opt-in (`gate_mode=block`).
**Activación**: trigger en invocación de `/prd [feature_name]` (PreToolUse).
**Configuración**: `specbox.discovery.gate_mode: "off" | "warn" | "block"` en `settings.local.json`.

**Lógica**:
1. Lee config `specbox.discovery.gate_mode` para el proyecto.
2. Si `gate_mode == "off"` → no-op, deja pasar.
3. Invoca `validate_discovery_completeness(feature_name, project_path)`.
4. Si verdict es `READY_FOR_PRD` → no-op, deja pasar.
5. Si verdict es `DISCOVERY_INCOMPLETE`:
   - Si `gate_mode == "warn"`: muestra mensaje pedagógico + razones específicas + atajo `/discovery [feature_name]`. Deja pasar (exit 0).
   - Si `gate_mode == "block"`: muestra mismo mensaje pero retorna exit code 1, abortando `/prd`.

**Implementación**: Node.js `.mjs` siguiendo el patrón establecido en v5.17 (shared `lib/`, zero npm deps).

#### 4.3.2 `app-docs-sync-guard.mjs` (REFACTORIZADO, NO NUEVO)

Hook existente desde v5.29.0. Se refactoriza para:
- Leer `templates/canonical_docs.json` descriptor (en lugar de hardcoded `PRD_PATH`/`SPEC_PATH`).
- Iterar sobre todos los docs canónicos.
- Aplicar gate `introduced_in` vs `engine_version_at_onboard` para no warnear sobre docs no introducidos aún en proyectos upgrade.
- Respetar marcador `status="template-pristine"` para no warnear sobre plantillas vacías recién creadas por `upgrade_project`.

La lógica de exit codes (warning vs blocking según `specbox.app_docs_sync.block_on_drift`) se preserva sin cambios.

### 4.4 Tools existentes extendidos (resumen consolidado en §4.2.4)

Ver §4.2.4. La extensión no consiste en "añadir if para app_market" sino en "iterar sobre `CANONICAL_DOCS`". Eso es la diferencia clave entre v6.0 (refactor) y un parche superficial.

### 4.5 Slash commands modificados

#### 4.5.1 `/prd [feature_name]` (modificado)

- **Paso 0 nuevo**: detecta `doc/discovery/<feature_name>/icp_jtbd.md`. Si existe y verdict es `READY_FOR_PRD`, pre-rellena secciones "Audience" y "Success Criteria" del PRD.
- **Paso N nuevo**: durante AC drafting, cada AC se acompaña de prompt "¿qué JTBD satisface este AC?". Tag `[JR-X.Y]` o `[JE-X.Y]` se inserta automáticamente.
- **Validación final**: PRD sin AC taggeados → warning (no blocking en v6.0).

#### 4.5.2 `/plan [feature_name]` (modificado)

- **Paso nuevo**: chequea cobertura JTBD en UCs. Si algún JTBD definido en discovery no tiene UC que lo satisfaga, emite warning estructurado.
- **No bloquea por defecto**: este es un guard pedagógico, no enforcement duro en v6.0.

#### 4.5.3 `/implement` (modificado)

- **Qualitative gate para AC con tag `[JE-X.Y]`**: antes de marcar AC como passed, prompt al developer con preguntas reflexivas estructuradas (3 preguntas fijas, según D-04 resuelta como opción (a)) + screenshot review obligatorio.
- **Evidence Report extendido**: nueva sección "Discovery alignment" en HTML output.

#### 4.5.4 `/app-init` y `/app-sync` (extendidos)

- **`/app-init --refresh`**: detecta missing `app_market.md` en proyectos con `app_prd.md` existente → propone creación opt-in al usuario (caso típico post-upgrade v5.x → v6.0 si por algún motivo `upgrade_project` no lo creó, ej. running el upgrade en una versión vieja del CLI).
- **`/app-init` modo `init`**: incluye `app_market.md` siempre como parte de la creación inicial.
- **`/app-sync --check`**: respeta marcador `status="template-pristine"` y `introduced_in` vs `engine_version_at_onboard`. No warnea sobre docs pristine o no introducidos aún.

### 4.6 Nuevo skill

#### 4.6.1 `.claude/skills/discovery/SKILL.md`

Contiene la lógica conversacional del flujo `/discovery`, los ejemplos del ecosistema, los anti-patterns, las micro-justificaciones pedagógicas y las preguntas reflexivas del qualitative gate. Frontmatter: `context: direct` (escribe artefactos al filesystem, debe correr en sesión principal). Estructura interna:

```
SKILL.md
├── Overview (lo que hace, cuándo se invoca)
├── Phase 1: ICP identification
│   ├── Pedagogical intro
│   ├── Examples from ecosystem
│   ├── Anti-patterns
│   └── Sanity check protocol
├── Phase 2: JTBD extraction (rational + emotional)
│   ├── Pedagogical intro
│   ├── Examples
│   ├── Anti-patterns
│   └── Format canónico
├── Phase 3: Validation gate
│   ├── Evidence types
│   ├── Drift handling
│   └── Verdict generation
├── Bootstrap mode (first /discovery in project)
└── Qualitative gate prompts (for emotional JTBDs) — 3 preguntas fijas
```

### 4.7 Configuración

Añadir a `settings.local.json` schema:

```json
{
  "specbox": {
    "discovery": {
      "enabled": false,                  // gate maestro v6.0; default false en upgrade, true en fresh-clone post-v6.0
      "gate_mode": "off",                // "off" | "warn" | "block"
      "engine_version_at_onboard": "5.35.0",  // capturado en onboard/upgrade; "unknown" si proyecto v5.x preexistente sin migración explícita
      "require_evidence": false,         // strict mode opt-in
      "max_session_minutes": 30,
      "pedagogical_mode": "auto",        // auto = enabled for first 5 features, then off
      "drift_warning": true,
      "qualitative_gate": true
    }
  }
}
```

### 4.8 Upgrade path para proyectos existentes (NUEVA SECCIÓN)

Proyectos existentes en v5.29-v5.35 reciben v6.0 sin breaking changes. El upgrade se ejecuta en tres etapas:

1. **`upgrade_project` automático**: bumpea version + **crea plantilla vacía de `app_market.md` con `status="template-pristine"`** (decisión nueva v6.0 que cambia el patrón v5.29 — ver AC-D005-10). Sin tocar `app_prd.md` ni `app_spec.md`. Devuelve `canonical_docs_created` y hint `discovery_alignment` en el return.
2. **`/app-init --refresh` manual opcional**: para proyectos donde `upgrade_project` no se ejecutó automáticamente (ej. usuarios que descargan v6.0 manualmente sin pasar por el tool MCP). Detecta missing `app_market.md` y propone crearlo desde plantilla.
3. **`/discovery [feature]` manual**: cuando se ejecuta por primera vez en un proyecto, detecta `app_market.md` vacío (template-pristine) → modo bootstrap.

Nueva tool MCP `detect_v60_migration_case(project_path)` análoga a `detect_v529_migration_case`. Devuelve plan estructurado para 8 casos hipotéticos:

| Case | Estado del proyecto | Acción |
|---|---|---|
| 1 | Pre-v5.29 (sin `doc/app/`) | Ejecutar v5.29 migration primero; luego v6.0 |
| 2 | v5.29-v5.35 con `app_prd.md` + `app_spec.md`, sin `app_market.md` | `upgrade_project` crea plantilla pristine. Usuario opt-in para rellenarla vía `/discovery` bootstrap. `discovery.gate_mode=off` por default |
| 3 | Active UC en curso | **Defer** — terminar UC, luego v6.0 (precedente case 7 de v5.29) |
| 4 | Pending feedback bloqueante | **Defer** — resolver feedback, luego v6.0 |
| 5 | Multirepo orchestrator | Aplicar v6.0 al orchestrator; satellites heredan automáticamente |
| 6 | Multirepo satellite | No-op directo — hereda del orchestrator |
| 7 | Fresh-clone post-v6.0 | `/app-init` → bootstrap completo vía `/discovery`. `discovery.enabled=true, gate_mode=warn` por default |
| 8 | Proyecto con `doc/discovery/` manual pre-existente (PoC user, no esperado) | `/app-init --upgrade-zones` para insertar marcadores |

**Defaults por origen del proyecto**:

- **Proyecto upgrade desde v5.x**: `discovery.enabled=false`, `gate_mode=off`. Sin cambio de comportamiento perceptible. `app_market.md` plantilla creada pero ignorada hasta que el usuario invoque `/discovery`.
- **Proyecto fresh post-v6.0**: `discovery.enabled=true`, `gate_mode=warn`. Pedagógico, no bloquea `/prd`.
- **Power users / beta validation explícita**: `discovery.enabled=true, gate_mode=block` opt-in vía `/app-init --enable-discovery-strict`.

---

## 5. Slash command flow specification (detalle)

### 5.1 `/discovery [feature_name]` — flujo completo

**Step 0 — Boot detection**
- Carga `settings.local.json`.
- Invoca `start_discovery(feature_name, project_path, mode="auto")`.
- Determina modo: bootstrap o standard.

**Step 1 — ICP identification (Phase 1)**
- **Si bootstrap**: inicia con definición de ICPs canónicos del producto entero (1-3 ICPs + no-ICPs).
- **Si standard**: muestra ICPs canónicos de `app_market.md` y pregunta cuáles aplican a esta feature (1-3 seleccionables, opción de añadir nuevo).
- Para cada ICP nuevo: sanity check "3 personas concretas".
- Pedagogical inline content per ICP: micro-justificación, ejemplo, anti-pattern.

**Step 2 — JTBD extraction (Phase 2)**
- Para cada ICP seleccionado:
  - Genera draft de 2-3 JTBDs racionales con Claude usando el contexto del feature_name y descripción del problema (D-01 resuelta como opción (a) con override a plantilla fija si user lo pide).
  - Genera draft de 1-2 JTBDs emocionales.
  - User edita, refina, elimina, añade libremente.
- Format canónico enforced: "Cuando [situación], quiero [motivación], para [resultado]".
- Pedagogical content: explica diferencia racional/emocional, da ejemplos del ecosystem, muestra anti-patterns.

**Step 3 — Drift detection (Phase 3a)**
- Compara ICPs y JTBDs declarados vs `app_market.md`.
- Lista elementos nuevos.
- Para cada elemento nuevo, pregunta: feature_creep_rejected | app_market_updated | documented_exception.
- Acción según respuesta.

**Step 4 — Validation gate (Phase 3b)**
- Resumen consolidado de ICPs + JTBDs + drift resolution.
- Pregunta evidence: "¿conversación reciente / datapoint / waiver?"
- Registra en artefacto.

**Step 5 — Output generation**
- Invoca `validate_discovery_completeness(feature_name, project_path)`.
- Genera `icp_jtbd.md` final con verdict.
- Muestra al user: verdict + path al artefacto + next step recomendado (`/prd [feature_name]` si READY, `/discovery [feature_name]` para resumir si INCOMPLETE).

### 5.2 Bootstrap mode (primer `/discovery` en proyecto)

- Detección automática via `app_market.md` vacío / template-pristine.
- Mensaje inicial: "Antes de definir esta feature, definamos para quién es el producto entero. Solo se hace una vez."
- Flujo bootstrap completa los 5 bloques esenciales de `app_market.md`.
- Bloques opcionales (posicionamiento, anti-features) se ofrecen pero pueden saltarse.
- Auto-deriva sección "Exportable copy" de ICPs+JTBDs definidos.
- Al rellenar la primera zona manual, el marcador `status="template-pristine"` se elimina automáticamente.
- Tras completar `app_market.md`, desciende automáticamente al flujo estándar para la feature.
- Tiempo target: ≤45 min producto + ≤30 min feature = ≤75 min total.

---

## 6. Pedagogical layer (especificación)

### 6.1 Per-step micro-justification

Cada paso del flujo viene con un bloque de 2-4 líneas explicando por qué este paso existe y qué riesgo mitiga. Tono: directo, argumentativo, no académico. Ejemplo para Phase 1:

> "Cada feature la usa alguien. Si no sabes quién, vas a tomar mil decisiones (¿móvil o desktop? ¿simple o potente?) sin un norte claro y vas a producir algo técnicamente correcto pero que no encaja con nadie. Vamos a identificar 1-3 ICPs concretos primero."

### 6.2 Inline examples from ecosystem

Cada concepto se introduce con un ejemplo real de uno de los productos embed.build. Catálogo mínimo a incluir en el skill:

- **PaddockManager** (motor sport ops): ICP racing managers, JTBD racional "controlar tiempos vuelta-a-vuelta sin errores manuales", JTBD emocional "sentir control en entornos de alta presión".
- **McProfit** (P&L hospitalería): ICP finance directors de cadenas restauración, JTBD racional "consolidar P&L de múltiples franquicias en <1 día", JTBD emocional "reducir ansiedad de cierre de mes".
- **Futbase** (gestión clubes): ICP club managers amateur/semi-pro, JTBD racional "centralizar comunicación con jugadores", JTBD emocional "sentirse profesional sin tener presupuesto pro".
- **SpecBox Engine** (este producto): ICP-1/2/3 definidos en sección 2.1, JTBDs en 2.3/2.4.

### 6.3 Anti-pattern surfacing

Para cada concepto, mostrar 1 anti-pattern explícito. Ejemplos:

- **Anti-pattern ICP**: "Developers que quieren más productividad" — demasiado vago, no permite priorizar features ni encontrar 3 personas concretas. Mejor: "Software developers solos usando Claude Code construyendo productos con clientes pagando".
- **Anti-pattern JTBD racional**: "Quiero que sea rápido" — no es un JTBD, es un atributo. Mejor: "Cuando despliego a producción, quiero feedback de errores en <30s para hacer rollback antes de que afecte a más usuarios".
- **Anti-pattern JTBD emocional**: "Quiero que se sienta moderno" — vago. Mejor: "Quiero sentir control sobre el proceso, no dependencia ciega del LLM".

### 6.4 Parallel dev/PM language

Mantener jerga PM canónica con traducción técnica en paralelo:
- **ICP** ↔ "user type" / "stakeholder principal"
- **JTBD racional** ↔ "user goal" / "functional intent"
- **JTBD emocional** ↔ "UX intent" / "perceived value"
- **North Star Metric** ↔ "primary success metric" / "telemetría principal"

### 6.5 Progressive onboarding

- **Primera feature en proyecto**: bootstrap mode completo + flujo estándar con todas las micro-justificaciones, ejemplos y anti-patterns expandidos.
- **Features 2-5**: modo pedagogical reducido, solo recordatorios breves de conceptos clave.
- **Feature 6+**: modo conciso, sin explicaciones inline. Usuario puede solicitar modo expanded con `/discovery --explain`.

Implementación via `record_skill_hint` + `get_skill_hint` (sistema existente).

### 6.6 Pedagogical hooks

Cuando `pre-prd-discovery-check` bloquea, mensaje estructurado:

```
⚠️ /prd bloqueado: discovery incompleto para feature <name>

Razones:
- Falta JTBD racional para ICP-2
- Drift sin resolver: ICP "freelancers" no está en app_market.md

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

### 6.7 Post-shipping feedback loop

Comando opcional `/discovery --review <feature_name>` (D-08 resuelta como opción (b): backlog v6.1, NO incluido en v6.0). Cuando se implemente, mostrará:

- ICPs y JTBDs originalmente predichos en discovery.
- AC del PRD taggeados a esos JTBDs.
- Resultado de implementación (passed/failed, healing attempts).
- Prompt al user: "¿Apareció algún ICP o JTBD que no anticipaste? ¿Algún JTBD predicho resultó irrelevante? Esto calibra tu intuición para futuras features."
- Respuesta se guarda en `doc/discovery/<feature_name>/post_shipping_review.md`.

---

## 7. Non-Functional Requirements

### 7.1 Performance
- `/discovery` arranca en ≤2 segundos.
- `validate_discovery_completeness` retorna en ≤500ms.
- Hook `pre-prd-discovery-check` añade ≤300ms al pipeline.
- `start_discovery` idempotente sin race conditions.
- Hook `app-docs-sync-guard.mjs` refactorizado mantiene tiempo de ejecución previo (no debe regresar performance) — medido en CI.

### 7.2 Backwards compatibility
- Proyectos existentes sin `app_market.md` o `doc/discovery/` siguen funcionando.
- `/prd` en proyectos existentes funciona como antes si `discovery.gate_mode=off` (default en upgrade).
- No breaking changes en API de MCP tools existentes (las refactorizaciones preservan signatura externa; `read_app_docs_tool` añade param opcional con default None que reproduce comportamiento previo).
- **`upgrade_project` preserva la invariante "nunca pisar contenido existente"**: solo CREA archivos nuevos (`app_market.md` plantilla pristine en proyectos v5.x). NO modifica `app_prd.md`, `app_spec.md`, ni ningún otro archivo existente. Validado por AC-D005-12.
- El descriptor `templates/canonical_docs.json` se distribuye con el engine; proyectos no necesitan regenerar nada.

### 7.3 Configurability
- Todos los gates configurables via `settings.local.json`.
- Modo pedagogical override via flag CLI.
- Strict evidence opt-in (default false).
- `gate_mode` configurable por proyecto: `off | warn | block`.

### 7.4 Internationalization
- Flujo conversacional, micro-justificaciones, ejemplos y anti-patterns en **español Y inglés**.
- Detección automática del idioma según `settings.local.json` (campo `language`) con override explícito (D-05 resuelta como opción (c): auto-detect con override).
- Artefactos `app_market.md` e `icp_jtbd.md` se generan en el idioma configurado.

### 7.5 Telemetry
- Eventos a `Sala de Máquinas` vía `report_session`:
  - `discovery_started` (feature_name, mode, timestamp)
  - `discovery_completed` (feature_name, verdict, duration_minutes, drift_detected)
  - `discovery_skipped` (feature_name, reason)
  - `qualitative_gate_passed` (feature_name, ac_id, jtbd_id)
  - `canonical_doc_created_by_upgrade` (doc_id, from_version, to_version)
- Métricas agregadas accesibles via dashboard SdM.

---

## 8. Risk table

| ID | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R-01 | PM theater: users rellenan formularios sin pensar | Alta | Alto | Evidence prompt + sanity check "3 personas concretas" + pedagogical content que enseña por contraste |
| R-02 | Scope creep durante la construcción del módulo | Alta | Alto | Cap arquitectural revisado: 4 US, 6 UC, 3 MCP tools nuevos + 5 refactor, 1 hook nuevo + 1 refactor, 1 doc canónico + 1 módulo `registry.py`. Cualquier feature nueva durante el build va a v6.1 |
| R-03 | Backwards compatibility rota en proyectos existentes | Media | Alto | `discovery.gate_mode=off` default en existentes; AC-D005-12 valida regresión 0 sobre fixtures de PaddockManager, McProfit, Futbase; invariante "upgrade_project nunca pisa contenido existente" preservada |
| R-04 | Beta users abandonan por fricción excesiva | Media | Alto | Bootstrap mode tiempo ≤75 min total; flujo estándar ≤30 min; progressive onboarding reduce con cada uso |
| R-05 | Drift detection genera ruido excesivo (false positives) | Media | Medio | Warning agrupado (max 1 alerta de drift por sesión), opción de silenciar tipo de drift específico |
| R-06 | Pedagogical content desigual entre español e inglés | Alta | Medio | QA explícito por idioma antes de release; un beta user nativo inglés (potencial: pedir voluntario en LinkedIn) |
| R-07 | Refactor multi-doc introduce regresión sutil en `app_docs` v5.29 behavior | Media | Alto | Snapshot tests obligatorios (AC-D005-06): matriz `{v5.29, v5.33, v5.35 fixtures} × {verify, repair, hook, app-sync}` debe pasar idéntica antes y después del refactor |
| R-08 | Heterogeneidad de feedback entre 5 beta users dificulta síntesis | Alta | Bajo | Protocolo de feedback estructurado (4 datapoints + 1 cita libre); sync semanal, no continuo |
| R-09 | Bug crítico en hook bloquea pipeline de proyecto productivo | Baja | Alto | `gate_mode=off` default en existentes; hook con fallback graceful (warn instead of block on error); rollback path documentado |
| R-10 | Conflicto con Stitch Design Gate o quality-first-guard existentes | Baja | Medio | Integration tests específicos chequeando orden de hooks; documentación de hook precedence |
| R-11 | `upgrade_project` crea `app_market.md` plantilla en proyecto que el usuario tenía intención de mantener "puro v5.x" | Baja | Bajo | Plantilla `template-pristine` no afecta comportamiento; hook la ignora; usuario puede borrar el archivo si lo desea sin consecuencias. Documentado en CHANGELOG. |
| R-12 | Sincronización `registry.py` → `canonical_docs.json` descriptor se desincroniza por error de developer | Media | Medio | Script de build automatizado (CI failure si desincronizados); test unitario que regenera y compara |

---

## 9. Definition of Done

El módulo v6.0 se considera Done cuando:

**Discovery user-facing (US-D01, US-D02, US-D03)**:
- [ ] Los 3 US de Discovery (D01, D02, D03) tienen sus UC implementados y todos los AC pasando.
- [ ] `start_discovery` y `validate_discovery_completeness` registrados como MCP tools `Specbox-engine:*`.
- [ ] Hook `pre-prd-discovery-check.mjs` funcional, con tests unitarios + integration tests.
- [ ] Skill `.claude/skills/discovery/SKILL.md` completo en español E inglés.
- [ ] `/prd`, `/plan`, `/implement` modificados con la integración acordada.
- [ ] HTML Evidence Report incluye sección "Discovery alignment".

**Multi-doc foundation (US-D04)**:
- [ ] `server/app_docs/registry.py` creado con `CANONICAL_DOCS` list completa (3 entries: app_prd, app_spec, app_market).
- [ ] `templates/canonical_docs.json` descriptor regenerado automáticamente desde Python source; script de build verificado en CI.
- [ ] `sync.py`, `app-docs-sync-guard.mjs` refactorizados a iteración sobre registro. Constantes `PRD_PATH`/`SPEC_PATH` eliminadas.
- [ ] `read_app_docs_tool`, `apply_app_docs_sync`, `record_app_docs_signature`, `detect_app_docs_drift`, `verify_app_docs` refactorizados a iteración sobre registro, signatura externa preservada.
- [ ] `upgrade_project` extendido para crear plantillas de docs canónicos con `introduced_in > engine_version_at_onboard`. AC-D005-10/11/12 verificados.
- [ ] `meta.json` field `engine_version_at_onboard` migrado: capturado en `onboard_project`, preservado en `upgrade_project`, marcado `"unknown"` con política conservadora para proyectos v5.x preexistentes (AC-D005-05).
- [ ] Marcador `status="template-pristine"` implementado en parser de zonas y respetado por hook (AC-D005-13).
- [ ] Tool MCP `detect_v60_migration_case(project_path)` creado con los 8 casos de §4.8.
- [ ] Documento `doc/decisions/multi_doc_registry.md` escrito (AC-D005-09).

**`app_market.md` introduction (US-D04 → UC-D006)**:
- [ ] Plantilla `templates/app_market.md.template` creada con 8 zonas (AC-D006-01).
- [ ] Entry añadida en `CANONICAL_DOCS` para `app_market` (AC-D006-02).
- [ ] Diff de PR de UC-D006 verifica el cap: 1 archivo nuevo + 1 entry + 0 cambios en lógica (AC-D006-03).
- [ ] Tools existentes (`read_app_docs_tool`, `apply_app_docs_sync`, etc.) operan sobre `app_market.md` sin cambios adicionales — la prueba es que UC-D006 no requiere tocarlos.

**Backwards compatibility**:
- [ ] Tests de regresión: matriz `{proyectos fixture v5.29, v5.33, v5.35} × {verify, repair, hook, /app-sync}` pasa sin cambio de comportamiento observable (AC-D005-06).
- [ ] Backwards compatibility validada contra fixtures de PaddockManager, McProfit, Futbase: cada uno simula upgrade v5.x → v6.0 y ejecuta su próximo `/prd` sin breaking changes con `discovery.gate_mode=off`.
- [ ] Test fixture AC-D005-12: "proyecto v5.35 con `app_prd.md` modificado manualmente recibe upgrade a v6.0" verifica byte-por-byte que `app_prd.md` y `app_spec.md` quedan intactos.

**Documentación y release**:
- [ ] Documentación en `doc/specifications/discovery_module.md` completa.
- [ ] README.md de SpecBox Engine actualizado con sección "v6.0: Product Discovery + Multi-doc Foundation".
- [ ] CHANGELOG.md con entries para Discovery (US-D01..D03) y Foundation (US-D04).
- [ ] CLAUDE.md actualizado: versión actual `6.0.0`, codename `"Discovery Foundations"`, sección "Discovery Module" con explicación.
- [ ] Telemetría a Sala de Máquinas operativa (incluyendo evento `canonical_doc_created_by_upgrade`).
- [ ] Tests E2E Playwright cubren happy path de `/discovery → /prd → /plan → /implement`.
- [ ] `get_engine_version` retorna `"6.0.0"` con codename "Discovery Foundations".
- [ ] Dogfooding propio: SpecBox v6.0 se desarrolla aplicando `/discovery` sobre cada US del propio módulo (este PRD ya es el primer paso).
- [ ] Audit `run_quality_audit` pasa con score ISO 25010 ≥ baseline v5.35.x.
- [ ] Release tagged como `v6.0.0` directo (sin pre-release rc/beta — D-07 resuelta como release directo).

---

## 10. Post-release metrics (a medir durante las 4 semanas de validación con beta users)

### Métricas cuantitativas (Discovery feature)

- **NSM**: porcentaje de features Done con discovery + AC taggeados a JTBD (target: ≥60% en semana 4).
- **Tiempo medio en `/discovery`** por feature post-bootstrap (target: ≤30 min, mediana).
- **Tasa de features descartadas en `/discovery`** (informativo, no target; valor 0% sugiere gate laxo, valor >50% sugiere problema en `/discovery` inicial).
- **Drift events resueltos**: % de drift detections que terminan en (a) feature_creep_rejected, (b) app_market_updated, (c) documented_exception. Distribución sana esperada: ~20% / ~50% / ~30%.
- **Verdict rate**: % de `/discovery` que terminan con `READY_FOR_PRD` (target: ≥80% en semana 4; <50% indica friction excesiva en gate).

### Métricas técnicas (Multi-doc Foundation)

- **Code metrics**: líneas de código en `server/app_docs/sync.py` antes/después del refactor (esperado: reducción ≥30% por de-duplicación de ramas hardcoded).
- **Cyclomatic complexity** medida con `lizard` sobre funciones del módulo `app_docs/` (esperado: reducción medible vs baseline v5.35).
- **Cero regresiones en proyectos v5.x**: validado contra fixtures de PaddockManager / McProfit / Futbase (test suite específico en CI).
- **Tiempo de ejecución del hook `app-docs-sync-guard.mjs`**: no debe regresar — medido en CI con fixture project.

### Métricas cualitativas (test pedagógico, beta users)

Cada beta user, al final de semana 4, responde:
- ¿Puedes explicar con tus palabras qué es un ICP?
- ¿Puedes explicar la diferencia entre JTBD racional y emocional?
- ¿Te ayudó `/discovery` a descartar o re-enfocar alguna feature antes de gastar tiempo en PRD?
- ¿Sentiste que el módulo añadía valor o burocracia?

### Safety net criterion

- Si ≥3 de los 5 beta users responden negativamente a la pregunta 4 al final de semana 4 → marcar Discovery feature como "needs UX redesign", abrir issue para reevaluación de la capa pedagógica. **La fundación multi-doc (US-D04) NO se rollbackea** — es base arquitectural permanente independientemente del éxito de Discovery user-facing.

---

## 11. Open decisions (resueltas — registro para `/plan`)

Las 8 decisiones originales más 3 nuevas introducidas por US-D04. Todas resueltas con su rationale; `/plan` puede arrancar sin volver a abrirlas.

| ID | Decisión | Resolución | Rationale |
|---|---|---|---|
| D-01 | ¿Cómo se generan los drafts iniciales de JTBDs en Phase 2? | (a) Claude usando contexto feature + descripción problema, con override (b) plantilla fija si user lo solicita | Default LLM-generated es más útil; override a plantilla para casos donde el usuario prefiere control total |
| D-02 | ¿`/discovery` debe ser invocable sin feature_name? | (a) No, siempre requiere argumento | Simplicidad; reduce ambigüedad |
| D-03 | ¿Drift detection es feature-only o también detecta drift dentro de `app_market.md` over time? | (a) Solo feature vs market en v6.0; (b) historical app_market evolution → backlog v6.1 | Respeta cap; añadible si beta lo pide |
| D-04 | ¿`qualitative gate` para JTBDs emocionales es prompt estructurado o flow conversacional? | (a) Prompt con 3 preguntas fijas | Predictibilidad; mide más fácil; reduce variability del flujo de implementación |
| D-05 | ¿Idioma del flujo conversacional se elige por settings o auto-detect? | (c) Auto-detect con override en `settings.local.json` field `language` | Best of both worlds |
| D-06 | ¿`app_market.md` se firma/versiona como `app_prd.md`? | (a) Sí, mismo mecanismo | Consistencia con `record_app_docs_signature` extendido vía registry |
| D-07 | ¿Beta users obtienen acceso al módulo via flag, branch o release público? | **Release público v6.0.0 directo, sin pre-release** | Decisión del usuario; valida en stable con 5 beta + dogfood propio en McProfit/Futbase |
| D-08 | ¿Comando `/discovery --review` se incluye en v6.0 o backlog v6.1? | (b) Backlog v6.1 | Respeta cap arquitectural; añadir si beta lo pide explícitamente |
| **D-09** | ¿La refactorización multi-doc (US-D04) se mergea en una PR atómica o se descompone en sub-PRs por archivo afectado? | (a) PR atómica con feature flag interno temporal | Refactor puro de bajo nivel: revisar de una pieza es más seguro que dual-code-path; feature flag por si hay que rollback parcial |
| **D-10** | ¿`CANONICAL_DOCS` se define en Python source-of-truth con JSON generado, o JSON source-of-truth con lectores en ambos lenguajes? | (b) Python `registry.py` source-of-truth + JSON `templates/canonical_docs.json` regenerado por script de build (CI verifica sync) | Mantiene el patrón existente (Python como SoT) y permite al hook Node.js leer sin parsear Python; falla rápida si desincronizados |
| **D-11** | ¿`engine_version_at_onboard` para proyectos v5.x preexistentes se infiere o se marca como `"unknown"`? | (b) `"unknown"` siempre + política conservadora documentada | Más seguro; no pretende saber lo que no sabe; hook solo verifica docs con `introduced_in <= 5.29.0` cuando es unknown |

**Sin decisiones pendientes que bloqueen `/plan`.**

---

## 12. Out of scope (v6.0 explícito)

Las siguientes capacidades NO están en v6.0 y se evaluarán para v6.x posteriores basado en feedback:

- Generación de scripts de entrevista a usuarios (estilo Mom Test).
- Opportunity Solution Tree visualization.
- Importación de discovery desde herramientas externas (ChatPRD, Notion, etc.).
- Discovery a nivel proyecto inicial (más allá de bootstrap del primer feature).
- Multi-language por feature (solo language del proyecto entero).
- AI-generated competitive analysis.
- Roadmap building multi-feature basado en priorización JTBD.
- Persona generation detallado (foto, demographics).
- `/discovery --review` post-shipping feedback loop (backlog v6.1 — D-08).
- Historical drift detection sobre `app_market.md` over time (backlog v6.1 — D-03).
- Migración automática de proyectos v5.x a `discovery.gate_mode=warn` o `block` (queda opt-in vía `/app-init --enable-discovery-strict`).

---

## 13. Versioning and rollout

### Version
- `get_engine_version` → `"6.0.0"`, codename `"Discovery Foundations"`.
- **Stable directo, sin pre-release tag rc/beta** (D-07 resuelta).
- ENGINE_VERSION.yaml, pyproject.toml, CLAUDE.md, README.md, CHANGELOG.md alineados (validado por pre-commit hook `version-consistency-check.mjs`).

### Rollout phases
1. **Internal dogfood** (semana 0): Jesús desarrolla v6.0 aplicando `/discovery` sobre cada US del módulo (meta-dogfood). Este PRD es el primer artefacto.
2. **Release público v6.0.0** (al cierre del implement pipeline): tag git `v6.0.0`, push a main, anuncio LinkedIn.
3. **Validation period** (semanas 1-4 post-release): sync con Valentín, Nani, Julio, Ramón vía DM. Patches v6.0.1, v6.0.2 según necesidad (sin breaking changes).
4. **Promotion to v6.1**: tras 4 semanas, si safety net criterion no se activa para Discovery user-facing → promover features de backlog (D-03 historical drift, D-08 `/discovery --review`). Si se activa → mantener v6.0.x y abrir issue de UX redesign de Discovery. **Multi-doc Foundation queda en pie en cualquier caso.**

### Communication
- LinkedIn announcement al release (semana 0): "SpecBox v6.0: Product Discovery + Multi-doc Foundation". Mensaje transparente sobre fase de validación con 5 power users y solicitud de feedback público.
- Final de validation (semana 4): post de retrospectiva con métricas reales (NSM, tiempo medio, % features descartadas en discovery, regresión 0 multi-doc, citas de beta users).

---

## 14. Beta users assignment (validación post-release)

| Beta user | Perfil ICP | Proyecto donde dogfoodear | Features esperadas (mínimo) | Foco de feedback |
|---|---|---|---|---|
| Jesús (tú) | ICP-1 | McProfit + Futbase | ≥2 features cada uno | Coherencia con resto del engine, performance, edge cases, **validación de regresión 0 en multi-doc**: ejecutar `/app-sync --check` antes y después del upgrade, verificar comportamiento idéntico |
| Valentín Ayesa | ICP-2 | Un flow propio (n8n-adjacent o herramienta propia) | ≥1 feature completa | Eficiencia, monetización, encaje con perfil n8n |
| Nani | ICP-3 | Su primera o segunda app | ≥1 feature completa | Test pedagógico crítico — ¿entiende los conceptos sin formación previa? |
| Julio Fariñas | ICP-1 | Tempo si encaja, o sub-feature | ≥1 feature | Integración con workflow existente; user early adopter |
| Ramón Iborra | ICP-1/2 híbrido | Una landing o feature marketing | ≥1 feature | Validar si `app_market.md` es exportable a copy comercial |

Cobertura objetivo: los 3 ICPs cubiertos por al menos 1 beta cada uno.

---

## 15. Apéndice — checklist `/plan` ready

Para que SpecBox pueda invocar `/plan` directamente sobre este PRD sin volver con preguntas mayores:

- ✅ **4 US** definidas con descripción, ICPs, JTBDs y UCs (US-D01..D04)
- ✅ **6 UC** detallados (UC-D001..D006) con AC mapeados a JTBDs específicos (tagging completo)
- ✅ Architecture spec con tools (3 nuevos + 5 refactor), hooks (1 nuevo + 1 refactor), artefactos (1 doc canónico + 1 módulo registry + 1 descriptor JSON) y configuración
- ✅ Slash command flows detallados (`/discovery`, `/prd`, `/plan`, `/implement`, `/app-init`, `/app-sync`)
- ✅ Pedagogical layer especificada
- ✅ NFRs incluyendo performance, compatibility, i18n, telemetría
- ✅ Risk table con 12 riesgos y mitigaciones (incluye R-11 plantilla pristine, R-12 sync registry↔JSON)
- ✅ Definition of Done explícito con secciones separadas para Discovery / Foundation / Backwards compat / Docs+Release
- ✅ Post-release metrics con métricas técnicas separadas (multi-doc) y safety net criterion solo aplicable a Discovery user-facing
- ✅ **11 Open decisions resueltas** (8 originales + D-09/D-10/D-11 nuevas)
- ✅ Out of scope explícito
- ✅ Versioning y rollout plan: **v6.0.0 stable directo, sin pre-release**
- ✅ Beta users assignment con foco específico de cada uno (incluye validación regresión multi-doc en Jesús)
- ✅ **§4.8 Upgrade path** con 8 casos y defaults por origen del proyecto

**Sin decisiones pendientes que bloqueen `/plan`. PRD listo para consumo.**

---

**Fin del PRD v6.0.0 — Discovery Foundations**

*Este PRD fue construido aplicando el propio módulo Discovery sobre sí mismo. La sección 2 es su `app_market.md`, las secciones 3.x son su `icp_jtbd.md` consolidado, y cada AC está taggeado a un JTBD. Esta es la primera prueba de que el modelo es operacionalizable: si funcionó para definir el propio módulo, debería funcionar para features de cualquier producto que use SpecBox.*

*Discovery viene para quedarse. La fundación arquitectural multi-doc (US-D04) garantiza que v6.x+ podrá añadir más documentos canónicos (`app_research.md`, `app_metrics.md`, lo que sea) sin refactorizar de nuevo.*
