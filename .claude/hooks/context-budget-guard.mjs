#!/usr/bin/env node
/**
 * context-budget-guard.mjs — PreToolUse hook for subagent launches (v5.32.0, UC-12208).
 *
 * Estimates tokens for the prompt of a subagent spawned by /implement
 * (or any other skill that delegates to a sub-agent) and reports
 * a note (default) or BLOCKS (strict mode) when the budget is exceeded.
 *
 * Claude Code launches subagents with the «Agent» tool; older versions called
 * it «Task». The hook is registered with the matcher «Agent|Task» and accepts
 * both (until UC-12208 it only listened to «Task» and never ran).
 *
 * Behaviour:
 *   - mode=warn  (default) → note to the agent (additionalContext), exit 0
 *   - mode=strict          → stderr BLOCKED, exit 2
 *   - mode=off             → no-op, exit 0
 *
 * Settings — `task_isolation.task_budget_tokens` (default 16000) and
 * `task_isolation.task_budget_mode` (default "warn"), read per key from:
 *   1. .claude/settings.local.json → specbox.implement.task_isolation (wins)
 *   2. .claude/settings.json       → implement.task_isolation (where the
 *      settings template writes it) or specbox.implement.task_isolation
 *
 * Side-effects:
 *   Updates .quality/task_isolation.json counters, plus `last_tool_name`
 *   (the tool name the hook received), for local inspection and external
 *   consumers (specbox_cloud, ad-hoc scripts).
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { estimatePromptTokens } from './lib/token-counter.mjs';
import { noteWith } from './lib/output.mjs';

const DEFAULT_BUDGET = 16000;
const DEFAULT_MODE = 'warn';
// Local first: a key written in settings.local.json wins over settings.json.
const SETTINGS_FILES = ['.claude/settings.local.json', '.claude/settings.json'];
const TASK_ISOLATION_CACHE = '.quality/task_isolation.json';
// The names Claude Code uses to launch a subagent: «Agent» today, «Task» before.
const SUBAGENT_TOOLS = new Set(['Agent', 'Task']);

// ── Read stdin payload ─────────────────────────────────────────────────

const raw = readStdinSync();
let payload = {};
try { payload = JSON.parse(raw); } catch { /* ignore */ }

const toolName = payload?.tool_name || payload?.toolName || '';
if (!SUBAGENT_TOOLS.has(toolName)) {
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
    `[context-budget-guard] BLOCKED — the subagent prompt (${toolName}) is ~${total} tokens ` +
      `(budget ${budget}, overshoot ${overshoot}). Breakdown: ${breakdownStr}. ` +
      `Reduce the prompt body, move shared context to ` +
      `.quality/evidence/{feature}/execution_context.json, or split the work ` +
      `into several subagents.`
  );
  process.exit(2);
}

// warn: a note to the agent (US-93/UC-9302: stderr with exit 0 reaches nobody).
noteWith('PreToolUse', '[context-budget-guard] El encargo del subagente se pasa de presupuesto', [
  `~${total} tokens (presupuesto ${budget}, ${overshoot} de más). Reparto: ${breakdownStr}.`,
  'Recórtalo o pasa el contexto común a .quality/evidence/{feature}/execution_context.json. La tarea sigue.',
]);

// ── Helpers ───────────────────────────────────────────────────────────

function readStdinSync() {
  try {
    return readFileSync(0, 'utf-8');
  } catch {
    return '';
  }
}

function taskIsolationOf(settings) {
  return settings?.specbox?.implement?.task_isolation ?? settings?.implement?.task_isolation ?? null;
}

function readSettings() {
  let budget;
  let mode;
  for (const file of SETTINGS_FILES) {
    if (!existsSync(file)) continue;
    try {
      const ti = taskIsolationOf(JSON.parse(readFileSync(file, 'utf-8')));
      if (budget === undefined && typeof ti?.task_budget_tokens === 'number') budget = ti.task_budget_tokens;
      if (mode === undefined && typeof ti?.task_budget_mode === 'string') mode = ti.task_budget_mode;
    } catch { /* ignore an unreadable file */ }
  }
  return { budget: budget ?? DEFAULT_BUDGET, mode: mode ?? DEFAULT_MODE };
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
    cache.last_tool_name = toolName;
    cache.last_event_at = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
    mkdirSync(dirname(TASK_ISOLATION_CACHE), { recursive: true });
    writeFileSync(
      TASK_ISOLATION_CACHE,
      JSON.stringify(cache, null, 2),
      'utf-8'
    );
  } catch { /* best-effort */ }
}
