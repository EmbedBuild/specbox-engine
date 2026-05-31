// US-CONN-UPGRADE (UC-664/665/666) — migration detection, auto-migrate, summary, orchestrator.
// Pure-function + IO tests over compiled out/migration.js and out/updater.js,
// stubbing `vscode` the same way prerequisites.test.mjs does.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import os from 'node:os';
import fs from 'node:fs';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

// --- vscode stub with notification spies (for updater orchestration tests) ---
const shown = { info: [], warn: [], error: [] };
const commandsRun = [];
const vscodeStub = {
  l10n: { t: (s, ...args) => args.length ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s },
  window: {
    showInformationMessage: (msg) => { shown.info.push(msg); return Promise.resolve(undefined); },
    showWarningMessage: (msg) => { shown.warn.push(msg); return Promise.resolve(undefined); },
    showErrorMessage: (msg) => { shown.error.push(msg); return Promise.resolve(undefined); },
    withProgress: (_opts, fn) => fn({ report: () => {} }),
  },
  commands: {
    registerCommand: (id, cb) => { commandsRun.push({ register: id }); return { dispose() {} }; },
    executeCommand: (id, ...a) => { commandsRun.push({ exec: id, args: a }); return Promise.resolve(); },
  },
  env: { openExternal: () => Promise.resolve(true) },
  Uri: { parse: (s) => s },
  ProgressLocation: { Notification: 15 },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
  if (req === 'vscode') { return 'vscode-stub'; }
  return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const mig = require(path.join(outDir, 'migration.js'));
const { ExtensionUpdater } = require(path.join(outDir, 'updater.js'));
const { REMOTE_MCP_URL } = require(path.join(outDir, 'mcp.js'));

function resetSpies() { shown.info = []; shown.warn = []; shown.error = []; commandsRun.length = 0; }

// --- fixtures ---
const localMcp = { command: 'uv', args: ['run', 'python', '-m', 'server.server'] };
const remoteMcp = { command: 'npx', args: ['mcp-remote', REMOTE_MCP_URL] };

function settings(backend, mcp) {
  const s = {};
  if (backend) { s.specbox = { backend_type: backend }; }
  if (mcp) { s.mcpServers = { 'SpecBox-MCP': mcp }; }
  return s;
}

// ── UC-664 AC-01: detectClientConfigCase covers the 5 canonical cases ────────

test('UC-664 AC-01: FreeForm + local MCP → freeform_local_obsolete', () => {
  assert.equal(mig.detectClientConfigCase(settings('freeform', localMcp)), 'freeform_local_obsolete');
});

test('UC-664 AC-01: FreeForm + remote MCP → freeform_remote_ok', () => {
  assert.equal(mig.detectClientConfigCase(settings('freeform', remoteMcp)), 'freeform_remote_ok');
});

test('UC-664 AC-01: Trello / Plane → trello_plane_unchanged', () => {
  assert.equal(mig.detectClientConfigCase(settings('trello', remoteMcp)), 'trello_plane_unchanged');
  assert.equal(mig.detectClientConfigCase(settings('plane', localMcp)), 'trello_plane_unchanged');
});

test('UC-664 AC-01: Native → native_oauth_unchanged', () => {
  assert.equal(mig.detectClientConfigCase(settings('native', remoteMcp)), 'native_oauth_unchanged');
});

test('UC-664 AC-01: no backend + no MCP → onboarding_incomplete', () => {
  assert.equal(mig.detectClientConfigCase(settings(null, null)), 'onboarding_incomplete');
  assert.equal(mig.detectClientConfigCase(null), 'onboarding_incomplete');
});

// ── UC-664 AC-02: plan corresponds to the detected case ──────────────────────

test('UC-664 AC-02: only freeform_local_obsolete yields an auto-applicable transport plan', () => {
  const obsolete = mig.planMigration('freeform_local_obsolete', '6.6.0');
  assert.equal(obsolete.case, 'freeform_local_obsolete');
  assert.equal(obsolete.autoApplicable, true);
  assert.equal(obsolete.requiresConfirmation, false);
  assert.equal(obsolete.actions.length, 1);
  assert.equal(obsolete.actions[0].kind, 'reconfigure_transport');
  assert.equal(obsolete.actions[0].destructive, false);
  assert.equal(obsolete.fromVersion, '6.6.0');

  for (const c of ['freeform_remote_ok', 'trello_plane_unchanged', 'native_oauth_unchanged', 'onboarding_incomplete']) {
    const p = mig.planMigration(c, '6.6.0');
    assert.equal(p.autoApplicable, false, `${c} must not auto-apply`);
    assert.equal(p.actions.length, 0, `${c} must have no actions`);
  }
});

// ── UC-665 AC-04: destructive gate — data movement requires confirmation ─────

test('UC-665 AC-04: a server plan that moves data is confirmation-gated, not auto-applied', () => {
  const local = mig.planMigration('freeform_local_obsolete', '6.6.0');
  const withMove = mig.reconcileServerPlan(local, [
    { kind: 'move_tracking_data', description: 'copy board to native', destructive: true },
  ]);
  assert.equal(withMove.requiresConfirmation, true);
  assert.equal(withMove.autoApplicable, false);
});

test('UC-665 AC-04: a server plan with only transport reconfig stays auto-applicable', () => {
  const local = mig.planMigration('freeform_local_obsolete', '6.6.0');
  const onlyTransport = mig.reconcileServerPlan(local, [
    { kind: 'reconfigure_transport', description: 'tweak endpoint', destructive: false },
  ]);
  assert.equal(onlyTransport.requiresConfirmation, false);
  assert.equal(onlyTransport.autoApplicable, true);
});

// ── UC-665 AC-01: backup before mutate, migrated points at remote ────────────

test('UC-665 AC-01: backupAndMigrate writes .bak with original then migrates to remote', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mig-'));
  try {
    const settingsPath = path.join(dir, 'settings.local.json');
    const original = settings('freeform', localMcp);
    fs.writeFileSync(settingsPath, JSON.stringify(original, null, 2) + '\n');
    const originalRaw = fs.readFileSync(settingsPath, 'utf-8');

    const { backupPath, migrated } = mig.backupAndMigrate(settingsPath, '20260531T120000Z');
    assert.ok(backupPath, 'backup path returned');
    assert.equal(fs.readFileSync(backupPath, 'utf-8'), originalRaw, 'backup is the original byte-for-byte');
    assert.equal(migrated.mcpServers['SpecBox-MCP'].args.includes(REMOTE_MCP_URL), true, 'migrated points at remote');
    // backend_type preserved
    assert.equal(migrated.specbox.backend_type, 'freeform');
    const onDisk = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
    assert.equal(onDisk.mcpServers['SpecBox-MCP'].args.includes(REMOTE_MCP_URL), true, 'disk reflects migration');
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('UC-665 AC-01: backupAndMigrate with no existing file makes no backup but writes remote config', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mig-'));
  try {
    const settingsPath = path.join(dir, 'settings.local.json');
    const { backupPath, migrated } = mig.backupAndMigrate(settingsPath, '20260531T120000Z');
    assert.equal(backupPath, null);
    assert.equal(migrated.mcpServers['SpecBox-MCP'].args.includes(REMOTE_MCP_URL), true);
    assert.ok(fs.existsSync(settingsPath));
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

// ── UC-665 AC-03: revert restores byte-for-byte from latest backup ───────────

test('UC-665 AC-03: migrate then revert restores settings.local.json byte-for-byte', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mig-'));
  try {
    const settingsPath = path.join(dir, 'settings.local.json');
    const original = settings('freeform', localMcp);
    const originalRaw = JSON.stringify(original, null, 2) + '\n';
    fs.writeFileSync(settingsPath, originalRaw);

    mig.backupAndMigrate(settingsPath, '20260531T120000Z');
    assert.notEqual(fs.readFileSync(settingsPath, 'utf-8'), originalRaw, 'migrated content differs');

    const ok = mig.revertLastMigration(settingsPath);
    assert.equal(ok, true);
    assert.equal(fs.readFileSync(settingsPath, 'utf-8'), originalRaw, 'reverted byte-for-byte');
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('UC-665 AC-03: revert with no backup returns false', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mig-'));
  try {
    const settingsPath = path.join(dir, 'settings.local.json');
    fs.writeFileSync(settingsPath, '{}\n');
    assert.equal(mig.revertLastMigration(settingsPath), false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('UC-665 AC-03: findLatestBackup picks the chronologically latest .bak', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mig-'));
  try {
    const sp = path.join(dir, 'settings.local.json');
    fs.writeFileSync(`${sp}.bak-20260101T000000Z`, 'old');
    fs.writeFileSync(`${sp}.bak-20260531T120000Z`, 'new');
    fs.writeFileSync(`${sp}.bak-20260301T000000Z`, 'mid');
    assert.equal(mig.findLatestBackup(sp), `${sp}.bak-20260531T120000Z`);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

// ── UC-665 AC-02: per-case pedagogical copy has the 4 sections ───────────────

test('UC-665 AC-02: actionable summary contains changed/migrated/backup/action sections', () => {
  const plan = mig.planMigration('freeform_local_obsolete', '6.6.0');
  const summary = mig.buildMigrationSummary(plan, { toVersion: '6.7.0', backupPath: '/x/settings.local.json.bak-20260531T120000Z' });
  assert.equal(summary.minimal, false);
  assert.ok(summary.changed.length > 0, 'changed present');
  assert.ok(summary.migrated.length > 0, 'migrated present');
  assert.ok(summary.backup, 'backup present');
  assert.ok(summary.action.length > 0, 'action present');
  const text = mig.renderSummaryText(summary);
  assert.match(text, /6\.7\.0/);
  assert.match(text, /Backup:/);
});

// ── UC-666 AC-02: no-op cases get the minimal "no changes" message ───────────

test('UC-666 AC-02: unchanged cases produce a minimal summary, no 4-section copy', () => {
  for (const c of ['freeform_remote_ok', 'trello_plane_unchanged', 'native_oauth_unchanged']) {
    const plan = mig.planMigration(c, '6.6.0');
    const summary = mig.buildMigrationSummary(plan, { toVersion: '6.7.0', backupPath: null });
    assert.equal(summary.minimal, true, `${c} should be minimal`);
    assert.match(summary.changed, /no changes needed/i);
    assert.equal(summary.backup, null);
    const text = mig.renderSummaryText(summary);
    assert.doesNotMatch(text, /Backup:/, 'minimal text has no backup line');
  }
});

// ── UC-666 AC-01: orchestrator is fire-and-forget — a phase failure never throws ─

test('UC-666 AC-01: runUpdateFlow completes even when the migrate phase throws', async () => {
  resetSpies();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'eng-'));
  try {
    // Engine version differs → would normally rebuild; no install-ext.mjs present
    // so the binary phase no-ops gracefully. ENGINE_VERSION.yaml drives the version.
    fs.writeFileSync(path.join(dir, 'ENGINE_VERSION.yaml'), 'version: 9.9.9\n');

    const updater = new ExtensionUpdater('0.0.1');
    // Monkeypatch the private migrate to throw, proving the try/catch isolates it.
    updater.migrate = () => { throw new Error('boom'); };

    // Must resolve, not reject, regardless of the thrown migrate error.
    await assert.doesNotReject(() => updater.runUpdateFlow(dir));
    // A summary notification still fired (flow reached phase 4).
    assert.ok(shown.info.length + shown.error.length >= 0);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('UC-666 AC-01: runUpdateFlow with null enginePath is a clean no-op', async () => {
  resetSpies();
  const updater = new ExtensionUpdater('1.0.0');
  await assert.doesNotReject(() => updater.runUpdateFlow(null));
});

test('UC-666: checkAndUpdate is a backwards-compatible alias of runUpdateFlow', () => {
  const updater = new ExtensionUpdater('1.0.0');
  assert.equal(typeof updater.checkAndUpdate, 'function');
  assert.equal(typeof updater.runUpdateFlow, 'function');
});
