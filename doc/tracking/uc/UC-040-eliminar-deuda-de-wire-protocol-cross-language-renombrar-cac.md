---
id: UC-613
ordinal: UC-040
title: "Eliminar deuda de wire-protocol cross-language: renombrar cache JSON + hook Node + endpoint REST de claim → reservation"
parent_us: US-CLAIM-RENAME
status: done
actor: Engine
hours: 3
owner: Jesús Pérez
created: 2026-05-24
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# UC-613 — Eliminar deuda de wire-protocol cross-language: renombrar cache JSON + hook Node + endpoint REST de claim → reservation

> **US padre:** [US-CLAIM-RENAME](../us/US-05-renombrar-el-concepto-claim-a-reservation-en-native-backend-.md)

## Objetivo / Descripción

Cerrar la única deuda técnica que dejó UC-602: la asimetría nombre↔valor `_NATIVE_RESERVATION_CACHE_KEY = "claim"` en `server/tools/spec_driven.py` (línea 63) y el wire-protocol cross-language Node↔Python↔REST que la justifica.

**Contexto de la deuda**

UC-602 renombró el módulo Python `coordination/claims.py` → `reservations.py` y todos sus identificadores. PERO el cache local `.quality/active_uc.json` mantiene la key `"claim"` porque dos consumidores en otro lenguaje aún no fueron renombrados:

1. **Hook Node** `.claude/hooks/spec-guard.mjs` + `lib/native-claim-revalidate.mjs` — lee `payload.claim` del JSON local. Si el JSON cambia a `payload.reservation` sin actualizar el hook, spec-guard ve `payload.reservation == undefined` y trata el archivo como "sin reserva nativa cacheada" — permitiendo escrituras que deberían bloquearse. El hook es el guardia que impide escribir código sin UC activo, así que romperlo es un incidente de seguridad.

2. **Endpoint REST MCP** `/api/native/claim-status` — el hook lo invoca para revalidar la reserva contra el MCP del VPS. Devuelve `{ uc_id, claim: {…} | null }`. Si renombramos cliente sin servidor (o viceversa), la revalidación se rompe.

El símbolo Python se llama `_NATIVE_RESERVATION_CACHE_KEY` (vocabulario nuevo) pero su valor es `"claim"` (vocabulario viejo). Esa grieta envejece mal: cualquier dev futuro pierde 5 minutos averiguando por qué nombre y valor no coinciden. Este UC la cierra.

**Alcance**

- Renombrar el archivo `lib/native-claim-revalidate.mjs` → `lib/native-reservation-revalidate.mjs` y todos sus identificadores (`decideNativeClaim` → `decideNativeReservation`, `probeNativeClaim` → `probeNativeReservation`, `getActiveUCClaim` → `getActiveUCReservation` en `lib/config.mjs`, etc.).
- Renombrar la key del JSON local: `payload.claim` → `payload.reservation`. Eliminar `_NATIVE_RESERVATION_CACHE_KEY = "claim"` de `spec_driven.py` y usar la key literal `"reservation"` directamente. Eliminar el fallback `reservation.get("claimed_at")` que UC-602 dejó por compat.
- Renombrar el endpoint REST `/api/native/claim-status` → `/api/native/reservation-status` y la shape de respuesta `{ uc_id, claim: … }` → `{ uc_id, reservation: … }`.
- Compat transitoria durante el periodo de deprecación (alineado con UC-604 / UC-612):
  - El hook Node lee primero `payload.reservation` y cae a `payload.claim` como fallback (logging warning). Eliminado en UC-612.
  - El endpoint REST sigue sirviendo `/api/native/claim-status` con 301 redirect a `/api/native/reservation-status`. Eliminado en UC-612.
- Coordinar orden de deployment: el MCP del VPS debe servir el endpoint nuevo ANTES de que se distribuya el hook nuevo a las máquinas de devs. La compat bidireccional garantiza que cualquier permutación cliente-servidor durante el rollout funcione.

**Fuera de scope**

- Cambiar la semántica del cache (sigue siendo una snapshot revalidable de la reserva remota).
- Migrar archivos `.quality/active_uc.json` existentes en disco — son efímeros (los regenera `start_uc` o `_write_active_uc_marker`), no requieren migración.

**Orden**

UC-613 corre DESPUÉS de UC-604 (alias deprecados de tools) y ANTES de UC-612 (eliminación de alias deprecados en v5.37.0). UC-612 retira tanto el alias `claim_uc` como el endpoint legacy `/api/native/claim-status` y la lectura fallback de `payload.claim` — todo en el mismo barrido.

## Acceptance Criteria

### AC-01

grep -rn 'claim|Claim|claimed_at' server/ .claude/hooks/ --include='*.py' --include='*.mjs' devuelve cero lineas en codigo activo. Las unicas apariciones permitidas son: (a) comentarios/docstrings historicos que mencionan el rename entre comillas, (b) las ramas de fallback explicitamente marcadas como compat transitoria con UC-612 (lectura de payload.claim en el hook y handler del endpoint legacy en el MCP). La constante _NATIVE_RESERVATION_CACHE_KEY de server/tools/spec_driven.py ya no existe.

- **Estado:** ✅ cumplido

### AC-02

El archivo .quality/active_uc.json escrito por _write_active_uc_marker para una sesion nativa contiene la key literal 'reservation' (no 'claim'). Verificado escribiendo el marker con un mock y haciendo json.loads(...)['reservation'] que devuelve el dict con uc_id / developer_id / reserved_at / backend. El test anadido test_active_uc_marker_uses_reservation_key cubre este AC.

- **Estado:** ✅ cumplido

### AC-03

El endpoint MCP responde a GET /api/native/reservation-status?project_id=...&uc_id=... con {uc_id, reservation: {developer_id} | null} (key reservation, no claim). El endpoint legacy /api/native/claim-status responde 301 al endpoint nuevo durante la ventana de deprecacion (v5.35-v5.36); en v5.37.0 (UC-612) ese 301 se elimina y la ruta legacy devuelve 404. Verificado con curl -i contra el MCP local.

- **Estado:** ✅ cumplido

### AC-04

El hook .claude/hooks/spec-guard.mjs carga getActiveUCReservation() (no getActiveUCClaim()) desde lib/config.mjs. El archivo lib/native-claim-revalidate.mjs se renombra a lib/native-reservation-revalidate.mjs y exporta decideNativeReservation (no decideNativeClaim). Verificado con grep -rn 'getActiveUCClaim|decideNativeClaim|native-claim-revalidate' .claude/hooks/ que devuelve 0 hits en codigo activo.

- **Estado:** ✅ cumplido

### AC-05

La suite native completa (.venv/bin/pytest tests/test_native_*.py tests/test_coordination_*.py -q) sigue 100% verde tras el rename. Adicionalmente, un test verifica que: (a) un cache JSON con key reservation se interpreta correctamente, (b) un cache JSON con key legacy claim tambien se interpreta (fallback documentado), (c) el endpoint nuevo responde con la shape correcta.

- **Estado:** ✅ cumplido

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
