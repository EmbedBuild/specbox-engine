# Hallazgo para v6.9.2 — el transporte de `source_content` no escala a sources reales

> Encontrado en dogfooding el 2026-06-02, **validando v6.9.1 "Atomic Switch"** sobre un
> proyecto real (`specbox_cloud`, el panel). La **lógica** del switch-backend funcionó; el
> **transporte** se bloqueó. Este es un gap de diseño de v6.9.1, no un fallo de uso.

## Qué funcionó (v6.9.1 cumplió en esto)

Migrando freeform→native el panel `specbox_cloud`, el skill `/switch-backend`:
- Leyó el source **del cliente** (no del filesystem del servidor) — el bug de path de UC-810
  está cerrado. ✅
- Hizo preview antes de escribir, **detectó que el `index.json` del source estaba driftado**
  (totals 88 UC vs 84 en disco, US-12/US-13 y UC-1301..1304 en disco pero no en el array,
  UC-1001..1005 declarados sin fichero) y **se paró** en vez de migrar basura. ✅
- Tras reconciliar (13 US / 89 UC / 466 AC), confirmó que los **estados se preservan por UC**
  (85 done / 4 backlog) — el G11 resuelto. ✅

## Qué falló — el gap

Al ir al dry-run real, el skill no pudo continuar: **`switch_project_backend` con
`source_type='freeform'` exige `source_content` como string, y el `items.json` reconciliado
son 133 KB / 568 ítems.** Un agente no puede transcribir 133 KB dentro del parámetro de una
tool de forma fiable — riesgo de truncar/corromper en silencio, que es justo el fallo que los
gates quieren evitar. El skill, correctamente, **se negó a pasar un blob no verificable**.

### Causa raíz (confirmada en código)
- MCP es **siempre remoto** desde v6.7.0 (modo local eliminado, sin fallback air-gapped).
- `resolve_source_backend()` (`server/tools/migration.py`) deja **`source_content` (string)
  como ÚNICA vía** de transporte del source freeform al servidor. No hay: lectura de path en
  disco del server, endpoint de upload, chunking, streaming, ni server-side fetch.
- Los tests (`tests/test_backend_switch_native.py`) usan **fixtures pequeñas generadas en
  memoria** (`CLIENT_11_88 = _items_json(...)`). **Ningún test pasa un items.json grande por
  el transporte real.** Por eso el test pasa y la realidad no.

## Por qué importa

Es el **modo por defecto** del producto: cliente con su proyecto en local + MCP remoto +
proyecto de tamaño real. Cualquier cliente que intente "subir mi proyecto a SpecBox Cloud"
con un board no-trivial se choca con esto. La feature está validada en lógica pero
**inutilizable end-to-end para proyectos reales** hasta resolver el transporte.

## Propuesta para v6.9.2 (a refinar en discovery)

Un transporte para sources grandes que **preserve la atomicidad** del switch:
- **Opción A — staging/upload**: el cliente sube el `items.json` a un endpoint/staging
  (o lo escribe el server-side fetch desde una URL firmada), el switch lo referencia por id.
- **Opción B — chunked con reensamblado server-side**: el cliente envía N trozos que el
  servidor reensambla y valida (hash) **antes** de empezar la operación atómica, de modo que
  el switch sigue siendo todo-o-nada (el chunking es solo del transporte, no de la migración).
- **Opción C — compresión**: gzip+base64 del `items.json` para subir el techo práctico
  (paliativo, no cura el límite de fondo).
- En todos los casos: **pre-flight de tamaño** + verificación de integridad (hash/conteo)
  antes de escribir, y mensaje claro si el source excede el límite del transporte elegido.

## Reproducción / datos de no-regresión

- Proyecto: `specbox_cloud` (panel), tracking freeform en `doc/tracking/` (133 KB items.json,
  568 ítems: 13 US / 89 UC / 466 AC, 85 done / 4 backlog).
- BD Cloud destino (`EmbedBuild/specbox_cloud`) **vacía a propósito** (backup en el repo del
  panel: `.quality/dogfood-backup/native-project-backup-pre-delete.json`).
- Un transporte correcto debe poder mover esos 133 KB y que el dry-run reporte **13 US / 89
  UC del cliente**, sin transcripción manual.

> Sugerencia: añadir un test de transporte con un items.json grande (≥100 KB) que cruce el
> camino real cliente→servidor, no una fixture en memoria. Si ese test no existe, el gap
> reaparecerá.
