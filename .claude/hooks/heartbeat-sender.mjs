#!/usr/bin/env node
/**
 * heartbeat-sender.mjs — Hook helper: sends consolidated heartbeat to VPS (fire-and-forget)
 * Usage: node heartbeat-sender.mjs [project_name] [last_operation]
 * Requires: SPECBOX_ENGINE_MCP_URL env var
 * If not configured or fails, saves to pending queue.
 */

import { git, getProjectName, readJsonFile, fileExists, findFiles, mkdir, appendLine, now } from './lib/utils.mjs';
import { getApiBase } from './lib/http.mjs';
import { readFileSync, writeFileSync } from 'fs';
import { join } from 'path';

const mcpUrl = process.env.SPECBOX_ENGINE_MCP_URL || process.env.DEV_ENGINE_MCP_URL || '';
if (!mcpUrl) process.exit(0);

const projectName = process.argv[2] || getProjectName();
if (projectName === 'unknown') process.exit(0);

const lastOperation = process.argv[3] || 'idle';
const timestamp = now();
const PENDING_FILE = '.quality/pending_heartbeats.jsonl';

// --- Gather state from local filesystem ---

const branch = git('branch --show-current');
const lastCommit = git('log -1 --pretty=format:%s');
const lastCommitAt = git("log -1 --pretty=format:%Y-%m-%dT%H:%M:%SZ");

// Current feature from checkpoint
let currentFeature = '';
let currentPhase = '';
const checkpoints = findFiles('.quality/evidence', /^checkpoint\.json$/);
if (checkpoints.length > 0) {
  // Sort and take the last one
  checkpoints.sort();
  const cp = readJsonFile(checkpoints[checkpoints.length - 1]);
  if (cp) {
    currentFeature = cp.feature || '';
    if (cp.phase) currentPhase = 'implement';
  }
}

// Coverage from quality baseline
let coverage = null;
const baselines = findFiles('.quality/baselines', /\.json$/);
if (baselines.length > 0) {
  const bl = readJsonFile(baselines[0]);
  if (bl) {
    const covVal = bl.coverage ?? bl.test_coverage ?? null;
    if (covVal !== null && covVal !== undefined) coverage = covVal;
  }
}

// Healing health
let healingEvents = 0;
let healingHealth = 'healthy';
const healingFiles = findFiles('.quality/evidence', /^healing\.jsonl$/);
if (healingFiles.length > 0) {
  try {
    const content = readFileSync(healingFiles[0], 'utf-8');
    healingEvents = content.split('\n').filter(Boolean).length;
    if (healingEvents > 5) healingHealth = 'degraded';
    if (healingEvents > 15) healingHealth = 'critical';
  } catch { /* ignore */ }
}

// Feedback
let openFeedback = 0;
let blockingFeedback = 0;
const fbFiles = findFiles('.quality/evidence', /^FB-.*\.json$/);
for (const fbFile of fbFiles) {
  const fb = readJsonFile(fbFile);
  if (!fb) continue;
  const status = fb.status || 'open';
  if (status === 'open') {
    openFeedback++;
    const severity = fb.severity || 'minor';
    if (severity === 'critical' || severity === 'major') {
      blockingFeedback++;
    }
  }
}

// v5.30.0 — Session Continuity: enrich payload with handoff + context_pressure.
let handoffPresent = false;
let handoffAgeMin = null;
const HANDOFF_PATH = '.quality/handoff.md';
if (fileExists(HANDOFF_PATH)) {
  handoffPresent = true;
  try {
    const { statSync } = await import('fs');
    handoffAgeMin = Math.round((Date.now() - statSync(HANDOFF_PATH).mtimeMs) / 60000);
  } catch { /* ignore */ }
}

// Latest session_end log entry → context tokens estimate
let contextPressure = null;
try {
  const today = timestamp.slice(0, 10);
  const sessionsLog = `.quality/logs/sessions_${today}.jsonl`;
  if (fileExists(sessionsLog)) {
    const lines = readFileSync(sessionsLog, 'utf-8').split('\n').filter(Boolean);
    if (lines.length > 0) {
      const last = JSON.parse(lines[lines.length - 1]);
      const tokens = last.context_tokens_est || 0;
      const pct = Math.round((tokens / 1_000_000) * 100);
      const level = tokens > 700000 ? 'critical' : tokens > 400000 ? 'warn' : 'healthy';
      contextPressure = { tokens_est: tokens, pct_of_window: pct, level };
    }
  }
} catch { /* ignore */ }

