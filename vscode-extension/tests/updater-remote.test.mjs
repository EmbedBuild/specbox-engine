// US-14 (UC-1401..1404) — remote-version check + guaranteed upgrade, and
// UC-10807 (US-108) — the managed clone follows the release tags, never runs code
// from the workspace and waits when the person says «Later».
// Pure-function + flow tests over compiled out/install.js, out/updater.js and
// out/health.js, stubbing `vscode` and injecting a scripted GitRunner. No test
// touches git or the network. Mirrors the mock style of autoclone.test.mjs.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

// --- vscode stub with scriptable dialog answers + spies ---
const shown = { info: [], warn: [], error: [] };
// The next button each *Message returns (FIFO queue). undefined = dismissed.
let infoAnswers = [];
let warnAnswers = [];
let errorAnswers = [];
let openedDocs = [];
let executed = [];

const vscodeStub = {
	l10n: { t: (s, ...args) => (args.length ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s) },
	window: {
		showInformationMessage: (msg, ...rest) => {
			shown.info.push(msg);
			// rest may be (options, ...buttons) or (...buttons); both fine — we ignore it.
			return Promise.resolve(infoAnswers.shift());
		},
		showWarningMessage: (msg, ...rest) => {
			shown.warn.push(msg);
			return Promise.resolve(warnAnswers.shift());
		},
		showErrorMessage: (msg, ...rest) => {
			shown.error.push(msg);
			return Promise.resolve(errorAnswers.shift());
		},
		withProgress: (_opts, fn) => fn({ report: () => {} }),
	},
	workspace: {
		isTrusted: true,
		workspaceFolders: [],
		openTextDocument: (p) => { openedDocs.push(p); return Promise.resolve({ uri: p }); },
		getConfiguration: () => ({ get: () => undefined, update: () => Promise.resolve() }),
	},
	commands: { executeCommand: (cmd) => { executed.push(cmd); return Promise.resolve(); } },
	ProgressLocation: { Notification: 15 },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const {
	compareSemver, fetchRemote, latestReleaseTag, checkoutRelease, managedEnginePath,
} = require(path.join(outDir, 'install.js'));
const { ExtensionUpdater } = require(path.join(outDir, 'updater.js'));
const { HealthChecker } = require(path.join(outDir, 'health.js'));

const MANAGED = managedEnginePath();

function reset() {
	shown.info = []; shown.warn = []; shown.error = [];
	infoAnswers = []; warnAnswers = []; errorAnswers = [];
	openedDocs = []; executed = [];
	vscodeStub.workspace.isTrusted = true;
	vscodeStub.workspace.workspaceFolders = [];
}

/**
 * Build a scripted GitRunner. `behavior` maps the first git arg to a GitRunResult.
 * `remoteVersion` is the newest release tag the clone knows (null = no tags).
 * `recorded` collects every invocation for assertions.
 */
function scriptedGit(opts = {}) {
	const recorded = [];
	const runner = async (args) => {
		recorded.push(args);
		const key = args[0];
		if (key === 'fetch') { return opts.fetch ?? { code: 0, stdout: '', stderr: '' }; }
		if (key === 'tag') {
			if (opts.remoteVersion === null) { return { code: 0, stdout: '', stderr: '' }; }
			return { code: 0, stdout: `v${opts.remoteVersion ?? '0.0.0'}\nv6.0.0\n`, stderr: '' };
		}
		if (key === 'checkout') { return opts.checkout ?? { code: 0, stdout: '', stderr: '' }; }
		return { code: 0, stdout: '', stderr: '' };
	};
	runner.recorded = recorded;
	return runner;
}

// A minimal updater whose local-version read is stubbed (avoids touching disk for
// ENGINE_VERSION.yaml). `postCheckoutVersion` is what resolveEngineVersion returns —
// it is only consulted by verifyAndFinish AFTER the checkout, so it models the
// on-disk version once the upgrade ran. Default '6.9.4' = the upgrade did NOT apply.
function makeUpdater(gitRunner, postCheckoutVersion = '6.9.4') {
	const u = new ExtensionUpdater('9.9.9', gitRunner);
	u.resolveEngineVersion = () => postCheckoutVersion;
	// Stub rebuildExtension so tests never spawn node/install-ext.mjs.
	u.rebuildExtension = async () => { executed.push('rebuild'); };
	return u;
}

// ============================================================
// UC-1402 — compareSemver (AC-04)
// ============================================================

test('AC-04: compareSemver is numeric, not lexicographic', () => {
	assert.equal(compareSemver('6.10.2', '6.9.4'), 1, '6.10.2 > 6.9.4 numerically');
	assert.equal(compareSemver('6.9.4', '6.10.2'), -1);
	assert.equal(compareSemver('6.10.2', '6.10.2'), 0);
	assert.equal(compareSemver('6.10', '6.10.0'), 0, 'missing patch counts as 0');
	assert.equal(compareSemver('v6.11.0', '6.10.9'), 1, 'leading v tolerated');
});

// ============================================================
// UC-1401 + UC-10807 — remote read helpers (AC-01, AC-02, AC-03)
// ============================================================

test('AC-01: fetchRemote calls git fetch origin --tags and never throws', async () => {
	const git = scriptedGit({ fetch: { code: 0, stdout: '', stderr: '' } });
	const r = await fetchRemote('/x', git);
	assert.equal(r.code, 0);
	assert.deepEqual(git.recorded[0], ['fetch', 'origin', '--tags']);
});

test('UC-10807 AC-02: latestReleaseTag is the newest vX.Y.Z tag, not main', async () => {
	const git = async () => ({ code: 0, stdout: 'v6.28.0-rc1\nv6.28.0\nv6.9.4\nvscode-ext-1\n', stderr: '' });
	assert.equal(await latestReleaseTag('/x', git), 'v6.28.0');
	const none = async () => ({ code: 0, stdout: 'nightly\n', stderr: '' });
	assert.equal(await latestReleaseTag('/x', none), null);
	const failed = async () => ({ code: 128, stdout: '', stderr: 'fatal' });
	assert.equal(await latestReleaseTag('/x', failed), null);
});

test('UC-10807: checkoutRelease detaches on the tag', async () => {
	const git = scriptedGit();
	await checkoutRelease('/x', 'v6.28.0', git);
	assert.deepEqual(git.recorded[0], ['checkout', '--quiet', '--detach', 'v6.28.0']);
});

test('AC-03: a failed fetch (git absent, code 127) shows no dialog, flow continues', async () => {
	reset();
	const git = scriptedGit({ fetch: { code: 127, stdout: '', stderr: 'git not found' } });
	const u = makeUpdater(git);
	const res = await u.checkRemoteAndOffer(MANAGED, '6.9.4');
	assert.equal(res, 'noop');
	assert.equal(shown.info.length, 0, 'no upgrade dialog when fetch failed');
	assert.equal(shown.warn.length, 0);
});

test('AC-03: no release tag → no dialog', async () => {
	reset();
	const u = makeUpdater(scriptedGit({ remoteVersion: null }));
	assert.equal(await u.checkRemoteAndOffer(MANAGED, '6.9.4'), 'noop');
	assert.equal(shown.info.length, 0);
});

// ============================================================
// UC-1402 — dialog X→Y (AC-05, AC-06, AC-07, AC-08)
// ============================================================

test('AC-05: a newer release than local → modal offers the X→Y upgrade', async () => {
	reset();
	infoAnswers = ['Later']; // dismiss by postponing
	const git = scriptedGit({ remoteVersion: '6.10.2' });
	const u = makeUpdater(git);
	const res = await u.checkRemoteAndOffer(MANAGED, '6.9.4');
	assert.equal(res, 'noop');
	assert.equal(shown.info.length, 1);
	assert.match(shown.info[0], /v6\.9\.4 → v6\.10\.2/, 'dialog names both versions');
});

test('AC-06: release equal or older → no dialog', async () => {
	reset();
	const gitEqual = scriptedGit({ remoteVersion: '6.9.4' });
	let u = makeUpdater(gitEqual);
	assert.equal(await u.checkRemoteAndOffer(MANAGED, '6.9.4'), 'noop');
	assert.equal(shown.info.length, 0, 'equal version shows nothing');

	const gitOlder = scriptedGit({ remoteVersion: '6.8.0' });
	u = makeUpdater(gitOlder);
	assert.equal(await u.checkRemoteAndOffer(MANAGED, '6.9.4'), 'noop');
	assert.equal(shown.info.length, 0, 'local-ahead (developer) shows nothing');
});

test('AC-07: View changes opens CHANGELOG then re-offers the decision', async () => {
	reset();
	// First answer: "View changes". Second answer (re-offer): "Later".
	infoAnswers = ['View changes', 'Later'];
	const git = scriptedGit({ remoteVersion: '6.10.2' });
	const u = makeUpdater(git);
	await u.checkRemoteAndOffer(MANAGED, '6.9.4');
	assert.equal(shown.info.length, 2, 'dialog shown again after viewing changes');
});

test('AC-08 / UC-10807 AC-03: Later postpones this version and the clone does not move', async () => {
	reset();
	const git = scriptedGit({ remoteVersion: '6.10.2' });
	const u = makeUpdater(git);
	infoAnswers = ['Later'];
	await u.checkRemoteAndOffer(MANAGED, '6.9.4');
	assert.equal(shown.info.length, 1);
	// Same version again → suppressed (no second dialog).
	await u.checkRemoteAndOffer(MANAGED, '6.9.4');
	assert.equal(shown.info.length, 1, 'same postponed version must not re-prompt');
	assert.ok(!git.recorded.some((a) => a[0] === 'checkout' || a[0] === 'pull'), 'after Later nothing moves the clone');
	// A newer release → prompts again.
	const gitNewer = scriptedGit({ remoteVersion: '6.11.0' });
	const u2 = makeUpdater(gitNewer);
	u2.postponedVersions = u.postponedVersions; // share session state
	infoAnswers = ['Later'];
	await u2.checkRemoteAndOffer(MANAGED, '6.9.4');
	assert.equal(shown.info.length, 2, 'a newer version re-prompts');
});

test('UC-10807 AC-03: the update flow never pulls on its own', () => {
	const source = fs.readFileSync(path.join(outDir, 'updater.js'), 'utf-8');
	assert.ok(!/['"]pull['"]/.test(source), 'no git pull left in the updater');
});

test('UC-10807: a clone of your own is never offered or touched', async () => {
	reset();
	const git = scriptedGit({ remoteVersion: '6.10.2' });
	const u = makeUpdater(git);
	assert.equal(await u.checkRemoteAndOffer('/Users/x/my-engine', '6.9.4'), 'noop');
	assert.equal(git.recorded.length, 0, 'no git command on a user clone');
	assert.equal(shown.info.length, 0);
});

// ============================================================
// UC-1403 + UC-10807 — upgrade to the release tag + verification (AC-09..AC-11)
// ============================================================

test('AC-09/AC-10: Update now → checkout of the tag, version moved → rebuild + reload', async () => {
	reset();
	infoAnswers = ['Update now'];
	const git = scriptedGit({ remoteVersion: '6.10.2' });
	// local reads 6.9.4 for the offer, then 6.10.2 after the checkout (verifyAndFinish).
	const u = makeUpdater(git, '6.10.2');
	const res = await u.checkRemoteAndOffer(MANAGED, '6.9.4');
	assert.equal(res, 'reloading');
	assert.deepEqual(git.recorded.find((a) => a[0] === 'checkout'), ['checkout', '--quiet', '--detach', 'v6.10.2']);
	assert.ok(executed.includes('rebuild'), 'rebuild ran on a verified upgrade');
});

test('AC-11: checkout reports success but version unchanged → error, NOT success', async () => {
	reset();
	infoAnswers = ['Update now'];
	errorAnswers = [undefined];
	const git = scriptedGit({ remoteVersion: '6.10.2' });
	// local stays 6.9.4 even after the checkout → mismatch.
	const u = makeUpdater(git);
	const res = await u.checkRemoteAndOffer(MANAGED, '6.9.4');
	assert.equal(res, 'noop', 'must not declare success');
	assert.equal(shown.error.length, 1, 'an actionable error is shown');
	assert.match(shown.error[0], /did not apply|still on v6\.9\.4/i);
	assert.ok(!executed.includes('rebuild'), 'no rebuild on a failed verification');
});

test('UC-10807: a failed checkout (local changes) only warns — nothing is reset', async () => {
	reset();
	infoAnswers = ['Update now'];
	const git = scriptedGit({
		remoteVersion: '6.10.2',
		checkout: { code: 1, stdout: '', stderr: 'error: Your local changes would be overwritten' },
	});
	const u = makeUpdater(git);
	const res = await u.checkRemoteAndOffer(MANAGED, '6.9.4');
	assert.equal(res, 'noop');
	assert.equal(shown.warn.length, 1);
	assert.match(shown.warn[0], /local changes/);
	assert.ok(!git.recorded.some((a) => ['reset', 'branch', 'pull'].includes(a[0])), 'no reset, backup or pull');
	assert.ok(!executed.includes('rebuild'));
});

// ============================================================
// UC-10807 AC-01 — no script of the opened folder ever runs
// ============================================================

/** A folder that looks like a newer engine and whose install-ext.mjs leaves a mark if it runs. */
function maliciousEngine() {
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'uc10807-'));
	fs.writeFileSync(path.join(dir, 'ENGINE_VERSION.yaml'), 'version: 99.0.0\n');
	fs.mkdirSync(path.join(dir, 'vscode-extension'));
	const mark = path.join(dir, 'RAN');
	fs.writeFileSync(
		path.join(dir, 'vscode-extension', 'install-ext.mjs'),
		`import fs from 'node:fs'; fs.writeFileSync(${JSON.stringify(mark)}, 'x');\n`,
	);
	return { dir, mark };
}

test('UC-10807 AC-01: the updater does not run install-ext.mjs of a folder that is not the managed clone', async () => {
	reset();
	const { dir, mark } = maliciousEngine();
	const u = new ExtensionUpdater('6.28.0', scriptedGit());
	await u.rebuildExtension(dir, '99.0.0');
	await new Promise((r) => setTimeout(r, 300));
	assert.equal(fs.existsSync(mark), false, 'install-ext.mjs of the folder must not run');
	assert.match(shown.info[0], /Marketplace/);
	fs.rmSync(dir, { recursive: true, force: true });
});

test('UC-10807 AC-01: in Restricted Mode not even the managed clone runs its script', async () => {
	reset();
	vscodeStub.workspace.isTrusted = false;
	const u = new ExtensionUpdater('6.28.0', scriptedGit());
	await u.rebuildExtension(MANAGED, '99.0.0');
	assert.equal(shown.info.length, 1, 'only the Marketplace notice');
	assert.equal(shown.error.length, 0, 'it did not even look for install-ext.mjs');
});

test('UC-10807 AC-01: in Restricted Mode a workspace folder is not taken as the engine', async () => {
	reset();
	const { dir } = maliciousEngine();
	vscodeStub.workspace.workspaceFolders = [{ uri: { fsPath: dir } }];
	vscodeStub.workspace.isTrusted = false;
	assert.notEqual(await new HealthChecker().findEnginePath(), dir, 'untrusted folder ignored');
	vscodeStub.workspace.isTrusted = true;
	assert.equal(await new HealthChecker().findEnginePath(), dir, 'a trusted engine checkout still counts');
	fs.rmSync(dir, { recursive: true, force: true });
});
