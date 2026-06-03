# Prompt v6.9.4 — Eliminar el tenant huérfano que desactiva la auto-provisión

> Dispara esto desde una sesión de Claude **dentro del repo `specbox-engine`**.
> Cierra el bug encontrado probando v6.9.3 (ver `HALLAZGO-v6.9.4-setup-board-tenant-huerfano.md`).
> Sigue el pipeline del engine: `/discovery` → `/prd` → `/plan` → `/implement`.

---

## Contexto (dogfooding 2026-06-03, probando v6.9.3 "Tenant Provisioning")

v6.9.3 implementó la auto-provisión de tenant + membresía (`provision_native_project`, atómico
y correcto) e integró `_maybe_auto_provision` en `start_migration_session`. **Pero la migración
real de un proyecto nuevo desde cero SIGUE fallando con FORBIDDEN.** El detalle con file:line
está en `HALLAZGO-v6.9.4-setup-board-tenant-huerfano.md` — léelo primero.

### El bug, en una frase
`setup_board` (`server/backends/native_backend.py:336-354`) hace `INSERT INTO projects` **sin
crear membresía**, fuera de `provision_native_project`. Cuando una operación previa
(`start_uc`/`import_spec`/una migración anterior, `setup_board` en `migration.py:337,630,1009`
y `spec_driven.py:276,460`) crea esa fila, queda un **tenant huérfano** (proyecto con CERO
miembros). Entonces `_maybe_auto_provision` (`migration.py:1436`) ve `exists = True` →
`return False` (no provisiona, cree que es un tenant legítimo) → el gate de membresía →
**FORBIDDEN**. El ecosistema se sabotea a sí mismo.

### Evidencia (Postgres, verificada por SQL directo)
Tras `start_migration_session` sobre BD vacía: `public.projects` = 1 fila (sin membresía),
`public.project_members` = 0, `public.audit_log` = 0. Firma de `setup_board`, no de
`provision_native_project` (que pondría membresía + audit en la misma transacción).

### Por qué el test de v6.9.3 no lo ve
El E2E (UC-822) ejerce el camino **limpio** (BD vacía → `start_migration_session` → provisión).
Nunca hay un `setup_board` previo creando la fila huérfana. **Pasa en test, falla en real.** Es
el mismo patrón de v6.9.2 (fixture en memoria vs transporte real): el test cubre el camino ideal,
el dogfooding encuentra el camino sucio.

## Decisión de diseño a resolver en el discovery (técnica — el engine elige con criterio)

Hay (al menos) dos enfoques de fix; el `/discovery` debe evaluar y elegir, justificando:

1. **Eliminar la creación de tenant fuera de la provisión atómica.** Que toda creación de tenant
   native pase por `provision_native_project` (tenant + membresía juntos en una transacción).
   `setup_board` para native no debería poder dejar un proyecto con cero miembros. (Más invasivo:
   toca todas las rutas que llaman `setup_board` para native.)
2. **Que `_maybe_auto_provision` distinga "tenant huérfano" de "tenant real".** Un proyecto que
   existe pero tiene **CERO** `project_members` es un fantasma, no un proyecto del que el guard
   AC-13 deba proteger. La condición de auto-provisión pasaría de "el proyecto no existe" a "el
   proyecto no existe **o no tiene ningún miembro**" → en ese caso provisiona/adopta el tenant
   huérfano (crea la membresía del creador). (Menos invasivo, pero hay que razonar la seguridad:
   ¿puede un atacante crear un tenant huérfano para que otro se auto-una? Evaluarlo — el guard
   AC-13 original protege contra auto-unirse a tenants **con miembros**, que es el caso real de
   robo; un tenant con 0 miembros no tiene a quién robarle.)
3. (Combinable) Cerrar la puerta de raíz **y** hacer la auto-provisión robusta a estados sucios.

El discovery debe decidir y dejar claro el contrato: **un tenant native nunca debe existir sin
al menos un miembro** (o, si puede existir transitoriamente, la auto-provisión debe saber
adoptarlo). Sea cual sea la opción, debe respetar el guard de seguridad real (no auto-unir a un
proyecto que YA tiene dueños) y la decisión canónica D2 de v6.9.3.

## Lo que quiero que hagas

### FASE 1 — `/discovery`
Discovery del **bug de tenant huérfano y la robustez de la auto-provisión ante estados sucios**:
- Traza todas las rutas que crean `public.projects` para native y cuáles dejan (o pueden dejar)
  el proyecto sin membresía. Define el invariante: **¿puede existir un tenant native sin ningún
  miembro? Si no, cómo se garantiza.**
- Elige el enfoque de fix (1 / 2 / 3 arriba), justifícalo, y razona la seguridad del caso
  "tenant con 0 miembros" (¿es siempre seguro adoptarlo / provisionarlo?).
- Define cómo la auto-provisión se vuelve **idempotente y robusta a estados sucios** (si la fila
  huérfana ya existe, el flujo se recupera en vez de FORBIDDEN).

### FASE 2 — `/prd` + `/plan`
US que cierre el bug, reutilizando `provision_native_project`. **Requisito de test ineludible:**
un E2E que reproduzca el **camino sucio real** — un `setup_board` (u operación equivalente) crea
la fila huérfana **primero**, y LUEGO `start_migration_session` debe recuperarse (provisionar la
membresía / adoptar el tenant) y completar la ingesta, **sin** FORBIDDEN. Verifica: 1 fila de
projects con el creador como `project_admin`, US/UC/AC con estados preservados.
> Principio transversal para los tests de migración (de los 4 hallazgos de este dogfooding): los
> E2E deben partir de **estados sucios realistas**, no solo de BD/fixtures vírgenes.

### FASE 3 — `/implement`
Por UCs, autopilot. Calidad sobre velocidad.

## Datos de reproducción / no-regresión
- Proyecto `specbox_cloud`: `doc/tracking/items.json` reconciliado (186 KB, 13 US / 89 UC /
  466 AC, 85 done / 4 backlog).
- BD Cloud (`EmbedBuild/specbox_cloud`) **vacía** ahora (la fila huérfana del intento se limpió;
  backup en el repo panel: `.quality/dogfood-backup/native-project-backup-pre-delete.json`).
- Identidad `jesusperezdeveloper` válida (dev_token autentica, whoami OK).
- Repro del bug: con una fila de `projects` sin membresía presente (la crea cualquier
  `setup_board` previo), `start_migration_session` → FORBIDDEN en vez de auto-provisionar.
- Resultado esperado tras el fix: migración freeform→native end-to-end desde cero (provisión
  robusta a estado sucio + ingesta por lotes), `jesusperezdeveloper` como `project_admin`,
  13 US / 89 UC / 466 AC, 85 done / 4 backlog, project_id canónico `EmbedBuild/specbox_cloud`.

## Cadena de hallazgos de este dogfooding (contexto)
1. v6.9.1 "Atomic Switch" — switch atómico + path bug remoto (cerrado).
2. v6.9.2 "Batch Ingest" — transporte de sources grandes por lotes (cerrado).
3. v6.9.3 "Tenant Provisioning" — provisión + contrato project_id (cierra la lógica).
4. **v6.9.4 (este)** — `setup_board` deja tenant huérfano que desactiva la auto-provisión de
   v6.9.3 en el camino real.

Patrón común a los 4: **el test pasa con el camino ideal; el dogfooding encuentra el camino real.**
Cerrar este bug debería incluir adoptar "estados sucios realistas" como estándar de los E2E de
migración, para romper la cadena.

**Empieza por `/discovery`. No escribas código hasta tener discovery y plan aprobados.**
