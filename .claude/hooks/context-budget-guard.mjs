#!/usr/bin/env node
/**
 * context-budget-guard.mjs — PreToolUse hook for subagent launches (v5.32.0, UC-12208, UC-12210).
 *
 * Estimates the tokens of the prompt of a subagent (/implement or any skill that delegates) and,
 * when it exceeds the budget, notes it («warn», the default) or does not launch it («block»).
 *
 * Claude Code launches subagents with the «Agent» tool; older versions called it «Task». The hook is
 * registered with the matcher «Agent|Task» and accepts both (until UC-12208 it only listened to
 * «Task» and never ran).
 *
 * Mode (UC-12210) — the EP-20 measure `context_budget`:
 *   1. `task_isolation.task_budget_mode` in .claude/settings.local.json (specbox.implement…) wins;
 *   2. then in .claude/settings.json (implement…), unless it is the template's «warn», which is not
 *      a decision of the project;
 *   3. otherwise the board's policy (lib/enforcement-policy.mjs), «warn» unless a person changed it.
 *   Values: off | warn | block (`strict`, the old name, means block).
 * Budget: `task_isolation.task_budget_tokens` (default 16000), read the same way.
 *
 * Side-effects:
 *   - every launch → one line in .quality/logs/context-budget.jsonl (tokens, budget, mode, outcome);
 *   - .quality/task_isolation.json counters and `last_tool_name`;
 *   - native: a block, and the next launch of that UC within budget, are recorded on the board
 *     (record_enforcement_event), so the impact report counts blocks and corrections (UC-12213);
 *     FreeForm: the same in doc/tracking/enforcement_events.jsonl.
 */

import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join } from 'node:path';
import { estimatePromptTokens } from './lib/token-counter.mjs';
import { noteWith } from './lib/output.mjs';
import { getProjectConfig } from './lib/config.mjs';
import { leerPolitica, modoDe, textoDeMedida } from './lib/enforcement-policy.mjs';
import { cabecerasDelDispositivo, URL_POR_DEFECTO } from './lib/heartbeat-send.mjs';
import { llamarTool } from './lib/mcp-client.mjs';

const DEFAULT_BUDGET = 16000;
const TEMPLATE_MODE = 'warn';
const MEASURE = 'context_budget';
const TASK_ISOLATION_CACHE = '.quality/task_isolation.json';
const LOG = '.quality/logs/context-budget.jsonl';
const STATE = '.quality/context_budget_state.json';
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

// ── Resolve budget and mode ────────────────────────────────────────────

const local = taskIsolationOf(readJson('.claude/settings.local.json'));
const shared = taskIsolationOf(readJson('.claude/settings.json'));
const budget = [local?.task_budget_tokens, shared?.task_budget_tokens].find((v) => typeof v === 'number') ?? DEFAULT_BUDGET;
const config = getProjectConfig();
const { mode, source } = await resolveMode();
if (mode === 'off') {
  process.exit(0);
}

// ── Estimate ──────────────────────────────────────────────────────────

const { total, breakdown } = estimatePromptTokens(payload);
const activeUc = readJson('.quality/active_uc.json')?.uc_id || '';

if (total <= budget) {
  bumpCounter('tasks_run_total');
  log('under');
  await recordCorrection();
  process.exit(0);
}

// ── Over budget ───────────────────────────────────────────────────────

bumpCounter('tasks_failed_budget');

const breakdownStr = Object.entries(breakdown)
  .map(([k, v]) => `${k}=${v}`)
  .join(', ');
const overshoot = total - budget;
const how =
  'Recorta el encargo, pasa el contexto común a .quality/evidence/{feature}/execution_context.json ' +
  'o divide el trabajo en varios subagentes.';

if (mode === 'block') {
  log('blocked');
  await recordEvent('blocked');
  console.error(
    textoDeMedida({
      medida: MEASURE,
      modo: 'block',
      motivo: `el encargo del subagente (${toolName}) tiene ~${total} tokens y el presupuesto es ${budget} (${overshoot} de más). Reparto: ${breakdownStr}.`,
      comoSeguir: `${how} El subagente no se ha lanzado.`,
    }),
  );
  process.exit(2);
}

