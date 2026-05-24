#!/usr/bin/env node
/**
 * app-docs-sync-guard.mjs — PostToolUse hook for git commit (v5.29.0 PR-13)
 *
 * Mode: warning-only in v5.29.0.x. Detects drift between canonical docs
 * (doc/app/app_prd.md, app_spec.md, and v6.0 app_market.md) and the
 * recorded signatures in `.quality/app_docs_sync.lock`. Emits a visible
 * warning but does not block the commit. From v5.29.1 onwards the same
 * hook can be promoted to BLOCKING by flipping `BLOCK_ON_DRIFT=true` in
 * the project's `.claude/settings.local.json` under
 * `specbox.app_docs_sync`.
 *
 * v6.0 (UC-D005): the hook iterates over the canonical-docs registry
 * loaded from `templates/canonical_docs.json` (descriptor generated from
 * `server/app_docs/registry.py`). For each doc:
 *   - If the file doesn't exist on disk → skip (no warning).
 *   - If the doc's `introduced_in` > project's `engine_version_at_onboard`
 *     → skip (the project is on a pre-v6.0 version that didn't know
 *     about this doc).
 *   - If all manual zones carry `status="template-pristine"` → skip
 *     (plantilla vacía recién creada por `upgrade_project`).
 *   - Otherwise compare current signature vs locked baseline; warn if drift.
 *
 * Backwards compat: when the JSON descriptor is missing (e.g. project on
 * v5.x that never received v6.0), the hook falls back to hardcoded
 * `app_prd` + `app_spec` checks — same behavior as v5.29.x.
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

import { existsSync, readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { createHash } from 'crypto';
import { getActiveUC } from './lib/config.mjs';
import { printWarning } from './lib/output.mjs';

function printError(message) {
  process.stderr.write(`\nERROR: ${message}\n`);
}
import { appendLine, readJsonFile } from './lib/utils.mjs';

const LOCK_PATH = '.quality/app_docs_sync.lock';
const TELEMETRY_PATH = '.quality/app_docs_drift.jsonl';

// ─── Canonical docs registry (loaded from JSON descriptor) ────────────

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Locate `templates/canonical_docs.json` relative to the engine repo.
 * The hook runs from the *project* CWD, not the engine repo, so we walk
 * upwards from this script's location until we find the descriptor (the
 * script is in `<engine>/.claude/hooks/`, the descriptor in
 * `<engine>/templates/`).
 *
 * In multirepo satellite mode the hook may run in a project that doesn't
 * have its own templates/ — fall back to looking next to the script's
 * symlink target.
 */
function locateCanonicalDocsJson() {
  // Try project CWD first (some projects ship the descriptor locally).
  const localTry = join(process.cwd(), 'templates', 'canonical_docs.json');
  if (existsSync(localTry)) return localTry;
  // Walk up from the script's actual location (works through symlinks
  // because install.sh symlinks .claude/hooks/ to the engine repo).
  let dir = __dirname;
  for (let i = 0; i < 6; i += 1) {
    const candidate = join(dir, 'templates', 'canonical_docs.json');
    if (existsSync(candidate)) return candidate;
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

const LEGACY_FALLBACK_DOCS = [
  {
    id: 'app_prd',
    path: 'doc/app/app_prd.md',
    introduced_in: '5.29.0',
  },
  {
    id: 'app_spec',
    path: 'doc/app/app_spec.md',
    introduced_in: '5.29.0',
  },
];

function loadCanonicalDocs() {
  const jsonPath = locateCanonicalDocsJson();
  if (!jsonPath) {
    // Fallback to v5.29 hardcoded behavior — no v6.0 descriptor available.
    return LEGACY_FALLBACK_DOCS;
  }
  try {
    const raw = readFileSync(jsonPath, 'utf-8');
    const data = JSON.parse(raw);
    if (data?.schema_version !== 1 || !Array.isArray(data.docs)) {
      // Unknown schema — fall back to safety.
      return LEGACY_FALLBACK_DOCS;
    }
    return data.docs.map((d) => ({
      id: d.id,
      path: d.path,
      introduced_in: d.introduced_in,
    }));
  } catch {
    return LEGACY_FALLBACK_DOCS;
  }
}

// ─── Version comparison ──────────────────────────────────────────────

/**
 * Parse a semver-ish string into a tuple of numbers. '6.0.0' → [6,0,0].
 * Tolerates pre-release suffixes by picking up numeric components only.
 * Mirrors `registry._semver_tuple` in Python so both sides agree.
 */
function semverTuple(version) {
  if (!version) return [0];
  const parts = String(version).match(/\d+/g);
  if (!parts || parts.length === 0) return [0];
  return parts.map((p) => parseInt(p, 10));
}

function semverLte(a, b) {
  const at = semverTuple(a);
  const bt = semverTuple(b);
  const len = Math.max(at.length, bt.length);
  for (let i = 0; i < len; i += 1) {
    const av = at[i] ?? 0;
    const bv = bt[i] ?? 0;
    if (av < bv) return true;
    if (av > bv) return false;
  }
  return true; // equal
}

function readEngineVersionAtOnboard() {
  const settings = readJsonFile('.claude/settings.local.json') || {};
  const v = settings?.specbox?.engine_version_at_onboard;
  return v || null; // null → "unknown" → conservative policy
}

function docIsEligible(doc, engineVersion) {
  // Conservative when unknown: only docs introduced in <= 5.29.0.
  if (!engineVersion) return semverLte(doc.introduced_in, '5.29.0');
  return semverLte(doc.introduced_in, engineVersion);
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
    // Reset lastIndex so multiple attr scans on different matches work.
    ATTR_RE.lastIndex = 0;
    while ((am = ATTR_RE.exec(match[1])) !== null) {
      attrs[am[1]] = am[2];
    }
    if (!attrs.id || !attrs.kind) continue;
    const body = match[2].replace(/^\n/, '').replace(/\n$/, '');
    zones.push({
      id: attrs.id,
      kind: attrs.kind,
      status: attrs.status || null,
      body,
    });
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

function docIsTemplatePristine(zones) {
  const manual = zones.filter((z) => z.kind === 'manual');
  if (manual.length === 0) return false;
  return manual.every((z) => z.status === 'template-pristine');
}

// ─── Settings ────────────────────────────────────────────────────────

function readBlockingFlag() {
  const settings = readJsonFile('.claude/settings.local.json') || {};
  return Boolean(settings?.specbox?.app_docs_sync?.block_on_drift);
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
  const zones = parseZones(content);
  // v6.0: pristine plantilla doesn't count as drift.
  if (docIsTemplatePristine(zones)) {
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
const engineVersion = readEngineVersionAtOnboard();
const docs = loadCanonicalDocs();

const drifts = [];
for (const doc of docs) {
  if (!docIsEligible(doc, engineVersion)) continue; // doc introduced after project's onboard version
  const drift = checkDoc(doc.id, doc.path, sigs[doc.id]);
  if (drift) drifts.push(drift);
}

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
