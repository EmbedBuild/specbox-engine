-- 0015_lifecycle_backfill_fns.sql
-- SpecBox NativeBackend — historical lifecycle backfill, PREPARED ONLY
-- (US-12 / UC-1205).
--
-- This migration CREATES two functions and EXECUTES NOTHING. The backfill of
-- pre-0012 history runs per project, later, as a gated operational decision —
-- only after the trigger-captured data has been validated against a real
-- overlap window (estimator calibration). Applying this file leaves zero
-- rows with source = 'backfill_estimate'.
--
-- DESIGN: transitions are the source of truth; the use_cases lifecycle
-- columns are a recomputable cache. That makes the backfill fully
-- reversible:
--
--     rollback = DELETE FROM uc_state_transitions
--                 WHERE project_id = $1 AND source = 'backfill_estimate';
--                SELECT fn_recompute_lifecycle_columns($1);
--
-- ESTIMATORS (in confidence order, all marked in metadata.estimator):
--   started_at   ← first audit_log 'reserve_uc' for the UC, else the UC's
--                  first branch_registry.created_at, else no proposal.
--   completed_at ← first audit_log 'complete_uc' for the UC (only for UCs
--                  currently in state 'done'). metadata.burst = true when the
--                  event is < 10 seconds after the same developer's previous
--                  complete_uc — administrative batch closes, which consumers
--                  should treat as low-confidence timestamps.
--
-- Synthetic rows NEVER overwrite trigger-captured data: the column UPDATE
-- fills NULLs only (COALESCE), and candidates are UCs missing at least one
-- timestamp. Column updates here do not touch `state`, so the 0012 triggers
-- do not fire; app.change_source is still set as belt and braces.
--
-- Idempotent: CREATE OR REPLACE FUNCTION only.

-- ── The backfill (dry-run by default) ────────────────────────────────

CREATE OR REPLACE FUNCTION fn_backfill_lifecycle(
    p_project_id TEXT,
    p_dry_run    BOOLEAN DEFAULT true
)
RETURNS TABLE (
    r_uc_id                 TEXT,
    r_proposed_started_at   TIMESTAMPTZ,
    r_start_estimator       TEXT,
    r_start_developer       TEXT,
    r_proposed_completed_at TIMESTAMPTZ,
    r_complete_burst        BOOLEAN,
    r_complete_developer    TEXT,
    r_applied               BOOLEAN
)
LANGUAGE plpgsql AS $$
DECLARE
    rec RECORD;