// warn: a note to the agent (US-93/UC-9302: stderr with exit 0 reaches nobody).
log('warned');
noteWith('PreToolUse', '[context-budget-guard] El encargo del subagente se pasa de presupuesto', [
  `~${total} tokens (presupuesto ${budget}, ${overshoot} de más). Reparto: ${breakdownStr}.`,
  `${how} La tarea sigue (medida context_budget en «warn»).`,
]);

// ── Helpers ───────────────────────────────────────────────────────────

function readStdinSync() {
  try {
    return readFileSync(0, 'utf-8');
  } catch {
    return '';
  }
}

function readJson(path) {
  try {
    return existsSync(path) ? JSON.parse(readFileSync(path, 'utf-8')) : null;
  } catch {
    return null;
  }
}

function taskIsolationOf(settings) {
  return settings?.specbox?.implement?.task_isolation ?? settings?.implement?.task_isolation ?? null;
}

function normal(m) {
  return m === 'strict' ? 'block' : ['off', 'warn', 'block'].includes(m) ? m : null;
}

/** The mode and where it comes from: local setting, the project's setting, or the board's policy. */
async function resolveMode() {
  const fromLocal = normal(local?.task_budget_mode);
  if (fromLocal) return { mode: fromLocal, source: 'settings.local.json' };
  const fromShared = normal(shared?.task_budget_mode);
  if (fromShared && fromShared !== TEMPLATE_MODE) return { mode: fromShared, source: 'settings.json' };
  const politica = await leerPolitica({
    root: process.cwd(),
    backendType: config.backendType,
    boardId: config.boardId,
    trackingDir: config.freeformRoot,
  });
  return { mode: modoDe(politica, MEASURE), source: `política (${politica.fuente})` };
}

function log(outcome) {
  try {
    mkdirSync(dirname(LOG), { recursive: true });
    const line = { at: new Date().toISOString(), tool: toolName, tokens: total, budget, mode, source, outcome };
    if (activeUc) line.uc_id = activeUc;
    appendFileSync(LOG, `${JSON.stringify(line)}\n`);
  } catch { /* best-effort */ }
}

/** A block, or the launch within budget that follows one, goes to the board (UC-12213). */
async function recordEvent(outcome) {
  if (!activeUc) return;
  try {
    writeFileSync(STATE, JSON.stringify(outcome === 'blocked' ? { blocked_uc: activeUc } : {}));
  } catch { /* best-effort */ }
  const at = new Date().toISOString();
  if (config.backendType === 'freeform') {
    try {
      const dir = config.freeformRoot && isAbsolute(config.freeformRoot) ? config.freeformRoot : join('doc', 'tracking');
      mkdirSync(dir, { recursive: true });
      appendFileSync(join(dir, 'enforcement_events.jsonl'), `${JSON.stringify({ measure: MEASURE, uc_id: activeUc, outcome, at, by: 'context-budget-guard' })}\n`);
    } catch { /* best-effort */ }
    return;
  }
  if (config.backendType !== 'native' || !config.boardId || process.env.SPECBOX_ENFORCEMENT_POLICY === 'off') return;
  try {
    const url = process.env.SPECBOX_MCP_URL || URL_POR_DEFECTO;
    const cabeceras = await cabecerasDelDispositivo({ ...process.env, CLAUDE_CODE_MCP_SERVER_URL: url });
    if (!cabeceras.Authorization) return;
    await llamarTool({
      url,
      cabeceras,
      nombre: 'record_enforcement_event',
      args: { measure: MEASURE, uc_id: activeUc, outcome, board_id: config.boardId },
      topeMs: 2500,
    });
  } catch { /* sin red: el registro local queda */ }
}

async function recordCorrection() {
  const state = readJson(STATE);
  if (state?.blocked_uc && state.blocked_uc === activeUc) await recordEvent('passed');
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
