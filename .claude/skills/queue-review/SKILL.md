---
name: queue-review
description: >
  Review and resolve entries in `doc/app/decisions_queue.md` — the deferred
  decisions queue introduced in v5.29.0. Lists pending entries from one or
  many projects, lets the user confirm / adjust / revert each, and moves
  resolved ones to the historical section. Use when the user says
  "queue review", "review queue", "revisar cola", "resolver pendientes",
  or wants to batch-process decisions accumulated by the autopilot in
  `equilibrado` / `agresivo` modes when `autopilot.queue_enabled=true`.
context: direct
allowed-tools: Read, Write, Edit, Bash(pwd), Bash(ls:*)
---

# /queue review — Resolver decisiones diferidas

Procesa la cola en `doc/app/decisions_queue.md`. La cola solo se llena cuando el proyecto tiene `specbox.autopilot.queue_enabled = true` (off por default en v5.29.0). Cuando está apagada, las decisiones diferibles se preguntan síncronamente como en v5.28.

## Uso

```
/queue review                       # Lista pendientes en este proyecto
/queue review --recent N            # Solo las N más recientes pendientes
/queue review --feature signup-flow # Filtrar por feature
/queue review --resolve dq-XXX      # Resolver una entrada específica
/queue review --all-projects        # Reservado para multi-proyecto (PR-15+)
```

---

## Paso 1 — Listar la cola

Llama:

```
list_decisions_queue(project_path=".")
```

Si retorna `exists=false`, informa "La cola no se ha creado aún. Las decisiones diferibles solo se acumulan cuando `autopilot.queue_enabled=true`." y termina.

Si retorna `pending_count=0`, informa "Sin decisiones pendientes." y termina.

Si hay pendientes, formatea la salida así:

```
🔄 Decisiones pendientes (N):

[1] dq-XXXX-abcd-veg
    feature: signup-flow
    decision_key: veg_preview
    Generado: hace 2 horas
    Default aplicado: Per-ICP arquetipo Startup (score=0.82)
    Bloquea: marcar UC-003 como ACCEPTED
    Evidencia: doc/veg/signup-flow/preview.md
    Acción: [c]onfirmar  [a]djust  [r]everter  [s]kip

[2] ...
```

Pide al usuario que elija qué quiere hacer (uno por uno o batch).

---

## Paso 2 — Resolver entradas

Cuando el usuario decide:

| Acción | Lógica |
|--------|--------|
| **Confirmar** | El default tentativo era correcto. Llama `resolve_queue_entry(engine_id, resolution="confirmed: <texto opcional>")`. |
| **Ajustar** | Pregunta el nuevo valor, aplica el cambio en el artefacto referenciado por `evidence`, y resuelve con `resolution="adjusted: <descripción>"`. |
| **Revertir** | El default fue incorrecto. Pregunta qué hacer (rehacer paso síncrono, abortar feature, etc.) y resuelve con `resolution="reverted: <razón>"`. |
| **Skip** | No hacer nada — la entrada queda pendiente. |

Si el usuario quiere batch-resolver con un patrón ("aprobar todos los veg_preview con score >0.85"):

1. Filtra `pendientes` por `decision_key` y/o por contenido en `default_applied`.
2. Aplica el `resolve_queue_entry` para cada match.
3. Reporta cuántas resolvió en batch.

---

## Paso 3 — Output final

```
✅ Resueltas en esta sesión: N
   doc/app/decisions_queue.md actualizado (M pendientes restantes)

UCs desbloqueados (si los hay): UC-003, UC-007
```

Los UCs se desbloquean automáticamente cuando todas sus entradas pendientes se resuelven (esto lo gestiona el sync layer de PR-12+).

---

## Inviolables

La cola **nunca** acepta:

- `destructive_action`
- `image_cost_over_budget`
- `branch_to_main_push`
- `definition_quality_gate`
- `feature_problem_definition`
- `feedback_field_classification`

Estos siempre se preguntan síncronamente. Si el usuario invoca `/queue review` y ve uno de estos en la cola, es un bug — reportar para revisar el flujo del skill que lo encoló indebidamente.

---

## Auto-resolve

Si una entrada tiene más de `autopilot.queue_auto_resolve_days` días (default 7), se auto-resuelve manteniendo el default tentativo. Esto evita que la cola se acumule indefinidamente. La auto-resolución queda registrada con `auto_resolved=true` para auditabilidad.

`/queue review` puede mostrar warnings sobre entradas que están a punto de auto-resolverse.

---

## Reglas

- Nunca borrar entradas resueltas — son histórico de decisiones del proyecto.
- Editar `decisions_queue.md` a mano está OK (es una zona `manual` del usuario), pero el formato lo gestiona el parser; un fichero con marcadores rotos hace que `list_decisions_queue` retorne errores.
- Después de resolver, mostrar al usuario el comando equivalente para que pueda automatizar:
  ```
  resolve_queue_entry(engine_id="dq-XXX", resolution="confirmed: looks good")
  ```
