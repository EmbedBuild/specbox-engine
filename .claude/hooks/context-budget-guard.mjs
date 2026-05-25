#!/usr/bin/env node
/**
 * context-budget-guard.mjs — PreToolUse hook for Task (v5.32.0).
 *
 * Estimates tokens for the prompt of a Task spawned by /implement
 * (or any other skill that delegates to a sub-agent) and reports
 * a WARNING (default) or BLOCKS (strict mode) when the budget is
 * exceeded.
 *
 * Behaviour:
 *   - mode=warn  (default) → stderr WARNING, exit 0
 *   - mode=strict          → stderr BLOCKED, exit 2
 *   - mode=off             → no-op, exit 0
 *
 * Settings (from .claude/settings.local.json):
 *   specbox.implement.task_isolation.task_budget_tokens (default 16000)
 *   specbox.implement.task_isolation.task_budget_mode  (default "warn")
 *
 * Side-effects:
 *   Updates .quality/task_isolation.json counters for local inspection
 *   and external consumers (specbox_cloud, ad-hoc scripts).
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { estimatePromptTokens } from './lib/token-counter.mjs';

const DEFAULT_BUDGET = 16000;
const DEFAULT_MODE = 'warn';
const SETTINGS_PATH = '.claude/settings.local.json';
const TASK_ISOLATION_CACHE = '.quality/task_isolation.json';

// ── Read stdin payload ─────────────────────────────────────────────────

const raw = readStdinSync();
let payload = {};
try { payload = JSON.parse(raw); } catch { /* ignore */ }

const toolName = payload?.tool_name || payload?.toolName || '';
if (toolName !== 'Task') {
  process.exit(0);
}

// ── Resolve settings ───────────────────────────────────────────────────

const { budget, mode } = readSettings();
if (mode === 'off') {
  process.exit(0);
}

// ── Estimate ──────────────────────────────────────────────────────────

const { total, breakdown } = estimatePromptTokens(payload);

if (total <= budget) {
  // Under budget → bump tasks_run_total counter and pass through.
  bumpCounter('tasks_run_total');
  process.exit(0);
}

// ── Over budget ───────────────────────────────────────────────────────

bumpCounter('tasks_failed_budget');

const breakdownStr = Object.entries(breakdown)
  .map(([k, v]) => `${k}=${v}`)
  .join(', ');
const overshoot = total - budget;

if (mode === 'strict') {
  console.error(
    `[context-budget-guard] BLOCKED — Task prompt is ~${total} tokens ` +
      `(budget ${budget}, overshoot ${overshoot}). Breakdown: ${breakdownStr}. ` +
      `Reduce the prompt body, move shared context to ` +
      `.quality/evidence/{feature}/execution_context.json, or split the work ` +
      `into multiple Tasks.`
  );
  process.exit(2);
}

// warn
console.error(
  `[context-budget-guard] WARNING — Task prompt is ~${total} tokens ` +
    `(budget ${budget}, overshoot ${overshoot}). Breakdown: ${breakdownStr}. ` +
    `Consider trimming. Run will proceed.`
);
process.exit(0);

// ── Helpers ───────────────────────────────────────────────────────────

function readStdinSync() {
  try {
    return readFileSync(0, 'utf-8');
  } catch {
    return '';
  }
}

function readSettings() {
  let budget = DEFAULT_BUDGET;
  let mode = DEFAULT_MODE;
  if (!existsSync(SETTINGS_PATH)) {
    return { budget, mode };
  }
  try {
    const settings = JSON.parse(readFileSync(SETTINGS_PATH, 'utf-8'));
    const ti = settings?.specbox?.implement?.task_isolation;
    if (typeof ti?.task_budget_tokens === 'number') budget = ti.task_budget_tokens;
    if (typeof ti?.task_budget_mode === 'string') mode = ti.task_budget_mode;
  } catch { /* ignore */ }
  return { budget, mode };
}

function bumpCounter(key) {
  try {
    let cache = {};
    if (existsSync(TASK_ISOLATION_CACHE)) {
      try {
        cache = JSON.parse(readFileSync(TASK_ISOLATION_CACHE, 'utf-8'));
      } catch { cache = {}; }
    }
    cache[key] = (cache[key] || 0) + 1;
    cache.last_event_at = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
    mkdirSync(dirname(TASK_ISOLATION_CACHE), { recursive: true });
    writeFileSync(
      TASK_ISOLATION_CACHE,
      JSON.stringify(cache, null, 2),
      'utf-8'
    );
  } catch { /* best-effort */ }
}
