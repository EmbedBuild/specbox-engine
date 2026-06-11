-- 0013_lifecycle_analytics.sql
-- SpecBox NativeBackend — lifecycle analytics views (US-12 / UC-1203).
--
-- The analytic layer over the 0012 capture: ALL KPI computation lives in the
-- database so the engine stays thin (one read-only tool) and the panel
-- (specbox_cloud) can SELECT these views directly. NORMAL views, not
-- materialized: at current scale they resolve in <1 ms (same call as
-- project_kpis in 0011, verified with EXPLAIN — the 0012 indexes keep the
-- LATERAL off Seq Scans) and staleness would hurt more than it saves. If a
-- project ever outgrows this, the upgrade path is matview + pg_cron without
-- touching any consumer.
--
-- NAMING: the v_ prefix marks the LIFECYCLE family. The existing project_kpis
-- view (0011, US-08) covers a different domain (live progress + reservations)
-- and is intentionally untouched.
--
-- HONESTY CONTRACT (US-12): every KPI that aggregates lead time is computed
-- ONLY over `measurable` UCs whose last transition source is 'interactive'.
-- UCs imported as done (no transitions, NULL timestamps), backfill estimates
-- and legacy rows are counted and EXPOSED (done_by_import, done_by_backfill,
-- done_unmeasured) but never averaged in. coverage_pct says how much of the
-- done population the metric actually represents.
--
-- Idempotent: CREATE OR REPLACE VIEW / FUNCTION (the dev runner re-applies
-- every file; production applies the byte-for-byte supabase mirror once).

-- ── Canonical per-UC lifecycle view ──────────────────────────────────

CREATE OR REPLACE VIEW v_uc_lifecycle AS
SELECT
  uc.project_id,
  uc.id    AS uc_id,
  uc.us_id,
  uc.state,
  uc.started_at,
  uc.completed_at,
  (uc.completed_at - uc.started_at) AS lead_time,   -- NULL unless measurable
  (uc.started_at IS NOT NULL AND uc.completed_at IS NOT NULL) AS measurable,
  COALESCE(t.cycles, 0) AS cycles,
  t.last_source
FROM use_cases uc
LEFT JOIN LATERAL (
  SELECT count(*) FILTER (WHERE tr.to_state = 'in_progress') AS cycles,
         (array_agg(tr.source ORDER BY tr.occurred_at DESC))[1] AS last_source
  FROM uc_state_transitions tr
  WHERE tr.project_id = uc.project_id AND tr.uc_id = uc.id
) t ON TRUE;

-- ── Per-project lifecycle KPIs ───────────────────────────────────────
-- One row per projects row (orphan project_ids in transitions are excluded,
-- same contract as project_kpis). Percentages guard the zero-total case.

CREATE OR REPLACE VIEW v_lifecycle_kpis AS
SELECT
  p.project_id,
  COALESCE(l.done_total, 0)       AS done_total,
  COALESCE(l.done_measurable, 0)  AS done_measurable,
  CASE WHEN COALESCE(l.done_total, 0) = 0 THEN 0
       ELSE round(100.0 * l.done_measurable / l.done_total, 1)
  END                             AS coverage_pct,
  l.lead_time_p50,
  l.lead_time_p90,
  COALESCE(l.wip, 0)              AS wip,
  COALESCE(l.done_by_import, 0)   AS done_by_import,
  COALESCE(l.done_by_backfill, 0) AS done_by_backfill,
  COALESCE(l.done_unmeasured, 0)  AS done_unmeasured
FROM projects p
LEFT JOIN LATERAL (
  SELECT
    count(*) FILTER (WHERE v.state = 'done') AS done_total,
    count(*) FILTER (
        WHERE v.state = 'done' AND v.measurable
          AND COALESCE(v.last_source, 'interactive') = 'interactive'
    ) AS done_measurable,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY v.lead_time) FILTER (
        WHERE v.state = 'done' AND v.measurable
          AND COALESCE(v.last_source, 'interactive') = 'interactive'
    ) AS lead_time_p50,
    percentile_cont(0.9) WITHIN GROUP (ORDER BY v.lead_time) FILTER (
        WHERE v.state = 'done' AND v.measurable
          AND COALESCE(v.last_source, 'interactive') = 'interactive'
    ) AS lead_time_p90,
    count(*) FILTER (WHERE v.state = 'in_progress')                    AS wip,
    count(*) FILTER (WHERE v.state = 'done'
                       AND v.last_source = 'import')                   AS done_by_import,
    count(*) FILTER (WHERE v.state = 'done'
                       AND v.last_source = 'backfill_estimate')        AS done_by_backfill,
    count(*) FILTER (WHERE v.state = 'done' AND NOT v.measurable)      AS done_unmeasured
  FROM v_uc_lifecycle v
  WHERE v.project_id = p.project_id
) l ON TRUE;

-- ── Per-US rollup ────────────────────────────────────────────────────

CREATE OR REPLACE VIEW v_us_progress AS
SELECT
  v.project_id,
  v.us_id,
  count(*)                                                        AS uc_total,
  count(*) FILTER (WHERE v.state = 'done')                        AS uc_done,
  count(*) FILTER (
      WHERE v.state = 'done' AND v.measurable
        AND COALESCE(v.last_source, 'interactive') = 'interactive'
  )                                                               AS uc_done_measurable,
  min(v.started_at)                                               AS first_started_at,
  max(v.completed_at) FILTER (WHERE v.state = 'done')             AS last_completed_at,
  sum(v.lead_time) FILTER (
      WHERE v.measurable
        AND COALESCE(v.last_source, 'interactive') = 'interactive'
  )                                                               AS total_lead_time
FROM v_uc_lifecycle v
WHERE v.us_id IS NOT NULL
GROUP BY v.project_id, v.us_id;

-- ── Weekly throughput (real completions only) ────────────────────────

CREATE OR REPLACE VIEW v_weekly_throughput AS
SELECT
  tr.project_id,
  date_trunc('week', tr.occurred_at) AS week_start,
  count(DISTINCT tr.uc_id)           AS ucs_completed
FROM uc_state_transitions tr
WHERE tr.to_state = 'done' AND tr.source = 'interactive'
GROUP BY tr.project_id, date_trunc('week', tr.occurred_at);

-- ── Service function (the MCP tool's single entry point) ─────────────
-- Parameterized per project: tenant isolation lives in the WHERE, and the
-- caller (server/tools) passes the SESSION's project_id, never a free param.

CREATE OR REPLACE FUNCTION fn_lifecycle_kpis(p_project_id TEXT)
RETURNS SETOF v_lifecycle_kpis
LANGUAGE sql STABLE AS $$
    SELECT * FROM v_lifecycle_kpis WHERE project_id = p_project_id
$$;
