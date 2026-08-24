-- 0021_ac_internal.sql
-- SpecBox NativeBackend — marca `internal` en los criterios de aceptación.
--
-- POR QUÉ (US-33 / UC-3301, satélite engine):
-- D7 convierte los AC en **entregable cara-al-cliente**: dejan de ser notas del
-- equipo y pasan a proyectarse en una reunión con el stakeholder. Algunos no
-- deberían estar ahí — un AC que describe una migración de datos, un detalle de
-- infraestructura o un refactor interno es ruido para quien paga el proyecto,
-- no información.
--
-- Esta columna es el opt-out: marca el AC como interno para que el portal de
-- negocio (`projects.embed.build`) no lo muestre. Es **bloqueante de UC-3204**,
-- que expone el marcado desde la UI del portal.
--
-- POR QUÉ `DEFAULT false` Y NO UN BACKFILL:
-- El AC-01 exige que tras la migración TODOS los AC existentes queden visibles y
-- ninguno se oculte. `NOT NULL DEFAULT false` lo garantiza por construcción: no
-- hay ventana en la que una fila tenga NULL, ni criterio que decida a posteriori
-- qué ocultar. Ocultar es siempre una decisión explícita de una persona.
--
-- COSTE EN PRODUCCIÓN:
-- Desde Postgres 11, `ADD COLUMN ... NOT NULL DEFAULT <constante>` NO reescribe
-- la tabla — el default se guarda en el catálogo y se materializa al reescribir
-- cada fila. Sobre los ~6.6k AC del board es una operación de metadatos.
--
-- IDEMPOTENTE: `IF NOT EXISTS`, como el resto del ledger. Re-aplicarla es un
-- no-op, que es lo que necesitan el runner local y los tests.

ALTER TABLE acceptance_criteria
    ADD COLUMN IF NOT EXISTS internal BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN acceptance_criteria.internal IS
    'US-33/UC-3301: si es true, el AC no se muestra al stakeholder en el portal '
    'de negocio. Default false — ocultar es siempre una decisión explícita.';

-- Índice parcial: las consultas del portal filtran por "los NO internos", y los
-- internos son la minoría esperada. Un índice parcial sobre los marcados es
-- pequeño y sirve al caso inverso (auditar qué se está ocultando en un proyecto)
-- sin penalizar las escrituras del caso común.
CREATE INDEX IF NOT EXISTS idx_ac_internal_marked
    ON acceptance_criteria (project_id, uc_id)
    WHERE internal;
