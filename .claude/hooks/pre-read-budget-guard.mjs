#!/usr/bin/env node
/**
 * pre-read-budget-guard.mjs — PreToolUse hook for Read tool.
 *
 * NON-BLOCKING. Estimates tokens for the file being read (chars / 4).
 * Emits a warning to stderr if the file would exceed warn_pct of the
 * Claude window. The agent is free to proceed — this just makes the
 * cost visible so the agent can choose Grep/Explore instead of a
 * full Read on a heavy file.
 *
 * Configurable via .claude/settings.local.json:
 *   {
 *     "specbox": {
 *       "context_budget": {
 *         "window_tokens": 1000000,   // Claude window size
 *         "warn_pct": 5,              // warn at >= 5% of window
 *         "enabled": true             // set false to disable warnings
 *       }
 *     }
 *   }
 *
 * v5.30.0 — Session Continuity
 */

import { statSync, existsSync } from 'fs';
import { readStdin, readJsonFile } from './lib/utils.mjs';

const DEFAULT_CONFIG = {
  window_tokens: 1_000_000,
  warn_pct: 5,
  enabled: true,
};

function loadConfig() {
  const local = readJsonFile('.claude/settings.local.json');
  const cfg = local?.specbox?.context_budget || {};
  return { ...DEFAULT_CONFIG, ...cfg };
}

function main() {
  const cfg = loadConfig();
  if (!cfg.enabled) process.exit(0);

  const input = readStdin();
  if (!input) process.exit(0);

  let filePath = '';
  try {
    const parsed = JSON.parse(input);
    filePath = parsed.tool_input?.file_path || parsed.file_path || '';
  } catch {
    const m = input.match(/"file_path"\s*:\s*"([^"]*)"/);
    filePath = m ? m[1] : '';
  }
  if (!filePath || !existsSync(filePath)) process.exit(0);

  let size;
  try {
    size = statSync(filePath).size;
  } catch {
    process.exit(0);
  }

  const tokensEst = Math.floor(size / 4);
  const pct = (tokensEst / cfg.window_tokens) * 100;

  if (pct >= cfg.warn_pct) {
    const pctRounded = pct >= 10 ? Math.round(pct) : pct.toFixed(1);
    console.error(
      `[BUDGET] Heavy Read detected: ${filePath} (~${tokensEst.toLocaleString()} tokens, ${pctRounded}% of ${cfg.window_tokens.toLocaleString()}-token window).\n` +
      `         Consider using Grep, Explore agent, or Read with offset/limit instead of full read.`,
    );
  }
  process.exit(0);
}

try {
  main();
} catch {
  process.exit(0);
}
