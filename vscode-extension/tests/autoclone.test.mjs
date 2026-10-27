// US-VSCODE-AUTOCLONE (UC-109..112) — managed-engine pure helpers, auto-clone in
// resolveEnginePath, the clone on the newest release tag (UC-10807), and docs without "clone first".
// Pure-function + IO tests over compiled out/install.js and out/updater.js,
// stubbing `vscode`, `git` (injected runner), and `fs` the same way the other
// extension tests do. No test touches git or the network.

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
const repoRoot = path.resolve(__dirname, '..', '..');
const require = createRequire(import.meta.url);

// --- vscode stub with notification + config spies ---
const shown = { info: [], warn: [], error: [], opened: 0 };
let configStore = {};
const vscodeStub = {
	l10n: { t: (s, ...args) => (args.length ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s) },
	window: {
		showInformationMessage: (msg) => { shown.info.push(msg); return Promise.resolve(undefined); },
		showWarningMessage: (msg) => { shown.warn.push(msg); return Promise.resolve(undefined); },
		showErrorMessage: (msg) => { shown.error.push(msg); return Promise.resolve(undefined); },
		showOpenDialog: () => { shown.opened += 1; return Promise.resolve(undefined); },
		withProgress: (_opts, fn) => fn({ report: () => {} }),
	},
	workspace: {
		workspaceFolders: [],
		getConfiguration: () => ({
			get: (key) => configStore[key],
			update: (key, value) => { configStore[key] = value; return Promise.resolve(); },
		}),
	},
	commands: { executeCommand: () => Promise.resolve() },
	env: { openExternal: () => Promise.resolve(true) },
	Uri: { parse: (s) => s },
	ProgressLocation: { Notification: 15 },
	ConfigurationTarget: { Global: 1 },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const {
	ENGINE_REPO_URL, managedEnginePath, isManagedPath, cloneManagedEngine, InstallManager,
} = require(path.join(outDir, 'install.js'));
const { ExtensionUpdater } = require(path.join(outDir, 'updater.js'));

function reset() {
	shown.info = []; shown.warn = []; shown.error = []; shown.opened = 0;
	configStore = {};
}

const MANAGED = managedEnginePath();

// ============================================================
// UC-109 — pure helpers (AC-01, AC-02)
// ============================================================

test('AC-01: managedEnginePath is absolute and ends in /.specbox/specbox-engine', () => {
	const p = managedEnginePath();
	assert.ok(path.isAbsolute(p), 'must be absolute');
	assert.ok(p.endsWith(path.join('.specbox', 'specbox-engine')), `unexpected tail: ${p}`);
	assert.equal(p, path.join(os.homedir(), '.specbox', 'specbox-engine'));
});

test('AC-01: ENGINE_REPO_URL is the public engine .git URL', () => {
	assert.equal(ENGINE_REPO_URL, 'https://github.com/EmbedBuild/specbox-engine.git');
});

test('AC-02: isManagedPath true only for the managed dir, false for a user clone', () => {
	assert.equal(isManagedPath(managedEnginePath()), true);
	assert.equal(isManagedPath('/Users/x/specbox-engine'), false);
	assert.equal(isManagedPath(''), false);
	// Non-normalized but equivalent path still matches.
	assert.equal(isManagedPath(path.join(os.homedir(), '.specbox', 'foo', '..', 'specbox-engine')), true);
});

// ============================================================
// UC-110 — cloneManagedEngine effects (AC-04, AC-05) + resolveEnginePath wiring (AC-03)
// ============================================================

// A clone stub that "creates" the managed dir with ENGINE_VERSION.yaml.
function makeSuccessfulClone() {
	const created = new Set();
	return {
		gitRunner: async (args) => {
			if (args[0] === 'clone') { created.add(MANAGED); }
			return { code: 0, stdout: '', stderr: '' };
		},
		existsSync: (p) => created.has(p) || p === path.join(MANAGED, 'ENGINE_VERSION.yaml') && created.has(MANAGED),
		mkdirSync: () => {},
		rmSync: () => {},
		_created: created,
	};
}

test('AC-04: successful clone returns the managed path', async () => {
	reset();
	const deps = makeSuccessfulClone();
	const r = await cloneManagedEngine(deps);
	assert.equal(r.ok, true);
	assert.equal(r.path, MANAGED);
	assert.equal(r.error, undefined);
});

test('AC-05: failed clone (git missing) does not throw, cleans up, reports error', async () => {
	reset();
	let rmCalledOn = null;
	const r = await cloneManagedEngine({
		gitRunner: async () => ({ code: 127, stdout: '', stderr: 'git not found' }),
		existsSync: (p) => p === MANAGED, // a partial dir exists after the abort
		mkdirSync: () => {},
		rmSync: (p) => { rmCalledOn = p; },
	});
	assert.equal(r.ok, false);
	assert.match(r.error, /git is not installed/);
	assert.equal(rmCalledOn, MANAGED, 'partial managed dir must be cleaned up');
});

test('AC-05: clone exits 0 but no ENGINE_VERSION.yaml → failure + cleanup', async () => {
	reset();
	let rmCalled = false;
	const r = await cloneManagedEngine({
		gitRunner: async () => ({ code: 0, stdout: '', stderr: '' }),
		existsSync: (p) => p === MANAGED, // dir exists, but ENGINE_VERSION.yaml does not
		mkdirSync: () => {},
		rmSync: () => { rmCalled = true; },
	});
	assert.equal(r.ok, false);
	assert.match(r.error, /ENGINE_VERSION\.yaml is missing/);
	assert.equal(rmCalled, true);
});

test('AC-03: resolveEnginePath auto-clones BEFORE showOpenDialog (clone wins)', async () => {
	reset();
	const mgr = new InstallManager({});
	// No config, no workspace, no common locations → must reach auto-clone.
	const spy = { cloneCalled: false };
	// Patch tryAutoCloneEngine via its injectable deps by stubbing cloneManagedEngine.
	const enginePath = await mgr.tryAutoCloneEngine({
		clone: async () => { spy.cloneCalled = true; return { ok: true, path: MANAGED }; },
		existsSync: () => false, // managed dir not yet present → must clone
	});
	assert.equal(spy.cloneCalled, true, 'clone must be attempted');
	assert.equal(enginePath, MANAGED);
	assert.equal(shown.opened, 0, 'showOpenDialog must NOT be reached on clone success');
	assert.equal(configStore.enginePath, MANAGED, 'enginePath persisted to config');
	assert.ok(shown.info.length > 0, 'a "cloned" notification is shown');
});

test('AC-03/AC-05: tryAutoCloneEngine falls through to null (→ openDialog) on clone failure', async () => {
	reset();
	const mgr = new InstallManager({});
	const enginePath = await mgr.tryAutoCloneEngine({
		clone: async () => ({ ok: false, error: 'network down' }),
		existsSync: () => false,
	});
	assert.equal(enginePath, null, 'returns null so resolveEnginePath degrades to showOpenDialog');
	assert.ok(shown.error.length > 0, 'an actionable error is shown');
	assert.match(shown.error[0], /git|network|manually/i);
});

test('NFR idempotency: a managed clone already on disk is used without re-cloning', async () => {
	reset();
	const mgr = new InstallManager({});
	let cloneCalled = false;
	const enginePath = await mgr.tryAutoCloneEngine({
		clone: async () => { cloneCalled = true; return { ok: false }; },
		existsSync: (p) => p === path.join(MANAGED, 'ENGINE_VERSION.yaml'),
	});
	assert.equal(enginePath, MANAGED);
	assert.equal(cloneCalled, false, 'must not re-clone when managed engine already present');
});

// ============================================================
// UC-10807 (US-108) — the managed clone starts on the newest release, not on main.
// UC-111's automatic `git pull` is gone: the clone only moves when the person
// accepts a release in the updater (see updater-remote.test.mjs).
// ============================================================

function cloneWithTags(tags, checkout = { code: 0, stdout: '', stderr: '' }) {
	const calls = [];
	const created = new Set();
	return {
		calls,
		gitRunner: async (args) => {
			calls.push(args);
			if (args[0] === 'clone') { created.add(MANAGED); }
			if (args[0] === 'tag') { return { code: 0, stdout: tags.join('\n'), stderr: '' }; }
			if (args[0] === 'checkout') { return checkout; }
			return { code: 0, stdout: '', stderr: '' };
		},
		existsSync: (p) => created.has(p) || (p === path.join(MANAGED, 'ENGINE_VERSION.yaml') && created.has(MANAGED)),
		mkdirSync: () => {},
		rmSync: (p) => { created.delete(p); calls.push(['rm', p]); },
	};
}

test('UC-10807 AC-02: a fresh clone is put on the newest vX.Y.Z tag', async () => {
	reset();
	const deps = cloneWithTags(['v6.28.0', 'v6.9.4', 'v6.28.0-rc1', 'vscode-ext-1']);
	const r = await cloneManagedEngine(deps);
	assert.equal(r.ok, true);
	assert.deepEqual(deps.calls.find((a) => a[0] === 'checkout'), ['checkout', '--quiet', '--detach', 'v6.28.0']);
});

test('UC-10807: a clone without release tags stays as cloned', async () => {
	reset();
	const deps = cloneWithTags([]);
	const r = await cloneManagedEngine(deps);
	assert.equal(r.ok, true);
	assert.ok(!deps.calls.some((a) => a[0] === 'checkout'), 'no tag, no checkout');
});

test('UC-10807: a failed checkout of the release cleans up and reports it', async () => {
	reset();
	const deps = cloneWithTags(['v6.28.0'], { code: 1, stdout: '', stderr: 'error: pathspec' });
	const r = await cloneManagedEngine(deps);
	assert.equal(r.ok, false);
	assert.match(r.error, /pathspec/);
	assert.ok(deps.calls.some((a) => a[0] === 'rm' && a[1] === MANAGED), 'partial clone removed');
});

test('UC-10807 AC-03: the updater module no longer exports an automatic pull', async () => {
	const updater = require(path.join(outDir, 'updater.js'));
	assert.equal(updater.pullManagedEngine, undefined);
	// enginePath null → flow returns early but must not throw.
	await assert.doesNotReject(new ExtensionUpdater('9.9.9').runUpdateFlow(null));
});

// ============================================================
// UC-112 — docs without "clone first" (AC-08)
// ============================================================

test('AC-08: walkthrough prerequisites does not require manual "git clone" and mentions auto-clone', () => {
	const wt = fs.readFileSync(
		path.join(repoRoot, 'vscode-extension', 'media', 'walkthrough', 'step-prerequisites.md'),
		'utf-8',
	);
	// No instruction telling the user to clone the repo first as a prerequisite.
	assert.ok(!/clone the (?:repo|repository) first/i.test(wt), 'must not instruct "clone the repo first"');
	// Mentions the managed auto-clone.
	assert.match(wt, /clones? (?:the )?(?:public )?engine|~\/\.specbox\/specbox-engine|automatically/i);
});
