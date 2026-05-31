#!/usr/bin/env node
/**
 * run-audit.mjs — Client-side ISO/IEC 25010 orchestrator (UC-663).
 *
 * Runs the 8 SQuaRE analyzers against the local repo and prints a
 * QualityReport JSON to stdout. The /audit skill captures that JSON and
 * submits it to the MCP via `submit_quality_audit(project, report)`, which
 * validates it server-side (server/audit/schema.py) and renders the PDF.
 *
 * v6.0.1 MCP Path Contract: analyzers MUST run on the client so they scan the
 * user's real filesystem, not the MCP host. This is the entry point for that.
 *
 * Usage:
 *   node .quality/scripts/audit/run-audit.mjs [--project NAME] [--stack STACK]
 *        [--scope CHAR] [--root DIR] [--commit SHA]
 *
 * --scope limits to a single characteristic id (e.g. security) — others are
 * emitted as skipped, mirroring the server's partial-scope behaviour.
 *
 * Importable too: `buildReport(opts)` returns the report dict without any I/O
 * to stdout, used by the tests.
 */

import { execSync } from 'node:child_process';
import { basename } from 'node:path';

import {
  SQUARE_ORDER, SquareCharacteristic, TrafficLight,
  AUDIT_SCHEMA_VERSION, characteristicResult, nowIso, newAuditId, round2,
} from './lib/schema.mjs';
import { globalScore, trafficLight } from './lib/scoring.mjs';
import { fetchSpecboxSignals } from './lib/signals.mjs';

import * as functional from './analyzers/functional_suitability.mjs';
import * as performance from './analyzers/performance_efficiency.mjs';
import * as compatibility from './analyzers/compatibility.mjs';
import * as usability from './analyzers/usability.mjs';
import * as reliability from './analyzers/reliability.mjs';
import * as security from './analyzers/security.mjs';
import * as maintainability from './analyzers/maintainability.mjs';
import * as portability from './analyzers/portability.mjs';

/** Analyzer modules keyed by characteristic id, in canonical order. */
const ANALYZERS = {
  [SquareCharacteristic.FUNCTIONAL_SUITABILITY]: functional,
  [SquareCharacteristic.PERFORMANCE_EFFICIENCY]: performance,
  [SquareCharacteristic.COMPATIBILITY]: compatibility,
  [SquareCharacteristic.USABILITY]: usability,
  [SquareCharacteristic.RELIABILITY]: reliability,
  [SquareCharacteristic.SECURITY]: security,
  [SquareCharacteristic.MAINTAINABILITY]: maintainability,
  [SquareCharacteristic.PORTABILITY]: portability,
};

/**
 * Run one analyzer module. Some return a bare result dict, some return
 * { result, toolsUsed } (security, maintainability). Normalise both.
 * Never throws — a failing analyzer becomes a skipped characteristic so one
 * bad block can't sink the whole audit.
 *
 * @returns {{ result: object, toolsUsed: object[] }}
 */
function runOne(mod, charId, ctx) {
  try {
    const out = mod.analyze(ctx);
    if (out && out.result) {
      return { result: out.result, toolsUsed: out.toolsUsed || [] };
    }
    return { result: out, toolsUsed: [] };
  } catch (err) {
    return {
      result: characteristicResult({
        characteristic: charId,
        score: 0,
        traffic_light: TrafficLight.RED,
        justification: `Analyzer crashed: ${err && err.message ? err.message : String(err)}`,
        skipped: true,
        skipped_reason: 'analyzer_error',
      }),
      toolsUsed: [],
    };
  }
}

/** A skipped characteristic placeholder (for --scope filtering). */
function skippedResult(charId) {
  return characteristicResult({
    characteristic: charId,
    score: 0,
    traffic_light: TrafficLight.GREEN, // skipped doesn't penalize; light is cosmetic
    justification: 'Skipped (out of requested scope).',
    skipped: true,
    skipped_reason: 'out_of_scope',
  });
}

/**
 * Build the full QualityReport dict. No stdout — returns the object.
 *
 * @param {object} [opts]
 * @param {string} [opts.root] - project root (default: git toplevel of CWD)
 * @param {string} [opts.project] - project name (default: basename of root)
 * @param {string} [opts.stack] - detected stack (default: 'unknown')
 * @param {string[]} [opts.infra]
 * @param {string} [opts.scope] - single characteristic id, or 'full'
 * @param {string} [opts.commit] - commit sha (default: git HEAD short)
 * @param {object} [opts.signals] - inject signals (tests bypass FS read)
 * @returns {object} QualityReport dict (submit_quality_audit-ready)
 */
export function buildReport(opts = {}) {
  const root = opts.root || gitToplevel();
  const project = opts.project || basename(root);
  const stack = opts.stack || 'unknown';
  const infra = opts.infra || [];
  const scope = opts.scope || 'full';
  const commit = opts.commit || gitHead(root);
  const signals = opts.signals || fetchSpecboxSignals(root);

  const ctx = { root, projectName: project, stack, infra, signals };

  const results = [];
  const toolsUsed = [];
  for (const charId of SQUARE_ORDER) {
    if (scope !== 'full' && scope !== charId) {
      results.push(skippedResult(charId));
      continue;
    }
    const { result, toolsUsed: tu } = runOne(ANALYZERS[charId], charId, ctx);
    results.push(result);
    toolsUsed.push(...tu);
  }

  const activeScores = results.filter((r) => !r.skipped).map((r) => ({ score: r.score, skipped: false }));
  const gScore = globalScore(activeScores);

  return {
    audit_schema_version: AUDIT_SCHEMA_VERSION,
    audit_id: opts.auditId || newAuditId(),
    project,
    project_path: root,
    commit,
    generated_at: nowIso(),
    stack: { stack, infra },
    global_score: round2(gScore),
    global_traffic_light: trafficLight(gScore),
    characteristics: results,
    tools_used: toolsUsed,
    meta: { generator: 'run-audit.mjs', scope },
  };
}

function gitToplevel() {
  return execSync('git rev-parse --show-toplevel', { encoding: 'utf-8' }).trim();
}

function gitHead(root) {
  try {
    return execSync('git rev-parse --short HEAD', { cwd: root, encoding: 'utf-8' }).trim();
  } catch {
    return 'unknown';
  }
}

function parseArgs(argv) {
  const opts = {};
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--project') opts.project = argv[++i];
    else if (a === '--stack') opts.stack = argv[++i];
    else if (a === '--scope') opts.scope = argv[++i];
    else if (a === '--root') opts.root = argv[++i];
    else if (a === '--commit') opts.commit = argv[++i];
  }
  return opts;
}

// CLI entry — only when run directly, not when imported by tests.
if (import.meta.url === `file://${process.argv[1]}`) {
  const report = buildReport(parseArgs(process.argv.slice(2)));
  process.stdout.write(JSON.stringify(report, null, 2) + '\n');
}
