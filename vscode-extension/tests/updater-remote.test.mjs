// US-14 (UC-1401..1404) — remote-version check + guaranteed upgrade.
// Pure-function + flow tests over compiled out/install.js and out/updater.js,
// stubbing `vscode` and injecting a scripted GitRunner. No test touches git or
// the network. Mirrors the mock style of autoclone.test.mjs.

import { test } from 'node:test';
import assert from 'node:assert/strict';
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
	compareSemver, fetchRemote, remoteEngineVersion, isDivergedFromRemote,
	managedEnginePath, DEFAULT_REMOTE_BRANCH,
} = require(path.join(outDir, 'install.js'));
const { ExtensionUpdater } = require(path.join(outDir, 'updater.js'));

const MANAGED = managedEnginePath();

function reset() {
	shown.info = []; shown.warn = []; shown.error = [];
	infoAnswers = []; warnAnswers = []; errorAnswers = [];
	openedDocs = []; executed = [];
}

/**
 * Build a scripted GitRunner. `behavior` maps the first git arg (or a custom key)
 * to a GitRunResult. `version` is what `git show origin/main:ENGINE_VERSION.yaml`
 * returns. `recorded` collects every invocation for assertions.
 */
function scriptedGit(opts = {}) {
	const recorded = [];
	const runner = async (args) => {
		recorded.push(args);
		const key = args[0];
		if (key === 'fetch') { return opts.fetch ?? { code: 0, stdout: '', stderr: '' }; }
		if (key === 'show') {
			if (opts.remoteVersion === null) { return { code: 1, stdout: '', stderr: 'fatal' }; }
			return { code: 0, stdout: `version: ${opts.remoteVersion ?? '0.0.0'}\ncodename: x\n`, stderr: '' };
		}
		if (key === 'pull') { return opts.pull ?? { code: 0, stdout: '', stderr: '' }; }
		if (key === 'rev-list') { return opts.revList ?? { code: 0, stdout: '0\t0', stderr: '' }; }
		if (key === 'rev-parse') { return { code: 0, stdout: opts.branch ?? 'main', stderr: '' }; }
		if (key === 'branch') { return opts.branch_cmd ?? { code: 0, stdout: '', stderr: '' }; }
		if (key === 'checkout') { return opts.checkout ?? { code: 0, stdout: '', stderr: '' }; }
		if (key === 'reset') { return opts.reset ?? { code: 0, stdout: '', stderr: '' }; }
		return { code: 0, stdout: '', stderr: '' };
	};
	runner.recorded = recorded;
	return runner;
}

