# Discovery: specbox_connectivity_ux

**Discovery ID**: disc-9d5fd2dc7146
**Created**: 2026-05-31
**Status**: READY_FOR_PRD
**Mode**: standard
**Source of inheritance**: doc/app/app_market.md

## Problema

El PR #82 (v6.7.0 "Zero-Friction Onboarding", 2026-05-28) eliminó Python del
path del cliente **eliminando el modo Local del MCP** en la extensión VSCode
(`vscode-extension/src/mcp.ts::configureSpecbox` ahora solo configura el endpoint
remoto vía `buildRemoteServerConfig()`). Esto produjo dos daños encadenados:

1. **Regresión funcional en FreeForm.** El MCP remoto corre en el VPS del owner
   y no puede tocar el filesystem del cliente (`doc/tracking/items.json`). Las
   tools FreeForm (`add_uc`, `mark_ac`, `find_next_uc`, `import_spec`) fallan o
   devuelven datos vacíos. Clientes que usan FreeForm — el backend más usado por
   los devs solo/locales — reportan tras actualizar mensajes tipo *"esto no
   existe / esto no lo puedo hacer ahora"*. `/audit` (8 analyzers que escanean
   código local) está igual de roto en remoto desde v6.0.1.

2. **Actualización ciega y no pedagógica.** El mecanismo de actualización actual
   (`vscode-extension/src/updater.ts`) solo actualiza el **binario** de la
   extensión comparando versión contra `ENGINE_VERSION.yaml`. No detecta
   configuraciones obsoletas, no migra `settings.json` ni el estado del
   proyecto, y no explica qué cambió. Un cliente FreeForm+Local que pulsó
   "Update Now" se quedó con su `settings.json` apuntando a un modo Python ya
   inexistente y descubrió la rotura por errores crípticos, no por un proceso
   que lo acompañara.

**Diagnóstico raíz**: se acoplaron tres ejes que debían ser independientes —
(1) runtime del cliente [Python sí/no], (2) transporte del MCP [local/remoto],
(3) ubicación del estado [filesystem/cloud/Supabase]. Eliminar Python (eje 1)
era correcto y deseable; el error fue **matarlo acoplándolo a la eliminación del
transporte local (eje 2)**, dejando el estado-en-filesystem (eje 3, FreeForm +
audit) inalcanzable.

Además, el PR violó una **decisión canónica registrada** en
`doc/app/app_spec.md` ("FreeForm requiere MCP local stdio") pero el drift gate
de `/discovery` la declaró `no_drift` porque solo valida contra
`app_market.md`, nunca contra `app_spec.md § decisiones canónicas`.

Esta feature reenfoca la arquitectura de conectividad cliente/servidor para
(a) cerrar la regresión, (b) hacer la actualización robusta y pedagógica, y
(c) cerrar el agujero de gobernanza que dejó pasar el cambio breaking.

## ICPs involucrados

Heredados de `doc/app/app_market.md` (sin ICPs nuevos):

- **ICP-2: Dev solo con Claude Code que adopta SpecBox** (primario). Es el perfil
  más golpeado: usa FreeForm local, actualizó vía extensión y se encontró el
  tracking roto sin aviso. Paradoja: la misma feature (zero-python) que buscaba
  reducirle fricción de entrada le rompió la operación diaria.
- **ICP-1: Owner-operator (JPS, dogfooding)** (primario). Mantiene el MCP remoto
  gratuito y recibe los tickets de soporte. Necesita una arquitectura unificada
  (un solo transporte) que reduzca su superficie de mantenimiento, y un proceso
  de actualización que no genere incidencias.
- **ICP-3: Equipo/agencia con reporting a cliente** (secundario). No sufre la
  regresión (Trello/Plane viven en cloud y el remoto los opera bien), pero debe
  vivir la actualización sin ruido — su caso es "sin cambios para ti".

No-ICP relevante: **usuarios air-gapped que requieran operar sin conexión al
remoto**. Decisión de producto explícita (ver Drift): el escenario offline NO
existe en SpecBox porque Claude Code exige conexión a internet — sin red no hay
agente que orqueste nada. Por tanto no se diseña un fallback offline.

## JTBDs racionales

### Transporte y estado (cierre de la regresión)

- **JR-FCUX.1 [ICP-2]**: Cuando trackeo mi proyecto con FreeForm en local,
  quiero que las tools de tracking lean y escriban mi `doc/tracking/` real sin
  instalar Python ni un MCP local, para tener trazabilidad US→UC→AC sin pagar
  el coste de runtime que zero-python prometió eliminar.
- **JR-FCUX.2 [ICP-2]**: Cuando configuro los servidores MCP en el onboarding,
  quiero que FreeForm sea una opción operativa de primera clase (no solo
  Native/Trello), para elegir el backend ligero local sin que me deje el
  tracking inservible.
- **JR-FCUX.3 [ICP-1]**: Cuando mantengo el engine, quiero un único transporte
  (MCP remoto) compartido por todos los backends, donde lo único que cambie sea
  dónde vive el estado (filesystem vía bridge / cloud / Supabase), para reducir
  la superficie de debugging y soporte a una sola ruta.
- **JR-FCUX.4 [ICP-2]**: Cuando uso una tool que necesita mis archivos locales
  (tracking, evidencia, audit), quiero que el cliente haga el I/O con las tools
  nativas de Claude Code (Node) y el server solo procese contenido, para que la
  misma operación funcione idéntica en local, remoto y cloud.

