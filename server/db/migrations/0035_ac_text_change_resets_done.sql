-- 0035_ac_text_change_resets_done.sql
-- SpecBox Engine — un criterio hecho que se reescribe queda pendiente de comprobar (US-117 · UC-11701).
--
-- Hasta ahora update_ac cambiaba el texto de un criterio hecho sin desmarcarlo, y la aceptación
-- humana de su UC (0029) seguía en pie: lo que se aceptó ya no era lo que hay. Decisión de Jesús
-- (2026-11-10): se invalida por eventos, y reescribir un criterio es uno de ellos.
--
-- Qué deja esta migración:
--   * trg_ac_text_change_resets_done (BEFORE UPDATE OF text): si un criterio hecho cambia de texto,
--     queda sin hacer y su último veredicto pasa a «no pasa» con el motivo (text_changed), quién lo
--     cambió (app.developer_id, si la sesión lo puso) y el texto anterior. El veredicto en «no pasa»
--     impide que una verificación antigua reaparezca si alguien vuelve a poner el criterio hecho sin
--     mark_ac. Los justificantes (meta.evidence) se conservan como historial.
--   * trg_uc_acceptance_void_on_criterion se dispara también con UPDATE OF text. Postgres decide qué
--     trigger «UPDATE OF» corre por las columnas del SET, no por lo que cambie un trigger BEFORE: un
--     «SET text = …» deja el criterio sin hacer, pero sin esto no anularía la aceptación.
--   * Vale para cualquier escritor: update_ac, import_spec o SQL directo. Un UPDATE con el mismo
--     texto no cambia nada.
--
-- Idempotente: CREATE OR REPLACE y DROP TRIGGER IF EXISTS.

CREATE OR REPLACE FUNCTION ac_text_change_resets_done() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    NEW.done := false;
    NEW.meta := COALESCE(NEW.meta, '{}'::jsonb) || jsonb_build_object(
        'verdict', jsonb_build_object(
            'passed', false,
            'by', NULLIF(current_setting('app.developer_id', true), ''),
            'at', now(),
            'reason', 'text_changed',
            'previous_text', OLD.text
        )
    );
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_ac_text_change_resets_done ON acceptance_criteria;
CREATE TRIGGER trg_ac_text_change_resets_done
    BEFORE UPDATE OF text ON acceptance_criteria
    FOR EACH ROW WHEN (OLD.text IS DISTINCT FROM NEW.text AND OLD.done)
    EXECUTE FUNCTION ac_text_change_resets_done();

-- La función de anulación es la de 0029; solo cambia cuándo se dispara.
DROP TRIGGER IF EXISTS trg_uc_acceptance_void_on_criterion ON acceptance_criteria;
CREATE TRIGGER trg_uc_acceptance_void_on_criterion
    AFTER INSERT OR UPDATE OF done, internal, text ON acceptance_criteria
    FOR EACH ROW WHEN (NOT NEW.done AND NOT NEW.internal)
    EXECUTE FUNCTION uc_acceptance_void_on_criterion();

-- ── La función del trigger, solo para el servidor (como en 0029) ──────
REVOKE ALL ON FUNCTION ac_text_change_resets_done() FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION ac_text_change_resets_done() FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION ac_text_change_resets_done() FROM authenticated;
    END IF;
END
$$;