// A minimal updater whose local-version read is stubbed (avoids touching disk for
// ENGINE_VERSION.yaml). `postPullVersion` is what resolveEngineVersion returns —
// it is only consulted by verifyAndFinish AFTER the pull/reset, so it models the
// on-disk version once the upgrade ran. Default '6.9.4' = the upgrade did NOT apply.
function makeUpdater(gitRunner, postPullVersion = '6.9.4') {
	const u = new ExtensionUpdater('9.9.9', gitRunner);
	u.resolveEngineVersion = () => postPullVersion;
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
// UC-1401 — remote read helpers (AC-01, AC-02, AC-03)
// ============================================================

test('AC-01: fetchRemote calls git fetch origin --tags and never throws', async () => {
	const git = scriptedGit({ fetch: { code: 0, stdout: '', stderr: '' } });
	const r = await fetchRemote('/x', git);
	assert.equal(r.code, 0);
	assert.deepEqual(git.recorded[0], ['fetch', 'origin', '--tags']);
});

test('AC-02: remoteEngineVersion parses version: from git show', async () => {
	const git = scriptedGit({ remoteVersion: '6.10.2' });
	const v = await remoteEngineVersion('/x', git);
	assert.equal(v, '6.10.2');
	assert.deepEqual(git.recorded[0], ['show', 'origin/main:ENGINE_VERSION.yaml']);
});

test('AC-02/AC-03: remoteEngineVersion returns null when git show fails (no network)', async () => {
	const git = scriptedGit({ remoteVersion: null });
	const v = await remoteEngineVersion('/x', git);
	assert.equal(v, null);
});

test('AC-03: a failed fetch (git absent, code 127) shows no dialog, flow continues', async () => {
	reset();
	const git = scriptedGit({ fetch: { code: 127, stdout: '', stderr: 'git not found' } });
	const u = makeUpdater(git);
	const res = await u.checkRemoteAndOffer('/x', '6.9.4');
	assert.equal(res, 'noop');
	assert.equal(shown.info.length, 0, 'no upgrade dialog when fetch failed');
	assert.equal(shown.warn.length, 0);
});

// ============================================================
// UC-1402 — dialog X→Y (AC-05, AC-06, AC-07, AC-08)
// ============================================================

test('AC-05: remote newer than local → modal offers the X→Y upgrade', async () => {
	reset();
	infoAnswers = ['Later']; // dismiss by postponing
	const git = scriptedGit({ remoteVersion: '6.10.2' });
	const u = makeUpdater(git);
	const res = await u.checkRemoteAndOffer('/x', '6.9.4');
	assert.equal(res, 'noop');
	assert.equal(shown.info.length, 1);
	assert.match(shown.info[0], /v6\.9\.4 → v6\.10\.2/, 'dialog names both versions');
});

test('AC-06: remote equal or older → no dialog', async () => {
	reset();
	const gitEqual = scriptedGit({ remoteVersion: '6.9.4' });
	let u = makeUpdater(gitEqual);
	assert.equal(await u.checkRemoteAndOffer('/x', '6.9.4'), 'noop');
	assert.equal(shown.info.length, 0, 'equal version shows nothing');

	const gitOlder = scriptedGit({ remoteVersion: '6.8.0' });
	u = makeUpdater(gitOlder);
	assert.equal(await u.checkRemoteAndOffer('/x', '6.9.4'), 'noop');
	assert.equal(shown.info.length, 0, 'local-ahead (developer) shows nothing');
});

test('AC-07: View changes opens CHANGELOG then re-offers the decision', async () => {
	reset();
	// First answer: "View changes". Second answer (re-offer): "Later".
	infoAnswers = ['View changes', 'Later'];
	const git = scriptedGit({ remoteVersion: '6.10.2' });
	const u = makeUpdater(git);
	// openChangelog calls fs.existsSync(CHANGELOG); the managed path won't have one,
	// so it's a no-op — but the decision must be re-offered regardless.
	await u.checkRemoteAndOffer('/x', '6.9.4');
	assert.equal(shown.info.length, 2, 'dialog shown again after viewing changes');
});

test('AC-08: Later postpones this version for the session; a newer one re-prompts', async () => {
	reset();
	const git = scriptedGit({ remoteVersion: '6.10.2' });
	const u = makeUpdater(git);
	infoAnswers = ['Later'];
	await u.checkRemoteAndOffer('/x', '6.9.4');
	assert.equal(shown.info.length, 1);
	// Same version again → suppressed (no second dialog).
	await u.checkRemoteAndOffer('/x', '6.9.4');
	assert.equal(shown.info.length, 1, 'same postponed version must not re-prompt');
	// A newer remote → prompts again.
	const gitNewer = scriptedGit({ remoteVersion: '6.11.0' });
	u.gitRunner = gitNewer; // not used directly; pass via new helper read
	const u2 = makeUpdater(gitNewer);
	u2.postponedVersions = u.postponedVersions; // share session state
	infoAnswers = ['Later'];
	await u2.checkRemoteAndOffer('/x', '6.9.4');
	assert.equal(shown.info.length, 2, 'a newer version re-prompts');
});

// ============================================================
// UC-1403 — guaranteed upgrade + verification (AC-09, AC-10, AC-11)
// ============================================================

test('AC-09/AC-10: Update now → pull --ff-only, version moved → rebuild + reload', async () => {
	reset();
	infoAnswers = ['Update now'];
	const git = scriptedGit({ remoteVersion: '6.10.2', pull: { code: 0, stdout: '', stderr: '' } });
	// local reads 6.9.4 for the offer, then 6.10.2 after the pull (verifyAndFinish).
	const u = makeUpdater(git, '6.10.2');
	const res = await u.checkRemoteAndOffer('/x', '6.9.4');
	assert.equal(res, 'reloading');
	assert.deepEqual(git.recorded.find(a => a[0] === 'pull'), ['pull', '--ff-only']);
	assert.ok(executed.includes('rebuild'), 'rebuild ran on a verified upgrade');
});

test('AC-11: pull reports success but version unchanged → error, NOT success', async () => {
	reset();
	infoAnswers = ['Update now'];
	errorAnswers = [undefined];
	const git = scriptedGit({ remoteVersion: '6.10.2', pull: { code: 0, stdout: '', stderr: '' } });
	// local stays 6.9.4 even after the pull → mismatch.
	const u = makeUpdater(git);
	const res = await u.checkRemoteAndOffer('/x', '6.9.4');
	assert.equal(res, 'noop', 'must not declare success');
	assert.equal(shown.error.length, 1, 'an actionable error is shown');
	assert.match(shown.error[0], /did not apply|still on v6\.9\.4/i);
	assert.ok(!executed.includes('rebuild'), 'no rebuild on a failed verification');
});

// ============================================================
// UC-1404 — divergence: reset --hard with backup (AC-12..15)
// ============================================================

test('AC-12: --ff-only fails by divergence → modal warning, no automatic reset', async () => {
	reset();
	infoAnswers = ['Update now'];
	warnAnswers = ['Cancel']; // divergence modal answered Cancel
	infoAnswers.push(undefined); // the "cancelled" info notice
	const git = scriptedGit({
		remoteVersion: '6.10.2',
		pull: { code: 1, stdout: '', stderr: 'fatal: Not possible to fast-forward, aborting.' },
		revList: { code: 0, stdout: '2\t3' }, // behind 2, ahead 3 → diverged
	});
	const u = makeUpdater(git);
	const res = await u.checkRemoteAndOffer(MANAGED, '6.9.4');
	assert.equal(res, 'noop');
	assert.equal(shown.warn.length, 1, 'divergence modal shown');
	// No reset/checkout ran because the user cancelled.
	assert.ok(!git.recorded.some(a => a[0] === 'reset'), 'no reset without confirmation');
	assert.ok(!git.recorded.some(a => a[0] === 'checkout'), 'no checkout without confirmation');
});

test('AC-13/AC-14: confirmed reset backs up the branch first, then fetch/checkout/reset/verify', async () => {
	reset();
	infoAnswers = ['Update now'];
	warnAnswers = ['Reset with backup'];
	infoAnswers.push(undefined); // final "reset done" info notice
	const git = scriptedGit({
		remoteVersion: '6.10.2',
		pull: { code: 1, stdout: '', stderr: 'Not possible to fast-forward' },
		revList: { code: 0, stdout: '1\t1' }, // diverged
		branch: 'docs/prd-dual-backend',
	});
	// after reset, local reads the target version.
	const u = makeUpdater(git, '6.10.2');
	const res = await u.checkRemoteAndOffer(MANAGED, '6.9.4');
	assert.equal(res, 'reloading');
	const order = git.recorded.map(a => a[0]);
	const branchIdx = order.indexOf('branch');
	const resetIdx = order.indexOf('reset');
	assert.ok(branchIdx !== -1, 'a backup branch was created');
	assert.ok(branchIdx < resetIdx, 'backup created BEFORE the reset');
	const backupArgs = git.recorded.find(a => a[0] === 'branch');
	assert.match(backupArgs[1], /^specbox-backup\/docs\/prd-dual-backend-/, 'backup ref names the branch');
	assert.ok(order.includes('checkout') && order.includes('reset'), 'fetch/checkout/reset ran');
	assert.ok(executed.includes('rebuild'), 'verified upgrade rebuilds');
});

test('AC-15: a diverged USER clone (not managed) is never reset — only a notice', async () => {
	reset();
	infoAnswers = ['Update now'];
	warnAnswers = []; // no modal expected
	const git = scriptedGit({
		remoteVersion: '6.10.2',
		pull: { code: 1, stdout: '', stderr: 'Not possible to fast-forward' },
		revList: { code: 0, stdout: '1\t1' },
		branch: 'wip',
	});
	const u = makeUpdater(git);
	const res = await u.checkRemoteAndOffer('/Users/x/my-engine', '6.9.4');
	assert.equal(res, 'noop');
	assert.ok(!git.recorded.some(a => a[0] === 'reset'), 'user clone is never reset');
	assert.ok(shown.warn.length >= 1, 'an informational warning is shown for the user clone');
});

// ============================================================
// isDivergedFromRemote helper (AC-12 robustness)
// ============================================================

test('AC-12: isDivergedFromRemote uses rev-list ahead count', async () => {
	const diverged = scriptedGit({ revList: { code: 0, stdout: '0\t3' } });
	assert.equal(await isDivergedFromRemote('/x', diverged), true, 'ahead>0 is diverged');
	const clean = scriptedGit({ revList: { code: 0, stdout: '0\t0' } });
	assert.equal(await isDivergedFromRemote('/x', clean), false, 'ahead=0 is not diverged');
	const failed = scriptedGit({ revList: { code: 1, stdout: '' } });
	assert.equal(await isDivergedFromRemote('/x', failed), false, 'rev-list failure is not diverged');
});
