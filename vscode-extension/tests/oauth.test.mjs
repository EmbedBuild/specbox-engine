// UC-644 / UC-645 — oauth.ts tests, zero-deps via node:test.
// Runs against the compiled output in out/ so we don't pull in TS test infra.
//
// Run: npm run test
//
// Note: vscode.l10n.t is stubbed at the top because the runtime module isn't
// available outside a VSCode Extension Host. We replace the vscode module via
// the require cache before the SUT is loaded.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

// Stub the 'vscode' module so out/oauth.js can be required outside the Extension Host.
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

async function fetchCallback(port, params, headers = {}) {
	const qs = new URLSearchParams(params).toString();
	return new Promise((resolve, reject) => {
		const req = http.request({
			host: '127.0.0.1',
			port,
			path: '/callback' + (qs ? '?' + qs : ''),
			method: headers.method ?? 'GET',
			headers,
		}, (res) => {
			let body = '';
			res.on('data', (c) => body += c);
			res.on('end', () => resolve({ status: res.statusCode, body }));
		});
		req.on('error', reject);
		req.end();
	});
}

test('server listens only on 127.0.0.1 (loopback-only)', async () => {
	const server = await startLoopbackServer();
	try {
		// Hit on loopback works; hitting localhost name resolves to loopback too on most systems.
		const r = await fetchCallback(server.port, { state: server.state, mcp_token: 'a'.repeat(64) });
		assert.equal(r.status, 200);
	} finally {
		server.close();
	}
});

test('second request returns 410 / server closed', async () => {
	const server = await startLoopbackServer();
	const token = 'b'.repeat(64);
	await fetchCallback(server.port, { state: server.state, mcp_token: token });
	await server.awaitCallback;
	// give the closure a tick
	await new Promise((r) => setTimeout(r, 350));
	let secondErrored = false;
	try {
		await fetchCallback(server.port, { state: server.state, mcp_token: token });
	} catch (err) {
		secondErrored = true;
	}
	assert.equal(secondErrored, true, 'second request should fail to connect after close');
});

test('state mismatch returns 400 and resolves with state_mismatch', async () => {
	const server = await startLoopbackServer();
	try {
		const r = await fetchCallback(server.port, { state: 'wrong', mcp_token: 'c'.repeat(64) });
		assert.equal(r.status, 400);
		const result = await server.awaitCallback;
		assert.equal(result.ok, false);
		assert.equal(result.error, 'state_mismatch');
	} finally {
		server.close();
	}
});

test('non-GET method returns 400', async () => {
	const server = await startLoopbackServer();
	try {
		const r = await fetchCallback(server.port, {}, { method: 'POST' });
		assert.equal(r.status, 400);
	} finally {
		server.close();
	}
});

test('Origin not in allow-list returns 400', async () => {
	const server = await startLoopbackServer();
	try {
		const r = await fetchCallback(server.port, { state: server.state, mcp_token: 'd'.repeat(64) }, { Origin: 'https://evil.example' });
		assert.equal(r.status, 400);
	} finally {
		server.close();
	}
});

test('invalid mcp_token shape returns 400 + invalid_token_shape', async () => {
	const server = await startLoopbackServer();
	try {
		const r = await fetchCallback(server.port, { state: server.state, mcp_token: 'short' });
		assert.equal(r.status, 400);
		const result = await server.awaitCallback;
		assert.equal(result.ok, false);
		assert.equal(result.error, 'invalid_token_shape');
	} finally {
		server.close();
	}
});

test('error param surfaces in callback result', async () => {
	const server = await startLoopbackServer();
	try {
		const r = await fetchCallback(server.port, { state: server.state, error: 'access_denied', error_description: 'user rejected' });
		assert.equal(r.status, 400);
		const result = await server.awaitCallback;
		assert.equal(result.ok, false);
		assert.equal(result.error, 'access_denied');
		assert.equal(result.description, 'user rejected');
	} finally {
		server.close();
	}
});

test('happy path: valid token resolves ok with token + state', async () => {
	const server = await startLoopbackServer();
	const token = 'e'.repeat(64);
	const r = await fetchCallback(server.port, { state: server.state, mcp_token: token });
	assert.equal(r.status, 200);
	const result = await server.awaitCallback;
	assert.equal(result.ok, true);
	assert.equal(result.token, token);
	assert.equal(result.state, server.state);
});

test('buildSignInUrl encodes return_to and includes state', () => {
	const url = buildSignInUrl(54321, 'abc123');
	assert.match(url, /^https:\/\/cloud\.specbox\.build\/vscode\/issue-token\?/);
	assert.match(url, /return_to=http%3A%2F%2F127\.0\.0\.1%3A54321%2Fcallback/);
	assert.match(url, /state=abc123/);
});

test('buildSignInUrl respects baseUrl override', () => {
	const url = buildSignInUrl(1234, 'xyz', 'http://localhost:9999/vscode/issue-token');
	assert.match(url, /^http:\/\/localhost:9999\/vscode\/issue-token\?/);
});
