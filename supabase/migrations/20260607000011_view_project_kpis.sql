-- 0011_view_project_kpis.sql
-- SpecBox NativeBackend — real-time KPI view, 1 row per project (US-08 / UC-803).
--
-- A NORMAL view (NOT materialized): the live dimensions (reservations, pulse)
-- lose all value if cached stale, and at <1 ms there is nothing to gain by
-- materializing. SQL verified against the live DB at 0.788 ms / 123 buffer hits
-- / 0 disk reads; the audit_log LATERAL uses idx_audit_log_project_occurred
-- (0006) — no Seq Scan [PRD AC-13].
--
-- One row per public.projects row (FROM projects + LEFT JOIN LATERAL), so an
-- orphan project_id present only in audit_log is excluded [PRD AC-08]. Tolerant
-- of an empty uc_reservations via COALESCE [PRD AC-11]. Percentages guard the
-- zero-total case to avoid NULL / division-by-zero [PRD AC-10].
--
-- Idempotent: CREATE OR REPLACE VIEW — the runner re-applies every file on each
-- call (server/db/migrate.py) and the test fixture applies twice, so a plain
-- CREATE VIEW would raise "relation already exists" on the second pass. REPLACE
-- is the idempotency contract for this object.
--
-- Mirrored byte-for-byte in server/db/migrations/0011_view_project_kpis.sql.

CREATE OR REPLACE VIEW project_kpis AS
SELECT
  p.project_id,
  COALESCE(us.us_total, 0)  AS us_total,
  COALESCE(uc.uc_total, 0)  AS uc_total,
  COALESCE(ac.ac_total, 0)  AS ac_total,
  COALESCE(uc.uc_done, 0)   AS uc_done,
  COALESCE(ac.ac_done, 0)   AS ac_done,
  CASE WHEN COALESCE(uc.uc_total, 0) = 0 THEN 0
       ELSE round(100.0 * uc.uc_done / uc.uc_total, 1) END  AS uc_done_pct,
  CASE WHEN COALESCE(ac.ac_total, 0) = 0 THEN 0
       ELSE round(100.0 * ac.ac_done / ac.ac_total, 1) END  AS ac_done_pct,
  COALESCE(rsv.active_reservations, 0) AS active_reservations,
  COALESCE(rsv.distinct_reservers, 0)  AS distinct_reservers,
  rsv.oldest_reservation_age           AS oldest_reservation_age,
  COALESCE(rsv.stale_reservations, 0)  AS stale_reservations,
  al.last_activity_at
FROM projects p
LEFT JOIN LATERAL (
  SELECT count(*) AS us_total
  FROM user_stories u WHERE u.project_id = p.project_id
) us ON TRUE
LEFT JOIN LATERAL (
  SELECT count(*) AS uc_total,
         count(*) FILTER (WHERE c.state = 'done') AS uc_done
  FROM use_cases c WHERE c.project_id = p.project_id
) uc ON TRUE
LEFT JOIN LATERAL (
  SELECT count(*) AS ac_total,
         count(*) FILTER (WHERE a.done) AS ac_done
  FROM acceptance_criteria a WHERE a.project_id = p.project_id
) ac ON TRUE
LEFT JOIN LATERAL (
  SELECT count(*)                       AS active_reservations,
         count(DISTINCT r.developer_id) AS distinct_reservers,
         now() - min(r.reserved_at)     AS oldest_reservation_age,
         count(*) FILTER (WHERE r.reserved_at < now() - interval '24 hours') AS stale_reservations
  FROM uc_reservations r WHERE r.project_id = p.project_id
) rsv ON TRUE
LEFT JOIN LATERAL (
  SELECT max(l.occurred_at) AS last_activity_at
  FROM audit_log l WHERE l.project_id = p.project_id
) al ON TRUE;
