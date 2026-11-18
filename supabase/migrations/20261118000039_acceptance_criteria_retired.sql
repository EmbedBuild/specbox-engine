-- 0039_acceptance_criteria_retired.sql
-- SpecBox Engine — un criterio conserva su id para siempre y el retirado sigue visible (US-125 · UC-12501).
--
-- Hasta ahora delete_ac borraba el criterio y renumeraba los siguientes borrándolos y creándolos de
-- nuevo: AC-04 pasaba a llamarse AC-03 y perdía su veredicto y sus recibos. Lo que se aceptaba al
-- final ya no era lo que se pidió con ese id.
--
-- Qué deja esta migración:
--   * acceptance_criteria_retired: los criterios retirados, con su texto, su veredicto y sus recibos
--     (meta), el motivo, quién y cuándo. Una tabla aparte y no una columna: el panel, el portal, la app,
--     el site y las vistas del engine leen acceptance_criteria, y así sus totales no cambian.
--   * trg_ac_reject_retired_id: un id retirado no se vuelve a usar en su UC, lo escriba quien lo
--     escriba (una herramienta, una migración o SQL a mano).
--   * Cerrada a los roles públicos como el resto del board (0024): la escribe y la lee el servidor.
--
-- No mueve ninguna fila: los totales de criterios de cada proyecto son los mismos antes y después.
-- Idempotente: CREATE ... IF NOT EXISTS, CREATE OR REPLACE y DROP ... IF EXISTS.

CREATE TABLE IF NOT EXISTS acceptance_criteria_retired (
    project_id  TEXT NOT NULL,
    uc_id       TEXT NOT NULL,
    ac_id       TEXT NOT NULL,
    text        TEXT NOT NULL,
    internal    BOOLEAN NOT NULL DEFAULT false,
    done        BOOLEAN NOT NULL DEFAULT false,
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason      TEXT NOT NULL CHECK (char_length(btrim(reason)) > 0),
    retired_by  TEXT NULL,
    retired_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, uc_id, ac_id),
    FOREIGN KEY (project_id, uc_id) REFERENCES use_cases (project_id, id) ON DELETE CASCADE
);

COMMENT ON TABLE acceptance_criteria_retired IS
    'Criterios retirados de su UC (UC-12501): siguen visibles y su id no se reutiliza. No cuentan en los totales.';

CREATE OR REPLACE FUNCTION ac_reject_retired_id() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM acceptance_criteria_retired r
         WHERE r.project_id = NEW.project_id AND r.uc_id = NEW.uc_id AND r.ac_id = NEW.ac_id
    ) THEN
        RAISE EXCEPTION 'El criterio % de % está retirado: su id no se vuelve a usar', NEW.ac_id, NEW.uc_id
            USING ERRCODE = 'unique_violation';
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_ac_reject_retired_id ON acceptance_criteria;
CREATE TRIGGER trg_ac_reject_retired_id
    BEFORE INSERT OR UPDATE OF ac_id, uc_id ON acceptance_criteria
    FOR EACH ROW EXECUTE FUNCTION ac_reject_retired_id();

DO $$
DECLARE
    has_anon CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon');
    has_auth CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated');
BEGIN
    ALTER TABLE public.acceptance_criteria_retired ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON TABLE public.acceptance_criteria_retired FROM PUBLIC;
    REVOKE ALL ON FUNCTION ac_reject_retired_id() FROM PUBLIC;
    IF has_anon THEN
        REVOKE ALL ON TABLE public.acceptance_criteria_retired FROM anon;
        REVOKE ALL ON FUNCTION ac_reject_retired_id() FROM anon;
    END IF;
    IF has_auth THEN
        REVOKE ALL ON TABLE public.acceptance_criteria_retired FROM authenticated;
        REVOKE ALL ON FUNCTION ac_reject_retired_id() FROM authenticated;
    END IF;
    IF has_anon AND has_auth THEN
        DROP POLICY IF EXISTS specbox_deny_anon_acceptance_criteria_retired ON public.acceptance_criteria_retired;
        CREATE POLICY specbox_deny_anon_acceptance_criteria_retired ON public.acceptance_criteria_retired
            AS RESTRICTIVE FOR ALL TO anon, authenticated USING (false) WITH CHECK (false);
    END IF;
END
$$;
