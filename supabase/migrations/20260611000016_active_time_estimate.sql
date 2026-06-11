-- 0016_active_time_estimate.sql
-- SpecBox NativeBackend — active-time ESTIMATE per UC (US-12 / UC-1206).
--
-- Lead time (v_uc_lifecycle) is wall clock: it includes nights, weekends and
-- context switches. This view estimates ACTIVE time with the classic
-- time-tracking heuristic: cluster the UC's activity events into work
-- sessions (a gap > 30 minutes starts a new session) and sum the session
-- spans. Events = the UC's state transitions ∪ its audit_log rows (mark_ac,
-- update_uc, reserve/complete...) — every mutation is a heartbeat of work.
--
-- THIS IS AN ESTIMATE, never an invoice: consumers must surface it as such.
-- events_count / sessions_count are exposed so the consumer can weigh
-- confidence (2 events say much less than 40). A UC with no measurable
-- in-between activity yields active_time NULL — never a fake 0: a UC whose
-- events all collapse into single instants (e.g. only a start and a complete
-- in two distant sessions) has UNKNOWN active time, not zero.
--
-- The 30-minute gap is fixed by design for v1 (changing it per-query would
-- make metrics incomparable across consumers). Revisit only with data.
--
-- Idempotent: CREATE OR REPLACE VIEW.

CREATE OR REPLACE VIEW v_active_time_estimate AS
WITH events AS (
    SELECT t.project_id, t.uc_id, t.occurred_at
    FROM uc_state_transitions t
    UNION ALL
    SELECT al.project_id, al.target_id AS uc_id, al.occurred_at
    FROM audit_log al
),
numbered AS (
    SELECT e.project_id, e.uc_id, e.occurred_at,
           CASE WHEN e.occurred_at - lag(e.occurred_at) OVER w
                     > interval '30 minutes'
                THEN 1 ELSE 0 END AS new_session
    FROM events e
    WINDOW w AS (PARTITION BY e.project_id, e.uc_id ORDER BY e.occurred_at)
),
sessions AS (
    SELECT n.project_id, n.uc_id, n.occurred_at,
           sum(n.new_session) OVER (PARTITION BY n.project_id, n.uc_id
                                    ORDER BY n.occurred_at) AS session_id
    FROM numbered n
),
per_session AS (
    SELECT s.project_id, s.uc_id, s.session_id,
           max(s.occurred_at) - min(s.occurred_at) AS session_time,
           count(*)                                AS session_events
    FROM sessions s
    GROUP BY s.project_id, s.uc_id, s.session_id
)
SELECT ps.project_id,
       ps.uc_id,
       NULLIF(sum(ps.session_time), interval '0') AS active_time,
       sum(ps.session_events)::int                AS events_count,
       count(*)::int                              AS sessions_count
FROM per_session ps
GROUP BY ps.project_id, ps.uc_id;

GRANT SELECT ON v_active_time_estimate TO specbox_analytics_ro;
