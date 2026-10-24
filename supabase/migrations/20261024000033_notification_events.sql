-- 0033_notification_events.sql
-- SpecBox Engine — los eventos que merecen un aviso en el teléfono (US-100 · UC-10001).
--
-- La app de SpecBox avisa de lo que avanza y de lo que necesita a la persona. Esta migración deja
-- que el board apunte esos eventos en el mismo momento del cambio, con una sola fila por cambio:
--
--   * notification_events: proyecto, tipo, objetivo (una UC o una US, o ninguno) y hora. Sin texto de
--     specs ni datos personales: el panel arma el aviso con el tipo, el nombre del proyecto y el
--     identificador (US-100 · UC-10002 AC-04). `event_key` es la identidad del cambio y es única por
--     proyecto: repetir, reintentar o volver a disparar el mismo cambio no crea otro evento (AC-02).
--     `dispatched_at` lo pone el panel cuando reparte el evento a los dispositivos.
--   * Cinco triggers, en la misma transacción que el cambio (AC-01):
--       - uc_done          una UC pasa a hecha (cada transición registrada en uc_state_transitions);
--       - us_done          una historia pasa a hecha;
--       - uc_ready         una UC queda lista para aceptar: hecha, sin aceptación, con criterios
--                          visibles y todos hechos con un recibo que pasa (la regla de
--                          v_uc_ready_to_accept del panel), una vez por cada vez que se completa;
--       - session_waiting  una sesión pasa a esperar una respuesta en el terminal (waiting = decision);
--       - session_stopped  una sesión con una UC abierta se cierra por tiempo (15 minutos sin latido).
--
-- Cerrada a los roles públicos, como el resto del board (0024, 0029). Las funciones de los triggers
-- son SECURITY DEFINER para que el evento se apunte escriba quien escriba el cambio, y nadie más
-- las puede ejecutar.
--
-- Idempotente: CREATE ... IF NOT EXISTS, CREATE OR REPLACE y DROP ... IF EXISTS.

CREATE TABLE IF NOT EXISTS notification_events (
    id             BIGSERIAL PRIMARY KEY,
    project_id     TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    kind           TEXT NOT NULL CHECK (kind IN ('uc_done', 'us_done', 'uc_ready', 'session_waiting', 'session_stopped')),
    -- El id de la UC o la US tal como está en el board (hay boards con ids libres: «UC-A», «US-VSCODE-…»).
    target_id      TEXT CHECK (target_id IS NULL OR char_length(target_id) <= 64),
    event_key      TEXT NOT NULL CHECK (char_length(event_key) <= 160),
    occurred_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    dispatched_at  TIMESTAMPTZ,
    UNIQUE (project_id, event_key)
);

COMMENT ON TABLE notification_events IS
    'Eventos de aviso del board (US-100 · UC-10001): proyecto, tipo, objetivo y hora, uno por cambio (event_key). Sin texto de specs ni datos personales; el panel los reparte (dispatched_at).';

-- La restricción del objetivo se rehace siempre: una base que aplicó una versión anterior de esta
-- migración (con un patrón más estricto) queda igual que una nueva.
ALTER TABLE notification_events DROP CONSTRAINT IF EXISTS notification_events_target_id_check;
ALTER TABLE notification_events ADD CONSTRAINT notification_events_target_id_check
    CHECK (target_id IS NULL OR char_length(target_id) <= 64);

CREATE INDEX IF NOT EXISTS idx_notification_events_pending
    ON notification_events (occurred_at)
    WHERE dispatched_at IS NULL;

-- ── Cerrada a los roles públicos, como el resto del board (0024) ──────
DO $$
DECLARE
    has_anon CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon');
    has_auth CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated');
