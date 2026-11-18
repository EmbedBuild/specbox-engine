-- 0040_uc_criteria_approvals.sql
-- SpecBox Engine — una persona aprueba los criterios antes de implementar (US-125 · UC-12502).
--
-- Hasta ahora no había paso ni registro de aprobación: las UC nacían en backlog, find_next_uc las
-- proponía y start_uc no comprobaba nada; la primera vez que una persona miraba los criterios era al
-- aceptar la UC hecha.
--
-- Qué deja esta migración:
--   * uc_criteria_approvals: cada aprobación de los criterios de una UC, con quién (developer y sesión
--     de Claude Code), cuándo y la huella de los criterios vigentes en ese momento (id y texto) junto
--     con su copia. Solo se añade: la última es la que cuenta, y vale mientras la huella sea la de los
--     criterios de ahora. Cambiar un texto, añadir un criterio o retirarlo cambia la huella y la UC
--     queda sin aprobar, lo escriba quien lo escriba: la regla se calcula al leer (server/approval.py),
--     no con un trigger.
--   * Cerrada a los roles públicos como el resto del board (0024): la escribe y la lee el servidor.
--
-- Idempotente: CREATE ... IF NOT EXISTS y DROP POLICY IF EXISTS.

CREATE TABLE IF NOT EXISTS uc_criteria_approvals (
    id           BIGSERIAL PRIMARY KEY,
    project_id   TEXT NOT NULL,
    uc_id        TEXT NOT NULL,
    fingerprint  TEXT NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{16,64}$'),
    criteria     JSONB NOT NULL DEFAULT '[]'::jsonb,
    approved_by  TEXT NULL,
    session_id   TEXT NULL CHECK (session_id IS NULL OR session_id ~ '^[A-Za-z0-9_.:@/-]{1,128}$'),
    source       TEXT NOT NULL DEFAULT 'person' CHECK (source IN ('person')),
    approved_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (project_id, uc_id) REFERENCES use_cases (project_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_uc_criteria_approvals_uc
    ON uc_criteria_approvals (project_id, uc_id, approved_at DESC, id DESC);

COMMENT ON TABLE uc_criteria_approvals IS
    'Aprobaciones de los criterios de una UC antes de implementar (UC-12502). Vale la última si su huella es la de los criterios vigentes.';

DO $$
DECLARE
    has_anon CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon');
    has_auth CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated');
BEGIN
    ALTER TABLE public.uc_criteria_approvals ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON TABLE public.uc_criteria_approvals FROM PUBLIC;
    REVOKE ALL ON SEQUENCE public.uc_criteria_approvals_id_seq FROM PUBLIC;
    IF has_anon THEN
        REVOKE ALL ON TABLE public.uc_criteria_approvals FROM anon;
        REVOKE ALL ON SEQUENCE public.uc_criteria_approvals_id_seq FROM anon;
    END IF;
    IF has_auth THEN
        REVOKE ALL ON TABLE public.uc_criteria_approvals FROM authenticated;
        REVOKE ALL ON SEQUENCE public.uc_criteria_approvals_id_seq FROM authenticated;
    END IF;
    IF has_anon AND has_auth THEN
        DROP POLICY IF EXISTS specbox_deny_anon_uc_criteria_approvals ON public.uc_criteria_approvals;
        CREATE POLICY specbox_deny_anon_uc_criteria_approvals ON public.uc_criteria_approvals
            AS RESTRICTIVE FOR ALL TO anon, authenticated USING (false) WITH CHECK (false);
    END IF;
END
$$;
