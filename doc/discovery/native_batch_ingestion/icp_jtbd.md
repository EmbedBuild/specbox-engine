# Discovery: native_batch_ingestion

**Discovery ID**: disc-9409945c825b
**Created**: 2026-06-02T21:19:34.581323+00:00
**Status**: READY_FOR_PRD
**Mode**: standard
**Source of inheritance**: doc/app/app_market.md @ 8ed0f1f8ed8ba005

## Problema (framing)

Migrar un proyecto freeform real a Native (SpecBox Cloud) se bloquea en el
**transporte**: `switch_project_backend` con `source_type='freeform'` exige el
`items.json` completo como **un único string** (`source_content`), y un board no
trivial (133 KB / 568 ítems) no cabe fiablemente en un parámetro de tool sin riesgo
de truncado/corrupción silenciosa. El MCP es **siempre remoto** desde v6.7.0 (no ve
el filesystem del cliente). La **lógica** del switch v6.9.1 funciona (lee el source
del cliente, detecta drift, preserva estados); el **transporte** no escala a sources
reales. Es el **modo por defecto** del producto: cliente local + MCP remoto + board
de tamaño real.

La feature resuelve el transporte como **ingesta por lotes server-side**: el cliente
envía los items en chunks pequeños y verificables, el servidor los acumula en una
zona de staging y los ingesta en **una transacción atómica** (commit al final),
reutilizando los INSERT item-por-item que el engine ya tiene. El chunking es solo del
transporte; la escritura sigue siendo todo-o-nada.

## ICPs involucrados

### ICP-1: Owner-operator del engine (JPS, dogfooding)
Heredado de `app_market.md` (canónico). Es quien encontró el gap migrando
`specbox_cloud` (133 KB, 568 ítems) el 2026-06-02 validando v6.9.1, y quien necesita
completar esa migración a Native sin transcripción manual de blobs.

### ICP-3: Equipo/agencia con reporting a cliente
Heredado de `app_market.md` (tentative). Cualquier equipo que quiera "subir mi
proyecto a SpecBox Cloud" para colaboración multi-dev con un board no-trivial se choca
con este gap. El Native Backend es precisamente el habilitador de colaboración
multi-dev que este ICP espera; sin transporte de sources reales, Native queda
inutilizable end-to-end para ellos.

## JTBDs racionales

- **JR-FNBI.1 [ICP-1, ICP-3]**: Cuando migro mi proyecto freeform a Native Cloud,
  quiero subir un `items.json` de tamaño real (≥100 KB / cientos de ítems) sin
  transcribirlo a mano ni arriesgar corrupción silenciosa en el transporte, para que
  el board en Postgres sea byte-fiel al source del cliente.
- **JR-FNBI.2 [ICP-1, ICP-3]**: Cuando el transporte fragmenta el source en lotes,
  quiero que la escritura a Postgres siga siendo todo-o-nada (commit diferido en una
  transacción, rollback total ante fallo a mitad), para no quedarme con un board
  parcialmente migrado e incoherente.
- **JR-FNBI.3 [ICP-1, ICP-3]**: Cuando inicio una sesión de migración por lotes,
  quiero declarar cuántos ítems voy a enviar y que el servidor verifique integridad
  por chunk (hash/conteo) y global (¿llegaron los N esperados?) **antes** de escribir
  nada, para que un transporte incompleto o corrupto se detecte y aborte en preflight,
  no a mitad de la escritura.
- **JR-FNBI.4 [ICP-1, ICP-3]**: Cuando una sesión de migración se corta a medias
  (chunks enviados sin commit), quiero que el staging se descarte limpiamente y poder
  reiniciar desde cero, para no reconciliar estado parcial ni colisionar con el
  `project_id` destino.

## JTBDs emocionales

- **JE-FNBI.1 [ICP-1, ICP-3]**: Confianza de que lo que sube es exactamente lo que
  llega — no transcripciones manuales de 133 KB ni blobs que el agente "espera que no
  se truncaron". El preflight de conteo + hash convierte la ansiedad de "¿se subió
  todo bien?" en una verificación observable antes de tocar la BD.
- **JE-FNBI.2 [ICP-1, ICP-3]**: Sentir que migrar a Cloud es una operación segura y
  reversible, no un salto al vacío. Si algo falla a mitad, el rollback total devuelve
  el destino al estado previo — no hay "medio proyecto migrado" que limpiar a mano.

## Validation evidence

**Datapoint de dogfooding real (2026-06-02)**: el gap se encontró migrando
`specbox_cloud` (el panel) freeform→native validando v6.9.1 "Atomic Switch" sobre un
board real (133 KB / 568 ítems: 13 US / 89 UC / 466 AC, 85 done / 4 backlog). El
skill `/switch-backend` leyó el source del cliente, detectó drift en el `index.json`
(totals 88 UC vs 84 en disco), se paró antes de migrar basura, y tras reconciliar
confirmó que los estados se preservan por UC. Al ir al dry-run real, el skill **se
negó correctamente** a pasar el blob de 133 KB no verificable dentro de un parámetro
de tool. Documentado en `HALLAZGO-v6.9.2-transporte-source-grande.md`. No es
hipótesis: es un bloqueo reproducible con datos concretos y backup de no-regresión en
`.quality/dogfood-backup/native-project-backup-pre-delete.json` (repo del panel).

## Drift from app_market

- **Nuevos ICPs introducidos**: ninguno. ICP-1 e ICP-3 se heredan de `app_market.md`.
- **Nuevos JTBDs introducidos**: JR-FNBI.1..4 y JE-FNBI.1..2 son específicos de la
  feature (no globales); concretan JR-G.1 (trazabilidad US→UC→AC, ahora cruzando el
  transporte) y JE-G.1 (confianza de que nada se pierde, ahora aplicada al transporte
  de migración). No contradicen ningún ICP ni JTBD global.
- **Resolución**: `no_drift`

## Verdict

**READY_FOR_PRD**

Todas las secciones completas: ICPs heredados sin drift, 4 JTBDs racionales y 2
emocionales en formato canónico, validation evidence con datapoint de dogfooding real,
drift resuelto como `no_drift`.

Next step: `/prd native_batch_ingestion`