### Actualización robusta y pedagógica

- **JR-FCUX.5 [ICP-2, ICP-3]**: Cuando actualizo SpecBox vía la extensión,
  quiero que detecte si mi configuración quedó obsoleta y la migre
  automáticamente (con backup), para no quedarme con un `settings.json`
  apuntando a algo que ya no existe.
- **JR-FCUX.6 [ICP-2, ICP-3]**: Cuando termina una actualización, quiero un
  resumen claro de qué cambió, qué se migró por mí y qué — si algo — debo hacer,
  para entender el impacto en lugar de descubrirlo por errores crípticos.
- **JR-FCUX.7 [ICP-1]**: Cuando libero una versión con cambios breaking, quiero
  que la inteligencia de migración viva en un solo sitio reutilizable (server,
  reusando `upgrade_project`/`detect_*_migration_case`) y que la extensión solo
  detecte la config local y orqueste, para no duplicar el conocimiento de
  migración entre cliente y server.

### Gobernanza (causa-raíz)

- **JR-FCUX.8 [ICP-1]**: Cuando una feature pasa por `/discovery`, quiero que el
  drift gate valide también contra `app_spec.md § decisiones canónicas` (no solo
  `app_market.md`), para que un cambio que contradiga una decisión registrada no
  pueda declararse `no_drift` y colarse a producción.

## JTBDs emocionales

- **JE-FCUX.1 [ICP-2]**: Sentir que actualizar SpecBox es seguro — confianza de
  que pulsar "Update" no va a romper mi trabajo en curso, porque el proceso me
  protege y me explica. (Deriva de JE-G.1 — nada se pierde — y JE-G.3 — la cara
  visible refleja la disciplina interna.)
- **JE-FCUX.2 [ICP-2]**: Sentir que FreeForm es un destino legítimo y permanente,
  no un modo de segunda que se rompe en cada release, para confiar en él como mi
  forma de trabajar solo/local a largo plazo. (Deriva de JE-G.2.)
- **JE-FCUX.3 [ICP-1]**: Confianza de que la arquitectura es coherente consigo
  misma — que ninguna decisión canónica puede ser violada silenciosamente por un
  gate ciego. La disciplina interna del engine se aplica también al propio engine.
  (Deriva de JE-G.3.)

## Validation evidence

- **[c] Conversación con usuario real**: el owner recibió reportes directos de
  varios clientes (perfil ICP-2, usando FreeForm y algunos Trello) que tras
  actualizar a v6.7.0 obtienen mensajes tipo "esto no existe / esto no lo puedo
  hacer ahora". Esta feature responde a ese feedback concreto y reciente
  (semana del 2026-05-28).
- **[d] Datapoint interno**: el incidente es trazable en git — PR #82 eliminó
  `configureSpecbox` modo Local; `app_spec.md` L70 conserva la decisión canónica
  contradicha; `updater.ts` no contiene lógica de migración de config/estado.
- **Antecedente**: el mismo updater ya causó un incidente bloqueante en v6.6.2
  (extensión atascada en "Activating…") — señal de que el mecanismo de
  actualización es un punto frágil recurrente, no un fallo aislado.

## Drift from app_market

- **Nuevos ICPs introducidos**: ninguno. Hereda ICP-1, ICP-2, ICP-3.
- **Nuevos JTBDs de producto**: ninguno. Los JTBDs de feature (JR-FCUX.*,
  JE-FCUX.*) derivan de JR-G.* y JE-G.* existentes.
- **Decisión canónica afectada (`app_spec.md § decisiones canónicas`)**: esta
  feature **revisa y sustituye** la decisión "FreeForm requiere MCP local
  (stdio)" por una nueva: *"El MCP server nunca toca un filesystem ajeno; el
  estado del cliente (FreeForm, evidencia, audit) entra/sale por content-passing
  vía el bridge Node; el estado cloud (Trello/Plane/Native) lo opera el server
  directamente contra su API. Transporte único: MCP remoto, online-first."*

- **Resolución**: `documented_exception`

  **Justificación**: el drift es deliberado y necesario, no feature creep. (1) La
  decisión canónica original asumía que filesystem-local exigía transporte-local;
  el MCP Path Contract (v6.0.1) ya demostró que content-passing rompe ese
  acople, haciendo la premisa obsoleta. (2) El escenario offline que justificaba
  el modo local no existe en un sistema agéntico que depende de Claude Code (que
  exige red). (3) Mantener un transporte local empaquetado (arquetipo B
  evaluado) sería resolver un problema inexistente, el mismo error que el
  subsistema de cuota de Stitch eliminado en v6.4.0. La nueva decisión unifica la
  arquitectura: Native (Supabase/SpecBoxCloud) y FreeForm comparten transporte y
  solo difieren en dónde vive el estado. El PRD debe registrar esta sustitución
  en `app_spec.md` vía la zona `canonical_decisions` (hybrid, append-only).

## Verdict

**READY_FOR_PRD**

ICPs heredados sin drift de mercado; JTBDs racionales y emocionales con formato
canónico cubriendo los tres frentes (transporte, actualización, gobernanza);
validation evidence basada en conversación real con usuarios ICP-2 + traza git;
drift resuelto como `documented_exception` con justificación que sustituye una
decisión canónica obsoleta.

---

> Next step: `/prd specbox_connectivity_ux`
