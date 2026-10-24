-- 0032_autopilot_decisions.sql
-- SpecBox Engine — las decisiones aplazadas del autopilot en el board (US-99 · UC-9902).
--
-- Hasta ahora la cola de decisiones del autopilot vivía solo en doc/app/decisions_queue.md del
-- proyecto: para decidir desde el teléfono o desde el panel tiene que estar también en el board.
--
-- Qué deja esta migración:
--   * autopilot_decisions: una fila por decisión aplazada, con el mismo id que la entrada de la
--     cola (dq-…), su UC, la pregunta, las opciones y la opción por defecto que la sesión aplicó
--     mientras tanto. Cuando una persona la resuelve (desde el panel, la app o una sesión) quedan
--     quién, cuándo y qué opción; cuando la siguiente sesión del proyecto la recoge, applied_at.
--     Longitudes máximas en cada campo; la tool que la escribe rechaza credenciales. Sin
--     privilegios para PUBLIC, anon ni authenticated, con seguridad por filas y la denegación
--     restrictiva del resto del board (0024, 0029).
--
-- Idempotente: CREATE ... IF NOT EXISTS, DROP ... IF EXISTS.

CREATE TABLE IF NOT EXISTS autopilot_decisions (
    project_id      TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    decision_id     TEXT NOT NULL CHECK (decision_id ~ '^dq-[0-9]{8}T[0-9]{6}-[0-9a-f]{4}-[a-z0-9]{1,6}$'),
    uc_id           TEXT CHECK (uc_id IS NULL OR uc_id ~ '^UC-[0-9]{1,6}[a-z]?$'),
    decision_key    TEXT NOT NULL CHECK (decision_key ~ '^[a-z][a-z0-9_]{1,63}$'),
    question        TEXT NOT NULL CHECK (char_length(question) BETWEEN 3 AND 300),
    -- [{"id": "...", "label": "..."}], de 2 a 6.
    options         JSONB NOT NULL CHECK (jsonb_typeof(options) = 'array'
                                          AND jsonb_array_length(options) BETWEEN 2 AND 6),
    default_option  TEXT NOT NULL CHECK (default_option ~ '^[a-z0-9][a-z0-9_-]{0,39}$'),
    created_by      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT,
    resolution      TEXT CHECK (resolution IS NULL OR resolution ~ '^[a-z0-9][a-z0-9_-]{0,39}$'),
    resolved_via    TEXT CHECK (resolved_via IS NULL OR resolved_via IN ('panel', 'app', 'session')),
    applied_at      TIMESTAMPTZ,
    PRIMARY KEY (project_id, decision_id),
    CHECK ((resolved_at IS NULL) = (resolution IS NULL)),
    CHECK ((resolved_at IS NULL) = (resolved_by IS NULL)),
    CHECK ((resolved_at IS NULL) = (resolved_via IS NULL)),
    CHECK (applied_at IS NULL OR resolved_at IS NOT NULL)
);

COMMENT ON TABLE autopilot_decisions IS
    'Decisiones aplazadas del autopilot (US-99 · UC-9902): pregunta, opciones y opción por defecto; quién, cuándo y qué resolvió; cuándo la recogió la siguiente sesión.';

CREATE INDEX IF NOT EXISTS idx_autopilot_decisions_pending
    ON autopilot_decisions (project_id, created_at)
    WHERE resolved_at IS NULL;

-- ── Cerrada a los roles públicos, como el resto del board (0024) ──────
DO $$
DECLARE
    has_anon CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon');
    has_auth CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated');
BEGIN
    ALTER TABLE public.autopilot_decisions ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON TABLE public.autopilot_decisions FROM PUBLIC;
    IF has_anon THEN
        REVOKE ALL ON TABLE public.autopilot_decisions FROM anon;
    END IF;
    IF has_auth THEN
        REVOKE ALL ON TABLE public.autopilot_decisions FROM authenticated;
    END IF;
    IF has_anon AND has_auth THEN
        DROP POLICY IF EXISTS specbox_deny_anon_autopilot_decisions ON public.autopilot_decisions;
        CREATE POLICY specbox_deny_anon_autopilot_decisions ON public.autopilot_decisions
            AS RESTRICTIVE FOR ALL TO anon, authenticated USING (false) WITH CHECK (false);
    END IF;
END
$$;
