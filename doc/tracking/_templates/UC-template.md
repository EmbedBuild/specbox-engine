---
id: UC-NNN
title: <Título técnico y accionable>
parent_us: US-NN
status: draft         # draft | ready | in-progress | review | done | blocked | wontdo
actor: <actor principal>
milestone: <M1 | M2 | M3 | M4 | M5>
hours: <estimación>
screens: <pantallas de diseño asociadas o vacío si es de Sistema>
design: missing       # covered | missing | pending | n/a
owner: <responsable>
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# UC-NNN — <Título>

> **US padre:** [US-NN](../us/US-NN_<slug>.md)

## Objetivo

<Qué hace este UC en una frase. Es la unidad mínima entregable.>

## Descripción

<Detalle funcional: actores, precondiciones, flujo principal, flujos alternativos, postcondiciones.>

### Precondiciones
- <…>

### Flujo principal
1. <…>

### Flujos alternativos / errores
- <…>

### Postcondiciones
- <…>

## Notas técnicas

<Decisiones de implementación, librerías, endpoints, esquema de datos, etc.>

## Diseño

<Pantallas en doc/design/ que cubren este UC, o ⚠️ SIN DISEÑO con motivo.>

## Acceptance Criteria

### AC-001 — <Título corto>
- **Given** <contexto>
- **When** <acción>
- **Then** <resultado observable>
- **Estado:** ⬜ pendiente   <!-- ⬜ pendiente | 🟡 en progreso | ✅ cumplido | ❌ no cumple -->

## Evidencia

<Enlaces a PRs, capturas, tests, etc. Se llena al cerrar el UC.>

## Dependencias

- **Bloqueado por:** <UC o ninguno>
- **Bloquea a:** <UC o ninguno>
