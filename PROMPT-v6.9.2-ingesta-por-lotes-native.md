# Prompt v6.9.2 — Migración a native como INGESTA POR LOTES server-side

> Dispara esto desde una sesión de Claude **dentro del repo `specbox-engine`**.
> Cierra el gap de transporte de v6.9.1 (ver `HALLAZGO-v6.9.2-transporte-source-grande.md`).
> Sigue el pipeline del engine: `/discovery` → `/prd` → `/plan` → `/implement`.

---

## Contexto (dogfooding 2026-06-02, validando v6.9.1 "Atomic Switch")

Migrando un proyecto real freeform→native (`specbox_cloud`, 133 KB / 568 ítems: 13 US / 89 UC /
466 AC), la **lógica** del switch funcionó (leyó el source del cliente, detectó drift y se paró,
preservó estados). Pero el **transporte** se bloqueó: `switch_project_backend` con
`source_type='freeform'` exige `source_content` como **un único string**, y 133 KB no caben
fiablemente en un parámetro de tool sin riesgo de corrupción silenciosa. El MCP es **siempre
remoto** desde v6.7.0 (no ve el filesystem del cliente). Es un gap de diseño: los tests usan
fixtures pequeñas en memoria, nunca un items.json real cruzando el transporte.

## La idea (validada técnicamente — el engine ya tiene el ~90%)

**El MCP remoto YA escribe a Postgres item-por-item** cuando hay cambios en un proyecto native
(reserve/complete/mark_ac/create_item). Una migración a native **es lo mismo, repetido N veces**.
Por tanto, en vez de transportar todo el source de golpe, se implementa como **ingesta por lotes
server-side**: el cliente envía los items en chunks pequeños y verificables, el servidor los
acumula y los ingesta en **una transacción atómica**, reutilizando los INSERT que ya existen.
El chunking es solo del **transporte**; la **escritura** sigue siendo todo-o-nada (commit al
final). Resuelve transporte Y preserva atomicidad. No toca el blindaje de seguridad (identidad
validada server-side, escritura solo en el tenant, audit).

### Piezas que YA EXISTEN (reutilizar, NO reescribir) — verificado en código
- `native_backend.create_item` → `_insert_us` / `_insert_uc` / `_insert_ac`
  (`server/backends/native_backend.py:421-604`): escritura item-por-item probada.
- `asyncpg.Pool` con transacciones, compatible Supabase Pooler (`server/db/pool.py:157-168`).
- `create_acceptance_criteria` ya envuelve varios INSERT en `async with conn.transaction()`
  (`native_backend.py:854`) — el patrón de transacción ya existe, solo hay que ampliarlo.
- `FreeformBackend(items_content=...)` — parser memory-mode sin filesystem (`migration.py:75`).
- `authenticate_and_authorize_cached` con TTL 30s (`coordination/identity.py:400-428`):
  valida el dev_token una vez, reúsa para los N items sin re-consultar Postgres.
- `write_target` (`server/migration/writer.py:70-171`) ya itera los items y llama `create_item`
  por fase (US, luego UC+AC).

### Lo que FALTA (gap real, ~100 LOC, sin bloqueadores arquitectónicos)
1. **Orquestador de sesión de migración multi-llamada**: mantiene el dev_token y acumula items
   entre requests (hoy `migrate_preview`→`migrate_project` es request-scoped).
2. **Zona de staging server-side**: dict en memoria o tabla temporal donde se acumulan los
   chunks hasta el commit.
3. **Transacción envolvente en `write_target`**: cambiar el manejo per-item-exception por
   `async with pool.acquire() as conn: async with conn.transaction():` para las 3 fases →
   atomicidad real (hoy si un item falla, hace `continue`, no rollback).
4. **Commit diferido**: ejecutar `write_target` sobre el staging acumulado y limpiar; rollback
   total si algo falla a mitad.

## Lo que quiero que hagas

### FASE 1 — `/discovery`
Discovery del **transporte de sources grandes a native como ingesta por lotes**, partiendo de
que el engine ya escribe item-por-item. Define:
- El **modelo de sesión de migración** (start → accumulate × N → commit), tamaño de chunk
  recomendado, verificación de integridad por chunk (hash/conteo) y global (¿llegaron los N
  esperados?) antes del commit.
- Cómo se **preserva la atomicidad** con transporte fragmentado (commit diferido en una
  transacción; rollback total ante fallo a mitad).
- Cómo encaja con el **`switch_project_backend` atómico** existente (la ingesta es el paso
  "write_target" de la operación; el switch de los 3 lugares de config sigue al final).
- **Identidad/seguridad**: validar dev_token al `start`, reusar caché; escribir solo en el
  tenant; audit. NO relajar `deny_anon` ni exponer `service_role` al cliente.
- **Idempotencia/reanudación**: si una sesión de migración se corta a medias, ¿se puede
  reanudar o se descarta el staging? ¿colisión de project_id?
- **Pre-flight**: el cliente declara al `start` cuántos items va a enviar; el commit verifica
  que recibió esa cantidad antes de escribir nada.

### FASE 2 — `/prd` + `/plan`
US para la ingesta por lotes a native, reutilizando las piezas listadas arriba. Incluye los 4
gaps como UCs. E2E que **reproduzca el caso real**: un items.json grande (≥100 KB) cruzando por
lotes, verificando que el resultado en Postgres = source del cliente, estados preservados,
atómico. (El test actual usa fixture pequeña en memoria — añadir uno de tamaño real.)

### FASE 3 — `/implement`
Por UCs, autopilot. Calidad sobre velocidad.

## No-regresión (dato real)
- Proyecto `specbox_cloud`: tracking freeform en `doc/tracking/` (133 KB, 13 US / 89 UC / 466
  AC, 85 done / 4 backlog). `items.json` ya reconciliado y generado.
- BD Cloud destino (`EmbedBuild/specbox_cloud`) **vacía a propósito** (backup en el repo panel:
  `.quality/dogfood-backup/native-project-backup-pre-delete.json`).
- Una ingesta por lotes correcta debe reconstruir el proyecto en Postgres con `jesusperezdeveloper`
  como project_admin, 85 UCs `done` / 4 `backlog`, sin transcripción manual de blobs.

**Empieza por `/discovery`. No escribas código hasta tener discovery y plan aprobados.**
