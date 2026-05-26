// UC-650 — integration test for the loopback ↔ mock-cloud round trip.
//
// Simulates a real browser by following the redirect from the mock cloud to
// the loopback. Validates the full happy path, the CSRF reject path, and the
// graceful error propagation.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { startMockCloudServer } from './mock-cloud-server.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

// vscode stub (same as oauth.test.mjs)
const vscodeStub = {
	l10n: { t: (s, ...args) => args.length ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s },
	Uri: { parse: (s) => ({ toString: () => s }) },
	window: { showInformationMessage: async () => undefined },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function(req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { startLoopbackServer, buildSignInUrl } = require(path.join(outDir, 'oauth.js'));

function followGet(url) {
	return new Promise((resolve, reject) => {
		http.get(url, (res) => {
			if (res.statusCode === 302 && res.headers.location) {
				followGet(res.headers.location).then(resolve, reject);
				return;
			}
			let body = '';
			res.on('data', (c) => body += c);
			res.on('end', () => resolve({ status: res.statusCode, body }));
		}).on('error', reject);
	});
}

test('happy path: mock cloud round-trip resolves with a valid token', async () => {
	const cloud = await startMockCloudServer();
	const loopback = await startLoopbackServer();
	try {
		const url = buildSignInUrl(loopback.port, loopback.state, cloud.url);
		const browser = followGet(url);
		const result = await loopback.awaitCallback;
		await browser;
		assert.equal(result.ok, true);
		assert.match(result.token, /^spbx_[A-Za-z0-9_-]{32,128}$/);
		assert.equal(result.state, loopback.state);
	} finally {
		loopback.close();
		await cloud.close();
	}
});

test('bad_state mode: callback rejects with state_mismatch', async () => {
	const cloud = await startMockCloudServer();
	const loopback = await startLoopbackServer();
	try {
		const url = buildSignInUrl(loopback.port, loopback.state, cloud.url) + '&mode=bad_state';
		const browser = followGet(url).catch(() => null);
		const result = await loopback.awaitCallback;
		await browser;
		assert.equal(result.ok, false);
		assert.equal(result.error, 'state_mismatch');
	} finally {
		loopback.close();
		await cloud.close();
	}
});

test('error mode: callback surfaces access_denied with description', async () => {
	const cloud = await startMockCloudServer();
	const loopback = await startLoopbackServer();
	try {
		const url = buildSignInUrl(loopback.port, loopback.state, cloud.url) + '&mode=error';
		const browser = followGet(url).catch(() => null);
		const result = await loopback.awaitCallback;
		await browser;
		assert.equal(result.ok, false);
		assert.equal(result.error, 'access_denied');
		assert.equal(result.description, 'user_rejected');
	} finally {
		loopback.close();
		await cloud.close();
	}
});