BEGIN
    ALTER TABLE public.notification_events ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON TABLE public.notification_events FROM PUBLIC;
    REVOKE ALL ON SEQUENCE public.notification_events_id_seq FROM PUBLIC;
    IF has_anon THEN
        REVOKE ALL ON TABLE public.notification_events FROM anon;
        REVOKE ALL ON SEQUENCE public.notification_events_id_seq FROM anon;
    END IF;
    IF has_auth THEN
        REVOKE ALL ON TABLE public.notification_events FROM authenticated;
        REVOKE ALL ON SEQUENCE public.notification_events_id_seq FROM authenticated;
    END IF;
    IF has_anon AND has_auth THEN
        DROP POLICY IF EXISTS specbox_deny_anon_notification_events ON public.notification_events;
        CREATE POLICY specbox_deny_anon_notification_events ON public.notification_events
            AS RESTRICTIVE FOR ALL TO anon, authenticated USING (false) WITH CHECK (false);
    END IF;
END
$$;

-- ── Apuntar un evento: una sola fila por cambio ───────────────────────
-- Un aviso nunca bloquea una escritura del board: si el evento no se puede apuntar (un id que no
-- cabe, una clave demasiado larga…), se deja un WARNING en el log y el cambio sigue adelante.
CREATE OR REPLACE FUNCTION notification_event_add(p_project TEXT, p_kind TEXT, p_target TEXT, p_key TEXT)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    INSERT INTO notification_events (project_id, kind, target_id, event_key)
    VALUES (p_project, p_kind, p_target, p_kind || ':' || p_key)
    ON CONFLICT (project_id, event_key) DO NOTHING;
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'notification_events: % % no apuntado (%)', p_kind, p_target, SQLSTATE;
END
$$;

-- ── La regla de «lista para aceptar», para una sola UC ────────────────
-- La misma que v_uc_ready_to_accept del panel: hecha, sin aceptación, con al menos un criterio
-- visible y todos los visibles hechos con un recibo que pasa.
CREATE OR REPLACE FUNCTION uc_ready_to_accept(p_project TEXT, p_uc TEXT)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT EXISTS (
        SELECT 1
          FROM use_cases uc
         WHERE uc.project_id = p_project AND uc.id = p_uc AND uc.state = 'done'
           AND NOT EXISTS (SELECT 1 FROM uc_acceptances a WHERE a.project_id = uc.project_id AND a.uc_id = uc.id)
           AND EXISTS (SELECT 1 FROM acceptance_criteria c
                        WHERE c.project_id = uc.project_id AND c.uc_id = uc.id AND NOT COALESCE(c.internal, false))
           AND NOT EXISTS (
               SELECT 1 FROM acceptance_criteria c
                WHERE c.project_id = uc.project_id AND c.uc_id = uc.id AND NOT COALESCE(c.internal, false)
                  AND (NOT c.done OR NOT jsonb_path_exists(COALESCE(c.meta, '{}'::jsonb),
                                                           '$."evidence"[*] ? (@."passed" == true)')))
    );
$$;

CREATE OR REPLACE FUNCTION notification_uc_ready_check(p_project TEXT, p_uc TEXT)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_completed TIMESTAMPTZ;
BEGIN
    IF NOT uc_ready_to_accept(p_project, p_uc) THEN
        RETURN;
    END IF;
    SELECT completed_at INTO v_completed FROM use_cases WHERE project_id = p_project AND id = p_uc;
    -- Una vez por cada vez que la UC se completa (completed_at cambia al volver a «done»).
    PERFORM notification_event_add(p_project, 'uc_ready', p_uc,
        p_uc || ':' || COALESCE(to_char(v_completed AT TIME ZONE 'UTC', 'YYYYMMDD"T"HH24MISS.US'), 'sin-fecha'));
END
$$;

