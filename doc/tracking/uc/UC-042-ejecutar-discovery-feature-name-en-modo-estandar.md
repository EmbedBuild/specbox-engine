---
id: UC-D001
ordinal: UC-042
title: Ejecutar /discovery [feature_name] en modo estándar
parent_us: US-D01
status: ready
actor: Engine
hours: 12
owner: Jesús Pérez
created: 2026-05-24
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# UC-D001 — Ejecutar /discovery [feature_name] en modo estándar

> **US padre:** [US-D01](../us/US-09-discovery-conversational-flow-per-feature.md)

## Objetivo / Descripción

Cuando el proyecto ya tiene doc/app/app_market.md completado, /discovery [feature_name] lanza un flujo conversacional de 3 fases (ICP identification, JTBD extraction, validation gate), genera doc/discovery/<feature_name>/icp_jtbd.md y termina con un verdict explícito.

## Acceptance Criteria

### AC-01

[AC-01] La invocación /discovery user_export en un proyecto con app_market.md completado lanza un flujo interactivo en <=2 segundos desde el comando. [JR-1.1, JR-3.1]

- **Estado:** ⬜ pendiente

### AC-02

[AC-02] La Fase 1 (ICP identification) muestra los ICPs canónicos del app_market.md y pregunta cuáles están involucrados en esta feature. El usuario puede seleccionar 1-3 ICPs preexistentes o añadir uno nuevo con warning de drift. [JR-3.1, JE-3.2]

- **Estado:** ⬜ pendiente

### AC-03

[AC-03] Para cada ICP nuevo (no presente en app_market.md), el flujo aplica el sanity check '¿conoces a 3 personas concretas que encajen?' y registra la respuesta en el artefacto. Si la respuesta es no, marca el ICP como tentativo. [JR-1.1, JE-1.2]

- **Estado:** ⬜ pendiente

### AC-04

[AC-04] La Fase 2 (JTBD extraction) genera, para cada ICP seleccionado, un draft de 2-3 JTBDs racionales y 1-2 JTBDs emocionales en formato canónico 'Cuando [situación], quiero [motivación], para [resultado esperado]'. El usuario edita/refina/elimina/añade libremente. [JR-1.1, JR-1.2, JR-3.1]

- **Estado:** ⬜ pendiente

### AC-05

[AC-05] Cada concepto nuevo introducido en el flujo (ICP, JTBD racional, JTBD emocional) viene acompañado de: (a) una micro-justificación en lenguaje natural de por qué importa, (b) un ejemplo real del ecosistema embed.build (PaddockManager/McProfit/Futbase/SpecBox), (c) un anti-pattern explícito como contraejemplo. [JE-3.2, JR-3.2]

- **Estado:** ⬜ pendiente

### AC-06

[AC-06] La Fase 3 (validation gate) muestra resumen consolidado y pregunta '¿hay alguna conversación reciente, datapoint de mercado o evidence externa que respalde estos JTBDs?'. La respuesta (libre, o explícito waiver) se registra en icp_jtbd.md. [JR-1.1, JE-1.2]

- **Estado:** ⬜ pendiente

### AC-07

[AC-07] El artefacto final doc/discovery/<feature_name>/icp_jtbd.md se genera con la estructura canónica definida en la sección 4.1 y contiene discovery_id único trazable. [JR-1.2, JR-2.1]

- **Estado:** ⬜ pendiente

### AC-08

[AC-08] El flujo completo se completa en <=30 minutos para un user experimentado y <=60 minutos para la primera feature de un user nuevo (en modo bootstrap). [JR-1.1]

- **Estado:** ⬜ pendiente

### AC-09

[AC-09] El flujo es interrumpible en cualquier fase. Una segunda invocación de /discovery [feature_name] detecta artefacto parcial y ofrece resumir o reiniciar. [JE-1.1, JE-2.1]

- **Estado:** ⬜ pendiente

### AC-10

[AC-10] El comando muestra al final un verdict explícito: READY_FOR_PRD o DISCOVERY_INCOMPLETE con lista específica de razones (ej: 'falta JTBD racional para ICP-2'). [JR-3.1, JE-3.3]

- **Estado:** ⬜ pendiente

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
