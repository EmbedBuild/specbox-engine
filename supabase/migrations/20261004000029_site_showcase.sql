-- 20261004000029_site_showcase.sql
-- SpecBox site — el escaparate en vivo de la home y la foto de actividad que cuadra
-- (US-70 / UC-7001, UC-7002).
--
-- POR QUÉ:
-- La home de specbox.build enseña un recibo real de nuestro propio board, la historia de
-- su UC y el progreso de unas historias. Los recibos del board llevan detalles internos
-- (referencias de infraestructura, notas del owner), así que la home no lee el board: lee
-- esta vista, que solo devuelve lo fijado a mano y solo lo que se puede publicar
-- (decisión de Jesús, 2026-10-04).
--
-- QUÉ HACE:
-- 1. `site_showcase_pin` (privada): qué UC y qué US del board EmbedBuild/specbox-manager se
--    pueden enseñar, en qué orden y, para una US, con qué título de negocio. Un CHECK
--    impide fijar nada de otro proyecto.
-- 2. `site_showcase_signer` (privada): el nombre público de quien acepta. Quien no está
--    aquí sale sin nombre (`null`), nunca con su identificador.
-- 3. `site_showcase` (pública, solo lectura, con los permisos de su dueño como
--    site_activity): de cada UC fijada, sus criterios (sin los internos) con el texto del
--    board y, de cada recibo, tipo, etiqueta, fecha, resultado y firma. El detalle del
--    recibo no sale nunca, y el enlace solo si apunta a specbox.build (o un subdominio) o
--    al repositorio público del engine. También su historia (cambios de estado). De cada
--    US fijada, cuántas de sus UC están hechas y cuántas cuentan (las archivadas no).
-- 4. `site_activity` publica los casos de uso por estado con TODOS los estados (los
--    archivados aparte), de modo que el total coincide con la suma. Hasta hoy contaba los
--    28 archivados en el total pero no en el desglose (UC-7002). Queda versionada por
--    primera vez, igual que `site_stats`: las dos se crearon con el MCP de Supabase.
-- 5. anon y authenticated solo pueden LEER las tres vistas (site_activity tenía también
--    INSERT, UPDATE, DELETE y TRUNCATE; fallaban por ser una vista no actualizable, pero
--    contradecían US-40) y no tienen ningún privilegio sobre las dos tablas.
--
-- CÓMO SE CAMBIA LO QUE SE ENSEÑA (con el rol de servicio, nunca desde el site):
--   INSERT INTO public.site_showcase_pin (kind, item_id, sort_order, business_title)
--   VALUES ('uc', 'UC-XXXX', 1, NULL) ON CONFLICT (project_id, kind, item_id) DO UPDATE
--   SET sort_order = excluded.sort_order, business_title = excluded.business_title;
--   DELETE FROM public.site_showcase_pin WHERE kind = 'uc' AND item_id = 'UC-XXXX';
-- Antes de fijar una UC, leer sus criterios y las etiquetas de sus recibos: salen tal
-- cual en la home.
--
-- Solo Supabase (migration_twins.yaml): objetos del site, no del esquema del board. La
-- cadena local mantiene cerradas todas las vistas de public (UC-4001).
-- Idempotente: se puede volver a aplicar.

-- ── 1. Lo que se puede enseñar ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.site_showcase_pin (
    project_id     text        NOT NULL DEFAULT 'EmbedBuild/specbox-manager',
    kind           text        NOT NULL,
    item_id        text        NOT NULL,
    sort_order     integer     NOT NULL DEFAULT 0,
    business_title text,
    pinned_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, kind, item_id),
    CONSTRAINT site_showcase_pin_only_our_board CHECK (project_id = 'EmbedBuild/specbox-manager'),
    CONSTRAINT site_showcase_pin_kind CHECK (kind IN ('uc', 'us'))
);

CREATE TABLE IF NOT EXISTS public.site_showcase_signer (
    developer_id text PRIMARY KEY REFERENCES public.developers (developer_id) ON DELETE CASCADE,
    public_name  text NOT NULL,
    CONSTRAINT site_showcase_signer_name CHECK (length(public_name) BETWEEN 1 AND 40)
);

ALTER TABLE public.site_showcase_pin ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.site_showcase_signer ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.site_showcase_pin, public.site_showcase_signer FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.site_showcase_pin, public.site_showcase_signer FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.site_showcase_pin, public.site_showcase_signer FROM authenticated;
    END IF;
