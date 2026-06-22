// US-26 (UC-2601 / UC-2602) — activation.ts pure-logic tests, zero-deps via
// node:test. activation.ts imports `vscode` (unavailable here), so we stub the
// module the same way cloud-api.test.mjs / updater-remote.test.mjs do, then
// exercise ONLY the pure, testable surface:
//   isValidAnonId, buildActivationPayload, postActivation (injectable client).
//
// NOT tested here (depend on the real `vscode` runtime, by design — see SKILL):
//   - registerActivationUriHandler (needs vscode.window.registerUriHandler + Uri)
//   - maybeEmitActivation idempotency (needs context.globalState / vscode.env)
// Those are covered by the human smoke test of the deep-link round-trip.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

// Minimal vscode stub — activation.ts only needs the symbol to resolve at import
// time; the pure functions under test don't touch vscode at all.
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

const { isValidAnonId, buildActivationPayload, postActivation } = require(path.join(outDir, 'activation.js'));

const VALID_UUID = '3f29c1a4-7b2e-4d6c-9a1f-0b8e2c4d6e8a';

// --- buildActivationPayload ---------------------------------------------------

test('buildActivationPayload with anon_id → correct p_anon_id + non-PII meta', () => {
	const payload = buildActivationPayload({
		anonId: VALID_UUID,
		extVersion: '6.11.0',
		platform: 'darwin',
		vscodeVersion: '1.86.0',
	});

	assert.equal(payload.p_anon_id, VALID_UUID);
	assert.equal(payload.p_event_type, 'activation');
	assert.equal(payload.p_page, null);
	assert.equal(payload.p_ref_id, null);
	assert.equal(payload.p_lang, null);
	assert.deepEqual(payload.p_meta, {
		ext_version: '6.11.0',
		platform: 'darwin',
		vscode_version: '1.86.0',
	});

	// AC-28 — meta must carry ONLY the 3 technical fields, no PII.
	assert.deepEqual(Object.keys(payload.p_meta).sort(), ['ext_version', 'platform', 'vscode_version']);
	const serialized = JSON.stringify(payload);
	assert.ok(!/@/.test(serialized), 'no email-like content in payload');
	assert.ok(!/\/(Users|home)\//.test(serialized), 'no local filesystem paths in payload');
});

test('buildActivationPayload without anon_id → p_anon_id null, no throw', () => {
	for (const anonId of [null, undefined, '', 'not-a-uuid', 123]) {
		const payload = buildActivationPayload({
			anonId,
			extVersion: '6.11.0',
			platform: 'linux',
			vscodeVersion: '1.90.0',
		});
		assert.equal(payload.p_anon_id, null, `anonId=${String(anonId)} → null`);
		assert.equal(payload.p_event_type, 'activation');
	}
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
		anonId: VALID_UUID, extVersion: '6.11.0', platform: 'darwin', vscodeVersion: '1.86.0',
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
	const payload = buildActivationPayload({
		anonId: null, extVersion: '6.11.0', platform: 'win32', vscodeVersion: '1.86.0',
	});
	const mockClient = async () => ({ status: 500 });
	const res = await postActivation('https://x/rpc', 'k', payload, mockClient);
	assert.equal(res.ok, false);
	assert.equal(res.status, 500);
});

test('postActivation with client that throws → ok:false, never propagates (resilience)', async () => {
	const payload = buildActivationPayload({
		anonId: VALID_UUID, extVersion: '6.11.0', platform: 'darwin', vscodeVersion: '1.86.0',
	});
	const mockClient = async () => { throw new Error('ECONNREFUSED'); };

	// Must resolve, not reject.
	const res = await postActivation('https://x/rpc', 'k', payload, mockClient);
	assert.equal(res.ok, false);
	assert.match(res.error, /ECONNREFUSED/);
});
