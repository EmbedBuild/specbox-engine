/**
 * lib/signals.mjs — Client-side SpecBox signals (UC-663).
 *
 * The Python server/audit/signals.py read these from the engine state
 * registry on the MCP host (the VPS in remote setups) — wrong filesystem.
 * This client version reads everything from the LOCAL repo:
 *
 *   - ac_status / board     ← doc/tracking/items.json (FreeForm source of truth)
 *   - evidence / healing    ← .quality/evidence/<feature>/{*, healing.jsonl}
 *   - tests                 ← .quality/baselines/*.json
 *   - acceptance            ← derived from board AC + review states
 *
 * Never throws — returns the neutral default block on any failure, exactly
 * like the Python (so analyzers degrade gracefully when a project has no
 * board or no .quality tree).
 */

import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

/** Neutral defaults — identical keys to signals.py's `signals` dict. */
function defaults() {
  return {
    ac_status: { total: 0, completed: 0 },
    evidence: { uc_total: 0, uc_with_evidence: 0 },
    healing: { total_events: 0, resolved: 0, failed: 0 },
    board: { us_total: 0, us_blocked: 0 },
    acceptance: { accepted: 0, rejected: 0 },
    tests: { total: 0, passed: 0 },
    prd_divergence_ratio: 0.0,
  };
}

/** Safe JSON parse of a file, or null. */
function readJson(absPath) {
  try {
    return JSON.parse(readFileSync(absPath, 'utf-8'));
  } catch {
    return null;
  }
}

/**
 * Gather SpecBox signals for a project from the local filesystem.
 *
 * @param {string} root - absolute project root (git toplevel)
 * @returns {object} signals dict matching signals.py shape
 */
export function fetchSpecboxSignals(root) {
  const signals = defaults();

  collectBoardSignals(root, signals);
  collectEvidenceAndHealing(root, signals);
  collectTests(root, signals);

  return signals;
}

/**
 * AC / US / acceptance counts from doc/tracking/items.json.
 *
 * FreeForm items carry `labels` (e.g. ["UC"], ["AC"], ["US"]) and a `state`
 * (done / review / todo / backlog / ...). We count AC items for ac_status,
 * US items for board, and treat AC in a rejected/blocked state as acceptance
 * rejections. This is a heuristic equivalent of the server's per-project
 * state files, derived from the single local source of truth.
 */
function collectBoardSignals(root, signals) {
  const itemsPath = join(root, 'doc', 'tracking', 'items.json');
  if (!existsSync(itemsPath)) return;
  const items = readJson(itemsPath);
  if (!Array.isArray(items)) return;

  const hasLabel = (it, label) =>
    Array.isArray(it.labels) && it.labels.includes(label);
  const tipoOf = (it) => (it.meta && it.meta.tipo) || null;
  const isAc = (it) => hasLabel(it, 'AC') || tipoOf(it) === 'AC';
  const isUs = (it) => hasLabel(it, 'US') || tipoOf(it) === 'US';

  let acTotal = 0;
  let acDone = 0;
  let acRejected = 0;
  let usTotal = 0;
  let usBlocked = 0;

  for (const it of items) {
    const state = it.state || '';
    if (isAc(it)) {
      acTotal += 1;
      if (state === 'done') {
        acDone += 1;
      } else if (state === 'rejected' || state === 'blocked') {
        acRejected += 1;
      }
    } else if (isUs(it)) {
      usTotal += 1;
      if (state === 'blocked') usBlocked += 1;
    }
  }

  signals.ac_status = { total: acTotal, completed: acDone };
  signals.board = { us_total: usTotal, us_blocked: usBlocked };
  signals.acceptance = { accepted: acDone, rejected: acRejected };
}

/**
 * Evidence + healing from .quality/evidence/<feature>/.
 * Mirrors signals.py: a feature dir with any file counts as "has evidence";
 * healing.jsonl lines with result resolved/failed are tallied.
 */
function collectEvidenceAndHealing(root, signals) {
  const evidenceDir = join(root, '.quality', 'evidence');
  if (!isDir(evidenceDir)) return;

  let features;
  try {
    features = readdirSync(evidenceDir, { withFileTypes: true })
      .filter((e) => e.isDirectory())
      .map((e) => join(evidenceDir, e.name));
  } catch {
    return;
  }

  let withEvidence = 0;
  let totalHealing = 0;
  let resolved = 0;
  let failed = 0;

  for (const dir of features) {
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    if (entries.some((e) => e.isFile())) withEvidence += 1;

    const healingFile = join(dir, 'healing.jsonl');
    if (existsSync(healingFile)) {
      const text = safeRead(healingFile);
      for (const line of text.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        let event;
        try {
          event = JSON.parse(trimmed);
        } catch {
          continue;
        }
        totalHealing += 1;
        if (event.result === 'resolved') resolved += 1;
        else if (event.result === 'failed') failed += 1;
      }
    }
  }

  signals.evidence = { uc_total: features.length, uc_with_evidence: withEvidence };
  signals.healing = { total_events: totalHealing, resolved, failed };
}

/** tests total/passed from .quality/baselines/*.json (mirrors signals.py). */
function collectTests(root, signals) {
  const baselineDir = join(root, '.quality', 'baselines');
  if (!isDir(baselineDir)) return;
  let files;
  try {
    files = readdirSync(baselineDir).filter((f) => f.endsWith('.json'));
  } catch {
    return;
  }
  for (const f of files) {
    const data = readJson(join(baselineDir, f));
    if (!data) continue;
    const metrics = data.metrics || {};
    if (metrics.tests_total !== undefined) {
      signals.tests.total = Number(metrics.tests_total) || signals.tests.total;
    }
    if (metrics.tests_passed !== undefined) {
      signals.tests.passed = Number(metrics.tests_passed) || signals.tests.passed;
    }
  }
}

function isDir(absPath) {
  try {
    return statSync(absPath).isDirectory();
  } catch {
    return false;
  }
}

function safeRead(absPath) {
  try {
    return readFileSync(absPath, 'utf-8');
  } catch {
    return '';
  }
}
