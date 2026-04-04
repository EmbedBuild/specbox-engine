#!/usr/bin/env node
/**
 * heartbeat-sender.mjs — Hook helper: sends consolidated heartbeat to VPS (fire-and-forget)
 * Usage: node heartbeat-sender.mjs [project_name] [last_operation]
 * Requires: SPECBOX_ENGINE_MCP_URL env var
 * If not configured or fails, saves to pending queue.
 */

import { git, getProjectName, readJsonFile, fileExists, findFiles, mkdir, appendLine, now } from './lib/utils.mjs';
import { heartbeat, getApiBase } from './lib/http.mjs';
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
