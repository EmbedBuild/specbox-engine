-- Bytes que cada tool del board pide a Postgres: antes de UC-8901 (`main`) y después.
--
-- US-89 / UC-8901. Solo lectura y sin sacar filas de la base: devuelve una fila
-- por tool con los bytes de las filas que lee cada versión, medidos como el texto
-- de cada fila (octet_length(fila::text)), que sigue de cerca lo que cruza el
-- pooler. Cambia el proyecto en `params`.
--
--   psql "$SPECBOX_NATIVE_DSN" -f scripts/measure-board-reads.sql
--
-- Antes: list_items lee US, UC y AC enteros (SELECT *); get_uc lo hace para
-- encontrar una UC; list_us, list_uc, get_sprint_status y get_delivery_report
-- leen además los criterios de cada UC solo para contarlos.
-- Después: las tools de una UC o una historia leen esa historia; las del board
-- entero leen US y UC sin descripción ni comments/context/attachments, los
-- criterios sin texto ni recibos (solo para contar) o un recuento agrupado.

WITH params AS (SELECT 'EmbedBuild/specbox-manager'::text AS p),
full_us AS (
    SELECT coalesce(sum(octet_length(t::text)), 0) AS b
    FROM user_stories t, params WHERE t.project_id = params.p
),
full_uc AS (
    SELECT coalesce(sum(octet_length(t::text)), 0) AS b
    FROM use_cases t, params WHERE t.project_id = params.p
),
full_ac AS (
    SELECT coalesce(sum(octet_length(t::text)), 0) AS b
    FROM acceptance_criteria t, params WHERE t.project_id = params.p
),
ac_of_story_ucs AS (
    SELECT coalesce(sum(octet_length(a::text)), 0) AS b
    FROM acceptance_criteria a
    JOIN use_cases u ON u.project_id = a.project_id AND u.id = a.uc_id, params
    WHERE a.project_id = params.p AND u.us_id IS NOT NULL
),
light_us AS (
    SELECT coalesce(sum(octet_length(t::text)), 0) AS b FROM (
        SELECT id, name, '' AS description, state, labels, priority, external_source, external_id,
               meta - 'comments' - 'context' - 'attachments' AS meta, version, epic_id
        FROM user_stories, params WHERE project_id = params.p
    ) t
),
light_uc AS (
    SELECT coalesce(sum(octet_length(t::text)), 0) AS b FROM (
        SELECT id, us_id, name, '' AS description, state, labels, priority, external_source, external_id,
               meta - 'comments' - 'context' - 'attachments' AS meta, version
        FROM use_cases, params WHERE project_id = params.p
    ) t
),
light_ac AS (
    SELECT coalesce(sum(octet_length(t::text)), 0) AS b FROM (
        SELECT id, uc_id, ac_id, '' AS text, done, '{}'::jsonb AS meta, version
        FROM acceptance_criteria, params WHERE project_id = params.p
    ) t
),
counts AS (
    SELECT coalesce(sum(octet_length(t::text)), 0) AS b FROM (
        SELECT uc_id, count(*)::int AS total, count(*) FILTER (WHERE done)::int AS done
        FROM acceptance_criteria, params WHERE project_id = params.p GROUP BY uc_id
    ) t
),
-- get_uc de cada UC: antes el board entero + sus criterios; después su historia,
-- las UC de esa historia y sus criterios. Media de todas las UC del proyecto.
per_uc AS (
    SELECT
        (SELECT coalesce(sum(octet_length(a::text)), 0) FROM acceptance_criteria a
          WHERE a.project_id = u.project_id AND a.uc_id = u.id) AS own_ac,
        (SELECT coalesce(sum(octet_length(s::text)), 0) FROM user_stories s
          WHERE s.project_id = u.project_id AND s.id = u.us_id)
        + (SELECT coalesce(sum(octet_length(x::text)), 0) FROM use_cases x
          WHERE x.project_id = u.project_id
            AND (x.us_id = u.us_id OR (u.us_id IS NULL AND x.id = u.id))) AS story
    FROM use_cases u, params WHERE u.project_id = params.p
),
get_uc AS (
    SELECT (SELECT b FROM full_us) + (SELECT b FROM full_uc) + (SELECT b FROM full_ac)
           + coalesce(avg(own_ac), 0) AS before,
           coalesce(avg(story + own_ac), 0) AS after
    FROM per_uc
),
f AS (SELECT (SELECT b FROM full_us) + (SELECT b FROM full_uc) + (SELECT b FROM full_ac) AS b),
l AS (SELECT (SELECT b FROM light_us) + (SELECT b FROM light_uc) AS b),
tools(tool, before, after) AS (
    SELECT 'get_board_status', (SELECT b FROM f), (SELECT b FROM l) + (SELECT b FROM light_ac)
    UNION ALL SELECT 'list_us', (SELECT b FROM f) + (SELECT b FROM ac_of_story_ucs), (SELECT b FROM l) + (SELECT b FROM counts)
    UNION ALL SELECT 'list_uc', (SELECT b FROM f) + (SELECT b FROM full_ac), (SELECT b FROM l) + (SELECT b FROM counts)
    UNION ALL SELECT 'find_next_uc', (SELECT b FROM f) + (SELECT before FROM get_uc), (SELECT b FROM l) + (SELECT after FROM get_uc)
    UNION ALL SELECT 'list_epics', (SELECT b FROM f), (SELECT b FROM l) + (SELECT b FROM light_ac)
    UNION ALL SELECT 'get_sprint_status', (SELECT b FROM f) + (SELECT b FROM full_ac), (SELECT b FROM l) + (SELECT b FROM counts)
    UNION ALL SELECT 'get_delivery_report', (SELECT b FROM f) + (SELECT b FROM ac_of_story_ucs), (SELECT b FROM l) + (SELECT b FROM counts)
    UNION ALL SELECT 'get_uc (una UC, media)', (SELECT before FROM get_uc), (SELECT after FROM get_uc)
)
SELECT tool,
       round(before / 1024.0) AS kb_antes,
       round(after / 1024.0, 1) AS kb_despues,
       round(100 - 100.0 * after / nullif(before, 0), 1) AS reduccion_pct
FROM tools;