END $$;

-- ── 2. La vista pública ──────────────────────────────────────────────

CREATE OR REPLACE VIEW public.site_showcase
WITH (security_invoker = false) AS
WITH pin AS (
    SELECT p.kind, p.item_id, p.sort_order, p.business_title
      FROM public.site_showcase_pin p
     WHERE p.project_id = 'EmbedBuild/specbox-manager'
)
SELECT 'uc'::text AS kind,
       pin.sort_order,
       uc.id AS item_id,
       regexp_replace(uc.name, '^UC-[0-9]+:\s*', '') AS title,
       pin.business_title,
       uc.state,
       uc.us_id,
       regexp_replace(regexp_replace(us.name, '^US-[0-9]+:\s*', ''), '\s*\[[^]]*\]\s*$', '') AS us_title,
       NULL::integer AS done,
       NULL::integer AS total,
       uc.started_at,
       uc.completed_at,
       COALESCE((
           SELECT jsonb_agg(jsonb_build_object(
                      'ac_id', ac.ac_id,
                      'text', ac.text,
                      'done', ac.done,
                      'accepted_at', CASE WHEN ac.meta -> 'verdict' ->> 'passed' = 'true'
                                          THEN ac.meta -> 'verdict' ->> 'at' END,
                      'accepted_by', CASE WHEN ac.meta -> 'verdict' ->> 'passed' = 'true'
                                          THEN (SELECT s.public_name FROM public.site_showcase_signer s
                                                 WHERE s.developer_id = ac.meta -> 'verdict' ->> 'by') END,
                      'evidence', COALESCE((
                          SELECT jsonb_agg(jsonb_build_object(
                                     'type', e ->> 'type',
                                     'label', e ->> 'label',
                                     'link', CASE WHEN e ->> 'link' ~ '^https://(([a-z0-9-]+\.)*specbox\.build|github\.com/EmbedBuild/specbox-engine)([/?#][^[:space:]]*)?$'
                                                  THEN e ->> 'link' END,
                                     'at', e ->> 'at',
                                     'by', (SELECT s.public_name FROM public.site_showcase_signer s
                                             WHERE s.developer_id = e ->> 'by'),
                                     'passed', CASE e ->> 'passed' WHEN 'true' THEN true WHEN 'false' THEN false END
                                 ) ORDER BY x.ord)
                            FROM jsonb_array_elements(
                                     CASE WHEN jsonb_typeof(ac.meta -> 'evidence') = 'array'
                                          THEN ac.meta -> 'evidence' ELSE '[]'::jsonb END
                                 ) WITH ORDINALITY AS x(e, ord)
                      ), '[]'::jsonb)
                  ) ORDER BY ac.ac_id)
             FROM public.acceptance_criteria ac
            WHERE ac.project_id = uc.project_id
              AND ac.uc_id = uc.id
              AND NOT COALESCE(ac.internal, false)
       ), '[]'::jsonb) AS criteria,
       COALESCE((
           SELECT jsonb_agg(jsonb_build_object(
                      'from', t.from_state,
                      'to', t.to_state,
                      'at', t.occurred_at,
                      'by', (SELECT s.public_name FROM public.site_showcase_signer s
                              WHERE s.developer_id = t.developer_id)
                  ) ORDER BY t.occurred_at)
             FROM public.uc_state_transitions t
            WHERE t.project_id = uc.project_id
              AND t.uc_id = uc.id
       ), '[]'::jsonb) AS history
  FROM pin
  JOIN public.use_cases uc
    ON uc.project_id = 'EmbedBuild/specbox-manager' AND uc.id = pin.item_id
  LEFT JOIN public.user_stories us
    ON us.project_id = uc.project_id AND us.id = uc.us_id
 WHERE pin.kind = 'uc'
UNION ALL
SELECT 'us'::text,
       pin.sort_order,
       us.id,
       regexp_replace(regexp_replace(us.name, '^US-[0-9]+:\s*', ''), '\s*\[[^]]*\]\s*$', ''),
       pin.business_title,
       us.state,
       us.id,
       NULL::text,
       counts.done,
       counts.total,
       NULL::timestamptz,
       NULL::timestamptz,
       '[]'::jsonb,
       '[]'::jsonb
  FROM pin
  JOIN public.user_stories us
    ON us.project_id = 'EmbedBuild/specbox-manager' AND us.id = pin.item_id
 CROSS JOIN LATERAL (
       SELECT (count(*) FILTER (WHERE u.state = 'done'))::integer AS done,
              (count(*) FILTER (WHERE u.state <> 'archived'))::integer AS total
         FROM public.use_cases u
        WHERE u.project_id = us.project_id AND u.us_id = us.id
 ) counts
 WHERE pin.kind = 'us';

