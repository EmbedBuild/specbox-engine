// US-118 (UC-11802) — heartbeat.ts tests, zero-deps via node:test. heartbeat.ts
// imports `vscode` (unavailable here), so we stub it like activation.test.mjs and
// exercise the testable surface: normalizeBackend, readWorkspaceBackend (fake fs),
// utcDay, buildHeartbeatPayload and emitHeartbeat (state as a Map, injectable HTTP).

import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

const vscodeStub = { window: {}, env: {}, workspace: {}, version: '1.106.0' };
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const {
	normalizeBackend, readWorkspaceBackend, utcDay, buildHeartbeatPayload, emitHeartbeat,
	_resetHeartbeatGuardForTests,
} = require(path.join(outDir, 'heartbeat.js'));

const INSTALL_ID = '3f29c1a4-7b2e-4d6c-9a1f-0b8e2c4d6e8a';

function memoryState(initial = {}) {
	const map = new Map(Object.entries(initial));
	return { map, get: (k) => map.get(k), update: async (k, v) => { map.set(k, v); } };
}

function deps(state, overrides = {}) {
	return {
		state,
		telemetryEnabled: () => true,
		backend: () => 'native',
		extVersion: '6.33.0',
		platform: 'linux',
		vscodeVersion: '1.106.0',
		now: () => new Date('2026-11-12T10:00:00Z'),
		log: () => {},
		...overrides,
	};
}

beforeEach(() => _resetHeartbeatGuardForTests());

// --- backend of the open workspace (AC-02) ---------------------------------------

test('normalizeBackend keeps the four backends and turns anything else into "none"', () => {
	for (const b of ['freeform', 'native', 'trello', 'plane']) { assert.equal(normalizeBackend(b), b); }
	assert.equal(normalizeBackend(' Native '), 'native');
	for (const b of [undefined, null, '', 'jira', 42, {}]) { assert.equal(normalizeBackend(b), 'none'); }
});

