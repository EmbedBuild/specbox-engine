-- 0038_uc_usage.sql
-- SpecBox Engine — el coste real de cada UC en tokens (US-124 · UC-12403).
--
-- Qué deja esta migración:
--   * uc_usage: los tokens que Claude Code informa (message.usage de la transcripción) de cada sesión
--     y cada subagente que trabajó en una UC. Una fila por UC, sesión y agente (agent_id '' = la
--     sesión principal); el hook uc-usage manda lo nuevo desde su último envío y la tool
--     report_uc_usage lo suma. Solo cifras e identificadores cortos: ninguna columna de texto libre,
--     nunca nada de la conversación (AC-04).
--   * Cerrada a los roles públicos como el resto del board (0024): la escribe y la lee el servidor.
--
-- Idempotente: CREATE ... IF NOT EXISTS y DROP POLICY IF EXISTS.

CREATE TABLE IF NOT EXISTS uc_usage (
    project_id                   TEXT NOT NULL,
    uc_id                        TEXT NOT NULL,
    session_id                   TEXT NOT NULL CHECK (session_id ~ '^[A-Za-z0-9-]{8,64}$'),
    agent_id                     TEXT NOT NULL DEFAULT '' CHECK (agent_id ~ '^[A-Za-z0-9_.:-]{0,128}$'),
    developer_id                 TEXT NULL,
    input_tokens                 BIGINT NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens                BIGINT NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    cache_creation_input_tokens  BIGINT NOT NULL DEFAULT 0 CHECK (cache_creation_input_tokens >= 0),
    cache_read_input_tokens      BIGINT NOT NULL DEFAULT 0 CHECK (cache_read_input_tokens >= 0),
    messages                     INTEGER NOT NULL DEFAULT 0 CHECK (messages >= 0),
    first_reported_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_reported_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, uc_id, session_id, agent_id),
    FOREIGN KEY (project_id, uc_id) REFERENCES use_cases (project_id, id) ON DELETE CASCADE
);

COMMENT ON TABLE uc_usage IS
    'Tokens reales de cada UC por sesión y subagente (UC-12403), del uso que informa Claude Code. Solo cifras.';

DO $$
DECLARE
    has_anon CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon');
    has_auth CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated');
BEGIN
    ALTER TABLE public.uc_usage ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON TABLE public.uc_usage FROM PUBLIC;
    IF has_anon THEN
        REVOKE ALL ON TABLE public.uc_usage FROM anon;
    END IF;
    IF has_auth THEN
        REVOKE ALL ON TABLE public.uc_usage FROM authenticated;
    END IF;
    IF has_anon AND has_auth THEN
        DROP POLICY IF EXISTS specbox_deny_anon_uc_usage ON public.uc_usage;
        CREATE POLICY specbox_deny_anon_uc_usage ON public.uc_usage
            AS RESTRICTIVE FOR ALL TO anon, authenticated USING (false) WITH CHECK (false);
    END IF;
END
$$;
