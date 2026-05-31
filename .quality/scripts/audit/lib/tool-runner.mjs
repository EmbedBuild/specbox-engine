/**
 * lib/tool-runner.mjs — Subprocess wrapper for optional external audit tools (UC-663).
 *
 * Mirrors server/audit/tool_runner.py: every external tool (semgrep, gitleaks,
 * pip-audit, npm, lizard, jscpd, checkov) is OPTIONAL. A missing binary is
 * reported in tools_used with status "missing" and never aborts the audit.
 *
 * Uses spawnSync so a slow tool can be bounded by a timeout. We resolve the
 * binary with `which` first so "missing" is distinguishable from "ran and
 * failed" (spawnSync ENOENT is also caught as a fallback).
 */

import { spawnSync } from 'node:child_process';

/**
 * @typedef {Object} ToolResult
 * @property {boolean} available - binary found and spawned
 * @property {boolean} timedOut
 * @property {number|null} returncode
 * @property {string} stdout
 * @property {string} stderr
 */

/** True if `bin` resolves on PATH. */
export function isAvailable(bin) {
  const r = spawnSync('which', [bin], { encoding: 'utf-8' });
  return r.status === 0 && Boolean((r.stdout || '').trim());
}

/**
 * Run an external tool with a timeout. Never throws.
 *
 * @param {string[]} argv - [bin, ...args]
 * @param {object} [opts]
 * @param {string} [opts.cwd]
 * @param {number} [opts.timeout] - seconds (mirrors python float seconds)
 * @param {number} [opts.maxBuffer] - bytes (default 16 MiB for big JSON reports)
 * @returns {ToolResult}
 */
export function runTool(argv, opts = {}) {
  const [bin, ...args] = argv;
  const result = {
    available: false,
    timedOut: false,
    returncode: null,
    stdout: '',
    stderr: '',
  };
  if (!isAvailable(bin)) {
    return result;
  }
  let r;
  try {
    r = spawnSync(bin, args, {
      cwd: opts.cwd,
      encoding: 'utf-8',
      timeout: (opts.timeout ?? 120) * 1000,
      maxBuffer: opts.maxBuffer ?? 16 * 1024 * 1024,
    });
  } catch {
    // ENOENT despite `which` (race) or other spawn error → treat as missing.
    return result;
  }
  result.available = true;
  result.stdout = r.stdout || '';
  result.stderr = r.stderr || '';
  result.returncode = r.status;
  // spawnSync sets r.signal === 'SIGTERM' and r.error.code 'ETIMEDOUT' on timeout.
  if (r.error && (r.error.code === 'ETIMEDOUT' || r.signal === 'SIGTERM')) {
    result.timedOut = true;
  }
  return result;
}

/**
 * Best-effort version string for a tool (mirrors detect_version).
 * @param {string} bin
 * @param {string} [flag] - default "--version"
 * @returns {string|null}
 */
export function detectVersion(bin, flag = '--version') {
  if (!isAvailable(bin)) return null;
  const r = spawnSync(bin, [flag], { encoding: 'utf-8', timeout: 10_000 });
  const out = ((r.stdout || '') + (r.stderr || '')).trim();
  return out ? out.split('\n')[0].trim() : null;
}