function fakeFs(files) {
	return {
		readFile: (file) => {
			if (!(file in files)) { throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' }); }
			return files[file];
		},
		exists: (file) => file in files,
	};
}

test('readWorkspaceBackend: specbox.backend_type in settings.local.json wins', () => {
	const ws = '/w';
	const fs = fakeFs({ [path.join(ws, '.claude', 'settings.local.json')]: '{"specbox":{"backend_type":"native"}}' });
	assert.equal(readWorkspaceBackend(ws, fs.readFile, fs.exists), 'native');
});

test('readWorkspaceBackend: falls back to settings.json, then to a FreeForm board on disk, then to legacy Trello/Plane', () => {
	const ws = '/w';
	let fs = fakeFs({ [path.join(ws, '.claude', 'settings.json')]: '{"specbox":{"backend_type":"plane"}}' });
	assert.equal(readWorkspaceBackend(ws, fs.readFile, fs.exists), 'plane');
	fs = fakeFs({ [path.join(ws, 'doc', 'tracking', 'items.json')]: '[]' });
	assert.equal(readWorkspaceBackend(ws, fs.readFile, fs.exists), 'freeform');
	fs = fakeFs({ [path.join(ws, '.claude', 'settings.local.json')]: '{"trello":{"boardId":"abc"}}' });
	assert.equal(readWorkspaceBackend(ws, fs.readFile, fs.exists), 'trello');
});

test('readWorkspaceBackend: no workspace, no SpecBox or unreadable settings → "none"', () => {
	assert.equal(readWorkspaceBackend(undefined), 'none');
	const ws = '/w';
	const fs = fakeFs({ [path.join(ws, '.claude', 'settings.local.json')]: '{not json' });
	assert.equal(readWorkspaceBackend(ws, fs.readFile, fs.exists), 'none');
	assert.equal(readWorkspaceBackend(ws, fakeFs({}).readFile, fakeFs({}).exists), 'none');
});

// --- payload (AC-02) ---------------------------------------------------------------

test('UC-11802 AC-02: the heartbeat carries only version, platform, VS Code version and backend', () => {
	const p = buildHeartbeatPayload({ installId: INSTALL_ID, extVersion: '6.33.0', platform: 'win32', vscodeVersion: '1.106.0', backend: 'freeform' });
	assert.equal(p.p_anon_id, INSTALL_ID);
	assert.equal(p.p_event_type, 'heartbeat');
	assert.deepEqual(Object.keys(p.p_meta).sort(), ['backend', 'ext_version', 'platform', 'vscode_version']);
	const s = JSON.stringify(p);
	assert.ok(!/@|\/(Users|home)\/|token|secret/i.test(s), 'no email, path or token');
});

test('utcDay is the natural UTC day', () => {
	assert.equal(utcDay(new Date('2026-11-12T23:59:59Z')), '2026-11-12');
	assert.equal(utcDay(new Date('2026-11-13T00:00:00Z')), '2026-11-13');
	// 00:30 in Madrid on the 13th is still the 12th in UTC.
	assert.equal(utcDay(new Date('2026-11-13T00:30:00+01:00')), '2026-11-12');
});

// --- emitHeartbeat (AC-01, AC-03, AC-04) -----------------------------------------------

test('UC-11802 AC-01: at most one heartbeat per UTC day, with the activation id', async () => {
	const state = memoryState({ 'specbox.funnel.installId': INSTALL_ID });
	const sent = [];
	const httpClient = async (url, key, body) => { sent.push(JSON.parse(body)); return { status: 204 }; };

	assert.equal(await emitHeartbeat(deps(state, { httpClient })), 'sent');
	assert.equal(await emitHeartbeat(deps(state, { httpClient, now: () => new Date('2026-11-12T22:00:00Z') })), 'already_today');
	assert.equal(sent.length, 1);
	assert.equal(sent[0].p_anon_id, INSTALL_ID);
	assert.equal(sent[0].p_meta.backend, 'native');

	assert.equal(await emitHeartbeat(deps(state, { httpClient, now: () => new Date('2026-11-13T08:00:00Z') })), 'sent');
	assert.equal(sent.length, 2, 'the next UTC day sends again');
});

test('UC-11802 AC-03: with VS Code telemetry off no heartbeat is sent', async () => {
	const state = memoryState({ 'specbox.funnel.installId': INSTALL_ID });
	let calls = 0;
	const httpClient = async () => { calls += 1; return { status: 204 }; };
	assert.equal(await emitHeartbeat(deps(state, { httpClient, telemetryEnabled: () => false })), 'opted_out');
	assert.equal(calls, 0);
});

test('UC-11802: without an activation id yet there is nothing to send', async () => {
	let calls = 0;
	const httpClient = async () => { calls += 1; return { status: 204 }; };
	assert.equal(await emitHeartbeat(deps(memoryState(), { httpClient })), 'no_install');
	assert.equal(calls, 0);
});

test('UC-11802 AC-04: a failed heartbeat shows nothing, leaves the day unmarked and is retried the same day', async () => {
	const state = memoryState({ 'specbox.funnel.installId': INSTALL_ID });
	const logs = [];
	assert.equal(await emitHeartbeat(deps(state, { httpClient: async () => ({ status: 503 }), log: (m) => logs.push(m) })), 'failed');
	assert.equal(await emitHeartbeat(deps(state, { httpClient: async () => { throw new Error('ETIMEDOUT'); }, log: (m) => logs.push(m) })), 'failed');
	assert.equal(state.map.get('specbox.funnel.heartbeatDay'), undefined);
	assert.equal(logs.length, 2, 'only console logs, no user-facing notice');
	assert.equal(await emitHeartbeat(deps(state, { httpClient: async () => ({ status: 204 }), now: () => new Date('2026-11-12T18:00:00Z') })), 'sent');
	assert.equal(state.map.get('specbox.funnel.heartbeatDay'), '2026-11-12');
});
