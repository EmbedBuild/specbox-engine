-- 0030_epics.sql
-- SpecBox Engine — la épica agrupa las historias (US-78 · UC-7801, decisión D20).
--
-- Hasta ahora no había nada por encima de la historia: las épicas vivían en la
-- prosa de los PRD y los milestones H1–H4 eran una etiqueta suelta en el meta de
-- cada UC que nadie usaba. Decisión de Jesús (2026-10-05): una épica con ficha
-- propia, y cada historia pertenece a una épica o a ninguna.
--
-- Qué deja esta migración:
--   * epics: una fila por épica (EP-NN único dentro del proyecto, nombre,
--     objetivo, enlace a su PRD o discovery, orden y fecha objetivo opcional).
--     Su estado y su avance no se guardan: se deducen de sus historias.
--   * user_stories.epic_id: la épica de cada historia, o NULL. La clave ajena
--     es compuesta (mismo proyecto, como 0009) y borrar una épica deja sus
--     historias sin épica sin tocar nada más: ON DELETE SET NULL (epic_id)
--     pone a NULL solo esa columna (Postgres 15+).
--   * Cerrada a los roles públicos, con seguridad por filas y la política
--     restrictiva de denegación, como el resto del board (0024, 0029).
--
-- Idempotente: CREATE ... IF NOT EXISTS, ADD COLUMN IF NOT EXISTS y la clave
-- ajena solo si no existe.

CREATE TABLE IF NOT EXISTS epics (
    project_id   TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    id           TEXT NOT NULL CHECK (id ~ '^EP-[0-9]+$'),
    name         TEXT NOT NULL CHECK (length(btrim(name)) > 0),
    objective    TEXT NOT NULL DEFAULT '',
    link         TEXT NOT NULL DEFAULT '',
    position     INTEGER NOT NULL DEFAULT 0,
    target_date  DATE,
    version      INTEGER NOT NULL DEFAULT 1,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, id)
);

COMMENT ON TABLE epics IS
    'Épicas del board (US-78, D20): agrupan historias; estado y avance se deducen de sus historias.';

ALTER TABLE user_stories ADD COLUMN IF NOT EXISTS epic_id TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'user_stories_epic_fk'
           AND conrelid = 'public.user_stories'::regclass
    ) THEN
        ALTER TABLE user_stories
            ADD CONSTRAINT user_stories_epic_fk
            FOREIGN KEY (project_id, epic_id) REFERENCES epics (project_id, id)
            ON DELETE SET NULL (epic_id);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS user_stories_epic_idx
    ON user_stories (project_id, epic_id) WHERE epic_id IS NOT NULL;

-- ── Cerrada a los roles públicos, como el resto del board (0024) ──────
DO $$
DECLARE
    has_anon CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon');
    has_auth CONSTANT boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated');
BEGIN
    ALTER TABLE public.epics ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON TABLE public.epics FROM PUBLIC;
    IF has_anon THEN
        REVOKE ALL ON TABLE public.epics FROM anon;
    END IF;
    IF has_auth THEN
        REVOKE ALL ON TABLE public.epics FROM authenticated;
    END IF;
    IF has_anon AND has_auth THEN
        DROP POLICY IF EXISTS specbox_deny_anon_epics ON public.epics;
        CREATE POLICY specbox_deny_anon_epics ON public.epics
            AS RESTRICTIVE FOR ALL TO anon, authenticated USING (false) WITH CHECK (false);
    END IF;
END
$$;