COMMENT ON VIEW public.site_showcase IS
    'US-70 / UC-7001: lo fijado en site_showcase_pin del board EmbedBuild/specbox-manager, '
    'sin detalle de recibos y con enlaces solo a dominios públicos. Lectura pública.';

-- ── 3. Las cifras públicas que cuadran (UC-7002) ─────────────────────

CREATE OR REPLACE VIEW public.site_stats
WITH (security_invoker = false) AS
SELECT (SELECT count(*) FROM public.projects)            AS projects_count,
       (SELECT count(*) FROM public.user_stories)        AS user_stories_count,
       (SELECT count(*) FROM public.use_cases)           AS use_cases_count,
       (SELECT count(*) FROM public.acceptance_criteria) AS acceptance_criteria_count,
       (SELECT count(*) FROM public.organizations)       AS organizations_count,
       (SELECT count(*) FROM public.developers)          AS developers_count;

CREATE OR REPLACE VIEW public.site_activity
WITH (security_invoker = false) AS
SELECT (SELECT count(*) FROM public.projects)            AS projects_count,
       (SELECT count(*) FROM public.developers)          AS developers_count,
       (SELECT count(*) FROM public.user_stories)        AS user_stories_count,
       (SELECT count(*) FROM public.use_cases)           AS use_cases_count,
       (SELECT count(*) FROM public.acceptance_criteria) AS acceptance_criteria_count,
       (SELECT count(*) FROM public.organizations)       AS organizations_count,
       jsonb_build_object('backlog', 0, 'in_progress', 0, 'review', 0, 'done', 0)
           || COALESCE((SELECT jsonb_object_agg(s.state, s.n)
                          FROM (SELECT COALESCE(state, 'unknown') AS state, count(*) AS n
                                  FROM public.use_cases
                                 GROUP BY 1) s), '{}'::jsonb) AS uc_by_state,
       COALESCE((SELECT jsonb_agg(jsonb_build_object(
                            'week', to_char(weekly.wk::timestamptz, 'YYYY-MM-DD'),
                            'count', weekly.cnt) ORDER BY weekly.wk)
                   FROM (SELECT date_trunc('week', completed_at)::date AS wk, count(*) AS cnt
                           FROM public.use_cases
                          WHERE state = 'done'
                            AND completed_at IS NOT NULL
                            AND completed_at >= date_trunc('week', now()) - interval '49 days'
                          GROUP BY 1) weekly), '[]'::jsonb) AS throughput_8w,
       now() AS as_of;

-- ── 4. Solo lectura para los roles públicos ──────────────────────────

REVOKE ALL ON public.site_showcase, public.site_activity, public.site_stats FROM PUBLIC;
DO $$
DECLARE
    r text;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON public.site_showcase, public.site_activity, public.site_stats FROM %I', r);
            EXECUTE format('GRANT SELECT ON public.site_showcase, public.site_activity, public.site_stats TO %I', r);
        END IF;
    END LOOP;
END $$;

-- ── 5. Lo que se enseña al estrenar la home (2026-10-04) ─────────────

INSERT INTO public.site_showcase_pin (kind, item_id, sort_order, business_title) VALUES
    ('uc', 'UC-5301', 1, NULL),
    ('us', 'US-50', 1, 'Todas las direcciones de SpecBox, decididas y bajo specbox.build'),
    ('us', 'US-51', 2, 'El servidor del engine estrena dirección sin cortar a nadie'),
    ('us', 'US-52', 3, 'La web vive en specbox.build'),
    ('us', 'US-53', 4, 'El portal de clientes estrena dirección'),
    ('us', 'US-54', 5, 'Los correos salen y se contestan desde specbox.build')
ON CONFLICT (project_id, kind, item_id) DO NOTHING;

INSERT INTO public.site_showcase_signer (developer_id, public_name)
SELECT 'jesusperezdeveloper', 'Jesús'
 WHERE EXISTS (SELECT 1 FROM public.developers WHERE developer_id = 'jesusperezdeveloper')
ON CONFLICT (developer_id) DO NOTHING;
