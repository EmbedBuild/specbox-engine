-- 0037_review_verdicts_void.sql
-- SpecBox Engine — un veredicto de revisión caduca cuando la UC vuelve a trabajo (US-124 · UC-12402).
--
-- Con 0036 un «aceptada» seguía valiendo aunque la UC volviera a «en curso», se rehiciera y regresara
-- a revisión: merge-guard la dejaba fusionar con el visto bueno de un trabajo que ya no existía. Y un
-- «devuelta» anterior a la rehechura tapaba el visto bueno nuevo de una persona.
--
-- Qué deja esta migración:
--   * uc_review_verdicts.voided_at: cuándo caducó el veredicto (NULL = vigente). La fila se queda como
--     historia; la regla de la revisión independiente solo cuenta los vigentes.
--   * El trigger de estado de la UC (uc_acceptance_void_on_state, 0029 y 0036) caduca los veredictos
--     vigentes con la misma regla con la que anula la aceptación humana: al volver a trabajo (backlog,
--     user_stories, in_progress) desde revisión o hecha, o al reabrir una UC hecha. Pasar de revisión
--     a hecha no caduca nada. FreeForm aplica la misma regla en el meta de la UC (server/review.py,
--     voids_review).
--   * Un criterio que queda sin hacer anula la aceptación humana (0029) pero no caduca los veredictos:
--     esa UC ya no cierra ni fusiona por la medida closing_evidence, y la regla es la misma en FreeForm.
--
-- El API del panel escribe además (UC-12404): un «aceptada» de persona al aceptar, un «devuelta» de
-- persona al devolver, y caduca los «aceptada» de persona al retirar una aceptación.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS y CREATE OR REPLACE.

ALTER TABLE uc_review_verdicts ADD COLUMN IF NOT EXISTS voided_at TIMESTAMPTZ NULL;

COMMENT ON COLUMN uc_review_verdicts.voided_at IS
    'Cuándo caducó el veredicto (la UC volvió a trabajo o se retiró la aceptación); NULL = vigente.';

CREATE OR REPLACE FUNCTION uc_acceptance_void_on_state() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF (OLD.state IN ('review', 'done') AND NEW.state NOT IN ('review', 'done'))
       OR (OLD.state = 'done' AND NEW.state = 'review') THEN
        DELETE FROM uc_acceptances WHERE project_id = NEW.project_id AND uc_id = NEW.id;
        UPDATE uc_review_verdicts SET voided_at = now()
         WHERE project_id = NEW.project_id AND uc_id = NEW.id AND voided_at IS NULL;
    END IF;
    RETURN NULL;
END
$$;

REVOKE ALL ON FUNCTION uc_acceptance_void_on_state() FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION uc_acceptance_void_on_state() FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION uc_acceptance_void_on_state() FROM authenticated;
    END IF;
END
$$;
