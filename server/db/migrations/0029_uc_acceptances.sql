-- 0029_uc_acceptances.sql
-- SpecBox Engine — la aceptación humana de cada UC (US-76 · UC-7601).
--
-- Hasta ahora «aceptado» era el veredicto de mark_ac, firmado por el dueño del
-- token de la sesión: en autopilot, la persona aunque marcara el agente. La
-- métrica norte de D17 («% de UC cerradas con evidencia completa aceptada por
-- un humano») necesita una señal que solo dé una persona. Decisión de Jesús
-- (2026-10-04): la da el owner o un admin del proyecto, una vez por UC, con el
-- botón «Aceptar» del panel.
--
-- Qué deja esta migración:
--   * uc_acceptances: una fila por UC aceptada (quién y cuándo). La escribe
--     solo el API del panel, con su rol de servicio y tras comprobar la sesión
--     de la persona y su rol; ninguna tool del MCP la escribe
--     (tests/test_uc_acceptances.py lo comprueba). Sin privilegios para
--     PUBLIC, anon ni authenticated, con seguridad por filas y la política
--     restrictiva de denegación, como el resto del board (0024).
--     accepted_by_developer_id no lleva clave foránea, como audit_log: borrar
--     un developer no borra lo que aceptó.
--   * La aceptación se anula sola cuando deja de valer: si la UC sale de
--     «done», o si uno de sus criterios no internos queda sin hacer (se
--     desmarca, se añade uno nuevo sin hacer o uno interno pasa a ser visible
--     sin estar hecho). Lo que se aceptó ya no es lo que hay.
--
-- Idempotente: CREATE ... IF NOT EXISTS, CREATE OR REPLACE y DROP ... IF EXISTS.

CREATE TABLE IF NOT EXISTS uc_acceptances (
    project_id                TEXT NOT NULL,
    uc_id                     TEXT NOT NULL,
    accepted_by_developer_id  TEXT NOT NULL,
    accepted_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, uc_id),
    FOREIGN KEY (project_id, uc_id) REFERENCES use_cases (project_id, id) ON DELETE CASCADE
);

COMMENT ON TABLE uc_acceptances IS
    'Aceptación humana de una UC (US-76): la escribe solo el API del panel por una persona owner o admin del proyecto; se anula sola si la UC deja de estar hecha.';

-- ── Cerrada a los roles públicos, como el resto del board (0024) ──────
DO $$
DECLARE
    has_anon CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon');
    has_auth CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated');
BEGIN
    ALTER TABLE public.uc_acceptances ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON TABLE public.uc_acceptances FROM PUBLIC;
    IF has_anon THEN
        REVOKE ALL ON TABLE public.uc_acceptances FROM anon;
    END IF;
    IF has_auth THEN
        REVOKE ALL ON TABLE public.uc_acceptances FROM authenticated;
    END IF;
    IF has_anon AND has_auth THEN
        DROP POLICY IF EXISTS specbox_deny_anon_uc_acceptances ON public.uc_acceptances;
        CREATE POLICY specbox_deny_anon_uc_acceptances ON public.uc_acceptances
            AS RESTRICTIVE FOR ALL TO anon, authenticated USING (false) WITH CHECK (false);
    END IF;
END
$$;

-- ── La aceptación se anula cuando la UC sale de «done» ────────────────
CREATE OR REPLACE FUNCTION uc_acceptance_void_on_state() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF OLD.state = 'done' AND NEW.state IS DISTINCT FROM 'done' THEN
        DELETE FROM uc_acceptances WHERE project_id = NEW.project_id AND uc_id = NEW.id;
    END IF;
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_uc_acceptance_void_on_state ON use_cases;
CREATE TRIGGER trg_uc_acceptance_void_on_state
    AFTER UPDATE OF state ON use_cases
    FOR EACH ROW EXECUTE FUNCTION uc_acceptance_void_on_state();

-- ── …y cuando un criterio no interno queda sin hacer ──────────────────
CREATE OR REPLACE FUNCTION uc_acceptance_void_on_criterion() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    DELETE FROM uc_acceptances WHERE project_id = NEW.project_id AND uc_id = NEW.uc_id;
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_uc_acceptance_void_on_criterion ON acceptance_criteria;
CREATE TRIGGER trg_uc_acceptance_void_on_criterion
    AFTER INSERT OR UPDATE OF done, internal ON acceptance_criteria
    FOR EACH ROW WHEN (NOT NEW.done AND NOT NEW.internal)
    EXECUTE FUNCTION uc_acceptance_void_on_criterion();

-- ── Las funciones de los triggers, solo para el servidor (como en 0023) ─
-- Un trigger se ejecuta aunque quien escribe no tenga EXECUTE sobre su función.
REVOKE ALL ON FUNCTION uc_acceptance_void_on_state(), uc_acceptance_void_on_criterion() FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION uc_acceptance_void_on_state(), uc_acceptance_void_on_criterion() FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION uc_acceptance_void_on_state(), uc_acceptance_void_on_criterion() FROM authenticated;
    END IF;
END
$$;
