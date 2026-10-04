-- 20261004200030_site_north_star.sql
-- SpecBox site — la métrica norte y la aceptación de una persona (US-76 / UC-7606).
--
-- POR QUÉ:
-- La métrica norte de D17 es el «% de UC cerradas con evidencia completa aceptada por un
-- humano». Hasta US-76 no se podía medir: el veredicto de cada criterio lo firma el dueño
-- del token de la sesión, aunque marque el agente. Desde UC-7601 la aceptación la da una
-- persona en el panel (public.uc_acceptances) y el veredicto pasa a llamarse lo que es:
-- verificación. Decisión de Jesús (2026-10-04): la métrica cuenta las UC cerradas desde
-- que existe el botón, y la página dice desde cuándo. Se publica aunque no favorezca.
--
-- QUÉ HACE:
-- 1. `site_north_star_start` (privada, una sola fila): desde cuándo cuenta la métrica. Se
--    rellena con el rol de servicio el día que se despliega el botón del panel (UC-7604).
--    Mientras esté vacía, la métrica no se publica (`north_star` es null).
-- 2. `site_activity` añade `north_star`: desde cuándo, UC cerradas desde entonces, cuántas
--    tienen la evidencia completa (cada criterio no interno hecho y con un recibo que pasa),
--    cuántas además las aceptó una persona, y el porcentaje sobre las cerradas. Solo
--    recuentos de todo el ecosistema, nunca un identificador.
-- 3. `site_showcase`: de cada criterio, quién y cuándo lo verificó (`verified_by`,
--    `verified_at`; antes se llamaban accepted_*), y de la UC fijada, quién y cuándo la
--    aceptó (`accepted_by`, `accepted_at`), o nada. El nombre sale solo si la persona está
--    en site_showcase_signer, como el resto de firmas.
-- 4. anon y authenticated siguen pudiendo solo LEER las vistas, y no tienen ningún
--    privilegio sobre la tabla nueva.
--
-- CÓMO SE FIJA LA FECHA (con el rol de servicio, nunca desde el site):
--   INSERT INTO public.site_north_star_start (started_at) VALUES ('2026-10-0XT..:..:..Z')
--   ON CONFLICT (only_row) DO UPDATE SET started_at = excluded.started_at;
--
-- Solo Supabase (migration_twins.yaml), como 20261004000029_site_showcase.sql, que va antes.
-- Idempotente: se puede volver a aplicar.

-- ── 1. Desde cuándo cuenta la métrica ────────────────────────────────

CREATE TABLE IF NOT EXISTS public.site_north_star_start (
    only_row   boolean     PRIMARY KEY DEFAULT true,
    started_at timestamptz NOT NULL,
    CONSTRAINT site_north_star_start_one_row CHECK (only_row)
);

ALTER TABLE public.site_north_star_start ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.site_north_star_start FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.site_north_star_start FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.site_north_star_start FROM authenticated;
    END IF;
END $$;

-- ── 2. La métrica norte en site_activity ─────────────────────────────

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
       now() AS as_of,
       (SELECT jsonb_build_object(
                   'since', s.started_at,
                   'closed', n.closed,
                   'with_evidence', n.with_evidence,
                   'accepted', n.accepted,
                   'pct', CASE WHEN n.closed > 0 THEN round(100.0 * n.accepted / n.closed, 1) END)
          FROM public.site_north_star_start s
         CROSS JOIN LATERAL (
               SELECT count(*)::integer AS closed,
                      (count(*) FILTER (WHERE c.complete))::integer AS with_evidence,
                      (count(*) FILTER (WHERE c.complete AND c.accepted))::integer AS accepted
                 FROM (SELECT EXISTS (SELECT 1 FROM public.acceptance_criteria ac
                                       WHERE ac.project_id = uc.project_id AND ac.uc_id = uc.id
                                         AND NOT COALESCE(ac.internal, false))
                              AND NOT EXISTS (
                                  SELECT 1 FROM public.acceptance_criteria ac
                                   WHERE ac.project_id = uc.project_id AND ac.uc_id = uc.id
                                     AND NOT COALESCE(ac.internal, false)
                                     AND NOT (ac.done
                                              AND jsonb_typeof(ac.meta -> 'evidence') = 'array'
                                              AND EXISTS (SELECT 1
                                                            FROM jsonb_array_elements(ac.meta -> 'evidence') e
                                                           WHERE e ->> 'passed' = 'true'))) AS complete,
                              EXISTS (SELECT 1 FROM public.uc_acceptances a
                                       WHERE a.project_id = uc.project_id AND a.uc_id = uc.id) AS accepted
                         FROM public.use_cases uc
                        WHERE uc.state = 'done'
                          AND uc.completed_at >= s.started_at) c
         ) n) AS north_star;

COMMENT ON VIEW public.site_activity IS
    'US-27 / UC-7002 / UC-7606: recuentos públicos de actividad y la métrica norte desde '
    'site_north_star_start. Solo cifras, nunca un identificador. Lectura pública.';

-- ── 3. Verificada frente a aceptada en site_showcase ─────────────────

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
                      'verified_at', CASE WHEN ac.meta -> 'verdict' ->> 'passed' = 'true'
                                          THEN ac.meta -> 'verdict' ->> 'at' END,
                      'verified_by', CASE WHEN ac.meta -> 'verdict' ->> 'passed' = 'true'
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
       ), '[]'::jsonb) AS history,
       a.accepted_at,
       (SELECT s.public_name FROM public.site_showcase_signer s
         WHERE s.developer_id = a.accepted_by_developer_id) AS accepted_by
  FROM pin
  JOIN public.use_cases uc
    ON uc.project_id = 'EmbedBuild/specbox-manager' AND uc.id = pin.item_id
  LEFT JOIN public.user_stories us
    ON us.project_id = uc.project_id AND us.id = uc.us_id
  LEFT JOIN public.uc_acceptances a
    ON a.project_id = uc.project_id AND a.uc_id = uc.id
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
       '[]'::jsonb,
       NULL::timestamptz,
       NULL::text
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
    'US-70 / UC-7001 / UC-7606: lo fijado en site_showcase_pin del board EmbedBuild/specbox-manager, '
    'sin detalle de recibos, con enlaces solo a dominios públicos, quién verificó cada criterio y '
    'quién aceptó la UC. Lectura pública.';

-- ── 4. Solo lectura para los roles públicos ──────────────────────────

REVOKE ALL ON public.site_showcase, public.site_activity FROM PUBLIC;
DO $$
DECLARE
    r text;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON public.site_showcase, public.site_activity FROM %I', r);
            EXECUTE format('GRANT SELECT ON public.site_showcase, public.site_activity TO %I', r);
        END IF;
    END LOOP;
END $$;