BEGIN
    -- Belt and braces: nothing in this function touches use_cases.state, but
    -- if that ever changes the 0012 triggers must see the right source.
    PERFORM set_config('app.change_source', 'backfill_estimate', true);

    FOR rec IN
        WITH done_events AS (
            SELECT al.target_id AS ev_uc_id,
                   al.developer_id,
                   al.occurred_at,
                   COALESCE(
                       (al.occurred_at
                        - lag(al.occurred_at) OVER (PARTITION BY al.developer_id
                                                    ORDER BY al.occurred_at)
                       ) < interval '10 seconds',
                       false
                   ) AS burst
            FROM audit_log al
            WHERE al.project_id = p_project_id AND al.operation = 'complete_uc'
        ),
        first_done AS (
            SELECT DISTINCT ON (de.ev_uc_id)
                   de.ev_uc_id, de.developer_id, de.occurred_at, de.burst
            FROM done_events de
            ORDER BY de.ev_uc_id, de.occurred_at
        ),
        first_reserve AS (
            SELECT DISTINCT ON (al.target_id)
                   al.target_id AS ev_uc_id, al.developer_id, al.occurred_at
            FROM audit_log al
            WHERE al.project_id = p_project_id AND al.operation = 'reserve_uc'
            ORDER BY al.target_id, al.occurred_at
        ),
        first_branch AS (
            SELECT DISTINCT ON (br.uc_id)
                   br.uc_id AS ev_uc_id, br.developer_id, br.created_at
            FROM branch_registry br
            WHERE br.project_id = p_project_id
            ORDER BY br.uc_id, br.created_at
        )
        SELECT uc.id        AS cand_uc_id,
               uc.us_id     AS cand_us_id,
               CASE WHEN uc.started_at IS NULL
                    THEN COALESCE(r.occurred_at, b.created_at) END AS p_start,
               CASE WHEN uc.started_at IS NULL THEN
                    CASE WHEN r.occurred_at IS NOT NULL THEN 'reserve_uc'
                         WHEN b.created_at  IS NOT NULL THEN 'branch_registry'
                    END END                                        AS p_start_est,
               CASE WHEN uc.started_at IS NULL
                    THEN COALESCE(r.developer_id, b.developer_id) END AS p_start_dev,
               CASE WHEN uc.completed_at IS NULL AND uc.state = 'done'
                    THEN d.occurred_at END                         AS p_done,
               COALESCE(d.burst, false)                            AS p_done_burst,
               d.developer_id                                      AS p_done_dev
        FROM use_cases uc
        LEFT JOIN first_reserve r ON r.ev_uc_id = uc.id
        LEFT JOIN first_branch  b ON b.ev_uc_id = uc.id
        LEFT JOIN first_done    d ON d.ev_uc_id = uc.id
        WHERE uc.project_id = p_project_id
          AND (uc.started_at IS NULL OR uc.completed_at IS NULL)
    LOOP
        IF rec.p_start IS NULL AND rec.p_done IS NULL THEN
            CONTINUE;  -- no signal for this UC: stays honestly unmeasured
        END IF;

        IF NOT p_dry_run THEN
            UPDATE use_cases
            SET started_at   = COALESCE(started_at, rec.p_start),
                completed_at = COALESCE(completed_at, rec.p_done)
            WHERE project_id = p_project_id AND id = rec.cand_uc_id;

            IF rec.p_start IS NOT NULL THEN
                INSERT INTO uc_state_transitions
                    (project_id, uc_id, us_id, from_state, to_state,
                     developer_id, source, metadata, occurred_at)
                VALUES
                    (p_project_id, rec.cand_uc_id, rec.cand_us_id,
                     'backlog', 'in_progress', rec.p_start_dev,
                     'backfill_estimate',
                     jsonb_build_object('estimator', rec.p_start_est),
                     rec.p_start);
            END IF;
            IF rec.p_done IS NOT NULL THEN
                INSERT INTO uc_state_transitions
                    (project_id, uc_id, us_id, from_state, to_state,
                     developer_id, source, metadata, occurred_at)
                VALUES
                    (p_project_id, rec.cand_uc_id, rec.cand_us_id,
                     'in_progress', 'done', rec.p_done_dev,
                     'backfill_estimate',
                     jsonb_build_object('estimator', 'complete_uc',
                                        'burst', rec.p_done_burst),
                     rec.p_done);
            END IF;
        END IF;

        r_uc_id                 := rec.cand_uc_id;
        r_proposed_started_at   := rec.p_start;
        r_start_estimator       := rec.p_start_est;
        r_start_developer       := rec.p_start_dev;
        r_proposed_completed_at := rec.p_done;
        r_complete_burst        := rec.p_done_burst;
        r_complete_developer    := rec.p_done_dev;
        r_applied               := NOT p_dry_run;
        RETURN NEXT;
    END LOOP;
END $$;

-- ── Recompute the column cache from the remaining transitions ────────
-- Reproduces the trigger + backfill semantics from uc_state_transitions:
-- started_at = first non-import transition INTO in_progress, completed_at =
-- last non-import transition INTO done (the trigger writes now() which equals
-- the transition's occurred_at — both are transaction-stable). After deleting
-- the backfill_estimate rows, this restores the exact pre-backfill state.

CREATE OR REPLACE FUNCTION fn_recompute_lifecycle_columns(p_project_id TEXT)
RETURNS INTEGER
LANGUAGE plpgsql AS $$
DECLARE
    n INTEGER;
BEGIN
    UPDATE use_cases uc
    SET started_at   = sub.first_start,
        completed_at = sub.last_done
    FROM (
        SELECT u.id AS sub_id,
               (SELECT min(t.occurred_at) FROM uc_state_transitions t
                 WHERE t.project_id = u.project_id AND t.uc_id = u.id
                   AND t.to_state = 'in_progress' AND t.source <> 'import') AS first_start,
               (SELECT max(t.occurred_at) FROM uc_state_transitions t
                 WHERE t.project_id = u.project_id AND t.uc_id = u.id
                   AND t.to_state = 'done' AND t.source <> 'import')        AS last_done
        FROM use_cases u
        WHERE u.project_id = p_project_id
    ) sub
    WHERE uc.project_id = p_project_id AND uc.id = sub.sub_id
      AND (uc.started_at   IS DISTINCT FROM sub.first_start
           OR uc.completed_at IS DISTINCT FROM sub.last_done);
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END $$;