-- ── uc_done: cada transición a «done» ─────────────────────────────────
CREATE OR REPLACE FUNCTION notification_on_uc_transition() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM notification_event_add(NEW.project_id, 'uc_done', NEW.uc_id, NEW.uc_id || ':' || NEW.id);
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_notification_uc_done ON uc_state_transitions;
CREATE TRIGGER trg_notification_uc_done
    AFTER INSERT ON uc_state_transitions
    FOR EACH ROW WHEN (NEW.to_state = 'done')
    EXECUTE FUNCTION notification_on_uc_transition();

-- ── uc_ready: al pasar a «done» y al cambiar sus criterios ────────────
CREATE OR REPLACE FUNCTION notification_on_uc_state() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM notification_uc_ready_check(NEW.project_id, NEW.id);
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_notification_uc_ready_state ON use_cases;
CREATE TRIGGER trg_notification_uc_ready_state
    AFTER UPDATE OF state ON use_cases
    FOR EACH ROW WHEN (NEW.state = 'done' AND OLD.state IS DISTINCT FROM NEW.state)
    EXECUTE FUNCTION notification_on_uc_state();

CREATE OR REPLACE FUNCTION notification_on_criterion() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM notification_uc_ready_check(NEW.project_id, NEW.uc_id);
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_notification_uc_ready_criterion ON acceptance_criteria;
CREATE TRIGGER trg_notification_uc_ready_criterion
    AFTER INSERT OR UPDATE OF done, meta, internal ON acceptance_criteria
    FOR EACH ROW
    EXECUTE FUNCTION notification_on_criterion();

-- ── us_done: una historia pasa a «done» ───────────────────────────────
CREATE OR REPLACE FUNCTION notification_on_us_state() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    -- Un cierre por transacción: si la misma transacción la cierra dos veces, un solo evento.
    PERFORM notification_event_add(NEW.project_id, 'us_done', NEW.id, NEW.id || ':' || txid_current());
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_notification_us_done ON user_stories;
CREATE TRIGGER trg_notification_us_done
    AFTER UPDATE OF state ON user_stories
    FOR EACH ROW WHEN (NEW.state = 'done' AND OLD.state IS DISTINCT FROM NEW.state)
    EXECUTE FUNCTION notification_on_us_state();

-- ── session_waiting y session_stopped: el latido de la sesión (0031) ──
CREATE OR REPLACE FUNCTION notification_on_session() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.waiting = 'decision'
       AND (TG_OP = 'INSERT' OR OLD.waiting IS DISTINCT FROM NEW.waiting) THEN
        PERFORM notification_event_add(NEW.project_id, 'session_waiting', NEW.uc_id,
            NEW.session_id || ':' || to_char(NEW.waiting_since AT TIME ZONE 'UTC', 'YYYYMMDD"T"HH24MISS.US'));
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.ended_reason = 'timeout' AND OLD.ended_at IS NULL AND NEW.uc_id IS NOT NULL THEN
        PERFORM notification_event_add(NEW.project_id, 'session_stopped', NEW.uc_id, NEW.session_id);
    END IF;
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS trg_notification_session ON session_heartbeats;
CREATE TRIGGER trg_notification_session
    AFTER INSERT OR UPDATE ON session_heartbeats
    FOR EACH ROW
    EXECUTE FUNCTION notification_on_session();

-- ── Las funciones, solo para el servidor (como en 0023 y 0029) ────────
-- Un trigger se ejecuta aunque quien escribe no tenga EXECUTE sobre su función.
DO $$
DECLARE
    fns CONSTANT text := 'notification_event_add(text, text, text, text), uc_ready_to_accept(text, text), '
        || 'notification_uc_ready_check(text, text), notification_on_uc_transition(), notification_on_uc_state(), '
        || 'notification_on_criterion(), notification_on_us_state(), notification_on_session()';
BEGIN
    EXECUTE 'REVOKE ALL ON FUNCTION ' || fns || ' FROM PUBLIC';
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON FUNCTION ' || fns || ' FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        EXECUTE 'REVOKE ALL ON FUNCTION ' || fns || ' FROM authenticated';
    END IF;
END
$$;
