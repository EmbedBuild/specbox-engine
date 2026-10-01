-- 0028_ac_evidence_backfill.sql
-- SpecBox NativeBackend — los recibos de cada criterio de aceptación (US-56 / UC-5601).
--
-- POR QUÉ:
-- Desde UC-5601, `mark_ac` / `mark_ac_batch` guardan en `acceptance_criteria.meta`
-- la evidencia de cada AC (`evidence`: lista de {type, label, link, detail, by,
-- at, passed}) y su último veredicto (`verdict`: {passed, by, at}). Antes, la
-- evidencia vivía solo como texto en los comentarios de la UC
-- (`use_cases.meta.comments`). Esta migración trae esos comentarios a la
-- estructura nueva para que el panel y el portal enseñen también el recibo de lo
-- aceptado antes de UC-5601.
--
-- QUÉ HACE (sin DDL: solo datos en `meta`):
-- 1. Cada comentario «AC-XX: PASSED|FAILED — texto [AAAA-MM-DD HH:MM UTC]» se
--    convierte en una evidencia de su AC: tipo `url`, el texto completo como
--    etiqueta, sin enlace ni detalle, con la fecha del comentario y
--    `by = null`. El autor queda desconocido: el comentario no lo registró y
--    nunca se inventa (AC-04). `source = 'migrated'` la distingue.
-- 2. El último veredicto de cada AC según sus comentarios (los de `mark_ac` y las
--    líneas de «Validacion AG-09b [...]:» de `mark_ac_batch`) pasa a `verdict`
--    con `by = null`, solo si coincide con el estado actual del AC: si alguien
--    lo cambió después por otra vía, no se atribuye una aceptación que no consta.
--
-- Las expresiones regulares son las mismas que `server/ac_evidence.py`, que hace
-- esta misma lectura al vuelo para Trello, Plane y FreeForm.
--
-- IDEMPOTENTE Y EN CUALQUIER ORDEN CON EL DESPLIEGUE:
-- - Un AC que ya tiene alguna evidencia `source = 'migrated'` no se vuelve a
--   tocar; las evidencias que `mark_ac` haya escrito antes de aplicar esta
--   migración se conservan detrás de las migradas.
-- - `verdict` solo se escribe donde no existe: el que haya escrito `mark_ac`
--   (con autor) siempre gana.
-- - No toca `done`, `version` ni `updated_at`: es un relleno de metadatos, no un
--   cambio de nadie.

-- 1) Evidencias desde los comentarios de `mark_ac`.
WITH single AS (
    SELECT uc.project_id,
           uc.id AS uc_id,
           m[1] AS ac_id,
           m[2] = 'PASSED' AS passed,
           m[3] AS label,
           COALESCE(NULLIF(c.e->>'created_at', '')::timestamptz, (m[4] || ' UTC')::timestamptz) AS at,
           c.ord
    FROM use_cases uc
    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(uc.meta->'comments', '[]'::jsonb))
        WITH ORDINALITY AS c(e, ord)
    CROSS JOIN LATERAL regexp_match(
        c.e->>'text',
        '^(AC-[0-9]+): (PASSED|FAILED) — (.*) \[([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}) UTC\]$'
    ) AS m
    WHERE m IS NOT NULL
),
legacy AS (
    SELECT project_id,
           uc_id,
           ac_id,
           jsonb_agg(
               jsonb_build_object(
                   'type', 'url',
                   'label', label,
                   'link', NULL,
                   'detail', NULL,
                   'by', NULL,
                   'at', at,
                   'passed', passed,
                   'source', 'migrated'
               )
               ORDER BY at, ord
           ) AS evidence
    FROM single
    GROUP BY project_id, uc_id, ac_id
)
UPDATE acceptance_criteria ac
SET meta = jsonb_set(ac.meta, '{evidence}', legacy.evidence || COALESCE(ac.meta->'evidence', '[]'::jsonb))
FROM legacy
WHERE ac.project_id = legacy.project_id
  AND ac.uc_id = legacy.uc_id
  AND ac.ac_id = legacy.ac_id
  AND NOT EXISTS (
      SELECT 1
      FROM jsonb_array_elements(COALESCE(ac.meta->'evidence', '[]'::jsonb)) AS x(ev)
      WHERE x.ev->>'source' = 'migrated'
  );

-- 2) Último veredicto, desde los comentarios de `mark_ac` y de `mark_ac_batch`.
WITH verdicts AS (
    SELECT uc.project_id,
           uc.id AS uc_id,
           m[1] AS ac_id,
           m[2] = 'PASSED' AS passed,
           COALESCE(NULLIF(c.e->>'created_at', '')::timestamptz, (m[3] || ' UTC')::timestamptz) AS at,
           c.ord
    FROM use_cases uc
    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(uc.meta->'comments', '[]'::jsonb))
        WITH ORDINALITY AS c(e, ord)
    CROSS JOIN LATERAL regexp_match(
        c.e->>'text',
        '^(AC-[0-9]+): (PASSED|FAILED)(?: — .*)? \[([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}) UTC\]$'
    ) AS m
    WHERE m IS NOT NULL
    UNION ALL
    SELECT uc.project_id,
           uc.id,
           l[1],
           l[2] = 'PASSED',
           COALESCE(NULLIF(c.e->>'created_at', '')::timestamptz, (h[1] || ' UTC')::timestamptz),
           c.ord
    FROM use_cases uc
    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(uc.meta->'comments', '[]'::jsonb))
        WITH ORDINALITY AS c(e, ord)
    CROSS JOIN LATERAL regexp_match(
        c.e->>'text',
        '^Validacion AG-09b \[([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}) UTC\]:'
    ) AS h
    CROSS JOIN LATERAL regexp_matches(c.e->>'text', '\n\s+(AC-[0-9]+): (PASSED|FAILED)', 'g') AS l
    WHERE h IS NOT NULL
),
latest AS (
    SELECT DISTINCT ON (project_id, uc_id, ac_id) project_id, uc_id, ac_id, passed, at
    FROM verdicts
    ORDER BY project_id, uc_id, ac_id, at DESC, ord DESC
)
UPDATE acceptance_criteria ac
SET meta = ac.meta || jsonb_build_object(
        'verdict',
        jsonb_build_object('passed', latest.passed, 'by', NULL, 'at', latest.at, 'source', 'migrated')
    )
FROM latest
WHERE ac.project_id = latest.project_id
  AND ac.uc_id = latest.uc_id
  AND ac.ac_id = latest.ac_id
  AND NOT (ac.meta ? 'verdict')
  AND ac.done = latest.passed;
