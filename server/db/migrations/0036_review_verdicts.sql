-- 0036_review_verdicts.sql
-- SpecBox Engine — quien implementa no da el visto bueno a su propio trabajo (US-124 · UC-12402).
--
-- Qué deja esta migración:
--   * uc_review_verdicts: cada veredicto de revisión de una UC («aceptada» o «devuelta»), con quién
--     lo dio (una persona desde el panel o un agente por MCP), desde qué contexto (sesión y agente de
--     Claude Code, que pone un hook) y si era independiente de quien implementó. La escriben la tool
--     record_review_verdict del MCP (agentes) y el API del panel (personas, UC-12404), con el rol de
--     servicio. Cerrada a los roles públicos como el resto del board (0024).
--   * La aceptación humana (uc_acceptances, 0029) vale ya desde la revisión: una persona acepta una
--     UC en revisión antes de que se fusione su PR. Se anula al volver a trabajo (backlog, user_stories,
--     in_progress) o al reabrir una UC hecha, no al pasar de revisión a hecha.
--
-- Idempotente: CREATE ... IF NOT EXISTS, CREATE OR REPLACE y DROP ... IF EXISTS.

CREATE TABLE IF NOT EXISTS uc_review_verdicts (
    id            BIGSERIAL PRIMARY KEY,
    project_id    TEXT NOT NULL,
    uc_id         TEXT NOT NULL,
    verdict       TEXT NOT NULL CHECK (verdict IN ('accepted', 'returned')),
    by_kind       TEXT NOT NULL CHECK (by_kind IN ('person', 'agent')),
    developer_id  TEXT NULL,
    session_id    TEXT NULL CHECK (session_id IS NULL OR length(session_id) <= 128),
    agent_id      TEXT NULL CHECK (agent_id IS NULL OR length(agent_id) <= 128),
    agent_type    TEXT NULL CHECK (agent_type IS NULL OR length(agent_type) <= 128),
    independent   BOOLEAN NOT NULL DEFAULT false,
    reason        TEXT NULL CHECK (reason IS NULL OR length(reason) <= 500),
    at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (project_id, uc_id) REFERENCES use_cases (project_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_uc_review_verdicts_uc
    ON uc_review_verdicts (project_id, uc_id, at DESC);

COMMENT ON TABLE uc_review_verdicts IS
    'Veredictos de revisión de una UC (UC-12402): persona (panel) o agente (MCP), con su contexto y si era independiente de quien implementó.';

-- ── Cerrada a los roles públicos, como el resto del board (0024) ──────
DO $$
DECLARE
    has_anon CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon');
    has_auth CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated');
BEGIN
    ALTER TABLE public.uc_review_verdicts ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON TABLE public.uc_review_verdicts FROM PUBLIC;
    REVOKE ALL ON SEQUENCE public.uc_review_verdicts_id_seq FROM PUBLIC;
    IF has_anon THEN
        REVOKE ALL ON TABLE public.uc_review_verdicts FROM anon;
        REVOKE ALL ON SEQUENCE public.uc_review_verdicts_id_seq FROM anon;
    END IF;
    IF has_auth THEN
        REVOKE ALL ON TABLE public.uc_review_verdicts FROM authenticated;
        REVOKE ALL ON SEQUENCE public.uc_review_verdicts_id_seq FROM authenticated;
    END IF;
    IF has_anon AND has_auth THEN
        DROP POLICY IF EXISTS specbox_deny_anon_uc_review_verdicts ON public.uc_review_verdicts;
        CREATE POLICY specbox_deny_anon_uc_review_verdicts ON public.uc_review_verdicts
            AS RESTRICTIVE FOR ALL TO anon, authenticated USING (false) WITH CHECK (false);
    END IF;
END
$$;

-- ── La aceptación humana vale desde la revisión (sustituye la función de 0029) ─
CREATE OR REPLACE FUNCTION uc_acceptance_void_on_state() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF (OLD.state IN ('review', 'done') AND NEW.state NOT IN ('review', 'done'))
       OR (OLD.state = 'done' AND NEW.state = 'review') THEN
        DELETE FROM uc_acceptances WHERE project_id = NEW.project_id AND uc_id = NEW.id;
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
