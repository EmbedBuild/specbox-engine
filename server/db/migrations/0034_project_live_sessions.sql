-- 0034_project_live_sessions.sql
-- SpecBox Engine — todas las sesiones vivas de un proyecto, no solo la última (US-99 · UC-10609).
--
-- Los satélites del ecosistema (manager, cloud, site, projects, mobile) escriben su latido en el
-- board del orquestador. v_live_sessions (0031) da una sola sesión por proyecto, la del último
-- latido: con dos sesiones en paralelo, el panel y la app solo veían la más reciente.
--
-- Qué deja esta migración:
--   * v_project_live_sessions: cada sesión sin terminar del proyecto que ha mandado latido en los
--     últimos quince minutos, con su UC, su fase y si espera respuesta (AC-01). Una sesión cerrada,
--     o sin latido en quince minutos, no aparece (AC-02): el barrido close_stale_sessions() la cierra
--     en los cinco minutos siguientes. El orden lo pone quien consulta (por last_beat_at, de la más
--     reciente a la más antigua), con el índice idx_session_heartbeats_live de 0031.
--   * v_live_sessions no cambia: la siguen leyendo get_live_session, el vistazo, el Inicio del
--     teléfono y la ficha del panel, que esperan una fila por proyecto y su marca «sin señal».
--
-- Corre con los derechos de quien consulta (0023) y solo la leen el servidor y el panel con su rol
-- de servicio, que aplican la pertenencia, como v_live_sessions.
--
-- Idempotente: CREATE OR REPLACE.

-- CREATE OR REPLACE VIEW borra las opciones de la vista: se repite security_invoker (0023).
CREATE OR REPLACE VIEW v_project_live_sessions WITH (security_invoker = on) AS
SELECT h.project_id,
       h.session_id,
       h.developer_id,
       h.uc_id,
       h.phase,
       h.waiting,
       h.waiting_since,
       h.started_at,
       h.last_beat_at
FROM session_heartbeats h
WHERE h.ended_at IS NULL
  AND h.last_beat_at >= now() - interval '15 minutes';

COMMENT ON VIEW v_project_live_sessions IS
    'Todas las sesiones vivas de cada proyecto (US-99 · UC-10609): sin terminar y con latido en los últimos 15 minutos; v_live_sessions da solo la última.';

DO $$
BEGIN
    REVOKE ALL ON public.v_project_live_sessions FROM PUBLIC;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.v_project_live_sessions FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.v_project_live_sessions FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT ON public.v_project_live_sessions TO service_role;
    END IF;
END
$$;