// v5.31.0 — Stitch Autopilot: enrich payload with cached quota state.
// The cache is written by the get_stitch_quota_status MCP tool. If the
// user never ran it, the field stays null and Sala de Máquinas hides
// the indicator gracefully.
let stitchQuota = null;
try {
  const QUOTA_CACHE = '.quality/stitch_quota.json';
  if (fileExists(QUOTA_CACHE)) {
    const q = readJsonFile(QUOTA_CACHE);
    if (q && q.standard && q.experimental) {
      stitchQuota = {
        month: q.month || null,
        standard_pct: q.standard.percent ?? null,
        experimental_pct: q.experimental.percent ?? null,
        warning: q.warning || null,
        reset_at: q.reset_at || null,
      };
    }
  }
} catch { /* ignore */ }

// v5.32.0 — Implement Task Isolation: surface task isolation health.
// Cache is written by context-budget-guard.mjs and file-ownership-guard.mjs
// hooks plus the SKILL.md (Paso 5.0) post-Task block. Best-effort: when
// the user has never run /implement under v5.32, the field stays null.
let taskIsolation = null;
try {
  const TI_CACHE = '.quality/task_isolation.json';
  if (fileExists(TI_CACHE)) {
    const t = readJsonFile(TI_CACHE);
    if (t) {
      taskIsolation = {
        enabled: t.enabled === true,
        tasks_run_total: t.tasks_run_total ?? 0,
        tasks_failed_budget: t.tasks_failed_budget ?? 0,
        tasks_failed_ownership: t.tasks_failed_ownership ?? 0,
        last_feature_slug: t.last_feature_slug ?? null,
        last_event_at: t.last_event_at ?? null,
      };
    }
  }
} catch { /* ignore */ }

// Build heartbeat payload
const payload = {
  project: projectName,
  timestamp,
  session_active: true,
  current_phase: currentPhase,
  current_feature: currentFeature,
  current_branch: branch,
  coverage_pct: coverage,
  open_feedback: openFeedback,
  blocking_feedback: blockingFeedback,
  healing_health: healingHealth,
  self_healing_events: healingEvents,
  last_operation: lastOperation,
  last_commit: lastCommit,
  last_commit_at: lastCommitAt,
  handoff_present: handoffPresent,
  handoff_age_minutes: handoffAgeMin,
  context_pressure: contextPressure,
  stitch_quota: stitchQuota,
  task_isolation: taskIsolation,
};

async function run() {
  const syncToken = process.env.SPECBOX_SYNC_TOKEN || '';
  const apiBase = getApiBase();
  const headers = { 'Content-Type': 'application/json' };
  if (syncToken) headers['Authorization'] = `Bearer ${syncToken}`;

  // --- Send pending heartbeats first ---
  if (fileExists(PENDING_FILE)) {
    try {
      const lines = readFileSync(PENDING_FILE, 'utf-8').split('\n').filter(Boolean);
      for (const line of lines) {
        try {
          const pendingPayload = JSON.parse(line);
          await fetch(`${apiBase}/api/heartbeat`, {
            method: 'POST',
            headers,
            body: JSON.stringify(pendingPayload),
            signal: AbortSignal.timeout(5000),
          }).catch(() => {});
        } catch { /* ignore individual failures */ }
      }
      writeFileSync(PENDING_FILE, '', 'utf-8');
    } catch { /* ignore */ }
  }

  // --- Send current heartbeat ---
  try {
    const res = await fetch(`${apiBase}/api/heartbeat`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(5000),
    });

    if (res.ok) {
      // Success — also write specbox-state.json locally
      const repoRoot = git('rev-parse --show-toplevel');
      if (repoRoot) {
        const localState = { ...payload, source: 'local' };
        writeFileSync(join(repoRoot, 'specbox-state.json'), JSON.stringify(localState, null, 2), 'utf-8');
      }
    } else {
      throw new Error(`HTTP ${res.status}`);
    }
  } catch {
    // Failed — queue for retry
    mkdir('.quality');
    appendLine(PENDING_FILE, JSON.stringify(payload));
  }
}

run().catch(() => {}).finally(() => process.exit(0));
