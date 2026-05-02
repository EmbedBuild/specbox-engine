#!/usr/bin/env node
/**
 * file-ownership-guard.mjs — PreToolUse hook for Write/Edit (v5.32.0).
 *
 * Validates that the active sub-agent (declared in
 * .quality/active_agent.json) only writes inside its declared
 * ownership in .claude/skills/implement/file-ownership.md.
 *
 * Behaviour:
 *   - No active_agent.json    → no-op (the orchestrator itself is
 *                              acting; not subject to this guard).
 *   - mode=warn (default)     → stderr WARNING, exit 0.
 *   - mode=strict             → stderr BLOCKED, exit 2 with actionable
 *                              message (which agent should own the path).
 *   - mode=off                → no-op.
 *
 * Settings:
 *   specbox.implement.task_isolation.ownership_mode (default "warn")
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { parseOwnershipMap, pathAllowedForAgent, isSuspiciousPath } from './lib/ownership-map.mjs';
import { readActiveAgent } from './lib/execution-context.mjs';

const SETTINGS_PATH = '.claude/settings.local.json';
const TASK_ISOLATION_CACHE = '.quality/task_isolation.json';
const DEFAULT_MODE = 'warn';

const raw = readStdinSync();
let payload = {};
try { payload = JSON.parse(raw); } catch { /* ignore */ }

const toolName = payload?.tool_name || payload?.toolName || '';
if (toolName !== 'Write' && toolName !== 'Edit') {
  process.exit(0);
}

const active = readActiveAgent();
if (!active?.agent) {
  // No active sub-agent = the orchestrator is doing the write itself.
  // Out of scope for this guard.
  process.exit(0);
}

const mode = readMode();
if (mode === 'off') {
  process.exit(0);
}

const filePath = extractFilePath(payload);
if (!filePath) {
  // Can't extract the target path — fail open.
  process.exit(0);
}

if (isSuspiciousPath(filePath)) {
  // Always block path traversal, regardless of mode.
  console.error(
    `[file-ownership-guard] BLOCKED — suspicious path '${filePath}' ` +
      `(.. or absolute path). Use a repo-relative path inside the project root.`
  );
  bumpCounter('tasks_failed_ownership');
  process.exit(2);
}

const map = parseOwnershipMap();
const allowed = pathAllowedForAgent(filePath, active.agent, map);

if (allowed === true) {
  process.exit(0);
}

if (allowed === null) {
  // Unknown agent or empty ownership → fail-open with a hint.
  console.error(
    `[file-ownership-guard] WARNING — agent ${active.agent} is not in ` +
      `the ownership map (or the map is empty). Path ${filePath} allowed by default. ` +
      `Update .claude/skills/implement/file-ownership.md if this is unexpected.`
  );
  process.exit(0);
}

// allowed === false → mismatch
const ownerHint = suggestOwner(filePath, map);
const message = ownerHint
  ? `Path ${filePath} is owned by ${ownerHint}, not ${active.agent}. ` +
    `Either delegate the write to ${ownerHint}, or report it as a pending dependency.`
  : `Path ${filePath} does not match the ownership of ${active.agent}. ` +
    `Either delegate the write to the correct agent, or report it as a pending dependency.`;

bumpCounter('tasks_failed_ownership');

if (mode === 'strict') {
  console.error(`[file-ownership-guard] BLOCKED — ${message}`);
  process.exit(2);
}

console.error(`[file-ownership-guard] WARNING — ${message} Run will proceed.`);
process.exit(0);

// ── Helpers ───────────────────────────────────────────────────────────

function readStdinSync() {
  try { return readFileSync(0, 'utf-8'); } catch { return ''; }
}

function readMode() {
  if (!existsSync(SETTINGS_PATH)) return DEFAULT_MODE;
  try {
    const settings = JSON.parse(readFileSync(SETTINGS_PATH, 'utf-8'));
    const m = settings?.specbox?.implement?.task_isolation?.ownership_mode;
    return typeof m === 'string' ? m : DEFAULT_MODE;
  } catch { return DEFAULT_MODE; }
}

function extractFilePath(payload) {
  const ti = payload?.tool_input ?? {};
  if (typeof ti.file_path === 'string') return normalisePath(ti.file_path);
  if (typeof ti.path === 'string') return normalisePath(ti.path);
  return null;
}

function normalisePath(p) {
  if (!p) return p;
  // If absolute, try to make relative to cwd. We accept both forms but
  // matching is done relative to repo root.
  const cwd = process.cwd();
  if (p.startsWith(cwd + '/')) return p.slice(cwd.length + 1);
  if (p.startsWith('/')) {
    // absolute path that is NOT under cwd — keep absolute so
    // isSuspiciousPath catches it.
    return p;
  }
  return p.replace(/^\.\//, '');
}

function suggestOwner(path, map) {
  for (const [agent, globs] of Object.entries(map)) {
    if (pathAllowedForAgent(path, agent, { [agent]: globs }) === true) {
      return agent;
    }
  }
  return null;
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
