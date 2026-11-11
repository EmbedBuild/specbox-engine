// US-26 (UC-2601 / UC-2602) + US-118 (UC-11801) — activation.ts tests, zero-deps via
// node:test. activation.ts imports `vscode` (unavailable here), so we stub the
// module the same way cloud-api.test.mjs / updater-remote.test.mjs do, then
// exercise the testable surface:
//   isValidAnonId, resolveInstallIdentity, buildActivationPayload, postActivation
//   (injectable client) and emitActivation (state as a Map, injectable HTTP).
//
// NOT tested here (depend on the real `vscode` runtime, by design):
//   - registerActivationUriHandler (needs vscode.window.registerUriHandler + Uri)
// Covered by the clean-install check after the release (UC-11801 AC-06).

import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

// Minimal vscode stub — activation.ts only needs the symbol to resolve at import
// time; the functions under test receive everything they need as arguments.
const vscodeStub = {
	window: {},
	env: {},
	version: '1.86.0',
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const {
	isValidAnonId, resolveInstallIdentity, buildActivationPayload, postActivation,
	emitActivation, getInstallId, _resetEmissionGuardForTests,
} = require(path.join(outDir, 'activation.js'));

const VALID_UUID = '3f29c1a4-7b2e-4d6c-9a1f-0b8e2c4d6e8a';
const OTHER_UUID = '9b1d5e2a-0c4f-4a8b-b6d3-7e2f1a9c8d4b';

/** A globalState stand-in backed by a Map. */
function memoryState(initial = {}) {
	const map = new Map(Object.entries(initial));
	return {
		map,
		get: (k) => map.get(k),
		update: async (k, v) => { map.set(k, v); },
	};
}

function deps(state, overrides = {}) {
	return {
		state,
		telemetryEnabled: () => true,
		extVersion: '6.33.0',
		platform: 'darwin',
		vscodeVersion: '1.106.0',
		generateId: () => OTHER_UUID,
		delay: async () => {},
		log: () => {},
		...overrides,
	};
}

beforeEach(() => _resetEmissionGuardForTests());

// --- resolveInstallIdentity (UC-11801 AC-01/AC-02) ------------------------------

test('UC-11801: an install from the Marketplace gets a generated UUID v4 and origin "marketplace"', () => {
	const id = resolveInstallIdentity({}, () => OTHER_UUID);
	assert.deepEqual(id, { installId: OTHER_UUID, origin: 'marketplace', isNew: true });
});

test('UC-11801: an install that came through the site keeps the visit id and origin "site"', () => {
	const id = resolveInstallIdentity({ siteAnonId: VALID_UUID }, () => OTHER_UUID);
	assert.deepEqual(id, { installId: VALID_UUID, origin: 'site', isNew: true });
});

test('UC-11801: once chosen, the identity never changes (a later deep link does not replace it)', () => {
	const id = resolveInstallIdentity({ installId: OTHER_UUID, origin: 'marketplace', siteAnonId: VALID_UUID }, () => 'x');
	assert.deepEqual(id, { installId: OTHER_UUID, origin: 'marketplace', isNew: false });
});

test('UC-11801: a stored install id that is not a UUID v4 is ignored', () => {
	const id = resolveInstallIdentity({ installId: 'garbage', siteAnonId: 'also-garbage' }, () => OTHER_UUID);
	assert.equal(id.installId, OTHER_UUID);
	assert.equal(id.origin, 'marketplace');
});

// --- buildActivationPayload -----------------------------------------------------

test('buildActivationPayload → the install id and only non-PII meta plus the origin', () => {
	const payload = buildActivationPayload({
		installId: VALID_UUID,
		origin: 'site',
		extVersion: '6.33.0',
		platform: 'darwin',
		vscodeVersion: '1.106.0',
	});

	assert.equal(payload.p_anon_id, VALID_UUID);
	assert.equal(payload.p_event_type, 'activation');
	assert.equal(payload.p_page, null);
	assert.equal(payload.p_ref_id, null);
	assert.equal(payload.p_lang, null);
	assert.deepEqual(payload.p_meta, {
		ext_version: '6.33.0',
		platform: 'darwin',
		vscode_version: '1.106.0',
		origin: 'site',
	});

	// AC-28 / UC-11801 AC-03 — meta carries ONLY the technical fields and the origin, no PII.
	assert.deepEqual(Object.keys(payload.p_meta).sort(), ['ext_version', 'origin', 'platform', 'vscode_version']);
	const serialized = JSON.stringify(payload);
	assert.ok(!/@/.test(serialized), 'no email-like content in payload');
	assert.ok(!/\/(Users|home)\//.test(serialized), 'no local filesystem paths in payload');
	assert.ok(!/token|secret/i.test(serialized), 'no token-like content in payload');
});

// --- isValidAnonId ------------------------------------------------------------

test('isValidAnonId accepts UUID v4, rejects garbage', () => {
	assert.equal(isValidAnonId(VALID_UUID), true);
	assert.equal(isValidAnonId(VALID_UUID.toUpperCase()), true); // case-insensitive

	// Wrong version nibble (v1), wrong variant, truncated, junk, non-strings.
	assert.equal(isValidAnonId('3f29c1a4-7b2e-1d6c-9a1f-0b8e2c4d6e8a'), false); // version 1
	assert.equal(isValidAnonId('3f29c1a4-7b2e-4d6c-1a1f-0b8e2c4d6e8a'), false); // bad variant
	assert.equal(isValidAnonId('3f29c1a4-7b2e-4d6c-9a1f'), false); // truncated
	assert.equal(isValidAnonId('hello world'), false);
	assert.equal(isValidAnonId(''), false);
	assert.equal(isValidAnonId(null), false);
	assert.equal(isValidAnonId(undefined), false);
	assert.equal(isValidAnonId(42), false);
	assert.equal(isValidAnonId({}), false);
});

// --- postActivation (injectable HTTP client) ---------------------------------

test('postActivation with mock client 2xx → ok:true', async () => {
	const payload = buildActivationPayload({
		installId: VALID_UUID, origin: 'marketplace', extVersion: '6.33.0', platform: 'darwin', vscodeVersion: '1.106.0',
	});

	let captured = null;
	const mockClient = async (url, apiKey, body) => {
		captured = { url, apiKey, body };
		return { status: 204 };
	};

	const res = await postActivation('https://x.supabase.co/rest/v1/rpc/ingest_site_event', 'anon-key', payload, mockClient);
	assert.equal(res.ok, true);
	assert.equal(res.status, 204);
	// The client received the serialized payload + key, unchanged.
	assert.equal(captured.apiKey, 'anon-key');
	assert.deepEqual(JSON.parse(captured.body), payload);
});

test('postActivation with non-2xx status → ok:false (no throw)', async () => {
	const mockClient = async () => ({ status: 500 });
	const res = await postActivation('https://x/rpc', 'k', { any: 1 }, mockClient);
	assert.equal(res.ok, false);
	assert.equal(res.status, 500);
});

test('postActivation with client that throws → ok:false, never propagates (resilience)', async () => {
	const mockClient = async () => { throw new Error('ECONNREFUSED'); };
	// Must resolve, not reject.
	const res = await postActivation('https://x/rpc', 'k', { any: 1 }, mockClient);
	assert.equal(res.ok, false);
	assert.match(res.error, /ECONNREFUSED/);
});

// --- emitActivation (UC-11801) --------------------------------------------------

test('UC-11801 AC-01: a Marketplace install stores a UUID v4 and sends one activation with origin "marketplace"', async () => {
	const state = memoryState();
	const sent = [];
	const httpClient = async (url, key, body) => { sent.push(JSON.parse(body)); return { status: 204 }; };

	assert.equal(await emitActivation(deps(state, { httpClient })), 'emitted');
	assert.equal(sent.length, 1);
	assert.equal(sent[0].p_anon_id, OTHER_UUID);
	assert.ok(isValidAnonId(sent[0].p_anon_id), 'the id is a UUID v4');
	assert.equal(sent[0].p_meta.origin, 'marketplace');
	assert.equal(state.map.get('specbox.funnel.installId'), OTHER_UUID);
	assert.equal(state.map.get('specbox.funnel.origin'), 'marketplace');
	assert.equal(getInstallId(state), OTHER_UUID);

	// Second start: nothing is sent again.
	assert.equal(await emitActivation(deps(state, { httpClient })), 'already');
	assert.equal(sent.length, 1);
});

test('UC-11801 AC-02: an install that came through the site sends the visit id with origin "site"', async () => {
	const state = memoryState({ 'specbox.funnel.anonId': VALID_UUID });
	const sent = [];
	const httpClient = async (url, key, body) => { sent.push(JSON.parse(body)); return { status: 201 }; };

	assert.equal(await emitActivation(deps(state, { httpClient })), 'emitted');
	assert.equal(sent[0].p_anon_id, VALID_UUID);
	assert.equal(sent[0].p_meta.origin, 'site');
});

test('UC-11801: the first emission waits for a deep link that arrives during the grace period', async () => {
	const state = memoryState();
	const sent = [];
	const httpClient = async (url, key, body) => { sent.push(JSON.parse(body)); return { status: 204 }; };
	// The deep link lands while the emitter waits.
	const delay = async () => { state.map.set('specbox.funnel.anonId', VALID_UUID); };

	await emitActivation(deps(state, { httpClient, delay, graceMs: 5000 }));
	assert.equal(sent[0].p_anon_id, VALID_UUID);
	assert.equal(sent[0].p_meta.origin, 'site');
});

test('UC-11801 AC-04: with VS Code telemetry off nothing is sent and the install is marked so it never retries', async () => {
	const state = memoryState();
	let calls = 0;
	const httpClient = async () => { calls += 1; return { status: 204 }; };

	assert.equal(await emitActivation(deps(state, { httpClient, telemetryEnabled: () => false })), 'opted_out');
	assert.equal(calls, 0);
	assert.equal(state.map.get('specbox.funnel.activationEmitted'), true);
	assert.equal(state.map.get('specbox.funnel.installId'), undefined, 'no id is created when telemetry is off');
	assert.equal(await emitActivation(deps(state, { httpClient })), 'already');
	assert.equal(calls, 0);
});

test('UC-11801 AC-05: a failed send stays pending and the retry reuses the same id, silently', async () => {
	const state = memoryState();
	const sent = [];
	const logs = [];
	let status = 500;
	const httpClient = async (url, key, body) => { sent.push(JSON.parse(body)); return { status }; };
	let generated = 0;
	const generateId = () => { generated += 1; return generated === 1 ? OTHER_UUID : VALID_UUID; };

	assert.equal(await emitActivation(deps(state, { httpClient, generateId, log: (m) => logs.push(m) })), 'failed');
	assert.equal(state.map.get('specbox.funnel.activationEmitted'), undefined);
	assert.equal(logs.length, 1, 'only a console log, no user-facing notice');

	// Network down: the client throws.
	const throwing = async () => { throw new Error('ENOTFOUND'); };
	assert.equal(await emitActivation(deps(state, { httpClient: throwing, generateId })), 'failed');

	status = 204;
	assert.equal(await emitActivation(deps(state, { httpClient, generateId })), 'emitted');
	assert.equal(generated, 1, 'the id was generated once');
	assert.equal(sent.length, 2);
	assert.equal(sent[0].p_anon_id, sent[1].p_anon_id, 'the retry carries the same id');
});

test('UC-11801: two emissions at the same time send a single event', async () => {
	const state = memoryState();
	let calls = 0;
	let release;
	const gate = new Promise((r) => { release = r; });
	const httpClient = async () => { calls += 1; await gate; return { status: 204 }; };

	const first = emitActivation(deps(state, { httpClient }));
	const second = await emitActivation(deps(state, { httpClient }));
	assert.equal(second, 'busy');
	release();
	assert.equal(await first, 'emitted');
	assert.equal(calls, 1);
});

// --- US-115 · UC-11509: the activation goes to SpecBox's own Supabase stack -----

test('UC-11509: the activation is sent to supabase.specbox.build with its publishable key, never to Supabase Cloud', () => {
	const { SUPABASE_URL, SUPABASE_ANON_KEY } = require(path.join(outDir, 'constants.js'));
	assert.equal(new URL(SUPABASE_URL).host, 'supabase.specbox.build');
	assert.doesNotMatch(SUPABASE_URL, /\.supabase\.co\b/);
	assert.match(SUPABASE_ANON_KEY, /^sb_publishable_/);
});
