#!/usr/bin/env node
/**
 * app-docs-sync-guard.mjs — PostToolUse hook for git commit (v5.29.0 PR-13)
 *
 * Mode: warning-only in v5.29.0.x. Detects drift between
 * `doc/app/app_prd.md` / `doc/app/app_spec.md` and the recorded
 * signature in `.quality/app_docs_sync.lock`. Emits a visible warning
 * but does not block the commit. From v5.29.1 onwards the same hook
 * can be promoted to BLOCKING by flipping `BLOCK_ON_DRIFT=true` in the
 * project's `.claude/settings.local.json` under `specbox.app_docs_sync`.
 *
 * Skipped when:
 *   - doc/app/ does not exist (project on legacy v5.28 flow).
 *   - .quality/app_docs_sync.lock does not exist (no baseline yet).
 *   - The active UC marker is set (feature in progress takes priority,
 *     per Case 7 of the v5.29 migration plan).
 *
 * Telemetry: every detection writes a JSONL entry to
 * `.quality/app_docs_drift.jsonl` so the drift detector (PR-15) can
 * surface it via heartbeat to Sala de Máquinas.
 */

import { existsSync, readFileSync, statSync } from 'fs';
import { join } from 'path';
import { createHash } from 'crypto';
import { getActiveUC } from './lib/config.mjs';
import { printWarning } from './lib/output.mjs';

function printError(message) {
  process.stderr.write(`\nERROR: ${message}\n`);
}
import { appendLine, readJsonFile } from './lib/utils.mjs';

const PRD_PATH = 'doc/app/app_prd.md';
const SPEC_PATH = 'doc/app/app_spec.md';
const LOCK_PATH = '.quality/app_docs_sync.lock';
const TELEMETRY_PATH = '.quality/app_docs_drift.jsonl';

// ─── Settings ────────────────────────────────────────────────────────

function readBlockingFlag() {
  const settings = readJsonFile('.claude/settings.local.json') || {};
  return Boolean(settings?.specbox?.app_docs_sync?.block_on_drift);
}

// ─── Zone signature (mirrors server/app_docs/zones.py) ───────────────

const ZONE_RE = /<!--\s*@specbox:zone\s+start\s+([^>]+?)\s*-->([\s\S]*?)<!--\s*@specbox:zone\s+end\s*-->/g;
const ATTR_RE = /(\w+)\s*=\s*"([^"]*)"/g;

function parseZones(content) {
  const zones = [];
  let match;
  while ((match = ZONE_RE.exec(content)) !== null) {
    const attrs = {};
    let am;
    while ((am = ATTR_RE.exec(match[1])) !== null) {
      attrs[am[1]] = am[2];
    }
    if (!attrs.id || !attrs.kind) continue;
    // Body is what's between the markers, trimmed of the leading/trailing newline.
    const body = match[2].replace(/^\n/, '').replace(/\n$/, '');
    zones.push({ id: attrs.id, kind: attrs.kind, body });
  }
  return zones;
}

function computeSignature(content) {
  const zones = parseZones(content);
  zones.sort((a, b) => a.id.localeCompare(b.id));
  const hash = createHash('sha256');
  for (const z of zones) {
    hash.update(z.id);
    hash.update('\x00');
    hash.update(z.kind);
    hash.update('\x00');
    hash.update(z.body);
    hash.update('\x00\x00');
  }
  return hash.digest('hex');
}

// ─── Detection ───────────────────────────────────────────────────────

function recordDrift(entry) {
  try {
    appendLine(TELEMETRY_PATH, JSON.stringify(entry));
  } catch {
    // telemetry must never break the hook
  }
}

function checkDoc(name, path, lockedSig) {
  if (!existsSync(path)) {
    return null; // not present = no drift
  }
  let content;
  try {
    content = readFileSync(path, 'utf-8');
  } catch {
    return null;
  }
  const currentSig = computeSignature(content);
  if (!lockedSig) {
    return null; // no baseline yet — ignored
  }
  if (currentSig === lockedSig) {
    return null;
  }
  return {
    document: name,
    path,
    locked_signature: lockedSig,
    current_signature: currentSig,
    detected_at: new Date().toISOString(),
  };
}

// ─── Main ────────────────────────────────────────────────────────────

if (!existsSync('doc/app')) {
  process.exit(0); // legacy project — nothing to guard
}
if (!existsSync(LOCK_PATH)) {
  process.exit(0); // no baseline yet — first sync hasn't run
}

const activeUC = getActiveUC();
if (activeUC && activeUC.feature) {
  // Case 7: feature in progress — defer enforcement. Still log telemetry.
  process.exit(0);
}

const lock = readJsonFile(LOCK_PATH) || {};
const sigs = lock.signatures || {};
const drifts = [
  checkDoc('app_prd', PRD_PATH, sigs.app_prd),
  checkDoc('app_spec', SPEC_PATH, sigs.app_spec),
].filter(Boolean);

if (drifts.length === 0) {
  process.exit(0);
}

for (const d of drifts) {
  recordDrift(d);
}

const blocking = readBlockingFlag();
const summary = drifts
  .map(
    (d) =>
      `  - ${d.document} (${d.path}): expected ${d.locked_signature.slice(0, 12)}…, ` +
      `actual ${d.current_signature.slice(0, 12)}…`
  )
  .join('\n');

const message =
  `[APP-DOCS-SYNC] doc/app/*.md drifted since the last recorded sync:\n` +
  `${summary}\n` +
  `Run \`/app-sync --check\` for details, or \`/app-sync --repair\` to reconcile.\n` +
  `Telemetry: ${TELEMETRY_PATH}`;

if (blocking) {
  printError(message);
  process.exit(1);
}

printWarning(
  `${message}\n` +
    `(Warning-only mode — v5.29.0 default. Set ` +
    `specbox.app_docs_sync.block_on_drift = true in .claude/settings.local.json ` +
    `to make this BLOCKING from v5.29.1.)`
);
process.exit(0);
