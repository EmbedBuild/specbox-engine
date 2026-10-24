-- 0031_session_heartbeats.sql
-- SpecBox Engine — el latido de cada sesión de Claude Code en el board (US-99 · UC-9901).
--
-- La app del teléfono y la ficha del panel enseñan qué hace cada sesión ahora: en qué proyecto,
-- con qué UC, en qué fase y si espera una decisión o un permiso. El latido anterior
-- (report_heartbeat, v5.x) escribía en el disco del servidor del MCP, sin desarrollador y sin
-- lectores, y nadie lo enviaba desde la v6.1.0. Este vive en el board.
--
-- Qué deja esta migración:
--   * session_heartbeats: una fila por sesión (proyecto + id de sesión de Claude Code). La
--     escribe solo la tool report_session_heartbeat, con la identidad del token y tras comprobar
--     que quien la manda es miembro del proyecto. Solo campos enumerados o de forma fija y con
--     longitud máxima: nunca texto de la conversación ni de las specs (AC-01). Sin privilegios
--     para PUBLIC, anon ni authenticated, con seguridad por filas y la denegación restrictiva del
--     resto del board (0024, 0029).
--   * v_live_sessions: la sesión más reciente sin terminar de cada proyecto, con `stale` cuando
--     lleva más de quince minutos sin latido. Corre con los derechos de quien consulta (0023) y
--     solo la leen el servidor y el panel con su rol de servicio, que aplican la pertenencia.
--   * close_stale_sessions(): da por terminadas, con ended_reason = 'timeout', las sesiones sin
--     latido desde hace quince minutos; pg_cron la ejecuta cada cinco (AC-02).
--
-- Idempotente: CREATE ... IF NOT EXISTS, CREATE OR REPLACE y DROP ... IF EXISTS.

CREATE TABLE IF NOT EXISTS session_heartbeats (
    project_id     TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    -- El id de sesión de Claude Code (un UUID); nunca texto libre.
    session_id     TEXT NOT NULL CHECK (session_id ~ '^[A-Za-z0-9-]{8,64}$'),
    developer_id   TEXT NOT NULL CHECK (char_length(developer_id) <= 200),
    uc_id          TEXT CHECK (uc_id IS NULL OR uc_id ~ '^UC-[0-9]{1,6}[a-z]?$'),
    phase          TEXT NOT NULL CHECK (phase IN (
                       'idle', 'discovery', 'prd', 'plan', 'design', 'implement', 'tests', 'review', 'release')),
    waiting        TEXT NOT NULL DEFAULT 'none' CHECK (waiting IN ('none', 'decision', 'permission')),
    waiting_since  TIMESTAMPTZ,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_beat_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at       TIMESTAMPTZ,
    ended_reason   TEXT CHECK (ended_reason IS NULL OR ended_reason IN ('closed', 'timeout')),
    PRIMARY KEY (project_id, session_id),
    CHECK ((ended_at IS NULL) = (ended_reason IS NULL)),
    CHECK ((waiting = 'none') = (waiting_since IS NULL))
);

COMMENT ON TABLE session_heartbeats IS
    'Latido de cada sesión de Claude Code (US-99 · UC-9901): proyecto, desarrollador, UC, fase y si espera; la escribe solo report_session_heartbeat y se cierra sola a los 15 minutos sin latido.';

CREATE INDEX IF NOT EXISTS idx_session_heartbeats_live
    ON session_heartbeats (project_id, last_beat_at DESC)
    WHERE ended_at IS NULL;

-- ── Cerrada a los roles públicos, como el resto del board (0024) ──────
DO $$
DECLARE
    has_anon CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon');
    has_auth CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated');
BEGIN
    ALTER TABLE public.session_heartbeats ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON TABLE public.session_heartbeats FROM PUBLIC;
    IF has_anon THEN
        REVOKE ALL ON TABLE public.session_heartbeats FROM anon;
    END IF;
    IF has_auth THEN
        REVOKE ALL ON TABLE public.session_heartbeats FROM authenticated;
    END IF;
    IF has_anon AND has_auth THEN
        DROP POLICY IF EXISTS specbox_deny_anon_session_heartbeats ON public.session_heartbeats;
        CREATE POLICY specbox_deny_anon_session_heartbeats ON public.session_heartbeats
            AS RESTRICTIVE FOR ALL TO anon, authenticated USING (false) WITH CHECK (false);
    END IF;
END
$$;

-- ── La sesión viva de cada proyecto ───────────────────────────────────
-- CREATE OR REPLACE VIEW borra las opciones de la vista: se repite security_invoker (0023).
CREATE OR REPLACE VIEW v_live_sessions WITH (security_invoker = on) AS
SELECT DISTINCT ON (h.project_id)
       h.project_id,
       h.session_id,
       h.developer_id,
       h.uc_id,
       h.phase,
       h.waiting,
       h.waiting_since,
       h.started_at,
       h.last_beat_at,
       (h.last_beat_at < now() - interval '15 minutes') AS stale
FROM session_heartbeats h
WHERE h.ended_at IS NULL
ORDER BY h.project_id, h.last_beat_at DESC;

DO $$
BEGIN
    REVOKE ALL ON public.v_live_sessions FROM PUBLIC;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.v_live_sessions FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.v_live_sessions FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT ON public.v_live_sessions TO service_role;
    END IF;
END
$$;

-- ── Ninguna sesión queda viva para siempre (AC-02) ────────────────────
-- CREATE OR REPLACE FUNCTION borra su SET: se repite search_path (0023).
CREATE OR REPLACE FUNCTION close_stale_sessions(p_after interval DEFAULT interval '15 minutes')
RETURNS integer
LANGUAGE sql
SET search_path = public, pg_temp
AS $$
    WITH cerradas AS (
        UPDATE session_heartbeats
           SET ended_at = now(), ended_reason = 'timeout', waiting = 'none', waiting_since = NULL
         WHERE ended_at IS NULL AND last_beat_at < now() - p_after
        RETURNING 1
    )
    SELECT count(*)::integer FROM cerradas;
$$;

REVOKE ALL ON FUNCTION public.close_stale_sessions(interval) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION public.close_stale_sessions(interval) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION public.close_stale_sessions(interval) FROM authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT EXECUTE ON FUNCTION public.close_stale_sessions(interval) TO service_role;
    END IF;
END
$$;

-- Cada cinco minutos donde exista pg_cron (Supabase). Con el mismo nombre, cron.schedule
-- sustituye el trabajo anterior: reaplicar deja exactamente uno (0027).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron') THEN
        CREATE EXTENSION IF NOT EXISTS pg_cron;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
        PERFORM cron.schedule(
            'close-stale-sessions',
            '*/5 * * * *',
            'SELECT public.close_stale_sessions()'
        );
    END IF;
END $$;
