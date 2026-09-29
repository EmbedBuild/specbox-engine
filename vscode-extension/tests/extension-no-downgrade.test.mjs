// UC-4307 — the extension never downgrades itself when it updates.
// install-ext.mjs pure helpers (imported without running its main), the updater's
// reinstall decision, and the notice after a (fake) install-ext.mjs reports the
// version it actually installed. No test touches VS Code, git or the network.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

import { pickVsix, parseListedVersion, expectedFromArgs } from '../install-ext.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

const shown = { info: [], error: [] };
const vscodeStub = {
	l10n: { t: (s, ...args) => (args.length ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s) },
	window: {
		showInformationMessage: (msg) => { shown.info.push(msg); return Promise.resolve(undefined); },
		showWarningMessage: () => Promise.resolve(undefined),
		showErrorMessage: (msg) => { shown.error.push(msg); return Promise.resolve(undefined); },
		withProgress: (_opts, fn) => fn({ report: () => {} }),
	},
	workspace: { getConfiguration: () => ({ get: () => undefined, update: () => Promise.resolve() }) },
	commands: { executeCommand: () => Promise.resolve() },
	ProgressLocation: { Notification: 15 },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { shouldReinstallExtension, parseInstalledVersion } = require(path.join(outDir, 'install.js'));
const { ExtensionUpdater } = require(path.join(outDir, 'updater.js'));

// ── AC-01: a package of another version is never used ─────────────────

test('AC-01: an old package in the folder is ignored; only the exact version is picked', () => {
	assert.equal(pickVsix(['specbox-engine-6.10.1.vsix'], '6.14.0'), null);
	assert.equal(pickVsix(['specbox-engine-6.10.1.vsix', 'specbox-engine-6.14.0.vsix'], '6.14.0'), 'specbox-engine-6.14.0.vsix');
	// Sorting by name used to pick 6.9.0 over 6.10.1 (and any old one over nothing).
	assert.equal(pickVsix(['specbox-engine-6.9.0.vsix', 'specbox-engine-6.10.1.vsix'], '6.10.1'), 'specbox-engine-6.10.1.vsix');
	assert.equal(pickVsix(['specbox-engine-6.14.0.vsix'], null), null);
});

test('install-ext reads the installed version and the expected one', () => {
	const list = 'ms-python.python@2026.1.0\nembedbuild.specbox-engine@6.14.0\nother.ext@1.0.0\n';
	assert.equal(parseListedVersion(list), '6.14.0');
	assert.equal(parseListedVersion('other.ext@1.0.0'), null);
	assert.equal(parseListedVersion(null), null);
	assert.equal(expectedFromArgs(['--prefer-marketplace', '--expect', '6.14.1']), '6.14.1');
	assert.equal(expectedFromArgs(['--expect', '--vsix']), null);
	assert.equal(expectedFromArgs([]), null);
});

// ── AC-02: never reinstall when the engine is not newer ───────────────

test('AC-02: the updater only reinstalls when the engine is strictly newer', () => {
	assert.equal(shouldReinstallExtension('6.14.0', '6.10.1'), true);
	assert.equal(shouldReinstallExtension('6.14.1', '6.14.0'), true);
	assert.equal(shouldReinstallExtension('6.14.0', '6.14.0'), false);
	// The case that looped: an engine behind the running extension.
	assert.equal(shouldReinstallExtension('6.10.1', '6.14.0'), false);
	assert.equal(shouldReinstallExtension('6.9.4', '6.10.0'), false);
});

test('parseInstalledVersion reads the INSTALLED_VERSION line', () => {
	assert.equal(parseInstalledVersion('  Installing...\nINSTALLED_VERSION=6.14.1\n  done'), '6.14.1');
	assert.equal(parseInstalledVersion('SpecBox Extension installed successfully.'), null);
	assert.equal(parseInstalledVersion(null), null);
});

// ── AC-03: the notice tells the version that really got installed ─────

function fakeEngine(installedVersion) {
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'specbox-uc4307-'));
	fs.mkdirSync(path.join(dir, 'vscode-extension'));
	fs.writeFileSync(
		path.join(dir, 'vscode-extension', 'install-ext.mjs'),
		`console.log('  Installing...');\nconsole.log('INSTALLED_VERSION=${installedVersion}');\n`,
	);
	return dir;
}

test('AC-03: when the expected version got installed, the notice names it', async () => {
	shown.info.length = 0; shown.error.length = 0;
	const updater = new ExtensionUpdater('6.13.0');
	await updater.rebuildExtension(fakeEngine('6.14.0'), '6.14.0');
	assert.deepEqual(shown.error, []);
	assert.equal(shown.info.length, 1);
	assert.match(shown.info[0], /updated to v6\.14\.0/);
});

test('AC-03: when another version got installed, it is an error, not a success', async () => {
	shown.info.length = 0; shown.error.length = 0;
	const updater = new ExtensionUpdater('6.13.0');
	await updater.rebuildExtension(fakeEngine('6.10.1'), '6.14.0');
	assert.deepEqual(shown.info, []);
	assert.equal(shown.error.length, 1);
	assert.match(shown.error[0], /installed v6\.10\.1 instead of v6\.14\.0/);
});
